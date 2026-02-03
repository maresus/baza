#!/usr/bin/env python3
"""
50 E2E Smoke Tests - Celotni pogovorni tokovi od začetka do konca

Testira:
- Booking flows z soft interrupts
- Service info queries
- Price/Info queries
- Mixed language
- Typos, sleng, brez šumnikov
- Edge cases

Zaženi z:
    cd /Volumes/SSD KLJUC/KOVACNIK AI/ZDRAVSTVENI CENTER
    source .venv/bin/activate
    python scripts/smoke_test_e2e_50.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.routing.unified_router import route, IntentType
from app.services.routing.confidence import detect_service_type

passed = 0
failed = 0
failed_tests = []


def test_single(msg: str, exp_intent: str, exp_service: str = None) -> bool:
    """Test single message, return True if pass."""
    decision = route(msg, {"flow": "idle"})
    service = detect_service_type(msg)
    intent_ok = decision.primary_intent.value == exp_intent
    service_ok = (exp_service is None) or (service == exp_service)
    return intent_ok and service_ok


def test_flow(name: str, steps: list) -> bool:
    """
    Test complete E2E flow.
    steps = [(message, expected_intent, expected_service), ...]
    """
    global passed, failed, failed_tests

    all_pass = True
    failed_step = None

    for i, step in enumerate(steps):
        msg, exp_intent, exp_service = step[0], step[1], step[2] if len(step) > 2 else None
        if not test_single(msg, exp_intent, exp_service):
            all_pass = False
            decision = route(msg, {"flow": "idle"})
            service = detect_service_type(msg)
            failed_step = (i+1, msg, exp_intent, exp_service,
                          decision.primary_intent.value, service)
            break

    if all_pass:
        print(f"✅ {name}")
        passed += 1
    else:
        print(f"❌ {name}")
        i, msg, exp_int, exp_svc, got_int, got_svc = failed_step
        print(f"   Step {i}: '{msg[:50]}...'")
        print(f"   Expected: {exp_int}, {exp_svc}")
        print(f"   Got:      {got_int}, {got_svc}")
        failed += 1
        failed_tests.append((name, failed_step))

    return all_pass


def main():
    global passed, failed

    print("=" * 70)
    print("🔥 50 E2E SMOKE TESTS - Celotni tokovi od začetka do konca")
    print("=" * 70)

    # ============================================================
    # FLOW 1-10: BOOKING FLOWS (različne storitve)
    # ============================================================
    print("\n--- 1-10: BOOKING FLOWS ---")

    test_flow("1. Dermatolog booking - basic", [
        ("Zdravo", "GREETING"),
        ("Rad bi termin pri dermatologu", "BOOKING_APPOINTMENT", "DERMATOLOG"),
        ("Da", "AFFIRMATIVE"),
    ])

    test_flow("2. Ortoped booking - s simptomom", [
        ("Boli me koleno že teden dni", "SERVICE_INFO", "ORTOPED"),
        ("Rad bi se naročil na pregled", "BOOKING_APPOINTMENT"),
        ("Ja prosim", "AFFIRMATIVE"),
    ])

    test_flow("3. Okulist booking - kontrola", [
        ("Potrebujem kontrolo pri okulistu", "BOOKING_APPOINTMENT", "OKULIST"),
        ("Ok", "AFFIRMATIVE"),
        ("Hvala", "GOODBYE"),
    ])

    test_flow("4. Estetski poseg - botox", [
        ("Zanima me botox", "SERVICE_INFO", "ESTETSKI_POSEG"),
        ("Bi se naročila", "BOOKING_APPOINTMENT"),
        ("Da prosim", "AFFIRMATIVE"),
    ])

    test_flow("5. Fizioterapija booking", [
        ("Rad bi termin za fizioterapijo", "BOOKING_APPOINTMENT", "FIZIOTERAPIJA"),
        ("Vredu", "AFFIRMATIVE"),
    ])

    test_flow("6. Kozmetika booking", [
        ("Želim rezervirati termin za kozmetiko", "BOOKING_APPOINTMENT", "KOZMETIKA"),
        ("Okej", "AFFIRMATIVE"),
    ])

    test_flow("7. Laserski poseg booking", [
        ("A delate laserske posege?", "SERVICE_INFO", "LASERSKI_POSEG"),
        ("Bi se naročil", "BOOKING_APPOINTMENT"),
        ("Ja", "AFFIRMATIVE"),
    ])

    test_flow("8. Booking brez storitve", [
        ("Rad bi se naročil na pregled", "BOOKING_APPOINTMENT"),
        ("Dermatolog", "SERVICE_INFO", "DERMATOLOG"),
        ("Da", "AFFIRMATIVE"),
    ])

    test_flow("9. Booking z datumom", [
        ("Rad bi termin za 15.3.2026", "BOOKING_APPOINTMENT"),
        ("Ja prosim", "AFFIRMATIVE"),
    ])

    test_flow("10. Booking z urgent", [
        ("Nujno rabim termin danes", "URGENCY"),
        ("Da", "AFFIRMATIVE"),
    ])

    # ============================================================
    # FLOW 11-20: BOOKING S SOFT INTERRUPTS
    # ============================================================
    print("\n--- 11-20: BOOKING S SOFT INTERRUPTS ---")

    test_flow("11. Booking + price interrupt", [
        ("Rad bi termin pri dermatologu", "BOOKING_APPOINTMENT", "DERMATOLOG"),
        ("Koliko stane pregled?", "PRICE"),
        ("Da prosim", "AFFIRMATIVE"),
    ])

    test_flow("12. Booking + location interrupt", [
        ("Termin za ortopeda prosim", "BOOKING_APPOINTMENT", "ORTOPED"),
        ("Kje se nahajate?", "INFO"),
        ("Ja", "AFFIRMATIVE"),
    ])

    test_flow("13. Booking + parking interrupt", [
        ("Rad bi se naročil", "BOOKING_APPOINTMENT"),
        ("A imate parking?", "INFO"),
        ("Ok", "AFFIRMATIVE"),
    ])

    test_flow("14. Booking + hours interrupt", [
        ("Potrebujem termin pri okulistu", "BOOKING_APPOINTMENT", "OKULIST"),
        ("Kdaj ste odprti?", "INFO"),
        ("Bom prišel", "AFFIRMATIVE"),
    ])

    test_flow("15. Booking + multiple interrupts", [
        ("Termin za dermatolog", "BOOKING_APPOINTMENT", "DERMATOLOG"),
        ("Kolko stane?", "PRICE"),
        ("Pa kje ste?", "INFO"),
        ("Okej vredu", "AFFIRMATIVE"),
    ])

    test_flow("16. Symptom → booking + price", [
        ("Imam izpuščaj na koži", "SERVICE_INFO", "DERMATOLOG"),
        ("A je drago?", "PRICE"),
        ("Rad bi termin", "BOOKING_APPOINTMENT"),
        ("Da", "AFFIRMATIVE"),
    ])

    test_flow("17. Booking + service info interrupt", [
        ("Termin za ortopeda", "BOOKING_APPOINTMENT", "ORTOPED"),
        ("Kako poteka pregled?", "SERVICE_INFO"),
        ("Super, ja prosim", "AFFIRMATIVE"),
    ])

    test_flow("18. Complex flow - all interrupts", [
        ("Zdravo", "GREETING"),
        ("Boli me hrbet", "SERVICE_INFO", "ORTOPED"),
        ("Koliko stane pregled?", "PRICE"),
        ("Kje se nahajate?", "INFO"),
        ("Rad bi termin", "BOOKING_APPOINTMENT"),
        ("Ja prosim", "AFFIRMATIVE"),
        ("Hvala", "GOODBYE"),
    ])

    test_flow("19. Booking + zavarovanje", [
        ("Termin za dermatolog", "BOOKING_APPOINTMENT", "DERMATOLOG"),
        ("Ali sprejemate zavarovanje?", "PRICE"),
        ("Da", "AFFIRMATIVE"),
    ])

    test_flow("20. Booking + email vprašanje", [
        ("Rad bi se naročil", "BOOKING_APPOINTMENT"),
        ("Kakšen je vaš email?", "INFO"),
        ("Ok", "AFFIRMATIVE"),
    ])

    # ============================================================
    # FLOW 21-30: SERVICE INFO FLOWS
    # ============================================================
    print("\n--- 21-30: SERVICE INFO FLOWS ---")

    test_flow("21. Dermatolog info", [
        ("Kaj dela dermatolog?", "SERVICE_INFO"),
        ("Hvala za info", "GOODBYE"),
    ])

    test_flow("22. Storitve splošno", [
        ("Kakšne storitve ponujate?", "SERVICE_INFO"),
        ("Hvala", "GOODBYE"),
    ])

    test_flow("23. Simptom → info → booking", [
        ("Slabo vidim na daleč", "SERVICE_INFO", "OKULIST"),
        ("Kaj vključuje pregled?", "SERVICE_INFO"),
        ("Rad bi termin", "BOOKING_APPOINTMENT"),
    ])

    test_flow("24. Več storitev naenkrat", [
        ("Zanima me dermatolog in ortoped", "SERVICE_INFO"),
        ("Hvala", "GOODBYE"),
    ])

    test_flow("25. Estetski info", [
        ("Katere estetske posege izvajate?", "SERVICE_INFO"),
        ("Me zanima botox", "SERVICE_INFO", "ESTETSKI_POSEG"),
    ])

    test_flow("26. Bolezni info", [
        ("Katere bolezni zdravite?", "SERVICE_INFO"),
        ("Hvala", "GOODBYE"),
    ])

    test_flow("27. Specialist info", [
        ("Kdo je vaš ortoped?", "SERVICE_INFO"),
        ("Kakšne izkušnje ima?", "SERVICE_INFO"),
    ])

    test_flow("28. Postopek info", [
        ("Kako poteka pregled pri okulistu?", "SERVICE_INFO"),
        ("Hvala za info", "GOODBYE"),
    ])

    test_flow("29. Priprava info", [
        ("Kaj moram prinesti s sabo?", "SERVICE_INFO"),
        ("Ok hvala", "GOODBYE"),
    ])

    test_flow("30. Simptom + vprašanje", [
        ("Boli me koleno, kaj mi priporočate?", "SERVICE_INFO", "ORTOPED"),
        ("Hvala", "GOODBYE"),
    ])

    # ============================================================
    # FLOW 31-40: SLENG, TYPOS, BREZ ŠUMNIKOV
    # ============================================================
    print("\n--- 31-40: SLENG, TYPOS, BREZ ŠUMNIKOV ---")

    test_flow("31. Sleng booking", [
        ("Ej zivjo", "GREETING"),
        ("A lohk dobim termin", "BOOKING_APPOINTMENT"),
        ("Ja okej", "AFFIRMATIVE"),
    ])

    test_flow("32. Typos flow", [
        ("Zdravjo", "GREETING"),
        ("Termin za ortopet", "BOOKING_APPOINTMENT", "ORTOPED"),
        ("Hvaal", "GOODBYE"),
    ])

    test_flow("33. Brez šumnikov flow", [
        ("Zelim se narociti na pregled", "BOOKING_APPOINTMENT"),
        ("Pri dermatolgu", "SERVICE_INFO", "DERMATOLOG"),
        ("Da prosim", "AFFIRMATIVE"),
    ])

    test_flow("34. Mešan sleng", [
        ("Mam problem z kozo", "SERVICE_INFO", "DERMATOLOG"),
        ("Kolko stane to?", "PRICE"),
        ("A lohk dobim termin?", "BOOKING_APPOINTMENT"),
        ("Ja", "AFFIRMATIVE"),
    ])

    test_flow("35. Typo okulist", [
        ("Okulsit pregled prosm", "BOOKING_APPOINTMENT", "OKULIST"),
        ("Okej", "AFFIRMATIVE"),
    ])

    test_flow("36. Sleng lokacija", [
        ("Kko pridm do vas?", "INFO"),
        ("A mate parkplac?", "INFO"),
        ("Hvala", "GOODBYE"),
    ])

    test_flow("37. Sleng cena", [
        ("Kva stane pregled?", "PRICE"),
        ("A je drago?", "PRICE"),
        ("Okej hvala", "GOODBYE"),
    ])

    test_flow("38. Affirmative variante", [
        ("Termin prosim", "BOOKING_APPOINTMENT"),
        ("Okej vredu bom prsou", "AFFIRMATIVE"),
    ])

    test_flow("39. Negative variante", [
        ("Termin?", "BOOKING_APPOINTMENT"),
        ("Ne hvala", "NEGATIVE"),
    ])

    test_flow("40. Kompleksen sleng", [
        ("Ej lej a mam lohk termin", "BOOKING_APPOINTMENT"),
        ("Kolko pa to stane", "PRICE"),
        ("Ja bom prsou", "AFFIRMATIVE"),
    ])

    # ============================================================
    # FLOW 41-50: MIXED LANGUAGE + EDGE CASES
    # ============================================================
    print("\n--- 41-50: MIXED LANGUAGE + EDGE CASES ---")

    test_flow("41. English booking", [
        ("Hi", "GREETING"),
        ("Need appointment please", "BOOKING_APPOINTMENT"),
        ("Yes", "AFFIRMATIVE"),
    ])

    test_flow("42. English info", [
        ("Where are you located?", "INFO"),
        ("What are your prices?", "PRICE"),
        ("Thanks", "GOODBYE"),
    ])

    test_flow("43. Mixed SLO+ENG", [
        ("Hello, rad bi termin", "BOOKING_APPOINTMENT"),
        ("What's the price?", "PRICE"),
        ("Ok cool", "AFFIRMATIVE"),
    ])

    test_flow("44. English symptom", [
        ("My back hurts", "SERVICE_INFO", "ORTOPED"),
        ("Rad bi termin", "BOOKING_APPOINTMENT"),
        ("Yes please", "AFFIRMATIVE"),
    ])

    test_flow("45. Urgency flow", [
        ("Nujno rabim pomoč!", "URGENCY"),
        ("Da", "AFFIRMATIVE"),
    ])

    test_flow("46. Danes nujno", [
        ("Rabim termin danes, nujno!", "URGENCY"),
        ("Ja prosim", "AFFIRMATIVE"),
    ])

    test_flow("47. Greeting → complex", [
        ("Pozdravljeni", "GREETING"),
        ("Že dalj časa me boli koleno", "SERVICE_INFO", "ORTOPED"),
        ("Koliko stane pregled?", "PRICE"),
        ("Rad bi termin", "BOOKING_APPOINTMENT"),
        ("Da", "AFFIRMATIVE"),
        ("Lep pozdrav", "GOODBYE"),
    ])

    test_flow("48. Samo info flow", [
        ("Dober dan", "GREETING"),
        ("Kje se nahajate?", "INFO"),
        ("Kdaj ste odprti?", "INFO"),
        ("Ali imate parking?", "INFO"),
        ("Hvala za informacije", "GOODBYE"),
    ])

    test_flow("49. Samo price flow", [
        ("Živjo", "GREETING"),
        ("Koliko stane dermatološki pregled?", "PRICE"),
        ("Pa koliko stane ortopedski?", "PRICE"),  # needs price keyword
        ("Hvala", "GOODBYE"),
    ])

    test_flow("50. Full complex flow", [
        ("Dober dan", "GREETING"),
        ("Imam težave s kožo že nekaj dni", "SERVICE_INFO", "DERMATOLOG"),
        ("Katere bolezni zdravite?", "SERVICE_INFO"),
        ("Koliko stane pregled?", "PRICE"),
        ("Kje se nahajate?", "INFO"),
        ("Ali imate parking?", "INFO"),
        ("Rad bi se naročil na pregled", "BOOKING_APPOINTMENT"),
        ("Da prosim", "AFFIRMATIVE"),
        ("Hvala za pomoč", "GOODBYE"),
    ])

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print(f"REZULTAT: {passed}/50 PASSED, {failed}/50 FAILED")
    print("=" * 70)

    if failed > 0:
        print("\n❌ FAILED TESTI:")
        for name, step_info in failed_tests:
            i, msg, exp_int, exp_svc, got_int, got_svc = step_info
            print(f"   {name} (step {i})")
            print(f"      '{msg[:50]}...'")
            print(f"      Expected: {exp_int}, {exp_svc}")
            print(f"      Got:      {got_int}, {got_svc}")

    if failed == 0:
        print("\n🎉 VSI TESTI USPEŠNI!")
        return 0
    elif failed <= 5:
        print(f"\n⚠️  {failed} testov ni uspelo - manjše prilagoditve potrebne")
        return 1
    else:
        print(f"\n❌ {failed} testov ni uspelo - potreben pregled")
        return 1


if __name__ == "__main__":
    sys.exit(main())
