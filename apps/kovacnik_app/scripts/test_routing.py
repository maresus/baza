#!/usr/bin/env python3
"""
Test Scenarios for Unified Routing System.

30 scenarios to validate routing behavior before deployment.
Run: python scripts/test_routing.py
"""

import sys
import os

# Add the shared_core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared_core"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared_core.app.services.routing import (
    IntentType,
    SwitchAction,
    route,
    compute_confidence,
    is_affirmative_response,
    is_negative_response,
)
from shared_core.app.services.session import (
    blank_unified_state,
    FlowType,
    FlowStep,
)


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_result(passed: bool, scenario: str, details: str = ""):
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    print(f"{status} | {scenario}")
    if details and not passed:
        print(f"       {Colors.YELLOW}→ {details}{Colors.RESET}")


def test_scenario(
    name: str,
    message: str,
    state: dict,
    expected_intent: IntentType,
    expected_action: SwitchAction = None,
    expected_confidence_min: float = None,
) -> bool:
    """Run a single test scenario."""
    decision = route(message, state)

    passed = True
    details = []

    # Check intent
    if decision.primary_intent != expected_intent:
        passed = False
        details.append(f"intent: got {decision.primary_intent.value}, expected {expected_intent.value}")

    # Check action if specified
    if expected_action and decision.action != expected_action:
        passed = False
        details.append(f"action: got {decision.action.value}, expected {expected_action.value}")

    # Check confidence if specified
    if expected_confidence_min and decision.confidence < expected_confidence_min:
        passed = False
        details.append(f"confidence: got {decision.confidence:.2f}, expected >= {expected_confidence_min}")

    print_result(passed, name, "; ".join(details))
    return passed


def run_all_tests():
    """Run all 30 test scenarios."""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}UNIFIED ROUTING TEST SUITE - 30 Scenarios{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    passed = 0
    failed = 0

    # === SECTION 1: GREETING & GOODBYE ===
    print(f"{Colors.BLUE}[Section 1] Greetings & Goodbyes{Colors.RESET}")

    # 1. Basic greeting
    if test_scenario(
        "1. Basic greeting 'živjo'",
        "živjo",
        blank_unified_state(),
        IntentType.GREETING,
        SwitchAction.HARD_SWITCH,
        1.0,
    ):
        passed += 1
    else:
        failed += 1

    # 2. English greeting
    if test_scenario(
        "2. English greeting 'hello'",
        "hello",
        blank_unified_state(),
        IntentType.GREETING,
        SwitchAction.HARD_SWITCH,
    ):
        passed += 1
    else:
        failed += 1

    # 3. Goodbye
    if test_scenario(
        "3. Goodbye 'hvala, adijo'",
        "hvala, adijo",
        blank_unified_state(),
        IntentType.GOODBYE,
        SwitchAction.HARD_SWITCH,
    ):
        passed += 1
    else:
        failed += 1

    # === SECTION 2: BOOKING INTENTS ===
    print(f"\n{Colors.BLUE}[Section 2] Booking Intents{Colors.RESET}")

    # 4. Table reservation explicit
    if test_scenario(
        "4. Explicit table reservation",
        "rad bi rezerviral mizo",
        blank_unified_state(),
        IntentType.BOOKING_TABLE,
        SwitchAction.HARD_SWITCH,
        1.0,
    ):
        passed += 1
    else:
        failed += 1

    # 5. Room reservation explicit
    if test_scenario(
        "5. Explicit room reservation",
        "želim rezervirati sobo",
        blank_unified_state(),
        IntentType.BOOKING_ROOM,
        SwitchAction.HARD_SWITCH,
        1.0,
    ):
        passed += 1
    else:
        failed += 1

    # 6. Table with soft keywords
    if test_scenario(
        "6. Table with soft keywords",
        "bi se dalo rezervirati mizo za soboto?",
        blank_unified_state(),
        IntentType.BOOKING_TABLE,
        None,  # Could be HARD_SWITCH or SOFT_INTERRUPT depending on confidence
        0.5,
    ):
        passed += 1
    else:
        failed += 1

    # 7. Room inquiry
    if test_scenario(
        "7. Room availability question",
        "ali imate prosto sobo za vikend?",
        blank_unified_state(),
        IntentType.BOOKING_ROOM,
        None,
        0.5,
    ):
        passed += 1
    else:
        failed += 1

    # === SECTION 3: INFO INTENTS ===
    print(f"\n{Colors.BLUE}[Section 3] Info Intents{Colors.RESET}")

    # 8. Location question
    if test_scenario(
        "8. Location question",
        "kje se nahajate?",
        blank_unified_state(),
        IntentType.INFO,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # 9. Opening hours
    if test_scenario(
        "9. Opening hours",
        "kdaj ste odprti?",
        blank_unified_state(),
        IntentType.INFO,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # 10. Contact info
    if test_scenario(
        "10. Contact request",
        "kakšen je vaš telefon?",
        blank_unified_state(),
        IntentType.INFO,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # === SECTION 4: PRODUCT INTENTS ===
    print(f"\n{Colors.BLUE}[Section 4] Product Intents{Colors.RESET}")

    # 11. Pesto question
    if test_scenario(
        "11. Pesto availability",
        "a imate pesto?",
        blank_unified_state(),
        IntentType.PRODUCT,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # 12. Marmalade order
    if test_scenario(
        "12. Marmalade order",
        "rad bi naročil marmelado",
        blank_unified_state(),
        IntentType.PRODUCT,
        None,
        0.5,
    ):
        passed += 1
    else:
        failed += 1

    # 13. Product catalog
    if test_scenario(
        "13. Product catalog",
        "kaj imate v prodaji?",
        blank_unified_state(),
        IntentType.PRODUCT,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # === SECTION 5: MENU INTENTS ===
    print(f"\n{Colors.BLUE}[Section 5] Menu Intents{Colors.RESET}")

    # 14. Menu request
    if test_scenario(
        "14. Menu request",
        "kakšen je jedilnik?",
        blank_unified_state(),
        IntentType.MENU,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # 15. Seasonal menu
    if test_scenario(
        "15. Seasonal menu",
        "kaj je na zimskem meniju?",
        blank_unified_state(),
        IntentType.MENU,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # === SECTION 6: WINE INTENTS ===
    print(f"\n{Colors.BLUE}[Section 6] Wine Intents{Colors.RESET}")

    # 16. Wine list
    if test_scenario(
        "16. Wine list",
        "kakšna vina imate?",
        blank_unified_state(),
        IntentType.WINE,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # 17. Red wine
    if test_scenario(
        "17. Red wine",
        "imate kakšno rdečo?",
        blank_unified_state(),
        IntentType.WINE,
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # === SECTION 7: AFFIRMATIVE/NEGATIVE ===
    print(f"\n{Colors.BLUE}[Section 7] Affirmative/Negative Responses{Colors.RESET}")

    # 18. Simple yes
    if test_scenario(
        "18. Simple 'da'",
        "da",
        blank_unified_state(),
        IntentType.AFFIRMATIVE,
        SwitchAction.IGNORE,
        1.0,
    ):
        passed += 1
    else:
        failed += 1

    # 19. Simple no
    if test_scenario(
        "19. Simple 'ne'",
        "ne",
        blank_unified_state(),
        IntentType.NEGATIVE,
        None,
        1.0,
    ):
        passed += 1
    else:
        failed += 1

    # 20. Okay
    if test_scenario(
        "20. 'ok, super'",
        "ok, super",
        blank_unified_state(),
        IntentType.AFFIRMATIVE,
        SwitchAction.IGNORE,
    ):
        passed += 1
    else:
        failed += 1

    # === SECTION 8: IN-FLOW INTERRUPTS ===
    print(f"\n{Colors.BLUE}[Section 8] In-Flow Interrupt Handling{Colors.RESET}")

    # State: in table reservation flow
    booking_state = blank_unified_state()
    booking_state["flow"] = FlowType.RESERVATION_TABLE.value
    booking_state["step"] = FlowStep.DATE.value

    # 21. Product question during booking (soft interrupt)
    if test_scenario(
        "21. Product during booking → SOFT_INTERRUPT",
        "a imate pesto?",
        booking_state.copy(),
        IntentType.PRODUCT,
        SwitchAction.SOFT_INTERRUPT,
    ):
        passed += 1
    else:
        failed += 1

    # 22. Info question during booking (soft interrupt)
    if test_scenario(
        "22. Info during booking → SOFT_INTERRUPT",
        "kje se nahajate?",
        booking_state.copy(),
        IntentType.INFO,
        SwitchAction.SOFT_INTERRUPT,
    ):
        passed += 1
    else:
        failed += 1

    # 23. New booking during booking (hard switch)
    if test_scenario(
        "23. New room booking during table booking → HARD_SWITCH",
        "pravzaprav rad bi rezerviral sobo",
        booking_state.copy(),
        IntentType.BOOKING_ROOM,
        SwitchAction.HARD_SWITCH,
    ):
        passed += 1
    else:
        failed += 1

    # 24. Affirmative during booking (continue flow)
    if test_scenario(
        "24. Affirmative during booking → IGNORE (continue)",
        "da, za soboto",
        booking_state.copy(),
        IntentType.AFFIRMATIVE,
        SwitchAction.IGNORE,
    ):
        passed += 1
    else:
        failed += 1

    # === SECTION 9: MIXED INTENTS ===
    print(f"\n{Colors.BLUE}[Section 9] Mixed Intents{Colors.RESET}")

    # 25. Table + product
    decision = route("rad bi rezerviral mizo, a imate tudi pesto?", blank_unified_state())
    if decision.primary_intent == IntentType.BOOKING_TABLE and decision.secondary_intent == IntentType.PRODUCT:
        passed += 1
        print_result(True, "25. Mixed: table + product → secondary=PRODUCT")
    else:
        failed += 1
        print_result(False, "25. Mixed: table + product → secondary=PRODUCT",
                    f"got primary={decision.primary_intent.value}, secondary={decision.secondary_intent}")

    # 26. Product + booking mention
    decision = route("imate marmelado? pa bi tudi mizo rezerviral", blank_unified_state())
    # Primary should be product (first mentioned) or booking
    if decision.primary_intent in [IntentType.PRODUCT, IntentType.BOOKING_TABLE]:
        passed += 1
        print_result(True, "26. Product + booking mention")
    else:
        failed += 1
        print_result(False, "26. Product + booking mention", f"got {decision.primary_intent.value}")

    # === SECTION 10: EDGE CASES ===
    print(f"\n{Colors.BLUE}[Section 10] Edge Cases{Colors.RESET}")

    # 27. Very short message
    decision = route("hm", blank_unified_state())
    if decision.action in [SwitchAction.IGNORE, SwitchAction.SOFT_INTERRUPT]:
        passed += 1
        print_result(True, "27. Short 'hm' → low confidence")
    else:
        failed += 1
        print_result(False, "27. Short 'hm' → low confidence", f"action={decision.action.value}")

    # 28. Typo in reservation
    if test_scenario(
        "28. Typo 'rezerviral' → still booking",
        "bi rezerriral mizo",
        blank_unified_state(),
        IntentType.BOOKING_TABLE,  # Should still detect
        None,
        0.4,
    ):
        passed += 1
    else:
        failed += 1

    # 29. English booking request
    if test_scenario(
        "29. English 'book a table'",
        "I would like to book a table",
        blank_unified_state(),
        IntentType.BOOKING_TABLE,
        SwitchAction.HARD_SWITCH,
    ):
        passed += 1
    else:
        failed += 1

    # 30. Inquiry state with different question
    inquiry_state = blank_unified_state()
    inquiry_state["flow"] = FlowType.INQUIRY.value
    inquiry_state["step"] = FlowStep.DETAILS.value

    if test_scenario(
        "30. Table booking during inquiry → HARD_SWITCH",
        "rad bi rezerviral mizo za nedeljo",
        inquiry_state,
        IntentType.BOOKING_TABLE,
        SwitchAction.HARD_SWITCH,
    ):
        passed += 1
    else:
        failed += 1

    # === SUMMARY ===
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    total = passed + failed
    percentage = (passed / total * 100) if total > 0 else 0

    if failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}ALL TESTS PASSED: {passed}/{total} (100%){Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}RESULTS: {passed}/{total} passed ({percentage:.1f}%){Colors.RESET}")
        print(f"{Colors.RED}FAILED: {failed} scenarios{Colors.RESET}")

    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
