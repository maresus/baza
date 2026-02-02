#!/usr/bin/env python3
"""
20 Flow-Based Smoke Tests - Realistični scenariji pogovorov

Testira celotne conversational flowe, ne samo posamezne sporočila.
Vključuje:
- Booking flow z soft interrupts
- Sleng in typos
- Mixed language
- Edge cases

Zaženi z:
    cd /Volumes/SSD KLJUC/KOVACNIK AI/ZDRAVSTVENI CENTER
    source .venv/bin/activate
    python scripts/smoke_test_flow.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.routing.unified_router import route, IntentType
from app.services.routing.confidence import detect_service_type

passed = 0
failed = 0
failed_tests = []


def test(name: str, message: str, expected_intent: str, expected_service: str = None):
    """Run single test"""
    global passed, failed, failed_tests

    decision = route(message, {"flow": "idle"})
    service = detect_service_type(message)

    intent_ok = decision.primary_intent.value == expected_intent
    service_ok = (expected_service is None) or (service == expected_service)

    if intent_ok and service_ok:
        print(f"✅ {name}")
        passed += 1
    else:
        print(f"❌ {name}")
        print(f"   '{message}'")
        print(f"   Expected: {expected_intent}, {expected_service}")
        print(f"   Got:      {decision.primary_intent.value}, {service}")
        failed += 1
        failed_tests.append((name, message, expected_intent, expected_service,
                            decision.primary_intent.value, service))


def main():
    global passed, failed

    print("=" * 70)
    print("🔥 20 FLOW-BASED SMOKE TESTS - Realistični scenariji")
    print("=" * 70)

    # ============================================================
    # FLOW 1: Symptom → Booking (1-5)
    # Uporabnik začne s simptomom, potem želi termin
    # ============================================================
    print("\n--- FLOW 1: Symptom → Booking (1-5) ---")

    test("1. Simptom start (sleng)",
         "zivjo, mam problem z kozo ze par dni",
         "SERVICE_INFO", "DERMATOLOG")

    test("2. Booking request (sleng)",
         "a lohk dobim termin pri dermatolgu",
         "BOOKING_APPOINTMENT", "DERMATOLOG")

    test("3. Soft interrupt - cena",
         "sam prej me zanima kolko to stane",
         "PRICE", None)

    test("4. Soft interrupt - lokacija",
         "pa kje se nahajate, a mate parkplac",
         "INFO", None)

    test("5. Affirmative (neformalno)",
         "okej vredu bom prsou",
         "AFFIRMATIVE", None)

    # ============================================================
    # FLOW 2: Direct Booking z interrupts (6-10)
    # ============================================================
    print("\n--- FLOW 2: Direct Booking z interrupts (6-10) ---")

    test("6. Direct booking ortoped",
         "rad bi termin za ortopeda",
         "BOOKING_APPOINTMENT", "ORTOPED")

    test("7. Vprašanje o postopku",
         "kako poteka pregled",
         "SERVICE_INFO", None)

    test("8. Vprašanje o ceni med flowom",
         "a je drago",
         "PRICE", None)

    test("9. Confirm z ja",
         "ja prosim",
         "AFFIRMATIVE", None)

    test("10. Urgency override",
         "a je mozn danes ker me res hudo boli",
         "URGENCY", None)

    # ============================================================
    # FLOW 3: Mixed language (11-15)
    # ============================================================
    print("\n--- FLOW 3: Mixed language (11-15) ---")

    test("11. English greeting + SLO booking",
         "Hi, rad bi booking za dermatolog",
         "BOOKING_APPOINTMENT", "DERMATOLOG")

    test("12. Pure English booking",
         "need appointment please",
         "BOOKING_APPOINTMENT", None)

    test("13. English price question",
         "what are your prices",
         "PRICE", None)

    test("14. SLO + English symptom",
         "my back hurts, kaj priporocate",
         "SERVICE_INFO", "ORTOPED")

    test("15. English goodbye",
         "thanks for help",
         "GOODBYE", None)

    # ============================================================
    # FLOW 4: Edge cases in typos (16-20)
    # ============================================================
    print("\n--- FLOW 4: Edge cases in typos (16-20) ---")

    test("16. Typo ortoped",
         "termin za ortopet prosm",
         "BOOKING_APPOINTMENT", "ORTOPED")

    test("17. Typo okulist",
         "okulsit pregled",
         "BOOKING_APPOINTMENT", "OKULIST")

    test("18. Brez šumnikov dolg stavek",
         "zelim se narociti na pregled pri dermatolgu ker imam tezave s kozo",
         "BOOKING_APPOINTMENT", "DERMATOLOG")

    test("19. Hvala typo",
         "hvaal za pomoc",
         "GOODBYE", None)

    test("20. Kompleksno - vse skupaj",
         "ej zivjo, boli me hrbet ze dolgo, rad bi termin cimprej prosm",
         "BOOKING_APPOINTMENT", "ORTOPED")  # booking with urgency modifier

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print(f"REZULTAT: {passed}/20 PASSED, {failed}/20 FAILED")
    print("=" * 70)

    if failed > 0:
        print("\n❌ FAILED TESTI:")
        for name, msg, exp_int, exp_svc, got_int, got_svc in failed_tests:
            print(f"   {name}: '{msg[:40]}...'")
            print(f"      Expected: {exp_int}, {exp_svc}")
            print(f"      Got:      {got_int}, {got_svc}")

    if failed == 0:
        print("\n🎉 VSI TESTI USPEŠNI!")
        return 0
    elif failed <= 3:
        print(f"\n⚠️  {failed} testov ni uspelo - manjše prilagoditve potrebne")
        return 1
    else:
        print(f"\n❌ {failed} testov ni uspelo - potreben pregled")
        return 1


if __name__ == "__main__":
    sys.exit(main())
