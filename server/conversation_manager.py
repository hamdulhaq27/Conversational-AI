"""
Phase III - Conversation Manager
Restaurant Reservation Conversational AI

Key design for qwen:1.8b:
  - Few-shot examples injected as real message turns (not text in system prompt)
  - System prompt kept short — small models lose long contexts
  - Stop tokens aggressively cut off the model's verbosity
  - Intent sticky-lock prevents cancel/modify intent being overwritten

Phase IV - Notes for API/Microservice layer
  - This module is intentionally framework-agnostic and synchronous.
  - The FastAPI service (see api.py) wraps the sync generator `chat_stream`
    inside async WebSocket and HTTP endpoints.
  - The Ollama endpoint URL is configurable via the OLLAMA_URL environment
    variable for containerised deployment (defaults to localhost).
"""

import os
import re
import uuid
import json
import time
from typing import Generator

from prompt_templates import (
    SIGNAL_KEYS,
    REQUIRED_FIELDS,
    _VAGUE_TIMES,
    build_system_prompt,
    build_modification_prompt,
    build_cancellation_prompt,
    build_confirmation_prompt,
    get_few_shot_examples,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# OLLAMA_URL can be overridden via environment variable for Docker/remote setups.
OLLAMA_URL      = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL_NAME      = "qwen:1.8b"
WINDOW_SIZE     = 6       # Keep real history short so few-shots stay in context
MAX_TOKENS      = 80      # qwen:1.8b needs a hard cap — it ignores soft instructions
TEMPERATURE     = 0.1     # Near-deterministic: copies examples more faithfully
REQUEST_TIMEOUT = 180

_sessions: dict[str, dict] = {}


# ===========================================================================
# Session lifecycle
# ===========================================================================

def create_session() -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "history":            [],
        "memory":             {k: None for k in SIGNAL_KEYS},
        "intent":             "unknown",
        "stage":              "greeting",
        "modify_field":       None,   # which field the user wants to change
        "modify_value_ready": False,  # True once field + new value both known
        "created_at":         time.time(),
    }
    return sid


def get_session(sid: str) -> dict | None:
    return _sessions.get(sid)


def reset_session(sid: str) -> None:
    if sid in _sessions:
        _sessions[sid]["history"]            = []
        _sessions[sid]["memory"]             = {k: None for k in SIGNAL_KEYS}
        _sessions[sid]["intent"]             = "unknown"
        _sessions[sid]["stage"]              = "greeting"
        _sessions[sid]["modify_field"]       = None
        _sessions[sid]["modify_value_ready"] = False


def list_sessions() -> list[str]:
    return list(_sessions.keys())


def session_debug_info(sid: str) -> dict:
    session = get_session(sid)
    if not session:
        return {}
    return {
        "session_id": sid,
        "stage":      session["stage"],
        "intent":     session["intent"],
        "memory":     dict(session["memory"]),
        "turns":      len(session["history"]),
        "window":     _get_window(session["history"]),
    }


# ===========================================================================
# Sliding-window history
# ===========================================================================

_NOISE_SET = {
    "hello", "hi", "hey", "thanks", "thank you", "sure", "okay", "ok",
    "absolutely", "great", "perfect", "got it", "noted", "yes", "no",
    "please", "alright", "yep", "nope", "yup",
}


def _is_noise(text: str) -> bool:
    return text.strip().lower() in _NOISE_SET


def _get_window(history: list[dict], size: int = WINDOW_SIZE) -> list[dict]:
    meaningful = [t for t in history if not _is_noise(t["content"])]
    return meaningful[-size:]


# ===========================================================================
# Signal extraction
# ===========================================================================

_DATE_RX = re.compile(
    r"\b(tomorrow|today|next\s+\w+|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2}|\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?)\b",
    re.IGNORECASE,
)
_TIME_RX = re.compile(
    r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}\s*o'?clock|"
    r"(?:noon|midnight|morning|afternoon|evening))\b",
    re.IGNORECASE,
)
_GUEST_RX = re.compile(
    r"table for\s+(\d+)"
    r"|it.{0,5}ll\s+be\s+(\d+)"
    r"|\b(\d+)\s*(?:people|persons?|guests?|pax)\b",
    re.IGNORECASE,
)
_NAME_RX = re.compile(
    r"(?i:my name is\s+|the name is\s+|name[:\s]+|(?:under|for)\s+(?:the name\s+)?)"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
)
_DIET_RX = re.compile(
    r"\b(vegetarian|vegan|halal|kosher|gluten[- ]free|nut[- ]free|dairy[- ]free|pescatarian)\b",
    re.IGNORECASE,
)
_SPECIAL_RX = re.compile(
    r"\b(birthday|anniversary|window seat|high chair|wheelchair|baby seat|quiet table|outdoor)\b",
    re.IGNORECASE,
)


def extract_signals(text: str, current_memory: dict) -> dict:
    memory = dict(current_memory)
    m = _DATE_RX.search(text)
    if m:
        memory["date"] = m.group(0)
    m = _TIME_RX.search(text)
    if m:
        memory["time"] = m.group(0)
    m = _GUEST_RX.search(text)
    if m:
        memory["guests"] = next(g for g in m.groups() if g is not None)
    m = _NAME_RX.search(text)
    if m:
        memory["name"] = m.group(1).strip()
    m = _DIET_RX.search(text)
    if m:
        memory["dietary_preferences"] = m.group(0)
    m = _SPECIAL_RX.search(text)
    if m:
        memory["special_requests"] = m.group(0)
    return memory


# ---------------------------------------------------------------------------
# Modify-field detection — which slot the customer wants to change
# ---------------------------------------------------------------------------

_MODIFY_FIELD_RX = re.compile(
    r"\b(date|day|time|hour|guest|people|person|number|count)\b",
    re.IGNORECASE,
)

def detect_modify_field(text: str) -> str | None:
    """
    Return 'date', 'time', or 'guests' if the user's text names a specific
    field they want to change, otherwise None.
    """
    m = _MODIFY_FIELD_RX.search(text)
    if not m:
        return None
    word = m.group(1).lower()
    if word in ("date", "day"):
        return "date"
    if word in ("time", "hour"):
        return "time"
    if word in ("guest", "people", "person", "number", "count"):
        return "guests"
    return None


# ===========================================================================
# Intent detection
# ===========================================================================

_CANCEL_KW  = {"cancel", "cancellation", "remove booking", "delete reservation", "call off"}
_MODIFY_KW  = {"change", "modify", "update", "reschedule", "move", "switch", "alter"}
_BOOK_KW    = {"book a table", "reserve a table", "reserve for", "make a reservation",
               "make a booking", "table for", "i want to book", "i'd like to book",
               "i want to reserve", "can i reserve", "seat for", "reservation for"}
_CONFIRM_KW = {"yes", "confirm", "that's correct", "go ahead", "sure", "correct",
               "sounds good", "that's right", "perfect", "confirmed"}
_DENY_KW    = {"no", "wrong", "incorrect", "not right", "cancel that", "don't confirm",
               "that's wrong", "change it"}


def detect_intent(text: str) -> str:
    lowered = text.lower()
    if any(kw in lowered for kw in _CANCEL_KW):
        return "cancel_reservation"
    if any(kw in lowered for kw in _MODIFY_KW):
        return "modify_reservation"
    if any(kw in lowered for kw in _BOOK_KW):
        return "new_reservation"
    if any(kw in lowered for kw in _CONFIRM_KW):
        return "confirm"
    if any(kw in lowered for kw in _DENY_KW):
        return "deny"
    return "general_query"


# ===========================================================================
# Policy guardrail
# ===========================================================================

_OFF_TOPIC_KW = {
    "flight", "hotel", "uber", "taxi", "weather", "news",
    "stock", "bitcoin", "code", "program", "write me", "recipe",
    "movie", "song", "joke",
}


def is_off_topic(text: str) -> bool:
    return any(kw in text.lower() for kw in _OFF_TOPIC_KW)


OFF_TOPIC_REPLY = (
    "I can only help with reservations and questions about La Bella Tavola — "
    "is there something I can help you with here?"
)


# ===========================================================================
# Stage machine
# ===========================================================================

_STICKY_STAGES = {"modifying", "cancelling"}


def _next_stage(session: dict, intent: str) -> str:
    current = session["stage"]
    memory  = session["memory"]
    # A vague period word ("evening", "morning", "afternoon") is treated as
    # unresolved — the bot still needs to ask for a specific clock time.
    missing = [
        k for k in REQUIRED_FIELDS
        if not memory.get(k) or
           (k == "time" and str(memory.get(k, "")).lower() in _VAGUE_TIMES)
    ]

    if intent == "modify_reservation":
        return "modifying"
    if intent == "cancel_reservation":
        return "cancelling"
    if intent == "new_reservation":
        return "collecting"
    if intent == "confirm" and current == "confirming":
        return "confirmed"
    if intent == "deny" and current == "confirming":
        return "collecting"
    if current in _STICKY_STAGES:
        return current
    if current == "collecting":
        return "confirming" if not missing else "collecting"
    # Stay in confirming until the customer gives an explicit confirm or deny —
    # a general question (e.g. "Can you recap?") must not exit the stage.
    if current == "confirming":
        return "confirming"
    if current == "confirmed":
        return "general"
    if intent == "general_query":
        return "general"
    return current


# ===========================================================================
# Message array construction
# ===========================================================================

def _build_messages(session: dict, user_message: str) -> list[dict]:
    """
    Build the full messages array for Ollama /api/chat.

    Structure (in order):
      1. System prompt  — short, direct, includes collected memory + task
      2. Few-shot pairs — 2-4 examples of the EXACT response style to copy
      3. Real history   — sliding window of actual conversation turns
      4. Current user message

    Putting few-shot examples BETWEEN the system prompt and real history
    is the key technique that makes qwen:1.8b follow the style correctly.
    """
    stage        = session["stage"]
    memory       = session["memory"]
    modify_field = session.get("modify_field")   # None outside modifying stage

    # Build the history window from everything EXCEPT the current user turn.
    # _process_turn appends the user message to history before this is called,
    # so history[-1] is always the current message.  If we include it here AND
    # append it again at step 4, qwen:1.8b sees it twice with no assistant
    # reply between them — which causes it to emit an empty response.
    window = _get_window(session["history"][:-1])

    # 1. System prompt
    system_text = build_system_prompt(memory, window, stage=stage,
                                      modify_field=modify_field)
    messages = [{"role": "system", "content": system_text}]

    # 2. Few-shot examples injected as real message turns
    examples = get_few_shot_examples(stage, memory, modify_field=modify_field)
    messages.extend(examples)

    # 3. Real conversation history
    messages.extend(window)

    # 4. Current user message
    messages.append({"role": "user", "content": user_message})

    return messages


# ===========================================================================
# Deterministic reply builders — bypass LLM for stages where the answer
# is a pure function of session memory (no creativity needed)
# ===========================================================================

def _build_confirming_reply(memory: dict) -> str:
    """
    Deterministic confirmation-request sentence built from real memory values.
    Prevents qwen:1.8b from echoing example names/numbers from FEW_SHOT_CONFIRMING.
    """
    date    = memory.get("date")    or "?"
    time_   = memory.get("time")    or "?"
    guests  = memory.get("guests")  or "?"
    name    = memory.get("name")    or "?"

    extras = []
    if memory.get("dietary_preferences"):
        extras.append(memory["dietary_preferences"])
    if memory.get("special_requests"):
        extras.append(memory["special_requests"])
    extra_str = f", {', '.join(extras)}" if extras else ""

    return (
        f"So that's a table for {guests} on {date} at {time_} "
        f"under {name}{extra_str} — shall I confirm that?"
    )


def _build_confirmed_reply(memory: dict) -> str:
    """
    Build the confirmation sentence entirely from memory — no LLM needed.
    This eliminates the pattern-copying hallucination where qwen:1.8b echoes
    the example names/dates from FEW_SHOT_CONFIRMED instead of the real values.
    """
    date    = memory.get("date")    or "the requested date"
    time_   = memory.get("time")    or "the requested time"
    guests  = memory.get("guests")  or "your group"
    name    = memory.get("name")    or "you"

    extras = []
    if memory.get("dietary_preferences"):
        extras.append(memory["dietary_preferences"])
    if memory.get("special_requests"):
        extras.append(memory["special_requests"])
    extra_str = f", {', '.join(extras)}" if extras else ""

    return (
        f"Your table for {guests} on {date} at {time_} "
        f"under {name} is confirmed{extra_str} — we look forward to seeing you!"
    )


def _build_modify_done_reply(memory: dict, modify_field: str) -> str:
    """
    Deterministic "change applied" reply — bypasses LLM to prevent qwen:1.8b
    from echoing example values (e.g. '8 PM') before the user even stated them.
    """
    name  = memory.get("name") or "Your"
    field_labels = {"date": "date", "time": "time", "guests": "number of guests"}
    label = field_labels.get(modify_field, modify_field)
    value = memory.get(modify_field) or "the new value"
    possessive = f"{name}'s" if name != "Your" else "Your"
    return f"Done — {possessive} reservation has been updated: {label} changed to {value}."


# ===========================================================================
# Session state update
# ===========================================================================

def _process_turn(session: dict, user_message: str) -> None:
    session["history"].append({"role": "user", "content": user_message})
    prev_memory = dict(session["memory"])                        # snapshot before extraction
    session["memory"] = extract_signals(user_message, session["memory"])
    intent = detect_intent(user_message)

    # While modifying and we have the name but not yet the target field:
    # detect which field the customer wants to change.
    # Only do this AFTER name is known — prevents "change the time" on turn 1
    # from setting modify_field before we even know the booking name.
    if session["stage"] == "modifying" and session["modify_field"] is None:
        if session["memory"].get("name"):                        # name must be known first
            detected = detect_modify_field(user_message)
            if detected:
                session["modify_field"] = detected
                # If the new value for that field also arrived in this same message,
                # we have everything needed — flag for deterministic completion.
                if session["memory"].get(detected) != prev_memory.get(detected):
                    session["modify_value_ready"] = True

    # Preserve intent in sticky stages
    if session["stage"] not in _STICKY_STAGES:
        session["intent"] = intent
    elif intent in ("cancel_reservation", "modify_reservation"):
        session["intent"] = intent

    prev_stage = session["stage"]
    session["stage"] = _next_stage(session, intent)

    # Clear modify tracking when leaving the modifying stage
    if prev_stage == "modifying" and session["stage"] != "modifying":
        session["modify_field"]       = None
        session["modify_value_ready"] = False


# ===========================================================================
# Main entry points
# ===========================================================================

import logging
logger = logging.getLogger("conversation_manager")
logger.setLevel(logging.INFO)

async def chat_stream(session_id: str, user_message: str):
    """
    Process a user message and stream the assistant reply token by token.
    """
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx is required. Install with: pip install httpx")

    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session '{session_id}' not found.")

    # Hard guardrail — no LLM call for off-topic messages
    if is_off_topic(user_message):
        session["history"].append({"role": "user",      "content": user_message})
        session["history"].append({"role": "assistant", "content": OFF_TOPIC_REPLY})
        yield OFF_TOPIC_REPLY
        return

    # Update session state
    _process_turn(session, user_message)

    # ── Deterministic shortcut: confirming stage ─────────────────────────────
    # qwen:1.8b copies guest counts / names from FEW_SHOT_CONFIRMING examples.
    # Build the "shall I confirm?" sentence directly from session memory.
    if session["stage"] == "confirming":
        reply = _build_confirming_reply(session["memory"])
        session["history"].append({"role": "assistant", "content": reply})
        yield reply
        return

    # ── Deterministic shortcut: confirmed stage ──────────────────────────────
    # qwen:1.8b pattern-copies example names/dates from few-shots instead of
    # using the real memory values, so we bypass the LLM entirely here.
    if session["stage"] == "confirmed":
        reply = _build_confirmed_reply(session["memory"])
        session["history"].append({"role": "assistant", "content": reply})
        yield reply
        return

    # ── Deterministic shortcut: modify completed ─────────────────────────────
    # When the user gives both the target field and its new value in one turn
    # (e.g. "Change the time to 8 PM"), skip the LLM and reply directly from
    # memory — prevents the model from echoing example values.
    if (session["stage"] == "modifying"
            and session.get("modify_value_ready")
            and session.get("modify_field")):
        reply = _build_modify_done_reply(session["memory"], session["modify_field"])
        session["history"].append({"role": "assistant", "content": reply})
        session["modify_value_ready"] = False   # reset for potential next change
        yield reply
        return

    # Build full message array with few-shots injected
    messages = _build_messages(session, user_message)

    payload = {
        "model":      MODEL_NAME,
        "messages":   messages,
        "stream":     True,
        "keep_alive": -1,  # Keep the model loaded in RAM permanently
        "options":    {
            "num_ctx": 1024, # Force a smaller context window to drastically speed up CPU prompt-eval
            "num_predict": MAX_TOKENS,
            "temperature": TEMPERATURE,
            # Stop tokens: cut off the moment the model tries to continue the
            # fake dialogue, write a sign-off, or start a list
            "stop": [
                "\nCustomer:", "\nUser:", "\n\nCustomer:", "\n\nUser:",
                "Thank you for", "I hope this", "Best regards",
                "Note:", "\n-", "\n1.", "\n2.",
            ],
        },
    }

    full_response = ""
    start_time = time.time()
    first_token_time = None
    
    logger.info(f"[{session_id}] Sending payload to LLM ({len(messages)} turns context)...")
    logger.info(f"[{session_id}] Payload: {json.dumps(payload)}")
    
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            async with client.stream("POST", OLLAMA_URL, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(f"[{session_id}] Failed to parse JSON line: {line}")
                        continue
                    
                    # Debug log the exact raw chunk from Ollama
                    logger.info(f"[{session_id}] RAW CHUNK: {data}")
                    
                    if "error" in data:
                        logger.error(f"[{session_id}] Ollama Internal Error: {data['error']}")
                        yield f"\n**Ollama engine error:** {data['error']}"
                        break
                    
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        if not first_token_time:
                            first_token_time = time.time()
                            logger.info(f"[{session_id}] First token latency: {first_token_time - start_time:.2f}s")
                            
                        full_response += chunk
                        yield chunk
                    if data.get("done"):
                        logger.info(f"[{session_id}] Ollama signaled done.")
                        break
        logger.info(f"[{session_id}] Generation complete in {time.time() - start_time:.2f}s")
    except httpx.HTTPStatusError as e:
        logger.error(f"[{session_id}] HTTP error from Ollama: {e.response.status_code} - {e.response.text}")
        error_msg = f"Sorry, I am having trouble connecting to my backend engine (HTTP {e.response.status_code})."
        yield error_msg
        full_response = error_msg
    except Exception as e:
        logger.error(f"[{session_id}] Error connecting to Ollama: {e}")
        error_msg = f"Sorry, I am having trouble connecting to my backend engine. Detailed error: {e}"
        yield error_msg
        full_response = error_msg

    session["history"].append({"role": "assistant", "content": full_response})

async def chat(session_id: str, user_message: str) -> str:
    tokens = []
    async for token in chat_stream(session_id, user_message):
        tokens.append(token)
    return "".join(tokens)