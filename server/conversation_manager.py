"""
Phase III - Conversation Manager
Restaurant Reservation Conversational AI

Performance-tuned for qwen:1.8b on CPU:
  - PURE REGEX tool detection — no second LLM call for tools (eliminates ~3s latency)
  - Tool result + RAG run in PARALLEL via asyncio.gather before LLM call
  - LRU cache for tool results (weather 5 min, menu permanent, lookup 30 s)
  - Stage-specific system prompts (no contradictory "retrieval-only" framing)
  - Few-shot examples injected as real message turns
  - Model pre-warmed on module load
  - Persistent HTTP client, sliding window history
  - Streaming preserved (word-by-word)
"""

import os
import re
import uuid
import json
import time
import logging
import asyncio
import hashlib
from datetime import datetime
from typing import Generator
from functools import lru_cache

from prompt_templates import (
    SIGNAL_KEYS,
    REQUIRED_FIELDS,
    _VAGUE_TIMES,
    build_system_prompt,
    get_few_shot_examples,
)
from tools.crm import get_user, update_user
from tools.weather import get_weather, RESTAURANT_CITY
from tools.menu import search_menu
from tools.reservation_lookup import lookup_reservation, save_reservation

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("conversation_manager")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_URL      = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL_NAME      = "qwen2.5:3b-instruct"
WINDOW_SIZE     = 5       # Keep history small for fast prompt eval
MAX_TOKENS      = 180     # Enough for a complete sentence, not an essay
TEMPERATURE     = 0.2     # Near-deterministic
REQUEST_TIMEOUT = 300

def get_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_network(msg: str):
    print(f"\n[{get_now()}] [NETWORK] User Message: \"{msg}\"", flush=True)

def log_crm(action: str, details: str):
    print(f"[{get_now()}] [CRM] {action}: {details}", flush=True)

def log_rag(query: str, doc_count: int):
    print(f"[{get_now()}] [RAG] Query: \"{query}\" -> Retrieved {doc_count} chunks", flush=True)

def log_llm_start(session_id: str):
    print(f"[{get_now()}] [LLM] Generating response for {session_id[:8]}...", flush=True)

def log_llm_end(response: str):
    print(f"[{get_now()}] [LLM] Response: \"{response}\"\n", flush=True)

_sessions: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Simple TTL cache for tool results (avoids repeated API / DB hits)
# ---------------------------------------------------------------------------
_tool_cache: dict[str, tuple[float, dict]] = {}

def _cache_get(key: str, ttl: float) -> dict | None:
    entry = _tool_cache.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None

def _cache_set(key: str, value: dict) -> None:
    _tool_cache[key] = (time.time(), value)


# ---------------------------------------------------------------------------
# RAG — lazy singleton
# ---------------------------------------------------------------------------
_rag_system = None
_rag_initialized = False

def _get_rag():
    global _rag_system, _rag_initialized
    if _rag_initialized:
        return _rag_system
    _rag_initialized = True
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from rag.retriever import RestaurantRAG
        _rag_system = RestaurantRAG()
        logger.info("[RAG] RestaurantRAG singleton initialized.")
    except Exception as e:
        logger.warning(f"[RAG] Could not initialize — RAG disabled: {e}")
        _rag_system = None
    return _rag_system


def _fetch_rag_context(query: str) -> str:
    """Retrieve top-k chunks. Cached by query hash for 5 minutes."""
    cache_key = f"rag:{hashlib.md5(query.encode()).hexdigest()}"
    cached = _cache_get(cache_key, ttl=300)
    if cached is not None:
        logger.info(f"[RAG] Cache hit for query: '{query[:40]}'")
        return cached.get("context", "")

    rag = _get_rag()
    if rag is None:
        return ""
    try:
        t0 = time.time()
        docs = rag.retrieve_documents(query)
        elapsed = time.time() - t0
        log_rag(query, len(docs))
        logger.info(f"[RAG] Retrieved {len(docs)} docs in {elapsed:.2f}s")
        if not docs:
            _cache_set(cache_key, {"context": ""})
            return ""
        parts = [f"[DOC {i}]\n{doc.page_content}" for i, doc in enumerate(docs, 1)]
        context = "\n\n".join(parts)
        _cache_set(cache_key, {"context": context})
        return context
    except Exception as e:
        logger.warning(f"[RAG] Retrieval failed for '{query}': {e}")
        return ""


# ---------------------------------------------------------------------------
# Persistent HTTP client
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
# Model pre-warming
# ---------------------------------------------------------------------------
_model_warmed = False

async def _warmup_model():
    global _model_warmed
    if _model_warmed:
        return
    _model_warmed = True
    logger.info("[SERVER] Pre-warming model...")
    try:
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
        logger.info("[SERVER] Model pre-warm complete.")
    except Exception as e:
        logger.warning(f"[SERVER] Model pre-warm failed: {e}")


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
        fallback_m = re.match(r"^\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)\b", text)
        if fallback_m:
            word = fallback_m.group(1).strip()
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
    lowered = text.lower().strip().rstrip("!?.,:;")
    return lowered in _GREETING_KW


# ===========================================================================
# Policy guardrail
# ===========================================================================

_OFF_TOPIC_KW = {
    "flight", "hotel", "uber", "taxi", "news",
    "stock", "bitcoin", "code", "program", "write me", "recipe",
    "movie", "song", "joke",
}

# Tool trigger regexes
_WEATHER_TRIGGER_RX = re.compile(
    r"\b(weather|rain|raining|sunny|sunshine|outdoor|outside|cold|hot|windy|temperature|forecast|umbrella)\b",
    re.IGNORECASE,
)
_MENU_TRIGGER_RX = re.compile(
    r"\b(menu|food|dish|dishes|pasta|pizza|eat|cuisine|special|specials|dessert|starter|appetizer|drink|drinks|price|cost|how much|what do you serve|what.*eat|vegetarian|vegan|gluten|wine|cocktail|steak|seafood|risotto)\b",
    re.IGNORECASE,
)
_LOOKUP_TRIGGER_RX = re.compile(
    r"\b(check|find|lookup|look\s*up|existing|do i have|have a reservation|have a booking|my reservation|my booking)\b",
    re.IGNORECASE,
)
_MENU_CATEGORY_RX = {
    "starters":     re.compile(r"\b(starter|starters|appetizer|antipasto|bruschetta|burrata|calamari)\b", re.IGNORECASE),
    "pasta":        re.compile(r"\b(pasta|risotto|spaghetti|penne|tagliatelle|linguine|gnocchi)\b",       re.IGNORECASE),
    "mains":        re.compile(r"\b(main|mains|entree|second|secondi|steak|chicken|fish|salmon|sea\s*bass)\b", re.IGNORECASE),
    "seafood":      re.compile(r"\b(seafood|fish|prawn|shrimp|lobster|clam|mussel)\b",                   re.IGNORECASE),
    "desserts":     re.compile(r"\b(dessert|sweet|tiramisu|cannoli|panna\s*cotta|gelato)\b",              re.IGNORECASE),
    "drinks":       re.compile(r"\b(drink|drinks|wine|cocktail|water|coffee|espresso|prosecco)\b",        re.IGNORECASE),
    "lunch_specials": re.compile(r"\b(lunch|lunch special)\b",                                           re.IGNORECASE),
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
    if intent == "new_reservation":
        # If all fields are already in hand, jump straight to confirming
        return "confirming" if not missing else "collecting"
    if current in _STICKY_STAGES:
        return current
    if current == "collecting":
        return "confirming" if not missing else "collecting"
    if current == "confirming":
        if intent == "confirm": return "confirmed"
        if intent == "deny":    return "collecting"
        return "confirming"
    if current == "confirmed":
        return "general"
    if intent == "general_query":
        return "general"
    return current


# ===========================================================================
# Message array construction
# ===========================================================================

def _build_messages(session: dict, user_message: str, user_data: dict,
                    retrieved_context: str = "",
                    tool_used: str | None = None) -> list[dict]:
    stage        = session["stage"]
    memory       = session["memory"]
    modify_field = session.get("modify_field")

    window = _get_window(session["history"][:-1])

    system_text = build_system_prompt(memory, window, stage=stage,
                                      retrieved_context=retrieved_context,
                                      modify_field=modify_field)

    # Append CRM user info (kept brief to avoid bloating prompt)
    if user_data and user_data.get("name"):
        system_text += f"\n\nReturning customer: {user_data.get('name')}."
        if user_data.get("dietary_preferences"):
            system_text += f" Dietary: {user_data['dietary_preferences']}."

    messages = [{"role": "system", "content": system_text}]

    examples = get_few_shot_examples(stage, memory, modify_field=modify_field, tool_used=tool_used)
    messages.extend(examples)
    messages.extend(window)
    messages.append({"role": "user", "content": user_message})

    return messages


# ===========================================================================
# Deterministic reply builders (no LLM needed for these)
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
# Tool execution helper
# ===========================================================================

async def _run_tool_async(tool_fn, *args, timeout: float = 5.0):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(tool_fn, *args),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error("[TOOL ERROR] Timed out.")
        return {"status": "error", "message": "Tool timed out."}
    except Exception as e:
        logger.error(f"[TOOL ERROR] {e}")
        return {"status": "error", "message": "Tool failed."}


# ===========================================================================
# Tool Orchestrator — PURE REGEX (no second LLM call)
# Results are formatted into a concise context string for the main LLM call
# ===========================================================================

async def tool_orchestrator(session_id: str, user_message: str,
                            extracted_memory: dict) -> tuple[str, str | None]:
    """
    Detect and execute the appropriate tool using regex only.
    Returns (context_string, tool_name) where context_string is injected into
    the system prompt and tool_name is used to select the right few-shot examples.

    No second LLM call → eliminates ~2-4s latency on CPU.
    Results are cached to keep repeated queries fast.
    """
    msg            = user_message
    _default_city  = RESTAURANT_CITY or "London"
    t0             = time.time()

    # ── CRM: name / dietary / special ───────────────────────────────────────
    name = extracted_memory.get("name")
    if name:
        log_crm("update_user", f"Updating record for '{name}'")
        res = await _run_tool_async(update_user, name, {"name": name}, session_id, timeout=1.5)
        logger.info(f"[TOOL] update_user(name) → {res}")

    diet = extracted_memory.get("dietary_preferences")
    if diet and name:
        log_crm("update_user", f"Saving dietary: {diet} for '{name}'")
        res = await _run_tool_async(update_user, name, {"dietary_preferences": diet}, session_id, timeout=1.5)
        logger.info(f"[TOOL] update_user(dietary) → {res}")

    special = extracted_memory.get("special_requests")
    if special and name:
        log_crm("update_user", f"Saving special request: {special} for '{name}'")
        res = await _run_tool_async(update_user, name, {"special_requests": special}, session_id, timeout=1.5)
        logger.info(f"[TOOL] update_user(special) → {res}")

    if any([name, diet, special]) and not name:
        logger.warning("[CRM] Info detected but no name available to key the record.")

    # ── Weather ──────────────────────────────────────────────────────────────
    if _WEATHER_TRIGGER_RX.search(msg):
        cache_key = f"weather:{_default_city}"
        cached = _cache_get(cache_key, ttl=300)  # 5-min cache
        if cached:
            logger.info("[TOOL] get_weather — cache hit")
            res = cached
        else:
            res = await _run_tool_async(get_weather, _default_city, timeout=6.0)
            if res.get("status") == "ok":
                _cache_set(cache_key, res)
            logger.info(f"[TOOL] get_weather({_default_city}) in {time.time()-t0:.2f}s")

        if res.get("status") == "ok":
            context = (
                f"Current weather in {res['city']}: {res['temperature_c']}°C, "
                f"{res['description']}, feels like {res['feels_like_c']}°C, "
                f"humidity {res['humidity_pct']}%. "
                f"{res['outdoor_note']}"
            )
        else:
            context = res.get("message", "Weather data unavailable.")
        return context, "get_weather"

    # ── Menu search ──────────────────────────────────────────────────────────
    if _MENU_TRIGGER_RX.search(msg):
        cat  = next((k for k, rx in _MENU_CATEGORY_RX.items() if rx.search(msg)), "")
        diet_match = re.search(r"\b(vegetarian|vegan|gluten[- ]free)\b", msg, re.IGNORECASE)
        diet = diet_match.group(0).lower().replace("-", "_") if diet_match else ""

        cache_key = f"menu:{cat}:{diet}"
        cached = _cache_get(cache_key, ttl=3600)  # 1-hour cache (menu rarely changes)
        if cached:
            logger.info("[TOOL] search_menu — cache hit")
            res = cached
        else:
            res = await _run_tool_async(search_menu, cat, diet, timeout=2.0)
            if res.get("status") == "ok":
                _cache_set(cache_key, res)
            logger.info(f"[TOOL] search_menu({cat},{diet}) in {time.time()-t0:.2f}s")

        if res.get("status") == "ok":
            context = _format_menu_context(res.get("results", {}), cat, diet)
        else:
            context = "Menu information is temporarily unavailable. Please ask your server."
        return context, "search_menu"

    # ── Reservation lookup ───────────────────────────────────────────────────
    if _LOOKUP_TRIGGER_RX.search(msg):
        name_m = _NAME_RX.search(msg)
        name   = name_m.group(1).strip() if name_m else extracted_memory.get("name", "")
        if not name:
            return "", None

        cache_key = f"lookup:{name.lower()}"
        cached = _cache_get(cache_key, ttl=30)  # 30s cache
        if cached:
            logger.info("[TOOL] lookup_reservation — cache hit")
            res = cached
        else:
            res = await _run_tool_async(lookup_reservation, name, timeout=2.0)
            if res.get("status") == "ok":
                _cache_set(cache_key, res)
            logger.info(f"[TOOL] lookup_reservation({name}) in {time.time()-t0:.2f}s")

        if res.get("status") == "ok" and res.get("found"):
            r = res["reservations"][0]
            context = (
                f"Reservation found: {r['name']}, {r['date']}, {r['time']}, "
                f"{r['guests']} guests. Status: {r['status']}."
            )
        elif res.get("status") == "ok":
            context = f"No active reservation found under '{name}'."
        else:
            context = res.get("message", "Could not check reservations.")
        return context, "lookup_reservation"

    return "", None


def _format_menu_context(results: dict, category: str, dietary: str) -> str:
    """Convert menu search results into a compact string for the LLM context."""
    if not results:
        return "No items found matching your request."

    lines = []
    item_count = 0
    MAX_ITEMS = 6  # Cap to avoid bloating the prompt for Qwen 1.8B

    for cat, items in results.items():
        for item in items:
            if item_count >= MAX_ITEMS:
                break
            name  = item.get("name", "")
            price = item.get("price")
            desc  = item.get("description", "")[:60]  # truncate long descriptions
            allergens = item.get("allergens", "")

            line = f"• {name}"
            if price:
                line += f" (${price:.0f})"
            if desc:
                line += f" — {desc}"
            if allergens and allergens.lower() not in ("none", ""):
                line += f" [contains {allergens}]"
            lines.append(line)
            item_count += 1

        if item_count >= MAX_ITEMS:
            remaining = sum(len(v) for v in results.values()) - item_count
            if remaining > 0:
                lines.append(f"...and {remaining} more items available.")
            break

    section = category if category else "menu"
    diet_str = f" ({dietary})" if dietary else ""
    header = f"La Bella Tavola {section}{diet_str}:\n"
    return header + "\n".join(lines)


# ===========================================================================
# Main entry points
# ===========================================================================

async def chat_stream(session_id: str, user_message: str):
    """
    Process a user message and stream the assistant reply token by token.
    Tools and RAG run in parallel BEFORE the LLM call to minimise latency.
    """
    import httpx

    log_network(user_message)
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session '{session_id}' not found.")

    # ── CRM Lookup: Load profile if we have a name ───────────────────────────
    name = session["memory"].get("name")
    user_data = {}
    if name:
        user_data = get_user(name)
        if user_data:
            log_crm("get_user", f"Loaded data for '{name}': {user_data}")
            # Seed memory from CRM if not already done
            if not session.get("seeded_from_crm"):
                for k in ("dietary_preferences", "special_requests"):
                    if not session["memory"].get(k) and user_data.get(k):
                        session["memory"][k] = user_data[k]
                session["seeded_from_crm"] = True

    # ── Deterministic shortcut: simple greetings ─────────────────────────────
    if _is_greeting(user_message):
        if user_data and user_data.get("name"):
            greeting = f"Welcome back, {user_data['name']}! Would you like to make a reservation or do you have a question?"
        else:
            greeting = GREETING_REPLY
        session["history"].append({"role": "user",      "content": user_message})
        session["history"].append({"role": "assistant", "content": greeting})
        yield greeting
        return

    # ── Off-topic guardrail ───────────────────────────────────────────────────
    if is_off_topic(user_message):
        session["history"].append({"role": "user",      "content": user_message})
        session["history"].append({"role": "assistant", "content": OFF_TOPIC_REPLY})
        yield OFF_TOPIC_REPLY
        return

    # ── Update session state ──────────────────────────────────────────────────
    _process_turn(session, user_message)
    stage  = session["stage"]
    memory = session["memory"]
    logger.info(f"[{get_now()}] [STAGE] {stage} | intent={session['intent']}")

    # ── Tool + RAG in parallel ────────────────────────────────────────────────
    pre_start = time.time()

    tool_task = tool_orchestrator(session_id, user_message, session["memory"])

    rag_stages = ("general", "answering")
    if stage in rag_stages:
        rag_task = asyncio.to_thread(_fetch_rag_context, user_message)
    else:
        rag_task = asyncio.coroutine(lambda: "")()

    # Run both concurrently
    (tool_context, tool_used), retrieved_context = await asyncio.gather(
        tool_task, rag_task
    )

    pre_elapsed = time.time() - pre_start
    logger.info(f"[PRE-GEN] tool={tool_used} rag={'yes' if retrieved_context else 'no'} in {pre_elapsed:.2f}s")

    # Merge: tool context takes priority over RAG for general queries
    final_context = tool_context or retrieved_context

    # Merge current turn updates with loaded profile
    user_profile = {**user_data, **(tool_context if isinstance(tool_context, dict) else {})}
    for k, v in memory.items():
        if v: user_profile[k] = v

    # ── Build LLM messages ────────────────────────────────────────────────────
    messages = _build_messages(session, user_message, user_profile,
                               retrieved_context=final_context,
                               tool_used=tool_used)

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
                "Note:", "\n-", "Human:", "Assistant:"
            ],
        },
    }

    full_response = ""
    start_time    = time.time()
    first_token   = None

    logger.info(f"[LLM] [{session_id}] Calling model ({len(messages)} msgs)...")
    log_llm_start(session_id)

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
                    logger.error(f"[LLM ERROR] {data['error']}")
                    yield "Sorry, there was an engine error."
                    break

                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    if not first_token:
                        first_token = time.time()
                        logger.info(f"[LLM] TTFT: {first_token - start_time:.2f}s")
                    full_response += chunk
                    yield chunk

                if data.get("done"):
                    break

        total = time.time() - start_time
        logger.info(f"[LLM] Done in {total:.2f}s | ~{len(full_response.split())} words")

    except httpx.HTTPStatusError as e:
        logger.error(f"[ERROR] HTTP {e.response.status_code}")
        full_response = "Sorry, I'm having trouble right now. Please try again."
        yield full_response
    except Exception as e:
        logger.error(f"[ERROR] {e}")
        full_response = "Sorry, I'm having trouble right now. Please try again."
        yield full_response

    log_llm_end(full_response)

    # ── Persistence for Confirmed bookings ────────────────────────────────────
    if stage == "confirmed" and not session.get("reservation_saved"):
        _name = memory.get("name", "")
        _date = memory.get("date", "")
        _time = memory.get("time", "")
        if _name and _date and _time:
            res_data = {
                "date":    _date,
                "time":    _time,
                "guests":  memory.get("guests", "2"),
                "dietary": memory.get("dietary_preferences", ""),
                "special": memory.get("special_requests", ""),
            }
            log_crm("add_reservation", f"Auto-saving booking for '{_name}'")
            add_reservation(_name, res_data, session_id)
            session["reservation_saved"] = True

    # ── Fallback ──────────────────────────────────────────────────────────────
    if not full_response.strip():
        full_response = "I can help with reservations and questions about La Bella Tavola — how may I assist you?"
        yield full_response

    session["history"].append({"role": "assistant", "content": full_response})


async def chat(session_id: str, user_message: str) -> str:
    tokens = []
    async for token in chat_stream(session_id, user_message):
        tokens.append(token)
    return "".join(tokens)