"""
Phase III – Dialogue Test Suite
Restaurant Reservation Conversational AI
=========================================
Covers:
  • Signal extraction  (unit)
  • Intent detection   (unit)
  • Policy guardrail   (unit)
  • Stage machine      (unit)
  • Prompt builder     (unit — checks structure, not wording)
  • Session lifecycle  (integration)
  • Sliding window     (integration)
  • Multi-turn flows   (E2E, requires live Ollama — set LIVE=True)

Run (mock mode, no Ollama):
    python test_dialogue.py

Run (live mode, Ollama must be running with qwen:1.8b):
    LIVE=1 python test_dialogue.py
    # or edit LIVE = True below
"""

import os
import sys
import time

# ── Toggle ────────────────────────────────────────────────────────────────────
# False  = unit/integration tests only  (fast, no Ollama needed)
# True   = also run full E2E multi-turn dialogue tests against live Ollama
LIVE: bool = os.environ.get("LIVE", "0") == "1"

# ── Imports ───────────────────────────────────────────────────────────────────
from prompt_templates import (
    SIGNAL_KEYS, REQUIRED_FIELDS,
    build_system_prompt, build_modification_prompt,
    build_cancellation_prompt, build_confirmation_prompt,
    RESTAURANT_INFO,
)
from conversation_manager import (
    create_session, get_session, reset_session, list_sessions,
    session_debug_info, extract_signals, detect_intent, is_off_topic,
    _next_stage, _get_window, _is_noise, SIGNAL_KEYS as CM_SIGNAL_KEYS,
)

# ── Test harness ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
_results: list[tuple[str, bool, str]] = []   # (label, passed, section)
_current_section = ""


def section(title: str):
    global _current_section
    _current_section = title
    width = 64
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}")


def check(label: str, condition: bool, detail: str = ""):
    """Record and print a single assertion."""
    _results.append((label, condition, _current_section))
    status = f"{GREEN}PASS{RESET}" if condition else f"{RED}FAIL{RESET}"
    print(f"  [{status}] {label}")
    if not condition and detail:
        print(f"         {RED}↳ {detail}{RESET}")


def check_eq(label: str, got, expected):
    ok = got == expected
    detail = f"expected {expected!r}, got {got!r}" if not ok else ""
    check(label, ok, detail)


def check_in(label: str, substring: str, text: str):
    ok = substring.lower() in text.lower()
    detail = f"{substring!r} not found in output" if not ok else ""
    check(label, ok, detail)


def _blank_memory() -> dict:
    return {k: None for k in SIGNAL_KEYS}


# ═════════════════════════════════════════════════════════════════════════════
# 1. Signal Extraction
# ═════════════════════════════════════════════════════════════════════════════

def test_signal_extraction():
    section("1 · Signal Extraction")

    b = _blank_memory

    # --- Date ---
    m = extract_signals("I'd like to book for March 6", b())
    check_eq("named-month date",       m["date"].lower(), "march 6")

    m = extract_signals("Can I come tomorrow evening?", b())
    check_eq("relative date (tomorrow)", m["date"].lower(), "tomorrow")

    m = extract_signals("Booking for today please.", b())
    check_eq("relative date (today)",    m["date"].lower(), "today")

    m = extract_signals("Next Friday works for me.", b())
    check("relative date (next ...)",   m["date"] is not None and "next" in m["date"].lower())

    # --- Time ---
    m = extract_signals("Around 7 PM please.", b())
    check_eq("PM time",   m["time"].lower(), "7 pm")

    m = extract_signals("Let's say 8:30 AM.", b())
    check("HH:MM AM time", m["time"] is not None and "8:30" in m["time"])

    m = extract_signals("We'll arrive at noon.", b())
    check_eq("noon keyword", m["time"].lower(), "noon")

    m = extract_signals("Come in the evening.", b())
    check_eq("evening keyword", m["time"].lower(), "evening")

    # --- Guests ---
    m = extract_signals("Table for 4 please.", b())
    check_eq("table-for N",           m["guests"], "4")

    m = extract_signals("It'll be 3 of us.", b())
    check_eq("it'll be N of us",      m["guests"], "3")

    m = extract_signals("We are 6 guests.", b())
    check_eq("N guests keyword",      m["guests"], "6")

    m = extract_signals("Just 2 people.", b())
    check_eq("N people keyword",      m["guests"], "2")

    # --- Name ---
    m = extract_signals("My name is Ahmed Khan.", b())
    check_eq("my name is",            m["name"], "Ahmed Khan")

    m = extract_signals("Book it under Ali Raza.", b())
    check_eq("under NAME",            m["name"], "Ali Raza")

    m = extract_signals("Reserve for Sara Ahmed please.", b())
    check_eq("for NAME",              m["name"], "Sara Ahmed")

    # --- Dietary ---
    m = extract_signals("One of us is vegetarian.", b())
    check_eq("vegetarian signal",     m["dietary_preferences"].lower(), "vegetarian")

    m = extract_signals("We need a halal menu.", b())
    check_eq("halal signal",          m["dietary_preferences"].lower(), "halal")

    # --- Special requests ---
    m = extract_signals("It's a birthday dinner.", b())
    check("birthday special request", m["special_requests"] is not None and
          "birthday" in m["special_requests"].lower())

    # --- Multi-signal utterance ---
    m = extract_signals("Table for 3 on March 15 at 8 PM for Sara Ahmed", b())
    check_eq("multi: guests",  m["guests"], "3")
    check_eq("multi: date",    m["date"].lower(), "march 15")
    check_eq("multi: time",    m["time"].lower(), "8 pm")
    check_eq("multi: name",    m["name"], "Sara Ahmed")

    # --- Memory persistence (existing value kept when no new signal) ---
    existing = b()
    existing["date"] = "March 6"
    m = extract_signals("Around 7 PM.", existing)
    check_eq("prior date preserved",  m["date"], "March 6")
    check_eq("new time added",        m["time"].lower(), "7 pm")

    # --- Memory overwrite (new signal replaces old) ---
    existing2 = b()
    existing2["time"] = "7 PM"
    m = extract_signals("Actually, make it 8 PM.", existing2)
    check_eq("time overwritten",      m["time"].lower(), "8 pm")

    # --- Noise produces no signals ---
    m = extract_signals("Sure, absolutely!", b())
    check("noise → no signals",       all(v is None for v in m.values()))


# ═════════════════════════════════════════════════════════════════════════════
# 2. Intent Detection
# ═════════════════════════════════════════════════════════════════════════════

def test_intent_detection():
    section("2 · Intent Detection")

    cases = [
        # (utterance, expected_intent)
        ("I want to book a table.",              "new_reservation"),
        ("Can I reserve for 4 people?",          "new_reservation"),
        ("Make a reservation for tomorrow.",     "new_reservation"),
        ("I'd like to make a booking.",          "new_reservation"),
        ("I want to change the time.",           "modify_reservation"),
        ("Please reschedule my reservation.",    "modify_reservation"),
        ("Update my booking to 8 PM.",           "modify_reservation"),
        ("I need to cancel my booking.",         "cancel_reservation"),
        ("Please cancel my reservation.",        "cancel_reservation"),
        ("Yes, that's correct.",                 "confirm"),
        ("Go ahead and confirm.",                "confirm"),
        ("No, that's wrong.",                    "deny"),
        ("What time do you open?",               "general_query"),
        ("Do you have parking?",                 "general_query"),
        ("What cuisine do you serve?",           "general_query"),
    ]

    for utterance, expected in cases:
        check_eq(f'intent("{utterance[:45]}")', detect_intent(utterance), expected)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Policy Guardrail
# ═════════════════════════════════════════════════════════════════════════════

def test_policy_guardrail():
    section("3 · Policy Guardrail (Off-Topic Detection)")

    off_topic = [
        "Can you book me a flight to Dubai?",
        "What's the weather like today?",
        "Tell me a joke.",
        "Write me a Python script.",
        "What's the Bitcoin price?",
    ]
    on_topic = [
        "I want to book a table.",
        "What time do you open?",
        "Do you have vegan options?",
        "I need to cancel my reservation.",
    ]

    for text in off_topic:
        check(f'off-topic: "{text[:50]}"', is_off_topic(text))

    for text in on_topic:
        check(f'on-topic:  "{text[:50]}"', not is_off_topic(text))


# ═════════════════════════════════════════════════════════════════════════════
# 4. Stage Machine
# ═════════════════════════════════════════════════════════════════════════════

def test_stage_machine():
    section("4 · Stage Machine (Turn-Taking Logic)")

    def make_session(stage: str, memory_overrides: dict = None) -> dict:
        mem = {k: None for k in SIGNAL_KEYS}
        if memory_overrides:
            mem.update(memory_overrides)
        return {"stage": stage, "memory": mem, "history": []}

    full_memory = {k: "dummy" for k in REQUIRED_FIELDS}

    # New reservation intent always moves to collecting
    s = make_session("greeting")
    check_eq("greeting + new_reservation → collecting",
             _next_stage(s, "new_reservation"), "collecting")

    # Collecting with missing fields stays collecting
    s = make_session("collecting", {"date": "March 6"})   # time, guests, name missing
    check_eq("collecting + missing fields → collecting",
             _next_stage(s, "general_query"), "collecting")

    # Collecting with all fields → confirming
    s = make_session("collecting", full_memory)
    check_eq("collecting + all fields collected → confirming",
             _next_stage(s, "general_query"), "confirming")

    # Confirming + user says yes → confirmed
    s = make_session("confirming", full_memory)
    check_eq("confirming + confirm intent → confirmed",
             _next_stage(s, "confirm"), "confirmed")

    # Confirming + user says no → back to collecting
    s = make_session("confirming", full_memory)
    check_eq("confirming + deny intent → collecting",
             _next_stage(s, "deny"), "collecting")

    # Modify intent
    s = make_session("collecting")
    check_eq("any stage + modify_reservation → modifying",
             _next_stage(s, "modify_reservation"), "modifying")

    # Cancel intent
    s = make_session("collecting")
    check_eq("any stage + cancel_reservation → cancelling",
             _next_stage(s, "cancel_reservation"), "cancelling")

    # Confirmed + new general query → general
    s = make_session("confirmed", full_memory)
    check_eq("confirmed + general_query → general",
             _next_stage(s, "general_query"), "general")


# ═════════════════════════════════════════════════════════════════════════════
# 5. Prompt Builder (structure checks)
# ═════════════════════════════════════════════════════════════════════════════

def test_prompt_builders():
    section("5 · Prompt Templates (Structure Checks)")

    mem_partial = {k: None for k in SIGNAL_KEYS}
    mem_partial.update({"date": "March 6", "time": "7 PM"})

    mem_full = {k: None for k in SIGNAL_KEYS}
    mem_full.update({"date": "March 6", "time": "7 PM",
                     "guests": "4", "name": "Ahmed Khan"})

    recent = [
        {"role": "user",      "content": "I want to book a table."},
        {"role": "assistant", "content": "Sure! For which date?"},
    ]

    # --- base system prompt ---
    p = build_system_prompt(mem_partial, recent, stage="collecting")
    check_in("system prompt: restaurant name",  RESTAURANT_INFO["name"], p)
    check_in("system prompt: hours",            RESTAURANT_INFO["hours"], p)
    check_in("system prompt: collected date",   "March 6", p)
    check_in("system prompt: collected time",   "7 PM", p)
    check_in("system prompt: missing guests",   "guests", p.lower())
    check_in("system prompt: missing name",     "name", p.lower())
    check_in("system prompt: policy present",   "Policy", p)
    check_in("system prompt: stage label",      "Stage:", p)
    check("system prompt: is a string",         isinstance(p, str))
    check("system prompt: non-empty",           len(p) > 200)

    # Confirming stage prompt
    p_confirm = build_confirmation_prompt(mem_full, recent)
    check_in("confirm prompt: reads back date",   "March 6", p_confirm)
    check_in("confirm prompt: reads back time",   "7 PM", p_confirm)
    check_in("confirm prompt: reads back guests", "4", p_confirm)
    check_in("confirm prompt: reads back name",   "Ahmed Khan", p_confirm)
    check_in("confirm prompt: asks to confirm",   "confirm", p_confirm.lower())

    # Modification prompt
    p_mod = build_modification_prompt(mem_partial, recent)
    check_in("modify prompt: asks for name",   "name", p_mod.lower())
    check_in("modify prompt: has Sofia persona", "reservation assistant", p_mod.lower())
    check_in("modify prompt: has example dialogue", "modif", p_mod.lower())

    # Cancellation prompt
    p_can = build_cancellation_prompt(mem_partial, recent)
    check_in("cancel prompt: asks for name",   "name", p_can.lower())
    check_in("cancel prompt: cancel keyword", "cancel", p_can.lower())

    # History appears in prompt
    check_in("prompt contains user history turn",
             "I want to book a table.", p)
    check_in("prompt contains assistant history turn",
             "Sure! For which date?", p)

    # Noise utterances filtered from window
    history_with_noise = [
        {"role": "user",      "content": "hello"},
        {"role": "user",      "content": "I want to book for March 6."},
        {"role": "assistant", "content": "What time?"},
        {"role": "user",      "content": "yes"},
    ]
    window = _get_window(history_with_noise)
    check("noise filtered from window",
          all(t["content"].lower() not in {"hello", "yes"} for t in window))
    check("signal turn kept in window",
          any("March 6" in t["content"] for t in window))


# ═════════════════════════════════════════════════════════════════════════════
# 6. Session Lifecycle & Integration
# ═════════════════════════════════════════════════════════════════════════════

def test_session_lifecycle():
    section("6 · Session Lifecycle & Integration")

    # Create
    sid = create_session()
    check("create_session returns string", isinstance(sid, str) and len(sid) > 0)
    check("session in store",              get_session(sid) is not None)
    check("session in list_sessions",      sid in list_sessions())

    info = session_debug_info(sid)
    check_eq("initial stage",   info["stage"],  "greeting")
    check_eq("initial intent",  info["intent"], "unknown")
    check_eq("initial turns",   info["turns"],  0)
    check("all signal keys present",
          set(info["memory"].keys()) == set(SIGNAL_KEYS))
    check("all memory values None",
          all(v is None for v in info["memory"].values()))

    # Unknown session
    check("unknown sid returns None", get_session("does-not-exist") is None)

    # Reset
    session = get_session(sid)
    session["history"].append({"role": "user", "content": "hello"})
    session["memory"]["date"] = "March 6"
    session["stage"] = "collecting"

    reset_session(sid)
    info2 = session_debug_info(sid)
    check_eq("reset: stage back to greeting", info2["stage"],  "greeting")
    check_eq("reset: turns cleared",          info2["turns"],  0)
    check("reset: memory cleared",
          all(v is None for v in info2["memory"].values()))

    # Multiple independent sessions
    sid_a = create_session()
    sid_b = create_session()
    get_session(sid_a)["memory"]["date"] = "March 6"
    check("sessions are independent",
          get_session(sid_b)["memory"]["date"] is None)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Sliding Window
# ═════════════════════════════════════════════════════════════════════════════

def test_sliding_window():
    section("7 · Sliding Window")

    # Build a history of 12 turns
    history = []
    for i in range(12):
        role = "user" if i % 2 == 0 else "assistant"
        history.append({"role": role, "content": f"message {i}"})

    window = _get_window(history, size=8)
    check_eq("window size capped at 8", len(window), 8)
    check("window contains most recent turns",
          window[-1]["content"] == "message 11")

    # Noise filtering
    noisy_history = [
        {"role": "user",      "content": "hi"},
        {"role": "user",      "content": "I want a table for March 6"},
        {"role": "assistant", "content": "What time?"},
        {"role": "user",      "content": "ok"},
        {"role": "user",      "content": "7 PM"},
    ]
    w = _get_window(noisy_history, size=8)
    content_values = [t["content"] for t in w]
    check("noise 'hi' filtered",  "hi" not in content_values)
    check("noise 'ok' filtered",  "ok" not in content_values)
    check("signal turn kept",     "I want a table for March 6" in content_values)
    check("time turn kept",       "7 PM" in content_values)


# ═════════════════════════════════════════════════════════════════════════════
# 8. E2E Multi-Turn Dialogue  (LIVE mode only)
# ═════════════════════════════════════════════════════════════════════════════

def _e2e_turn(sid: str, msg: str, expected_keywords: list[str]) -> str:
    """Send one turn, print it, and assert at least one keyword appears."""
    from conversation_manager import chat
    print(f"\n    User : {msg}")
    t0    = time.time()
    reply = chat(sid, msg)
    ms    = int((time.time() - t0) * 1000)
    print(f"    Bot  : {reply.strip()}  [{ms}ms]")

    found = any(kw.lower() in reply.lower() for kw in expected_keywords)
    check(f'response relevant: "{msg[:48]}"', found,
          f"none of {expected_keywords} found in reply")
    return reply


def test_e2e_new_reservation():
    section("8a · E2E – New Reservation (5-turn multi-turn)")

    sid = create_session()
    _e2e_turn(sid, "Hi, I want to book a table.",
              ["date", "when", "day", "time", "assist", "help", "book", "reserv"])
    _e2e_turn(sid, "Tomorrow evening.",
              ["time", "pm", "hour", "prefer"])
    _e2e_turn(sid, "Around 7 PM.",
              ["guest", "how many", "people", "party"])
    _e2e_turn(sid, "4 people.",
              ["name", "may i", "your name", "who"])
    _e2e_turn(sid, "My name is Ahmed Khan.",
              ["ahmed", "confirm", "reservation", "4"])
    _e2e_turn(sid, "Yes, please confirm it.",
              ["ahmed", "confirmed", "booked", "table", "7", "tomorrow"])

    info = session_debug_info(sid)
    print(f"\n    Final memory: {info['memory']}")
    print(f"    Final stage:  {info['stage']}")

    check_eq("name in memory",   info["memory"]["name"],             "Ahmed Khan")
    check_eq("time in memory",   info["memory"]["time"].lower(),     "7 pm")
    check_eq("guests in memory", info["memory"]["guests"],           "4")
    check("stage is confirmed",  info["stage"] == "confirmed")


def test_e2e_modification():
    section("8b · E2E – Modify Reservation (3-turn)")

    sid = create_session()
    # Turn 1: state modify intent (generic — not field-specific) → bot asks for name
    _e2e_turn(sid, "I already have a reservation and want to change it.",
              ["name", "booking", "reservation", "under", "sure", "which"])
    # Turn 2: give name → bot acknowledges reservation found, asks what to change
    _e2e_turn(sid, "The name is Ali Raza.",
              ["ali raza", "change", "date", "time", "guest", "what", "like", "update", "which"])
    # Turn 3: give field + new value in one message → deterministic "done" reply
    _e2e_turn(sid, "Change the time to 8 PM.",
              ["done", "updated", "changed", "8", "time", "ali raza", "reservation"])

    info = session_debug_info(sid)
    check("intent recorded as modify",  info["intent"] == "modify_reservation")
    check_eq("name in memory",          info["memory"]["name"], "Ali Raza")
    check("time updated in memory",
          info["memory"]["time"] is not None and "8" in info["memory"]["time"])


def test_e2e_cancellation():
    section("8c · E2E – Cancel Reservation (2-turn)")

    sid = create_session()
    _e2e_turn(sid, "I need to cancel my reservation.",
              ["name", "booking", "cancel", "which"])
    _e2e_turn(sid, "My name is Sara Ahmed, booked for March 10 at 7 PM.",
              ["cancel", "confirm", "sara", "march", "7 pm"])

    info = session_debug_info(sid)
    check("intent is cancel", info["intent"] == "cancel_reservation")


def test_e2e_general_query():
    section("8d · E2E – General Queries")

    sid = create_session()
    _e2e_turn(sid, "What time do you open?",
              ["12", "pm", "open", "noon", "daily"])
    _e2e_turn(sid, "Do I need a reservation for lunch?",
              ["lunch", "weekend", "recommend", "required"])
    _e2e_turn(sid, "What cuisine do you serve?",
              ["italian", "mediterranean", "cuisine"])


def test_e2e_off_topic():
    section("8e · E2E – Off-Topic Rejection (hard guardrail)")

    sid = create_session()
    from conversation_manager import chat
    reply = chat(sid, "Can you book me a flight to Dubai?")
    print(f"\n    User : Can you book me a flight to Dubai?")
    print(f"    Bot  : {reply.strip()}")

    check("off-topic gets canned reply (not sent to LLM)",
          any(w in reply.lower() for w in
              ["only assist", "restaurant", "reservation", "la bella"]))

    # Session history should record the exchange but stage unchanged
    info = session_debug_info(sid)
    check("session still in greeting stage after off-topic",
          info["stage"] == "greeting")


def test_e2e_context_fidelity():
    section("8f · E2E – Multi-Turn Context Fidelity")
    """
    Verifies the model remembers information stated several turns ago.
    We give a name early, then later ask it to confirm — the name must appear.
    """
    sid = create_session()

    from conversation_manager import chat
    chat(sid, "I'd like to make a reservation.")
    chat(sid, "March 20.")
    chat(sid, "8 PM.")
    chat(sid, "2 guests.")
    reply = chat(sid, "My name is Bilal Ahmed.")

    # Now explicitly ask it to recap
    recap = chat(sid, "Can you confirm what you have so far?")
    print(f"\n    Recap: {recap.strip()}")

    check("model recalls name across turns",
          "bilal" in recap.lower() or "ahmed" in recap.lower()
          or session_debug_info(sid)["memory"].get("name") == "Bilal Ahmed")
    check("model recalls date across turns",
          "march 20" in recap.lower() or "20" in recap)
    check("model recalls time across turns",
          "8 pm" in recap.lower() or "8:00" in recap.lower())


# ═════════════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════════════

def _print_summary():
    total  = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed

    # Group by section
    sections: dict[str, list[tuple[str, bool]]] = {}
    for label, ok, sec in _results:
        sections.setdefault(sec, []).append((label, ok))

    print(f"\n{'═' * 64}")
    print("  SUMMARY BY SECTION")
    print(f"{'═' * 64}")
    for sec, items in sections.items():
        sec_pass = sum(1 for _, ok in items if ok)
        marker   = GREEN + "✓" + RESET if sec_pass == len(items) else RED + "✗" + RESET
        print(f"  {marker}  {sec}  ({sec_pass}/{len(items)})")

    print(f"{'─' * 64}")
    overall = GREEN + "ALL PASSED" + RESET if failed == 0 else RED + f"{failed} FAILED" + RESET
    print(f"  Total: {passed}/{total}  —  {overall}")
    print(f"{'═' * 64}\n")
    return failed


def main():
    print("\n" + "═" * 64)
    print("  Phase III · Restaurant Reservation AI — Test Suite")
    mode = f"{YELLOW}LIVE (Ollama){RESET}" if LIVE else f"{YELLOW}MOCK (no Ollama){RESET}"
    print(f"  Mode: {mode}")
    print("═" * 64)

    # ── Unit / Integration (always run) ──────────────────────────────────────
    test_signal_extraction()
    test_intent_detection()
    test_policy_guardrail()
    test_stage_machine()
    test_prompt_builders()
    test_session_lifecycle()
    test_sliding_window()

    # ── E2E (only when Ollama is running) ────────────────────────────────────
    if LIVE:
        print(f"\n{YELLOW}  ── E2E Tests (live Ollama) ──{RESET}")
        test_e2e_new_reservation()
        test_e2e_modification()
        test_e2e_cancellation()
        test_e2e_general_query()
        test_e2e_off_topic()
        test_e2e_context_fidelity()
    else:
        print(f"\n  {YELLOW}ℹ  Skipping E2E tests — run with  LIVE=1 python test_dialogue.py{RESET}")

    failed = _print_summary()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()