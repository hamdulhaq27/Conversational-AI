"""
Phase III - Prompt Templates
Restaurant Reservation Conversational AI

Strategy for qwen:1.8b:
  - System prompt is SHORT and direct
  - Few-shot examples injected as real message turns (not text in system prompt)
  - Stage-specific examples so the model always sees the exact pattern to copy
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

# Vague time words that need a specific-time follow-up (e.g. "evening" → "7 PM?")
_VAGUE_TIMES = {"evening", "morning", "afternoon"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _missing_fields(memory: dict) -> list[str]:
    """
    Return required fields that are still unresolved.
    Vague period words ("evening", "morning", "afternoon") count as unresolved
    because the model must ask for a specific clock time.
    """
    missing = []
    for k in REQUIRED_FIELDS:
        v = memory.get(k)
        if not v:
            missing.append(k)
        elif k == "time" and str(v).lower() in _VAGUE_TIMES:
            missing.append(k)   # treat vague period as still missing
    return missing

def _next_field(memory: dict) -> str:
    m = _missing_fields(memory)
    return m[0] if m else ""

def _collected_summary(memory: dict) -> str:
    """
    Summarise what has been collected so far.
    • Vague period times ("evening") are excluded — they don't count as resolved.
    • Optional fields (dietary_preferences, special_requests) are included if set.
    """
    _DISPLAY_KEYS = REQUIRED_FIELDS + ["dietary_preferences", "special_requests"]
    parts = []
    for k in _DISPLAY_KEYS:
        v = memory.get(k)
        if not v:
            continue
        if k == "time" and str(v).lower() in _VAGUE_TIMES:
            continue   # don't show unresolved vague time as collected
        parts.append(f"{k}: {v}")
    return ", ".join(parts) if parts else "nothing yet"

def _missing_summary(memory: dict) -> str:
    missing = _missing_fields(memory)
    return ", ".join(missing) if missing else "none"

def _history_block(recent_turns: list[dict]) -> str:
    """Render conversation history as labelled turns — used in system prompt text."""
    if not recent_turns:
        return "(no prior turns)"
    lines = []
    for t in recent_turns:
        label = "Customer" if t["role"] == "user" else "Assistant"
        lines.append(f'{label}: {t["content"]}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompt — short but complete enough for all test assertions
# ---------------------------------------------------------------------------

def build_system_prompt_text(memory: dict, recent_turns: list[dict],
                             stage: str, modify_field: str | None = None) -> str:
    """
    Compact system prompt that still contains all required fields for tests:
      - restaurant name, hours
      - collected signals  (date, time, etc.)
      - missing required fields  (name, guests, etc.)
      - policy line
      - stage/task instruction
      - conversation history
    """
    next_f    = _next_field(memory)
    collected = _collected_summary(memory)
    missing   = _missing_summary(memory)
    history   = _history_block(recent_turns)

    field_questions = {
        "date":   "Ask the customer what date they would like.",
        "time":   "Ask the customer what specific time they would like (e.g. 7 PM, 8 PM).",
        "guests": "Ask the customer how many guests.",
        "name":   (
            "Ask the customer for the name on the reservation and, "
            "since this is the last required detail, also ask whether they have "
            "any dietary preferences (vegetarian, halal, etc.) or special requests "
            "(birthday, anniversary, window seat, etc.)."
        ),
    }

    if stage == "greeting":
        task = "Greet the customer briefly and ask how you can help."
    elif stage == "collecting":
        task = field_questions.get(next_f, "Ask for the next missing detail.")
    elif stage == "confirming":
        task = f"Read back all details ({collected}) and ask the customer to confirm."
    elif stage == "confirmed":
        # Inject exact values directly — model must echo these in its reply
        _date   = memory.get("date")   or "?"
        _time   = memory.get("time")   or "?"
        _guests = memory.get("guests") or "?"
        _name   = memory.get("name")   or "?"
        task = (
            f"Respond with ONE warm sentence confirming the reservation. "
            f"You MUST include ALL of these exact details in your reply:\n"
            f"  NAME={_name}  DATE={_date}  TIME={_time}  GUESTS={_guests}\n"
            f'Example: "Your table for {_guests} on {_date} at {_time} under {_name} is confirmed!"'
        )
    elif stage == "modifying":
        has_name = bool(memory.get("name"))
        _mname   = memory.get("name") or "the customer"
        if not has_name:
            # Sub-state 1: need the booking name
            task = "Ask for the name the reservation is under. One sentence only."
        else:
            # Sub-state 2: have the name, ask WHAT to change (field + new value)
            task = (
                f"You found {_mname}'s reservation. "
                "Ask what they would like to change (date, time, or number of guests). "
                "One sentence — do NOT suggest or mention any specific new value."
            )
    elif stage == "cancelling":
        task = ("Help cancel the reservation. "
                "If no Name yet, ask for the Name on the booking. "
                "Then confirm the cancellation.")
    else:
        task = "Answer the customer's question about the restaurant in one sentence."

    return f"""You are a reservation assistant at {RESTAURANT_INFO['name']} restaurant.
Hours: {RESTAURANT_INFO['hours']} | Location: {RESTAURANT_INFO['location']}
Lunch: {RESTAURANT_INFO['lunch_reservation']}
Dinner: {RESTAURANT_INFO['dinner_reservation']}
Parking: {RESTAURANT_INFO['parking']} | Dress: {RESTAURANT_INFO['dress_code']}

Policy: Reply in ONE short sentence only. No lists. No "Thank you for providing". No sign-offs. Do NOT use fake placeholders like [date] or [name]. If you don't know a detail, simply ASK the customer for it.
Stage: {stage.upper()}
Collected: {collected}
Missing required fields: {missing}

Recent conversation:
{history}

Task: {task}"""


# ---------------------------------------------------------------------------
# Few-shot message pairs — injected as real message turns in _build_messages
# This is what actually controls qwen:1.8b's response style
# ---------------------------------------------------------------------------

FEW_SHOT_GREETING = [
    {"role": "user",      "content": "Hi, I'd like to book a table."},
    {"role": "assistant", "content": "Sure! What date did you have in mind?"},
    {"role": "user",      "content": "Hello, can I make a reservation?"},
    {"role": "assistant", "content": "Of course — what date works for you?"},
]

FEW_SHOT_DATE = [
    {"role": "user",      "content": "I want to book a table."},
    {"role": "assistant", "content": "What date would you like?"},
    {"role": "user",      "content": "Can I reserve for this weekend?"},
    {"role": "assistant", "content": "Sure — Saturday or Sunday?"},
]

FEW_SHOT_TIME = [
    {"role": "user",      "content": "March 15th."},
    {"role": "assistant", "content": "Great, what time on March 15th?"},
    {"role": "user",      "content": "This Saturday."},
    {"role": "assistant", "content": "Saturday it is — what time were you thinking?"},
    {"role": "user",      "content": "Tomorrow evening."},
    {"role": "assistant", "content": "Tomorrow evening works — what time exactly, like 7 or 8 PM?"},
    {"role": "user",      "content": "Sometime in the morning."},
    {"role": "assistant", "content": "Morning it is — what time were you thinking, around 11 AM or noon?"},
]

FEW_SHOT_GUESTS = [
    {"role": "user",      "content": "7 PM."},
    {"role": "assistant", "content": "Perfect. How many guests will that be?"},
    {"role": "user",      "content": "Around 8 in the evening."},
    {"role": "assistant", "content": "Got it — and how many people?"},
]

FEW_SHOT_NAME = [
    {"role": "user",      "content": "Just the two of us."},
    {"role": "assistant", "content": "Perfect — what name for the booking, and any dietary preferences or special requests?"},
    {"role": "user",      "content": "4 people."},
    {"role": "assistant", "content": "Table for 4 — what name for the reservation, and any dietary needs or special occasions?"},
    {"role": "user",      "content": "3 guests."},
    {"role": "assistant", "content": "Got it, 3 guests — what name should I use, and do you have any dietary requirements or special requests?"},
]

FEW_SHOT_CONFIRMING = [
    {"role": "user",      "content": "Ahmed Khan, no dietary needs."},
    {"role": "assistant", "content": "So that's a table for 4 on tomorrow at 7 PM under Ahmed Khan — shall I confirm that?"},
    {"role": "user",      "content": "Sara Ali, I'm vegetarian."},
    {"role": "assistant", "content": "Table for 2 on Saturday at 8 PM under Sara Ali, vegetarian noted — does that look right?"},
    {"role": "user",      "content": "Bilal Ahmed."},
    {"role": "assistant", "content": "So that's a table for 2 on March 20 at 8 PM under Bilal Ahmed — shall I confirm that?"},
]

FEW_SHOT_CONFIRMED = [
    {"role": "user",      "content": "Yes, that's correct."},
    {"role": "assistant", "content": "All set — your table for 4 on tomorrow at 7 PM under Ahmed Khan is confirmed, see you then!"},
    {"role": "user",      "content": "Perfect, go ahead."},
    {"role": "assistant", "content": "Confirmed! Your table for 2 on March 20 at 8 PM under Bilal Ahmed is booked — see you soon!"},
    {"role": "user",      "content": "Can you confirm what you have so far?"},
    {"role": "assistant", "content": "Of course — your table for 2 on March 20 at 8 PM under Bilal Ahmed is confirmed!"},
    {"role": "user",      "content": "Yes go ahead and book it."},
    {"role": "assistant", "content": "Done! Your table for 3 on Saturday at 7 PM under Sara Ali is confirmed!"},
    {"role": "user",      "content": "Yes please confirm."},
    {"role": "assistant", "content": "Confirmed — your table for 4 on Friday at 8 PM under Omar Khan is all booked!"},
]


# Modifying — Sub-state 1: no name yet, just ask for it
# NOTE: examples must NOT exactly match test inputs or qwen:1.8b pattern-matches
# the few-shot answer and returns empty for the real user message.
FEW_SHOT_MODIFYING_NO_NAME = [
    {"role": "user",      "content": "I need to change something on my booking."},
    {"role": "assistant", "content": "Sure — what name is the reservation under?"},
    {"role": "user",      "content": "I want to update my reservation details."},
    {"role": "assistant", "content": "Of course — what name is the booking under?"},
    {"role": "user",      "content": "Can I make a change to my reservation?"},
    {"role": "assistant", "content": "Happy to help — what name is the booking under?"},
]

# Modifying — Sub-state 2: have the name, ask WHAT to change
FEW_SHOT_MODIFYING_WHAT = [
    {"role": "user",      "content": "It's under Ali Raza."},
    {"role": "assistant", "content": "Got it — I have Ali Raza's reservation. What would you like to change: the date, the time, or the number of guests?"},
    {"role": "user",      "content": "The name is Omar Khan."},
    {"role": "assistant", "content": "Found it — Omar Khan's reservation is here. What would you like to update: date, time, or guest count?"},
    {"role": "user",      "content": "My name is Sara Ahmed."},
    {"role": "assistant", "content": "Got Sara Ahmed's reservation — what would you like to change: the date, the time, or the number of guests?"},
]

# Keep legacy alias
FEW_SHOT_MODIFYING = FEW_SHOT_MODIFYING_NO_NAME

FEW_SHOT_CANCELLING = [
    {"role": "user",      "content": "I want to cancel my reservation."},
    {"role": "assistant", "content": "No problem — what name is the booking under?"},
    {"role": "user",      "content": "Omar Khan, March 10 at 7 PM."},
    {"role": "assistant", "content": "Done — Omar Khan's reservation for March 10 at 7 PM has been cancelled."},
]

FEW_SHOT_GENERAL = [
    {"role": "user",      "content": "What time do you open?"},
    {"role": "assistant", "content": "We're open every day from 12 PM to 11 PM."},
    {"role": "user",      "content": "Do I need a reservation for lunch?"},
    {"role": "assistant", "content": "Walk-ins are welcome for lunch, though we recommend booking on weekends."},
    {"role": "user",      "content": "Is there parking?"},
    {"role": "assistant", "content": "Yes, street parking is available and we offer valet on weekends."},
    {"role": "user",      "content": "What's the dress code?"},
    {"role": "assistant", "content": "Smart casual — no sportswear, nothing too formal."},
    {"role": "user",      "content": "What cuisine do you serve?"},
    {"role": "assistant", "content": "Italian-Mediterranean — fresh pasta, grilled meats, and seafood."},
]


def get_few_shot_examples(stage: str, memory: dict,
                          modify_field: str | None = None) -> list[dict]:
    """Return the right few-shot message pairs for the current stage."""
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
        # Sub-state 1: no name yet; sub-state 2: have name, ask what to change.
        # Sub-state 3 (done) is handled deterministically — no LLM call.
        return FEW_SHOT_MODIFYING_WHAT if memory.get("name") else FEW_SHOT_MODIFYING_NO_NAME
    elif stage == "cancelling":
        return FEW_SHOT_CANCELLING
    else:
        return FEW_SHOT_GENERAL


# ---------------------------------------------------------------------------
# Public builders — used by conversation_manager
# ---------------------------------------------------------------------------

def build_system_prompt(memory: dict, recent_turns: list[dict],
                        stage: str = "collecting",
                        modify_field: str | None = None) -> str:
    return build_system_prompt_text(memory, recent_turns, stage,
                                    modify_field=modify_field)

def build_modification_prompt(memory: dict, recent_turns: list[dict],
                               modify_field: str | None = None) -> str:
    return build_system_prompt_text(memory, recent_turns, "modifying",
                                    modify_field=modify_field)

def build_cancellation_prompt(memory: dict, recent_turns: list[dict]) -> str:
    return build_system_prompt_text(memory, recent_turns, "cancelling")

def build_confirmation_prompt(memory: dict, recent_turns: list[dict]) -> str:
    return build_system_prompt_text(memory, recent_turns, "confirming")