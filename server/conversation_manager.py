"""
Phase III - Conversation Manager
Restaurant Reservation Conversational AI

Performance-tuned for qwen:1.8b on CPU:
  - Few-shot examples injected as real message turns
  - System prompt kept short
  - Stop tokens aggressively cut off verbosity
  - Intent sticky-lock prevents cancel/modify intent being overwritten
  - Model pre-warmed on module load to eliminate cold-start
  - Persistent HTTP client to avoid TCP overhead
  - Aggressive token cap (40 tokens) for fast CPU generation
"""

import os
import re
import uuid
import json
import time
import logging
import asyncio
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
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("conversation_manager")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_URL      = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL_NAME      = "qwen:1.8b"
WINDOW_SIZE     = 4       # Keep history small for fast prompt eval
MAX_TOKENS      = 250     # Allows model to finish full sentences
TEMPERATURE     = 0.1     # Near-deterministic
REQUEST_TIMEOUT = 300     # Wait for LLM as long as it takes

_sessions: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Persistent HTTP client — avoids TCP handshake on every request
# ---------------------------------------------------------------------------
_http_client = None

async def _get_client():
    global _http_client
    if _http_client is None:
        import httpx
        _http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        logger.info("[SERVER] Created persistent httpx.AsyncClient")
    return _http_client


# ---------------------------------------------------------------------------
# Model pre-warming — fire a tiny request on first use to load into RAM
# ---------------------------------------------------------------------------
_model_warmed = False

async def _warmup_model():
    """Send a trivial request so Ollama loads the model into RAM."""
    global _model_warmed
    if _model_warmed:
        return
    _model_warmed = True
    logger.info("[SERVER] Pre-warming model (loading into RAM)...")
    try:
        import httpx
        client = await _get_client()
        warmup_payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "keep_alive": -1,
            "options": {"num_predict": 1, "num_ctx": 512},
        }
        resp = await client.post(OLLAMA_URL, json=warmup_payload)
        resp.raise_for_status()
        logger.info("[SERVER] Model pre-warm complete — loaded in RAM.")
    except Exception as e:
        logger.warning(f"[SERVER] Model pre-warm failed (will cold-start on first real request): {e}")


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
        "modify_field":       None,
        "modify_value_ready": False,
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
    r"\b(tomorrow|tonight|today|next\s+\w+|"
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
    r"(?i:my name is\s+|the name is\s+|name[:\s]+|under\s+(?:the name\s+)?)"
    r"([A-Za-z]+(?:\s+[A-Za-z]+)*)"
)
_DIET_RX = re.compile(
    r"\b(vegetarian|vegan|halal|kosher|gluten[- ]free|nut[- ]free|dairy[- ]free|pescatarian|lactose intolerant|no dairy|dairy)\b",
    re.IGNORECASE,
)
_SPECIAL_RX = re.compile(
    r"\b(birthday|anniversary|window seat|high chair|wheelchair|baby seat|quiet table|outdoor)\b",
    re.IGNORECASE,
)


def extract_signals(text: str, current_memory: dict, expected_field: str = None) -> dict:
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
    elif expected_field == "name":
        # Aggressive capture if we explicitly expect a name: e.g. "haider abbas and for diet..."
        # Just grab the first 2 or 3 words if they look like names.
        fallback_m = re.match(r"^\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)\b", text)
        if fallback_m:
            word = fallback_m.group(1).strip()
            # Try to avoid grabbing noise words 
            if word.lower() not in _NOISE_SET and word.lower() not in _BOOK_KW and word.lower() not in _CANCEL_KW:
                memory["name"] = word

    m = _DIET_RX.search(text)
    if m:
        memory["dietary_preferences"] = m.group(0)
    m = _SPECIAL_RX.search(text)
    if m:
        memory["special_requests"] = m.group(0)
    return memory


# ---------------------------------------------------------------------------
# Modify-field detection
# ---------------------------------------------------------------------------

_MODIFY_FIELD_RX = re.compile(
    r"\b(date|day|time|hour|guest|people|person|number|count)\b",
    re.IGNORECASE,
)

def detect_modify_field(text: str) -> str | None:
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
               "i want to reserve", "can i reserve", "seat for", "reservation for",
               "reservation", "reservations", "booking", "bookings"}
_CONFIRM_KW = {"yes", "confirm", "that's correct", "go ahead", "sure", "correct",
               "sounds good", "that's right", "perfect", "confirmed"}
_DENY_KW    = {"no", "wrong", "incorrect", "not right", "cancel that", "don't confirm",
               "that's wrong", "change it"}

# Greeting keywords — answer deterministically, no LLM needed
_GREETING_KW = {"hello", "hi", "hey", "good morning", "good afternoon", "good evening",
                "howdy", "greetings", "what's up", "sup"}


def detect_intent(text: str) -> str:
    lowered = text.lower().strip()
    
    def contains_kw(kw_set):
        return any(re.search(r'\b' + re.escape(kw) + r'\b', lowered) for kw in kw_set)

    if contains_kw(_CANCEL_KW):
        return "cancel_reservation"
    if contains_kw(_MODIFY_KW):
        return "modify_reservation"
    if contains_kw(_BOOK_KW):
        return "new_reservation"
    if contains_kw(_CONFIRM_KW):
        return "confirm"
    if contains_kw(_DENY_KW):
        return "deny"
    return "general_query"


def _is_greeting(text: str) -> bool:
    """Check if the message is a simple greeting."""
    lowered = text.lower().strip().rstrip("!?.,:;")
    return lowered in _GREETING_KW


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

GREETING_REPLY = (
    "Hello! Welcome to La Bella Tavola 🍝 — "
    "would you like to make a reservation, or do you have a question about the restaurant?"
)


# ===========================================================================
# Stage machine
# ===========================================================================

_STICKY_STAGES = {"modifying", "cancelling"}


def _next_stage(session: dict, intent: str) -> str:
    current = session["stage"]
    memory  = session["memory"]
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
    stage        = session["stage"]
    memory       = session["memory"]
    modify_field = session.get("modify_field")

    window = _get_window(session["history"][:-1])

    system_text = build_system_prompt(memory, window, stage=stage,
                                      modify_field=modify_field)
    messages = [{"role": "system", "content": system_text}]

    examples = get_few_shot_examples(stage, memory, modify_field=modify_field)
    messages.extend(examples)
    messages.extend(window)
    messages.append({"role": "user", "content": user_message})

    return messages


# ===========================================================================
# Deterministic reply builders
# ===========================================================================

def _build_confirming_reply(memory: dict) -> str:
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
    prev_memory = dict(session["memory"])
    
    # Determine what field we might be expecting
    expected = None
    if session["stage"] == "collecting":
        missing = [
            k for k in REQUIRED_FIELDS
            if not prev_memory.get(k) or
               (k == "time" and str(prev_memory.get(k, "")).lower() in _VAGUE_TIMES)
        ]
        if missing:
            expected = missing[0]
    elif session["stage"] in ("modifying", "cancelling") and not prev_memory.get("name"):
        expected = "name"

    session["memory"] = extract_signals(user_message, session["memory"], expected_field=expected)
    intent = detect_intent(user_message)

    if session["stage"] == "modifying" and session["modify_field"] is None:
        if session["memory"].get("name"):
            detected = detect_modify_field(user_message)
            if detected:
                session["modify_field"] = detected
                if session["memory"].get(detected) != prev_memory.get(detected):
                    session["modify_value_ready"] = True

    if session["stage"] not in _STICKY_STAGES:
        session["intent"] = intent
    elif intent in ("cancel_reservation", "modify_reservation"):
        session["intent"] = intent

    prev_stage = session["stage"]
    session["stage"] = _next_stage(session, intent)

    if prev_stage == "modifying" and session["stage"] != "modifying":
        session["modify_field"]       = None
        session["modify_value_ready"] = False


# ===========================================================================
# Main entry points
# ===========================================================================

async def chat_stream(session_id: str, user_message: str):
    """
    Process a user message and stream the assistant reply token by token.
    """
    import httpx

    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session '{session_id}' not found.")

    # ── Deterministic shortcut: simple greetings ─────────────────────────────
    if _is_greeting(user_message):
        logger.info(f"[SERVER] [{session_id}] Greeting detected — returning instant reply (no LLM)")
        session["history"].append({"role": "user",      "content": user_message})
        session["history"].append({"role": "assistant", "content": GREETING_REPLY})
        yield GREETING_REPLY
        return

    # Hard guardrail — no LLM call for off-topic messages
    if is_off_topic(user_message):
        logger.info(f"[SERVER] [{session_id}] Off-topic detected — returning canned reply")
        session["history"].append({"role": "user",      "content": user_message})
        session["history"].append({"role": "assistant", "content": OFF_TOPIC_REPLY})
        yield OFF_TOPIC_REPLY
        return

    # Update session state
    _process_turn(session, user_message)
    stage  = session["stage"]
    memory = session["memory"]
    logger.info(f"[SERVER] [{session_id}] Stage: {stage} | Intent: {session['intent']} | Memory: {memory}")

    # ══════════════════════════════════════════════════════════════════════════
    # LLM CALL — generates answers directly based on the system prompt context
    # ══════════════════════════════════════════════════════════════════════════
    messages = _build_messages(session, user_message)

    payload = {
        "model":      MODEL_NAME,
        "messages":   messages,
        "stream":     True,
        "keep_alive": -1,
        "options":    {
            "num_ctx":     1024,
            "num_predict": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "stop": [
                "\nCustomer:", "\nUser:", "\n\nCustomer:", "\n\nUser:",
                "Thank you for", "I hope this", "Best regards",
                "Note:", "\n-"
            ],
        },
    }

    full_response = ""
    start_time = time.time()
    first_token_time = None

    logger.info(f"[SERVER] [{session_id}] Calling AI model... ({len(messages)} turns)")

    try:
        client = await _get_client()
        async with client.stream("POST", OLLAMA_URL, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if "error" in data:
                    logger.error(f"[ERROR] [{session_id}] Ollama error: {data['error']}")
                    yield "Sorry, there was an engine error."
                    break

                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    if not first_token_time:
                        first_token_time = time.time()
                        ttft = first_token_time - start_time
                        logger.info(f"[SERVER] [{session_id}] First token: {ttft:.2f}s")

                    full_response += chunk
                    yield chunk
                if data.get("done"):
                    break

        total = time.time() - start_time
        logger.info(f"[SERVER] [{session_id}] AI done in {total:.2f}s")
        logger.info(f"[PERFORMANCE] [{session_id}] {total:.2f}s | ~{len(full_response.split())} words")

    except httpx.HTTPStatusError as e:
        logger.error(f"[ERROR] [{session_id}] HTTP {e.response.status_code}")
        full_response = "Sorry, I'm having trouble right now. Please try again."
        yield full_response
    except Exception as e:
        logger.error(f"[ERROR] [{session_id}] {e}")
        full_response = "Sorry, I'm having trouble right now. Please try again."
        yield full_response

    # ── Fallback if LLM returned empty ───────────────────────────────────────
    if not full_response.strip():
        logger.warning(f"[WARNING] [{session_id}] LLM returned empty response — using fallback")
        full_response = "I can help with reservations and questions about La Bella Tavola — how may I help you?"
        yield full_response

    session["history"].append({"role": "assistant", "content": full_response})


async def chat(session_id: str, user_message: str) -> str:
    tokens = []
    async for token in chat_stream(session_id, user_message):
        tokens.append(token)
    return "".join(tokens)