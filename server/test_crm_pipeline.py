"""
CRM Safety Checks — Deterministic Test Suite
Validates minimal rule-based safety checks without a live LLM.
"""

from conversation_manager import _rule_based_safety_check

def test_rule_based_safety():
    print("\n=== Rule-Based Safety Tests ===")
    results = []

    ok, err = _rule_based_safety_check(
        "Try our grilled chicken and steak.",
        {"dietary_preferences": "vegetarian"},
    )
    _log("SAFE-01", "Vegetarian violation detected", not ok, err or "")
    results.append(not ok)

    ok, err = _rule_based_safety_check(
        "Our pasta and salad options are great.",
        {"dietary_preferences": "vegetarian"},
    )
    _log("SAFE-02", "Vegetarian allowed response", ok, err or "")
    results.append(ok)

    ok, err = _rule_based_safety_check(
        "We recommend pork belly tonight.",
        {"dietary_preferences": "halal"},
    )
    _log("SAFE-03", "Halal violation detected", not ok, err or "")
    results.append(not ok)

    ok, err = _rule_based_safety_check(
        "We have seafood and vegetarian options.",
        {"dietary_preferences": "halal"},
    )
    _log("SAFE-04", "Halal allowed response", ok, err or "")
    results.append(ok)

    ok, err = _rule_based_safety_check(
        "Any questions about the restaurant?",
        {},
    )
    _log("SAFE-05", "No CRM data passes", ok, err or "")
    results.append(ok)

    return results


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def _log(tid: str, label: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    detail_str = f" | {detail}" if detail and not passed else ""
    print(f"  [{status}] {tid}: {label}{detail_str}")


def run_all():
    all_results = []
    all_results += test_rule_based_safety()

    total  = len(all_results)
    passed = sum(all_results)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed ({100*passed//total}%)")
    print(f"{'='*50}")
    return passed == total


if __name__ == "__main__":
    success = run_all()
    raise SystemExit(0 if success else 1)
