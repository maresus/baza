#!/usr/bin/env python3
"""
50 Smoke Tests - Najtežje kombinacije za Unified Routing System

Zaženi z:
    cd /Volumes/SSD KLJUC/KOVACNIK AI/ZDRAVSTVENI CENTER
    source .venv/bin/activate
    python scripts/smoke_test_50.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.routing.unified_router import route, IntentType
from app.services.routing.confidence import detect_service_type, compute_confidence
from app.services.session.unified_state import (
    get_unified_state,
    reset_unified_state,
    start_flow,
    FlowType,
    FlowStep,
)

# Test counter
passed = 0
failed = 0

def test(name: str, message: str, expected_intent: str, expected_service: str = None, in_flow: bool = False):
    """Run single test"""
    global passed, failed

    session_id = f"smoke_{name.replace(' ', '_')}"
    reset_unified_state(session_id)

    if in_flow:
        start_flow(session_id, FlowType.APPOINTMENT, FlowStep.DATE)

    state = get_unified_state(session_id)
    decision = route(message, {"flow": state.get("flow", "idle") if isinstance(state, dict) else "idle"})

    intent_ok = decision.primary_intent.value == expected_intent
    service_ok = (expected_service is None) or (decision.service_type == expected_service)

    if intent_ok and service_ok:
        print(f"✅ {name}")
        passed += 1
    else:
        print(f"❌ {name}")
        print(f"   Msg: '{message}'")
        print(f"   Expected: intent={expected_intent}, service={expected_service}")
        print(f"   Got:      intent={decision.primary_intent.value}, service={decision.service_type}")
        failed += 1

def main():
    global passed, failed

    print("=" * 70)
    print("🔥 50 SMOKE TESTS - Najtežje kombinacije")
    print("=" * 70)

    # ============================================================
    # 1-10: BOOKING z različnimi formulacijami
    # ============================================================
    print("\n--- BOOKING VARIATIONS (1-10) ---")

    test("1. Direktno naročilo", "Rad bi se naročil na pregled", "BOOKING_APPOINTMENT")
    test("2. Z željami", "Želel bi termin pri dermatologu", "BOOKING_APPOINTMENT", "DERMATOLOG")
    test("3. Vljudno", "Prosim, lahko dobim termin za ortopeda?", "BOOKING_APPOINTMENT", "ORTOPED")
    test("4. Neformalno", "Ej, a je možn dobit termin?", "BOOKING_APPOINTMENT")
    test("5. S simptomi", "Boli me koleno, rad bi pregled", "BOOKING_APPOINTMENT", "ORTOPED")
    test("6. Dolga oblika", "Pozdravljeni, rad bi se naročil na dermatološki pregled ker imam težave s kožo", "BOOKING_APPOINTMENT", "DERMATOLOG")
    test("7. Kratka oblika", "Termin ortoped", "BOOKING_APPOINTMENT", "ORTOPED")
    test("8. Z datumom", "Rad bi termin za 15.3.2026", "BOOKING_APPOINTMENT")
    test("9. Kontrola", "Potrebujem kontrolo pri okulistu", "BOOKING_APPOINTMENT", "OKULIST")
    test("10. Rezervacija", "Rezerviral bi termin za kozmetiko", "BOOKING_APPOINTMENT", "KOZMETIKA")

    # ============================================================
    # 11-20: SERVICE INFO vs BOOKING (težko ločiti)
    # ============================================================
    print("\n--- SERVICE INFO vs BOOKING (11-20) ---")

    test("11. Kaj zdravite", "Katere bolezni zdravite?", "SERVICE_INFO")
    test("12. Kaj delate", "Kaj vse delate?", "SERVICE_INFO")
    test("13. Dermatolog info", "Kaj dela dermatolog?", "SERVICE_INFO")
    test("14. Ali imate", "Ali imate dermatologa?", "SERVICE_INFO")
    test("15. Kakšne storitve", "Kakšne storitve ponujate?", "SERVICE_INFO")
    test("16. Pregledi info", "Katere preglede izvajate?", "SERVICE_INFO")
    test("17. Specialist info", "Kdo je vaš ortoped?", "SERVICE_INFO")
    test("18. Postopek", "Kako poteka pregled pri okulistu?", "SERVICE_INFO")
    test("19. Kaj vključuje", "Kaj vključuje dermatološki pregled?", "SERVICE_INFO")
    test("20. Izkušnje", "Kakšne izkušnje ima vaš dermatolog?", "SERVICE_INFO")

    # ============================================================
    # 21-30: CENE in INFO
    # ============================================================
    print("\n--- CENE in INFO (21-30) ---")

    test("21. Cena pregleda", "Koliko stane pregled?", "PRICE")
    test("22. Cenik", "Ali imate cenik?", "PRICE")
    test("23. Cena ortoped", "Koliko stane ortopedski pregled?", "PRICE")
    test("24. Zavarovanje", "Ali sprejemate zavarovanje?", "PRICE")
    test("25. Lokacija", "Kje se nahajate?", "INFO")
    test("26. Delovni čas", "Kdaj ste odprti?", "INFO")
    test("27. Parking", "Ali imate parking?", "INFO")
    test("28. Kako pridem", "Kako pridem do vas?", "INFO")
    test("29. Telefon", "Kakšna je vaša telefonska številka?", "INFO")
    test("30. Email", "Kakšen je vaš email?", "INFO")

    # ============================================================
    # 31-35: SIMPTOMI (brez explicit booking signala = SERVICE_INFO)
    # ============================================================
    print("\n--- SIMPTOMI → SERVICE_INFO (31-35) ---")

    test("31. Koleno", "Boli me koleno", "SERVICE_INFO", "ORTOPED")
    test("32. Koža", "Imam izpuščaj na koži", "SERVICE_INFO", "DERMATOLOG")
    test("33. Oči", "Slabo vidim na daleč", "SERVICE_INFO", "OKULIST")
    test("34. Hrbet", "Že teden dni me boli hrbet", "SERVICE_INFO", "ORTOPED")
    test("35. Simptom+booking", "Imam gube, rada bi se naročila na botox", "BOOKING_APPOINTMENT", "ESTETSKI_POSEG")

    # ============================================================
    # 36-40: AFFIRMATIVE/NEGATIVE
    # ============================================================
    print("\n--- AFFIRMATIVE/NEGATIVE (36-40) ---")

    test("36. Da", "da", "AFFIRMATIVE")
    test("37. Ja prosim", "ja prosim", "AFFIRMATIVE")
    test("38. OK", "ok", "AFFIRMATIVE")
    test("39. Ne", "ne", "NEGATIVE")
    test("40. Ne hvala", "ne hvala", "NEGATIVE")

    # ============================================================
    # 41-45: EDGE CASES
    # ============================================================
    print("\n--- EDGE CASES (41-45) ---")

    test("41. Pozdrav", "Zdravo!", "GREETING")
    test("42. Dober dan čist", "Dober dan", "GREETING")
    test("43. Hvala", "Hvala za pomoč", "GOODBYE")
    test("44. Urgentno", "Rabim nujno pomoč!", "URGENCY")
    test("45. Danes nujno", "Rabim termin danes, nujno!", "URGENCY")

    # ============================================================
    # 46-50: KOMBINACIJE (najtežje)
    # ============================================================
    print("\n--- KOMBINACIJE - NAJTEŽJE (46-50) ---")

    test("46. Info + booking", "Koliko stane in kako se naročim na ortopeda?", "BOOKING_APPOINTMENT", "ORTOPED")
    test("47. Simptom + cena", "Boli me koleno, koliko stane pregled?", "PRICE", "ORTOPED")  # User asking about price
    test("48. Pozdrav + booking", "Zdravo, rad bi termin pri dermatologu", "BOOKING_APPOINTMENT", "DERMATOLOG")
    test("49. Več storitev", "Zanima me dermatolog in ortoped", "SERVICE_INFO")
    test("50. Kompleksno", "Že dalj časa me boli koleno in bi rad vedel koliko stane ter dobil termin", "BOOKING_APPOINTMENT", "ORTOPED")

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print(f"REZULTAT: {passed}/50 PASSED, {failed}/50 FAILED")
    print("=" * 70)

    if failed == 0:
        print("\n🎉 VSI TESTI USPEŠNI! Pripravljeno za produkcijo.")
        return 0
    elif failed <= 5:
        print(f"\n⚠️  {failed} testov ni uspelo - manjše prilagoditve potrebne.")
        return 1
    else:
        print(f"\n❌ {failed} testov ni uspelo - potreben pregled.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
