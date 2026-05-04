"""
Prompt Templates — La Bella Tavola Conversational AI
Clean, LLM-first design:
  - Stage-specific system prompts (short, unambiguous)
  - CRM data injected directly as plain text (no intermediate plan)
  - Few-shot examples as real message turns
  - No planner, no compile_plan, no validate_plan
"""

import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SIGNAL_KEYS     = ["date", "time", "guests", "name", "dietary_preferences", "special_requests"]
REQUIRED_FIELDS = ["date", "time", "guests", "name"]
_VAGUE_TIMES    = {"evening", "morning", "afternoon"}

_RESTAURANT_FACTS = (
    "La Bella Tavola — Italian-Mediterranean restaurant. "
    "Open 12 PM–11 PM daily. 123 Main Street, Downtown. "
    "Phone: +1-800-555-1234. Smart casual dress code. "
    "Street parking; valet on weekends. Max 8 guests per table."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _missing_fields(memory: dict) -> list[str]:
    missing = []
    for k in REQUIRED_FIELDS:
        v = memory.get(k)
        if not v or (k == "time" and str(v).lower() in _VAGUE_TIMES):
            missing.append(k)
    return missing


def _next_field(memory: dict) -> str:
    m = _missing_fields(memory)
    return m[0] if m else ""


def _collected_summary(memory: dict) -> str:
    parts = []
    for k in REQUIRED_FIELDS + ["dietary_preferences", "special_requests"]:
        v = memory.get(k)
        if v and not (k == "time" and str(v).lower() in _VAGUE_TIMES):
            parts.append(f"{k}: {v}")
    return ", ".join(parts) if parts else "nothing yet"


def _crm_block(user_data: dict) -> str:
    """Render non-empty CRM fields plus active reservation as a plain-text block."""
    order = ["name", "dietary_preferences", "special_requests"]
    active = {k: user_data.get(k) for k in order if user_data.get(k)}

    reservations = user_data.get("reservations") or []
    latest_active = next(
        (r for r in reversed(reservations) if r.get("status") != "cancelled"),
        None,
    )

    if not active and not latest_active:
        return ""

    lines = ["[AUTHORITATIVE USER MEMORY]"]
    for k, v in active.items():
        lines.append(f"  {k}: {v}")
    if latest_active:
        lines.append(
            f"  current_reservation: {latest_active.get('date','?')} at "
            f"{latest_active.get('time','?')} for {latest_active.get('guests','?')} guests"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# System prompt builder — one function, dispatches by stage
# ---------------------------------------------------------------------------

def build_system_prompt(memory: dict, stage: str,
                        user_data: dict | None = None,
                        retrieved_context: str = "",
                        modify_field: str | None = None,
                        retry_hint: str | None = None) -> str:
    """
    Build a short, stage-specific system prompt.
    CRM data is injected as plain text — no plan, no compile step.
    """
    crm   = _crm_block(user_data or {})
    retry = f"\n[CORRECTION NEEDED]: {retry_hint}\n" if retry_hint else ""

    # Dietary safety line — only added when CRM has a preference
    diet_line = ""
    diet = (user_data or {}).get("dietary_preferences", "")
    if diet:
        diet_line = f"IMPORTANT: This customer is {diet}. Only suggest {diet}-appropriate food.\n"

    # Name reminder — only when CRM has a name
    name_line = ""
    crm_name = (user_data or {}).get("name", "")
    if crm_name:
        name_line = f"Address the customer as {crm_name}.\n"

    base_identity = (
        "You are the front-of-house host at La Bella Tavola, an Italian-Mediterranean restaurant.\n"
        "YOUR ONLY JOB: Help guests make, modify, or cancel table reservations at this restaurant, "
        "and answer questions about La Bella Tavola's menu, hours, and services.\n"
        "STRICT RULES:\n"
        "- Reply in ONE short, natural sentence. Never use bullet points, numbered lists, or steps.\n"
        "- NEVER ask about the 'purpose' of a booking — every reservation here is a restaurant table booking.\n"
        "- NEVER mention movies, cinemas, flights, hotels, or anything unrelated to this restaurant.\n"
        "- Never tell the customer to visit a website, use a link, fill a form, or do steps themselves — YOU handle the booking.\n"
        "- Use the [AUTHORITATIVE USER MEMORY] block as ground truth. Never ask for info already in it.\n"
        "- If the customer's words contradict memory, trust the customer.\n"
        "- If the customer wants to make a reservation, guide them through it — do not ask what the reservation is for.\n"
    )

    if stage == "greeting":
        if crm_name:
            return (
                base_identity
                + name_line + diet_line + crm
                + f"Greet {crm_name} warmly by name in ONE sentence and ask if they'd like to make a reservation or have a question about the restaurant."
                + retry
            )
        return (
            base_identity
            + "Welcome the guest to La Bella Tavola in ONE warm sentence and offer to help them make a table reservation or answer questions about the restaurant."
            + retry
        )

    if stage == "collecting":
        next_f   = _next_field(memory)
        already  = _collected_summary(memory)
        field_ask = {
            "date":    "Reply with ONE short question asking what date they would like. Do not list options or steps.",
            "time":    "Reply with ONE short question asking what specific time (e.g. 7 PM). Do not accept vague answers.",
            "guests":  "Reply with ONE short question asking how many guests. Do not list options.",
            "name":    "Reply with ONE short question asking for the name to book under, and dietary preferences or special requests.",
        }.get(next_f, "Reply with ONE short question for the next missing reservation detail.")
        return (
            base_identity
            + name_line + diet_line + crm
            + f"Already collected: {already}.\n"
            + f"Next missing field: {next_f}.\n"
            + field_ask
            + retry
        )

    if stage == "confirming":
        collected = _collected_summary(memory)
        return (
            base_identity
            + name_line + crm
            + f"Read these details back in ONE friendly sentence and ask 'shall I confirm?': {collected}.\n"
            + "Do NOT add extra fields, steps, or links."
            + retry
        )

    if stage == "confirmed":
        mem_name = memory.get("name") or crm_name or "you"
        extras = []
        if memory.get("dietary_preferences"):
            extras.append(memory["dietary_preferences"])
        elif diet:
            extras.append(diet)
        if memory.get("special_requests"):
            extras.append(memory["special_requests"])
        extra_str = f", {', '.join(extras)}" if extras else ""
        return (
            base_identity
            + f"Confirm in ONE warm sentence that the booking is set: table for "
            f"{memory.get('guests','?')} on {memory.get('date','?')} at "
            f"{memory.get('time','?')} under {mem_name}{extra_str}. "
            "End with 'see you then!' or similar. Do NOT add lists, steps, or links."
            + retry
        )

    if stage == "modifying":
        name_to_use = memory.get("name") or crm_name
        if not name_to_use:
            return base_identity + "Ask: what name is the reservation under?" + retry
        if modify_field and memory.get(modify_field):
            label = {"date": "date", "time": "time", "guests": "number of guests"}.get(modify_field, modify_field)
            return (
                base_identity
                + f"Confirm the change for {name_to_use}: {label} updated to {memory[modify_field]}. One sentence."
                + retry
            )
        return (
            base_identity
            + f"You have {name_to_use}'s reservation. Ask: what would you like to change — date, time, or guest count?"
            + retry
        )

    if stage == "cancelling":
        name_to_use = memory.get("name") or crm_name
        if not name_to_use:
            return base_identity + "Ask: what name is the reservation under?" + retry
        return (
            base_identity
            + f"Confirm cancellation of {name_to_use}'s reservation in one friendly sentence."
            + retry
        )

    # general / answering
    info = retrieved_context.strip() if retrieved_context.strip() else _RESTAURANT_FACTS
    return (
        base_identity
        + name_line + diet_line + crm
        + "Answer the customer's question in 1–3 sentences using ONLY the restaurant information below.\n"
        + "If the customer seems to want a table reservation, ask if they'd like to make one.\n"
        + "If the answer is not in the information below, say: 'I don't have that detail — please call us on +1-800-555-1234.'\n\n"
        + f"RESTAURANT INFORMATION:\n{info}\n"
        + retry
    )


# ---------------------------------------------------------------------------
# Few-shot examples — unchanged, these steer Qwen effectively
# ---------------------------------------------------------------------------

FEW_SHOT_GREETING = [
    {"role": "user",      "content": "Hi"},
    {"role": "assistant", "content": "Welcome to La Bella Tavola! Would you like to make a reservation or do you have a question?"},
    {"role": "user",      "content": "Hello, can I book a table?"},
    {"role": "assistant", "content": "Of course! What date were you thinking?"},
]

FEW_SHOT_RETURNING_USER = [
    {"role": "user",      "content": "Hi there"},
    {"role": "assistant", "content": "Welcome back, John! Great to see you again — shall I make a reservation or can I help with something else?"},
    {"role": "user",      "content": "What's good today?"},
    {"role": "assistant", "content": "Since you prefer vegetarian options, I'd recommend our Truffle Mushroom Risotto — it's excellent tonight."},
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
]

FEW_SHOT_CONFIRMING = [
    {"role": "user",      "content": "CUSTOMER_NAME, no dietary needs."},
    {"role": "assistant", "content": "So that's a table for 4 on Saturday at 7 PM under CUSTOMER_NAME — shall I confirm?"},
    {"role": "user",      "content": "ANOTHER_NAME, I'm vegetarian."},
    {"role": "assistant", "content": "Table for 2 on Friday at 8 PM under ANOTHER_NAME, vegetarian noted — does that look right?"},
]

FEW_SHOT_CONFIRMED = [
    {"role": "user",      "content": "Yes, confirm please."},
    {"role": "assistant", "content": "All set — your table for 4 on Saturday at 7 PM under CUSTOMER_NAME is confirmed, see you then!"},
    {"role": "user",      "content": "Perfect, go ahead."},
    {"role": "assistant", "content": "Confirmed! Table for 2 on March 20 at 8 PM under ANOTHER_NAME is booked — see you soon!"},
]

FEW_SHOT_MODIFYING_NO_NAME = [
    {"role": "user",      "content": "I need to change my booking."},
    {"role": "assistant", "content": "Sure — what name is the reservation under?"},
]

FEW_SHOT_MODIFYING_WHAT = [
    {"role": "user",      "content": "It's under EXAMPLE_NAME."},
    {"role": "assistant", "content": "Got it — what would you like to change: the date, the time, or the number of guests?"},
]

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
]

FEW_SHOT_TOOL_MENU = [
    {"role": "user",      "content": "What pasta dishes do you have?"},
    {"role": "assistant", "content": "We have Tagliatelle al Ragù Bolognese ($20), Spaghetti ai Frutti di Mare ($22), and Fettuccine Alfredo ($18), among others."},
    {"role": "user",      "content": "Do you have vegetarian options?"},
    {"role": "assistant", "content": "Yes — vegetarian options include Bruschetta al Pomodoro ($9), Burrata and Heirloom Tomatoes ($14), and Arancini Siciliani ($11)."},
]

FEW_SHOT_TOOL_WEATHER = [
    {"role": "user",      "content": "What's the weather like?"},
    {"role": "assistant", "content": "It's currently 18°C and clear — outdoor seating looks great today!"},
]

FEW_SHOT_TOOL_LOOKUP = [
    {"role": "user",      "content": "Check my reservation under Ahmed."},
    {"role": "assistant", "content": "I found a reservation for Ahmed on Friday at 7 PM for 4 guests — is that the one?"},
]


def get_few_shot_examples(stage: str, memory: dict,
                          modify_field: str | None = None,
                          tool_used: str | None = None,
                          user_data: dict | None = None) -> list[dict]:
    if tool_used == "search_menu":
        return FEW_SHOT_TOOL_MENU
    if tool_used == "get_weather":
        return FEW_SHOT_TOOL_WEATHER
    if tool_used == "lookup_reservation":
        return FEW_SHOT_TOOL_LOOKUP

    next_f = _next_field(memory)
    if stage == "greeting":
        return FEW_SHOT_RETURNING_USER if (memory.get("name") or (user_data or {}).get("name")) else FEW_SHOT_GREETING
    if stage == "collecting":
        return {"date": FEW_SHOT_DATE, "time": FEW_SHOT_TIME,
                "guests": FEW_SHOT_GUESTS, "name": FEW_SHOT_NAME}.get(next_f, FEW_SHOT_GREETING)
    if stage == "confirming":  return FEW_SHOT_CONFIRMING
    if stage == "confirmed":   return FEW_SHOT_CONFIRMED
    if stage == "modifying":   return FEW_SHOT_MODIFYING_WHAT if memory.get("name") else FEW_SHOT_MODIFYING_NO_NAME
    if stage == "cancelling":  return FEW_SHOT_CANCELLING
    return FEW_SHOT_GENERAL
