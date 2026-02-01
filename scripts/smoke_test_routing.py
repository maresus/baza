#!/usr/bin/env python3
"""
Smoke Test - 40 scenarijev za Zdravstveni Center Unified Routing System.
Lokalni test brez web serverja.

Run: python scripts/smoke_test_routing.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.routing.confidence import detect_intents, pick_primary_secondary, detect_service_type
from app.services.routing.unified_router import route, IntentType
from app.services.routing.confidence import SwitchAction
from app.services.session.unified_state import blank_unified_state, FlowType


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def test(
    name: str,
    message: str,
    state: dict = None,
    expected_intent: str = None,
    expected_action: str = None,
    min_confidence: float = None,
    expected_service: str = None,
) -> bool:
    """Run a single test case."""
    if state is None:
        state = blank_unified_state()

    decision = route(message, state)

    passed = True
    errors = []

    if expected_intent and decision.primary_intent.value != expected_intent:
        passed = False
        errors.append(f"intent: got {decision.primary_intent.value}, expected {expected_intent}")

    if expected_action and decision.action.value != expected_action:
        passed = False
        errors.append(f"action: got {decision.action.value}, expected {expected_action}")

    if min_confidence and decision.confidence < min_confidence:
        passed = False
        errors.append(f"confidence: got {decision.confidence:.2f}, expected >= {min_confidence}")

    if expected_service and decision.service_type != expected_service:
        passed = False
        errors.append(f"service: got {decision.service_type}, expected {expected_service}")

    status = f"{Colors.GREEN}✓{Colors.RESET}" if passed else f"{Colors.RED}✗{Colors.RESET}"
    print(f"  {status} {name}")
    if errors:
        for e in errors:
            print(f"      {Colors.YELLOW}→ {e}{Colors.RESET}")

    return passed


def in_appointment_flow() -> dict:
    """Create state in appointment booking flow."""
    state = blank_unified_state()
    state["flow"] = FlowType.APPOINTMENT.value
    state["step"] = "date"
    return state


def run_all():
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}ZDRAVSTVENI CENTER - SMOKE TEST ROUTING (40 SCENARIJEV){Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

    passed = 0
    failed = 0

    # ========== SECTION 1: POZDRAVI ==========
    print(f"{Colors.CYAN}[1-4] POZDRAVI IN SLOVO{Colors.RESET}")

    if test("1. živjo", "živjo", expected_intent="GREETING", min_confidence=1.0): passed += 1
    else: failed += 1

    if test("2. dober dan", "dober dan", expected_intent="GREETING"): passed += 1
    else: failed += 1

    if test("3. pozdravljeni", "pozdravljeni", expected_intent="GREETING"): passed += 1
    else: failed += 1

    if test("4. hvala, adijo", "hvala, adijo", expected_intent="GOODBYE"): passed += 1
    else: failed += 1

    # ========== SECTION 2: NAROČANJE TERMINOV ==========
    print(f"\n{Colors.CYAN}[5-12] NAROČANJE TERMINOV{Colors.RESET}")

    if test("5. rad bi naročil termin", "rad bi naročil termin",
            expected_intent="BOOKING_APPOINTMENT", min_confidence=0.6): passed += 1
    else: failed += 1

    if test("6. naročil bi se na pregled pri dermatologu", "naročil bi se na pregled pri dermatologu",
            expected_intent="BOOKING_APPOINTMENT", expected_service="DERMATOLOG"): passed += 1
    else: failed += 1

    if test("7. termin za ortopeda", "termin za ortopeda",
            expected_intent="BOOKING_APPOINTMENT", expected_service="ORTOPED"): passed += 1
    else: failed += 1

    if test("8. bi se naročil na pregled oči", "bi se naročil na pregled oči",
            expected_intent="BOOKING_APPOINTMENT", expected_service="OKULIST"): passed += 1
    else: failed += 1

    if test("9. naročilo na fizioterapijo", "naročilo na fizioterapijo",
            expected_intent="BOOKING_APPOINTMENT", expected_service="FIZIOTERAPIJA"): passed += 1
    else: failed += 1

    if test("10. želim rezervirati termin za botox", "želim rezervirati termin za botox",
            expected_intent="BOOKING_APPOINTMENT", expected_service="ESTETSKI_POSEG"): passed += 1
    else: failed += 1

    if test("11. lasersko odstranjevanje žilic", "naročilo za lasersko odstranjevanje žilic",
            expected_intent="BOOKING_APPOINTMENT", expected_service="LASERSKI_POSEG"): passed += 1
    else: failed += 1

    if test("12. termin za kozmetični tretma", "termin za kozmetični tretma",
            expected_intent="BOOKING_APPOINTMENT", expected_service="KOZMETIKA"): passed += 1
    else: failed += 1

    # ========== SECTION 3: INFO O STORITVAH ==========
    print(f"\n{Colors.CYAN}[13-18] INFO O STORITVAH{Colors.RESET}")

    if test("13. kaj zdravi dermatolog?", "kaj zdravi dermatolog?",
            expected_intent="SERVICE_INFO", expected_service="DERMATOLOG"): passed += 1
    else: failed += 1

    if test("14. katere bolezni zdravite?", "katere bolezni zdravite?",
            expected_intent="SERVICE_INFO"): passed += 1
    else: failed += 1

    if test("15. kakšne ortopedske preglede delate?", "kakšne ortopedske preglede delate?",
            expected_intent="SERVICE_INFO", expected_service="ORTOPED"): passed += 1
    else: failed += 1

    if test("16. a zdravite akne?", "a zdravite akne?",
            expected_intent="SERVICE_INFO", expected_service="DERMATOLOG"): passed += 1
    else: failed += 1

    if test("17. kaj pomaga za bolečine v hrbtu?", "kaj pomaga za bolečine v hrbtu?",
            expected_intent="SERVICE_INFO", expected_service="ORTOPED"): passed += 1
    else: failed += 1

    if test("18. a delate botox?", "a delate botox?",
            expected_intent="SERVICE_INFO", expected_service="ESTETSKI_POSEG"): passed += 1
    else: failed += 1

    # ========== SECTION 4: CENE ==========
    print(f"\n{Colors.CYAN}[19-22] CENE IN PLAČILO{Colors.RESET}")

    if test("19. koliko stane pregled?", "koliko stane pregled?",
            expected_intent="PRICE", min_confidence=0.9): passed += 1
    else: failed += 1

    if test("20. cenik storitev", "cenik storitev",
            expected_intent="PRICE"): passed += 1
    else: failed += 1

    if test("21. a sprejemate zavarovanje?", "a sprejemate zavarovanje?",
            expected_intent="PRICE"): passed += 1
    else: failed += 1

    if test("22. koliko stane botox?", "koliko stane botox?",
            expected_intent="PRICE"): passed += 1
    else: failed += 1

    # ========== SECTION 5: SPLOŠNE INFO ==========
    print(f"\n{Colors.CYAN}[23-28] SPLOŠNE INFORMACIJE{Colors.RESET}")

    if test("23. kdaj ste odprti?", "kdaj ste odprti?",
            expected_intent="INFO", min_confidence=0.8): passed += 1
    else: failed += 1

    if test("24. kje se nahajate?", "kje se nahajate?",
            expected_intent="INFO"): passed += 1
    else: failed += 1

    if test("25. imate parking?", "imate parking?",
            expected_intent="INFO"): passed += 1
    else: failed += 1

    if test("26. telefonska številka", "telefonska številka",
            expected_intent="INFO"): passed += 1
    else: failed += 1

    if test("27. email naslov", "email naslov",
            expected_intent="INFO"): passed += 1
    else: failed += 1

    if test("28. delovni čas", "delovni čas",
            expected_intent="INFO"): passed += 1
    else: failed += 1

    # ========== SECTION 6: DA/NE ODGOVORI ==========
    print(f"\n{Colors.CYAN}[29-32] DA/NE ODGOVORI{Colors.RESET}")

    if test("29. da", "da", expected_intent="AFFIRMATIVE", expected_action="ignore"): passed += 1
    else: failed += 1

    if test("30. ok", "ok", expected_intent="AFFIRMATIVE"): passed += 1
    else: failed += 1

    if test("31. ne", "ne", expected_intent="NEGATIVE"): passed += 1
    else: failed += 1

    if test("32. ne hvala", "ne hvala", expected_intent="NEGATIVE"): passed += 1
    else: failed += 1

    # ========== SECTION 7: NUJNOST ==========
    print(f"\n{Colors.CYAN}[33-34] NUJNI PRIMERI{Colors.RESET}")

    if test("33. nujno rabim termin", "nujno rabim termin",
            expected_intent="URGENCY", min_confidence=0.9): passed += 1
    else: failed += 1

    if test("34. zelo boli, rabim danes", "zelo boli, rabim danes",
            expected_intent="URGENCY"): passed += 1
    else: failed += 1

    # ========== SECTION 8: SOFT INTERRUPTS MED FLOWOM ==========
    print(f"\n{Colors.CYAN}[35-38] SOFT INTERRUPTS MED NAROČANJEM{Colors.RESET}")

    if test("35. cena med naročanjem", "koliko stane pregled?",
            state=in_appointment_flow(), expected_intent="PRICE", expected_action="soft_interrupt"): passed += 1
    else: failed += 1

    if test("36. info med naročanjem", "a imate parking?",
            state=in_appointment_flow(), expected_intent="INFO", expected_action="soft_interrupt"): passed += 1
    else: failed += 1

    if test("37. storitev info med naročanjem", "kaj zdravi dermatolog?",
            state=in_appointment_flow(), expected_intent="SERVICE_INFO", expected_action="soft_interrupt"): passed += 1
    else: failed += 1

    if test("38. delovni čas med naročanjem", "kdaj ste odprti?",
            state=in_appointment_flow(), expected_intent="INFO", expected_action="soft_interrupt"): passed += 1
    else: failed += 1

    # ========== SECTION 9: EDGE CASES ==========
    print(f"\n{Colors.CYAN}[39-40] EDGE CASES{Colors.RESET}")

    if test("39. kratko 'hm'", "hm", expected_intent="GENERAL"): passed += 1
    else: failed += 1

    if test("40. prazen string", "", expected_intent="GENERAL"): passed += 1
    else: failed += 1

    # ========== SUMMARY ==========
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    total = passed + failed
    pct = (passed / total * 100) if total > 0 else 0

    if failed == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}VSI TESTI USPELI: {passed}/{total} (100%){Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}REZULTAT: {passed}/{total} ({pct:.1f}%){Colors.RESET}")
        print(f"{Colors.RED}NEUSPELI: {failed} scenarijev{Colors.RESET}")

    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
