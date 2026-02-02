#!/usr/bin/env python3
"""
Test scenariji za Unified Routing System

Zaženi z:
    cd /Volumes/SSD KLJUC/KOVACNIK AI/ZDRAVSTVENI CENTER
    source .venv/bin/activate
    python scripts/test_routing.py

Pričakovani rezultati:
    - 30 scenarijev
    - Vsi morajo PASS
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.routing.confidence import (
    compute_confidence,
    detect_intents,
    pick_primary_secondary,
    detect_service_type,
    SwitchAction,
    decide_action,
)
from app.services.routing.unified_router import route, IntentType
from app.services.session.unified_state import (
    get_unified_state,
    reset_unified_state,
    start_flow,
    FlowType,
    FlowStep,
    set_appointment_field,
    is_in_flow,
)


def test_scenario(name: str, message: str, expected_intent: str, expected_service: str | None = None, in_flow: bool = False, session_id: str = "test"):
    """Run a single test scenario."""
    # Reset state
    reset_unified_state(session_id)

    # Set up flow if needed
    if in_flow:
        start_flow(session_id, FlowType.APPOINTMENT, FlowStep.DATE)

    # Get unified state and route
    unified_state = get_unified_state(session_id)
    decision = route(message, unified_state.copy() if hasattr(unified_state, 'copy') else {"flow": "idle"})

    # Check intent
    intent_match = decision.primary_intent.value == expected_intent

    # Check service
    service_match = True
    if expected_service is not None:
        service_match = decision.service_type == expected_service

    passed = intent_match and service_match

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if not passed:
        print(f"       Expected: intent={expected_intent}, service={expected_service}")
        print(f"       Got:      intent={decision.primary_intent.value}, service={decision.service_type}")

    return passed


def test_confidence(name: str, message: str, intent: str, min_conf: float, max_conf: float = 1.0):
    """Test confidence scoring."""
    conf = compute_confidence(message, intent)
    passed = min_conf <= conf <= max_conf

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name} (conf={conf:.2f})")
    if not passed:
        print(f"       Expected: {min_conf} <= conf <= {max_conf}")
        print(f"       Got:      {conf}")

    return passed


def test_action(name: str, confidence: float, expected_action: str):
    """Test action decision."""
    action = decide_action(confidence)
    passed = action.value == expected_action

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name}")
    if not passed:
        print(f"       Expected: {expected_action}")
        print(f"       Got:      {action.value}")

    return passed


def main():
    print("=" * 60)
    print("UNIFIED ROUTING SYSTEM - Test Suite")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    # ============================================================
    # SECTION 1: GREETING & GOODBYE
    # ============================================================
    print("\n--- GREETINGS & GOODBYE ---")

    if test_scenario("Greeting - zdravo", "Zdravo", "GREETING"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Greeting - dober dan", "Dober dan", "GREETING"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Goodbye - hvala", "Hvala za pomoč", "GOODBYE"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Goodbye - adijo", "Adijo", "GOODBYE"):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 2: BOOKING INTENTS
    # ============================================================
    print("\n--- BOOKING INTENTS ---")

    if test_scenario("Booking - explicit ortoped", "Rad bi se naročil na ortopedski pregled", "BOOKING_APPOINTMENT", "ORTOPED"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Booking - explicit dermatolog", "Želim termin pri dermatologu", "BOOKING_APPOINTMENT", "DERMATOLOG"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Booking - generic", "Rad bi se naročil", "BOOKING_APPOINTMENT", None):
        passed += 1
    else:
        failed += 1

    if test_scenario("Booking - okulist", "Potrebujem pregled oči", "BOOKING_APPOINTMENT", "OKULIST"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Booking - kozmetika", "Rada bi kozmetični tretma", "BOOKING_APPOINTMENT", "KOZMETIKA"):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 3: SERVICE INFO (not booking)
    # ============================================================
    print("\n--- SERVICE INFO ---")

    if test_scenario("Service info - kaj zdravite", "Katere bolezni zdravite?", "SERVICE_INFO"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Service info - kaj delate", "Kaj vse delate?", "SERVICE_INFO"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Service info - kaj ponujate", "Katere storitve ponujate?", "SERVICE_INFO"):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 4: PRICE INTENTS
    # ============================================================
    print("\n--- PRICE INTENTS ---")

    if test_scenario("Price - cenik", "Koliko stane pregled?", "PRICE"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Price - cene", "Kakšne so cene?", "PRICE"):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 5: INFO INTENTS
    # ============================================================
    print("\n--- INFO INTENTS ---")

    if test_scenario("Info - lokacija", "Kje se nahajate?", "INFO"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Info - delovni čas", "Kdaj ste odprti?", "INFO"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Info - parking", "Ali imate parking?", "INFO"):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 6: AFFIRMATIVE/NEGATIVE
    # ============================================================
    print("\n--- AFFIRMATIVE/NEGATIVE ---")

    if test_scenario("Affirmative - da", "da", "AFFIRMATIVE"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Affirmative - ok", "ok", "AFFIRMATIVE"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Negative - ne", "ne", "NEGATIVE"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Negative - ne hvala", "ne hvala", "NEGATIVE"):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 7: URGENCY
    # ============================================================
    print("\n--- URGENCY ---")

    if test_scenario("Urgency - nujno", "Rabim nujno pomoč", "URGENCY"):
        passed += 1
    else:
        failed += 1

    if test_scenario("Urgency - danes", "Rabim termin danes", "URGENCY"):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 8: CONFIDENCE SCORING
    # ============================================================
    print("\n--- CONFIDENCE SCORING ---")

    if test_confidence("High conf - explicit booking", "Rad bi se naročil na ortopedski pregled", "BOOKING_APPOINTMENT", 0.9):
        passed += 1
    else:
        failed += 1

    if test_confidence("Medium conf - generic booking", "Rad bi termin", "BOOKING_APPOINTMENT", 0.6, 0.9):
        passed += 1
    else:
        failed += 1

    if test_confidence("High conf - greeting", "Zdravo", "GREETING", 1.0):
        passed += 1
    else:
        failed += 1

    if test_confidence("Low conf - random text", "miza okno drevo", "BOOKING_APPOINTMENT", 0.0, 0.3):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 9: ACTION DECISIONS
    # ============================================================
    print("\n--- ACTION DECISIONS ---")

    if test_action("Action - hard switch (0.9)", 0.9, "hard_switch"):
        passed += 1
    else:
        failed += 1

    if test_action("Action - soft interrupt (0.6)", 0.6, "soft_interrupt"):
        passed += 1
    else:
        failed += 1

    if test_action("Action - ignore (0.3)", 0.3, "ignore"):
        passed += 1
    else:
        failed += 1

    # ============================================================
    # SECTION 10: SERVICE TYPE DETECTION
    # ============================================================
    print("\n--- SERVICE TYPE DETECTION ---")

    services = [
        ("Boli me koleno", "ORTOPED"),
        ("Imam izpuščaj na koži", "DERMATOLOG"),
        ("Slabo vidim", "OKULIST"),
        ("Želim botox", "ESTETSKI_POSEG"),
        ("Lasersko odstranjevanje žilic", "LASERSKI_POSEG"),
        ("Nega obraza", "KOZMETIKA"),
    ]

    for msg, expected in services:
        detected = detect_service_type(msg)
        passed_svc = detected == expected
        status = "✅ PASS" if passed_svc else "❌ FAIL"
        print(f"{status} | Service: {msg} -> {detected}")
        if passed_svc:
            passed += 1
        else:
            failed += 1
            print(f"       Expected: {expected}")

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {failed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
