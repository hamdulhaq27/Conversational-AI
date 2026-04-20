"""
Phase III - Prompt Templates
Restaurant Reservation Conversational AI

Strategy for qwen:1.8b:
  - System prompt is stage-specific and SHORT (model gets confused by long prompts)
  - NO "retrieval-only" framing on reservation stages — that causes hallucination
  - RAG context only injected on general/answering stages, not during booking flow
  - Few-shot examples injected as real message turns (NOT in system prompt text)
  - Each stage has a clear, single task sentence
"""

RESTAURANT_INFO = {
    "name":               "La Bella Tavola",
    "cuisine":            "Italian-Mediterranean",
    "hours":              "12 PM to 11 PM daily",
    "location":           "123 Main Street, Downtown",
    "phone":              "+1-800-555-1234",
    "max_table_capacity": "up to 8 guests",
    "lunch_reservation":  "walk-ins welcome, reservations recommended on weekends",
    "dinner_reservation": "reservations strongly recommended, especially Fri-Sun",
    "parking":            "street parking available, valet on weekends",
    "dress_code":         "smart casual",
}

SIGNAL_KEYS     = ["date", "time", "guests", "name", "dietary_preferences", "special_requests"]
REQUIRED_FIELDS = ["date", "time", "guests", "name"]

# Vague time words that need a specific-time follow-up
_VAGUE_TIMES = {"evening", "morning", "afternoon"}

CRM_PROMPT = ""  # Kept for import compatibility — CRM is handled by tool orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _missing_fields(memory: dict) -> list[str]:
    missing = []
    for k in REQUIRED_FIELDS:
        v = memory.get(k)
        if not v:
            missing.append(k)
        elif k == "time" and str(v).lower() in _VAGUE_TIMES:
            missing.append(k)
    return missing

def _next_field(memory: dict) -> str:
    m = _missing_fields(memory)
    return m[0] if m else ""

def _collected_summary(memory: dict) -> str:
    _DISPLAY_KEYS = REQUIRED_FIELDS + ["dietary_preferences", "special_requests"]
    parts = []
    for k in _DISPLAY_KEYS:
        v = memory.get(k)
        if not v:
            continue
        if k == "time" and str(v).lower() in _VAGUE_TIMES:
            continue
        parts.append(f"{k}: {v}")
    return ", ".join(parts) if parts else "nothing yet"

def _missing_summary(memory: dict) -> str:
    missing = _missing_fields(memory)
    return ", ".join(missing) if missing else "none"

def _history_block(recent_turns: list[dict]) -> str:
    if not recent_turns:
        return "(no prior turns)"
    lines = []
    for t in recent_turns:
        label = "Customer" if t["role"] == "user" else "Assistant"
        lines.append(f'{label}: {t["content"]}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompt — stage-specific, SHORT, no contradictory framing
# ---------------------------------------------------------------------------

def build_system_prompt_text(memory: dict, recent_turns: list[dict],
                             stage: str, retrieved_context: str = "",
                             modify_field: str | None = None) -> str:

    next_f    = _next_field(memory)
    collected = _collected_summary(memory)

    # ── RESERVATION STAGES — no RAG framing, pure conversational ────────────
    if stage == "greeting":
        return (
            "You are a friendly host at La Bella Tavola Italian restaurant. "
            "Greet the customer warmly in one sentence and ask how you can help."
        )

    elif stage == "collecting":
        field_prompts = {
            "date":   "You are taking a reservation at La Bella Tavola. Ask only: what date?",
            "time":   "You are taking a reservation at La Bella Tavola. Ask only: what time? (needs a specific time like 7 PM, not just 'evening')",
            "guests": "You are taking a reservation at La Bella Tavola. Ask only: how many guests?",
            "name":   "You are taking a reservation at La Bella Tavola. Ask for the name and any dietary preferences or special requests.",
        }
        return field_prompts.get(next_f, "You are taking a reservation. Ask for the next missing detail.")

    elif stage == "confirming":
        return (
            f"You are confirming a reservation at La Bella Tavola. "
            f"Repeat these details and ask if correct: {collected}. "
            "One sentence only."
        )

    elif stage == "confirmed":
        _date   = memory.get("date")   or "the date"
        _time   = memory.get("time")   or "the time"
        _guests = memory.get("guests") or "your group"
        _name   = memory.get("name")   or "you"
        extras  = []
        if memory.get("dietary_preferences"):
            extras.append(memory["dietary_preferences"])
        if memory.get("special_requests"):
            extras.append(memory["special_requests"])
        extra_str = f", {', '.join(extras)}" if extras else ""
        return (
            f"Confirm the reservation in ONE short sentence: "
            f"table for {_guests} on {_date} at {_time} under {_name}{extra_str}. "
            "End warmly. No extra questions."
        )

    elif stage == "modifying":
        if not memory.get("name"):
            return (
                "A customer wants to modify their reservation at La Bella Tavola. "
                "Ask only: what name is the reservation under?"
            )
        else:
            if modify_field and memory.get(modify_field):
                field_label = {"date": "date", "time": "time", "guests": "number of guests"}.get(
                    modify_field, modify_field
                )
                return (
                    f"Confirm the reservation change for {memory.get('name')}: "
                    f"{field_label} updated to {memory.get(modify_field)}. One sentence."
                )
            return (
                f"You have the reservation for {memory.get('name')}. "
                "Ask only: what would you like to change — the date, the time, or the number of guests?"
            )

    elif stage == "cancelling":
        if not memory.get("name"):
            return (
                "A customer wants to cancel their reservation. "
                "Ask only: what name is it under?"
            )
        else:
            return (
                f"Confirm cancellation of {memory.get('name')}'s reservation in one friendly sentence."
            )

    # ── GENERAL / ANSWERING — inject tool result or RAG context ─────────────
    else:
        # Build restaurant facts as fallback even without RAG
        facts = (
            "La Bella Tavola — Italian-Mediterranean restaurant. "
            "Open 12 PM–11 PM daily. Located at 123 Main Street, Downtown. "
            "Phone: +1-800-555-1234. Smart casual dress code. "
            "Street parking, valet on weekends. Up to 8 guests per table."
        )

        base = (
            "You are a helpful assistant for La Bella Tavola restaurant. "
            "Answer the customer's question in 1–3 sentences using only the information below. "
            "If the answer is not there, say: 'I don't have that detail — please call us on +1-800-555-1234.'\n\n"
        )

        if retrieved_context and retrieved_context.strip():
            base += f"INFORMATION:\n{retrieved_context}\n"
        else:
            base += f"INFORMATION:\n{facts}\n"

        return base


def build_system_prompt(memory: dict, recent_turns: list[dict],
                        stage: str = "collecting",
                        retrieved_context: str = "",
                        modify_field: str | None = None) -> str:
    return build_system_prompt_text(
        memory, recent_turns, stage,
        retrieved_context=retrieved_context,
        modify_field=modify_field
    )

def build_modification_prompt(memory: dict, recent_turns: list[dict],
                               modify_field: str | None = None) -> str:
    return build_system_prompt_text(memory, recent_turns, "modifying",
                                    modify_field=modify_field)

def build_cancellation_prompt(memory: dict, recent_turns: list[dict]) -> str:
    return build_system_prompt_text(memory, recent_turns, "cancelling")

def build_confirmation_prompt(memory: dict, recent_turns: list[dict]) -> str:
    return build_system_prompt_text(memory, recent_turns, "confirming")


# ---------------------------------------------------------------------------
# Few-shot message pairs — these are what actually steer Qwen 1.8B
# Keep them SHORT and concrete — model copies the pattern exactly
# ---------------------------------------------------------------------------

FEW_SHOT_GREETING = [
    {"role": "user",      "content": "Hi"},
    {"role": "assistant", "content": "Welcome to La Bella Tavola! Would you like to make a reservation or do you have a question?"},
    {"role": "user",      "content": "Hello, can I book a table?"},
    {"role": "assistant", "content": "Of course! What date were you thinking?"},
]

FEW_SHOT_DATE = [
    {"role": "user",      "content": "I want to book a table."},
    {"role": "assistant", "content": "What date would you like?"},
    {"role": "user",      "content": "Can I reserve for this weekend?"},
    {"role": "assistant", "content": "Sure — Saturday or Sunday?"},
]

FEW_SHOT_TIME = [
    {"role": "user",      "content": "March 15th."},
    {"role": "assistant", "content": "Great — what time on March 15th?"},
    {"role": "user",      "content": "Tomorrow evening."},
    {"role": "assistant", "content": "Tomorrow evening — what time exactly, like 7 or 8 PM?"},
    {"role": "user",      "content": "This Saturday."},
    {"role": "assistant", "content": "Saturday it is — what time were you thinking?"},
]

FEW_SHOT_GUESTS = [
    {"role": "user",      "content": "7 PM."},
    {"role": "assistant", "content": "Perfect. How many guests?"},
    {"role": "user",      "content": "8 PM works."},
    {"role": "assistant", "content": "Got it — how many people will be joining?"},
]

FEW_SHOT_NAME = [
    {"role": "user",      "content": "Just 2 of us."},
    {"role": "assistant", "content": "Table for 2 — what name for the booking, and any dietary preferences or special requests?"},
    {"role": "user",      "content": "4 people."},
    {"role": "assistant", "content": "Table for 4 — what name, and any dietary needs or special occasions?"},
    {"role": "user",      "content": "3 guests."},
    {"role": "assistant", "content": "Got it — what name should I put the reservation under? Any dietary needs?"},
]

FEW_SHOT_CONFIRMING = [
    {"role": "user",      "content": "Ahmed Khan, no dietary needs."},
    {"role": "assistant", "content": "So that's a table for 4 on Saturday at 7 PM under Ahmed Khan — shall I confirm?"},
    {"role": "user",      "content": "Sara Ali, I'm vegetarian."},
    {"role": "assistant", "content": "Table for 2 on Friday at 8 PM under Sara Ali, vegetarian noted — does that look right?"},
    {"role": "user",      "content": "Bilal Ahmed."},
    {"role": "assistant", "content": "Table for 2 on March 20 at 8 PM under Bilal Ahmed — shall I confirm?"},
]

FEW_SHOT_CONFIRMED = [
    {"role": "user",      "content": "Yes, confirm please."},
    {"role": "assistant", "content": "All set — your table for 4 on Saturday at 7 PM under Ahmed Khan is confirmed, see you then!"},
    {"role": "user",      "content": "Perfect, go ahead."},
    {"role": "assistant", "content": "Confirmed! Table for 2 on March 20 at 8 PM under Bilal Ahmed is booked — see you soon!"},
    {"role": "user",      "content": "Yes that's right."},
    {"role": "assistant", "content": "Wonderful — your table for 3 on Sunday at 7 PM under Sara Ali is all set!"},
]

FEW_SHOT_MODIFYING_NO_NAME = [
    {"role": "user",      "content": "I need to change my booking."},
    {"role": "assistant", "content": "Sure — what name is the reservation under?"},
    {"role": "user",      "content": "I want to update my reservation."},
    {"role": "assistant", "content": "Of course — what name is the booking under?"},
]

FEW_SHOT_MODIFYING_WHAT = [
    {"role": "user",      "content": "It's under Ali Raza."},
    {"role": "assistant", "content": "Got it — what would you like to change: the date, the time, or the number of guests?"},
    {"role": "user",      "content": "My name is Sara Ahmed."},
    {"role": "assistant", "content": "Found Sara Ahmed's reservation — what would you like to update: date, time, or guest count?"},
]

FEW_SHOT_MODIFYING = FEW_SHOT_MODIFYING_NO_NAME  # legacy alias

FEW_SHOT_CANCELLING = [
    {"role": "user",      "content": "I want to cancel my reservation."},
    {"role": "assistant", "content": "No problem — what name is the booking under?"},
    {"role": "user",      "content": "Omar Khan."},
    {"role": "assistant", "content": "Done — Omar Khan's reservation has been cancelled. We hope to see you another time!"},
]

FEW_SHOT_GENERAL = [
    {"role": "user",      "content": "What time do you open?"},
    {"role": "assistant", "content": "We're open every day from 12 PM to 11 PM."},
    {"role": "user",      "content": "Is there parking?"},
    {"role": "assistant", "content": "Yes — street parking is available, and we offer valet on weekends."},
    {"role": "user",      "content": "What cuisine do you serve?"},
    {"role": "assistant", "content": "Italian-Mediterranean — fresh pasta, grilled meats, and seafood."},
    {"role": "user",      "content": "Do I need a reservation for lunch?"},
    {"role": "assistant", "content": "Walk-ins are welcome for lunch, though we recommend booking on weekends."},
]

# Tool-result few-shots — used when a tool just ran
FEW_SHOT_TOOL_MENU = [
    {"role": "user",      "content": "What pasta dishes do you have?"},
    {"role": "assistant", "content": "We have Tagliatelle al Ragù Bolognese ($20), Spaghetti ai Frutti di Mare ($22), and Fettuccine Alfredo ($18), among others. Would you like more details?"},
    {"role": "user",      "content": "Do you have vegetarian options?"},
    {"role": "assistant", "content": "Yes — vegetarian options include Bruschetta al Pomodoro ($9), Burrata and Heirloom Tomatoes ($14), and Arancini Siciliani ($11). Shall I list more?"},
]

FEW_SHOT_TOOL_WEATHER = [
    {"role": "user",      "content": "What's the weather like?"},
    {"role": "assistant", "content": "It's currently 18°C and clear — outdoor seating looks great today!"},
    {"role": "user",      "content": "Is outdoor seating a good idea?"},
    {"role": "assistant", "content": "It's a bit rainy right now, so our indoor tables would be more comfortable today."},
]

FEW_SHOT_TOOL_LOOKUP = [
    {"role": "user",      "content": "Check my reservation under Ahmed."},
    {"role": "assistant", "content": "I found a reservation for Ahmed on Friday at 7 PM for 4 guests — is that the one?"},
    {"role": "user",      "content": "Do I have a booking?"},
    {"role": "assistant", "content": "I couldn't find a reservation under that name. Would you like to make a new booking?"},
]


def get_few_shot_examples(stage: str, memory: dict,
                          modify_field: str | None = None,
                          tool_used: str | None = None) -> list[dict]:
    """Return the right few-shot message pairs for the current stage/tool."""

    # Tool-specific few-shots take priority
    if tool_used == "search_menu":
        return FEW_SHOT_TOOL_MENU
    if tool_used == "get_weather":
        return FEW_SHOT_TOOL_WEATHER
    if tool_used == "lookup_reservation":
        return FEW_SHOT_TOOL_LOOKUP

    next_f = _next_field(memory)
    if stage == "greeting":
        return FEW_SHOT_GREETING
    elif stage == "collecting":
        return {"date": FEW_SHOT_DATE, "time": FEW_SHOT_TIME,
                "guests": FEW_SHOT_GUESTS, "name": FEW_SHOT_NAME}.get(next_f, FEW_SHOT_GREETING)
    elif stage == "confirming":
        return FEW_SHOT_CONFIRMING
    elif stage == "confirmed":
        return FEW_SHOT_CONFIRMED
    elif stage == "modifying":
        return FEW_SHOT_MODIFYING_WHAT if memory.get("name") else FEW_SHOT_MODIFYING_NO_NAME
    elif stage == "cancelling":
        return FEW_SHOT_CANCELLING
    else:
        return FEW_SHOT_GENERAL