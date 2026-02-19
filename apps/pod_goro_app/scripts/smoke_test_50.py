#!/usr/bin/env python3
"""
Smoke Test - 50 scenarijev za Unified Routing System.
Lokalni test brez web serverja.

Run: USE_UNIFIED_ROUTER=true python scripts/smoke_test_50.py
"""

import sys
import os

# Set env before imports
os.environ["USE_UNIFIED_ROUTER"] = "true"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared_core"))

from shared_core.app.services.routing.confidence import detect_intents, pick_primary_secondary
from shared_core.app.services.routing.unified_router import route, IntentType, Decision
from shared_core.app.services.routing.confidence import SwitchAction
from shared_core.app.services.session.unified_state import blank_unified_state, FlowType


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

    status = f"{Colors.GREEN}✓{Colors.RESET}" if passed else f"{Colors.RED}✗{Colors.RESET}"
    print(f"  {status} {name}")
    if errors:
        for e in errors:
            print(f"      {Colors.YELLOW}→ {e}{Colors.RESET}")

    return passed


def in_table_flow() -> dict:
    """Create state in table reservation flow."""
    state = blank_unified_state()
    state["flow"] = FlowType.RESERVATION_TABLE.value
    state["step"] = "date"
    return state


def in_room_flow() -> dict:
    """Create state in room reservation flow."""
    state = blank_unified_state()
    state["flow"] = FlowType.RESERVATION_ROOM.value
    state["step"] = "date"
    return state


def in_inquiry_flow() -> dict:
    """Create state in inquiry flow."""
    state = blank_unified_state()
    state["flow"] = FlowType.INQUIRY.value
    state["step"] = "details"
    return state


def run_all():
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}SMOKE TEST - 50 SCENARIJEV{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

    passed = 0
    failed = 0

    # ========== SECTION 1: POZDRAVI ==========
    print(f"{Colors.CYAN}[1-5] POZDRAVI IN SLOVO{Colors.RESET}")

    if test("1. živjo", "živjo", expected_intent="GREETING", min_confidence=1.0): passed += 1
    else: failed += 1

    if test("2. dober dan", "dober dan", expected_intent="GREETING"): passed += 1
    else: failed += 1

    if test("3. hello", "hello", expected_intent="GREETING"): passed += 1
    else: failed += 1

    if test("4. hvala, adijo", "hvala, adijo", expected_intent="GOODBYE"): passed += 1
    else: failed += 1

    if test("5. lep pozdrav", "lep pozdrav", expected_intent="GOODBYE"): passed += 1
    else: failed += 1

    # ========== SECTION 2: REZERVACIJA MIZE ==========
    print(f"\n{Colors.CYAN}[6-12] REZERVACIJA MIZE{Colors.RESET}")

    if test("6. rad bi rezerviral mizo", "rad bi rezerviral mizo", expected_intent="BOOKING_TABLE", min_confidence=0.6): passed += 1
    else: failed += 1

    if test("7. rezervacija mize za soboto", "rezervacija mize za soboto", expected_intent="BOOKING_TABLE"): passed += 1
    else: failed += 1

    if test("8. bi se dalo rezervirat mizo?", "bi se dalo rezervirat mizo?", expected_intent="BOOKING_TABLE"): passed += 1
    else: failed += 1

    if test("9. mizo za 4 osebe", "mizo za 4 osebe", expected_intent="BOOKING_TABLE"): passed += 1
    else: failed += 1

    if test("10. book a table", "book a table", expected_intent="BOOKING_TABLE"): passed += 1
    else: failed += 1

    if test("11. lahko rezerviram mizo", "ali lahko rezerviram mizo?", expected_intent="BOOKING_TABLE"): passed += 1
    else: failed += 1

    if test("12. želim mizo za nedeljo", "želim mizo za nedeljo", expected_intent="BOOKING_TABLE"): passed += 1
    else: failed += 1

    # ========== SECTION 3: REZERVACIJA SOBE ==========
    print(f"\n{Colors.CYAN}[13-18] REZERVACIJA SOBE{Colors.RESET}")

    if test("13. rad bi rezerviral sobo", "rad bi rezerviral sobo", expected_intent="BOOKING_ROOM"): passed += 1
    else: failed += 1

    if test("14. nočitev za 2 osebi", "nočitev za 2 osebi", expected_intent="BOOKING_ROOM"): passed += 1
    else: failed += 1

    if test("15. imate prosto sobo?", "imate prosto sobo?", expected_intent="BOOKING_ROOM"): passed += 1
    else: failed += 1

    if test("16. book a room", "book a room", expected_intent="BOOKING_ROOM"): passed += 1
    else: failed += 1

    if test("17. prenočitev vikend", "prenočitev vikend", expected_intent="BOOKING_ROOM"): passed += 1
    else: failed += 1

    if test("18. sobe za družino", "sobe za družino", expected_intent="BOOKING_ROOM"): passed += 1
    else: failed += 1

    # ========== SECTION 4: VINO ==========
    print(f"\n{Colors.CYAN}[19-25] VINO{Colors.RESET}")

    if test("19. kakšna vina imate?", "kakšna vina imate?", expected_intent="WINE", min_confidence=0.9): passed += 1
    else: failed += 1

    if test("20. rdeča vina", "rdeča vina", expected_intent="WINE"): passed += 1
    else: failed += 1

    if test("21. imate kakšno rdečo?", "imate kakšno rdečo?", expected_intent="WINE"): passed += 1
    else: failed += 1

    if test("22. bela vina", "bela vina", expected_intent="WINE"): passed += 1
    else: failed += 1

    if test("23. peneča vina", "peneča vina", expected_intent="WINE"): passed += 1
    else: failed += 1

    if test("24. imate pinot?", "imate pinot?", expected_intent="WINE"): passed += 1
    else: failed += 1

    if test("25. vinska karta", "vinska karta", expected_intent="WINE"): passed += 1
    else: failed += 1

    # ========== SECTION 5: MENI ==========
    print(f"\n{Colors.CYAN}[26-30] MENI/JEDILNIK{Colors.RESET}")

    if test("26. jedilnik prosim", "jedilnik prosim", expected_intent="MENU", min_confidence=0.9): passed += 1
    else: failed += 1

    if test("27. kaj ponujate?", "kaj ponujate?", expected_intent="MENU"): passed += 1
    else: failed += 1

    if test("28. dnevni meni", "dnevni meni", expected_intent="MENU"): passed += 1
    else: failed += 1

    if test("29. sezonski meni", "sezonski meni", expected_intent="MENU"): passed += 1
    else: failed += 1

    if test("30. kaj imate za jest", "kaj imate za jest", expected_intent="MENU"): passed += 1
    else: failed += 1

    # ========== SECTION 6: PRODUKTI ==========
    print(f"\n{Colors.CYAN}[31-35] PRODUKTI{Colors.RESET}")

    if test("31. a imate pesto?", "a imate pesto?", expected_intent="PRODUCT", min_confidence=0.8): passed += 1
    else: failed += 1

    if test("32. marmelada cena", "marmelada cena", expected_intent="PRODUCT"): passed += 1
    else: failed += 1

    if test("33. katalog izdelkov", "katalog izdelkov", expected_intent="PRODUCT"): passed += 1
    else: failed += 1

    if test("34. kje lahko kupim sirup", "kje lahko kupim sirup", expected_intent="PRODUCT"): passed += 1
    else: failed += 1

    if test("35. imate liker?", "imate liker?", expected_intent="PRODUCT"): passed += 1
    else: failed += 1

    # ========== SECTION 7: INFO ==========
    print(f"\n{Colors.CYAN}[36-40] INFO VPRAŠANJA{Colors.RESET}")

    if test("36. kje se nahajate?", "kje se nahajate?", expected_intent="INFO", min_confidence=0.8): passed += 1
    else: failed += 1

    if test("37. imate parking?", "imate parking?", expected_intent="INFO"): passed += 1
    else: failed += 1

    if test("38. kdaj ste odprti?", "kdaj ste odprti?", expected_intent="INFO"): passed += 1
    else: failed += 1

    if test("39. telefonska številka", "telefonska številka", expected_intent="INFO"): passed += 1
    else: failed += 1

    if test("40. kdaj je zajtrk?", "kdaj je zajtrk?", expected_intent="INFO"): passed += 1
    else: failed += 1

    # ========== SECTION 8: AFFIRMATIVE/NEGATIVE ==========
    print(f"\n{Colors.CYAN}[41-44] DA/NE ODGOVORI{Colors.RESET}")

    if test("41. da", "da", expected_intent="AFFIRMATIVE", expected_action="ignore"): passed += 1
    else: failed += 1

    if test("42. ok", "ok", expected_intent="AFFIRMATIVE"): passed += 1
    else: failed += 1

    if test("43. ne", "ne", expected_intent="NEGATIVE"): passed += 1
    else: failed += 1

    if test("44. pustimo", "pustimo", expected_intent="NEGATIVE"): passed += 1
    else: failed += 1

    # ========== SECTION 9: SOFT INTERRUPTS MED FLOWOM ==========
    print(f"\n{Colors.CYAN}[45-48] SOFT INTERRUPTS MED REZERVACIJO{Colors.RESET}")

    if test("45. vino med rezervacijo mize", "kakšna vina imate?",
            state=in_table_flow(), expected_intent="WINE", expected_action="soft_interrupt"): passed += 1
    else: failed += 1

    if test("46. info med rezervacijo", "a imate parking?",
            state=in_table_flow(), expected_intent="INFO", expected_action="soft_interrupt"): passed += 1
    else: failed += 1

    if test("47. produkt med rezervacijo sobe", "a imate pesto?",
            state=in_room_flow(), expected_intent="PRODUCT", expected_action="soft_interrupt"): passed += 1
    else: failed += 1

    if test("48. menu med rezervacijo", "jedilnik prosim",
            state=in_table_flow(), expected_intent="MENU", expected_action="soft_interrupt"): passed += 1
    else: failed += 1

    # ========== SECTION 10: EDGE CASES ==========
    print(f"\n{Colors.CYAN}[49-50] EDGE CASES{Colors.RESET}")

    if test("49. kratko 'hm'", "hm", expected_intent="GENERAL"): passed += 1
    else: failed += 1

    # Mixed: miza + produkt
    scores = detect_intents("rad bi rezerviral mizo, a imate tudi pesto?")
    primary, secondary, conf = pick_primary_secondary(scores)
    if primary == "BOOKING_TABLE" and secondary == "PRODUCT":
        print(f"  {Colors.GREEN}✓{Colors.RESET} 50. mixed intent miza+pesto → primary=TABLE, secondary=PRODUCT")
        passed += 1
    else:
        print(f"  {Colors.RED}✗{Colors.RESET} 50. mixed intent miza+pesto")
        print(f"      {Colors.YELLOW}→ got primary={primary}, secondary={secondary}{Colors.RESET}")
        failed += 1

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
