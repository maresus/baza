#!/usr/bin/env python3
"""
110 Smoke Tests - EKSTREMNI TESTI za Unified Routing System

50 osnovnih + 60 dodatnih kompleksnih testov:
- Tipkarske napake
- Slovnične napake
- Sleng in neformalno
- Mešanica jezikov
- Edge cases
- Nejasne formulacije
- Emojiji in posebni znaki

Zaženi z:
    cd /Volumes/SSD KLJUC/KOVACNIK AI/ZDRAVSTVENI CENTER
    source .venv/bin/activate
    python scripts/smoke_test_110.py
"""

import sys
import os

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

passed = 0
failed = 0
failed_tests = []

def test(name: str, message: str, expected_intent: str, expected_service: str = None):
    """Run single test"""
    global passed, failed, failed_tests

    session_id = f"smoke_{hash(name) % 10000}"
    reset_unified_state(session_id)

    state = get_unified_state(session_id)
    decision = route(message, {"flow": "idle"})

    intent_ok = decision.primary_intent.value == expected_intent
    service_ok = (expected_service is None) or (decision.service_type == expected_service)

    if intent_ok and service_ok:
        print(f"✅ {name}")
        passed += 1
    else:
        print(f"❌ {name}")
        print(f"   '{message}'")
        print(f"   Expected: {expected_intent}, {expected_service}")
        print(f"   Got:      {decision.primary_intent.value}, {decision.service_type}")
        failed += 1
        failed_tests.append((name, message, expected_intent, expected_service, decision.primary_intent.value, decision.service_type))

def main():
    global passed, failed

    print("=" * 70)
    print("🔥 110 SMOKE TESTS - EKSTREMNI TESTI")
    print("=" * 70)

    # ============================================================
    # 1-10: BOOKING VARIATIONS (osnova)
    # ============================================================
    print("\n--- 1-10: BOOKING OSNOVNE VARIACIJE ---")
    test("1", "Rad bi se naročil na pregled", "BOOKING_APPOINTMENT")
    test("2", "Želel bi termin pri dermatologu", "BOOKING_APPOINTMENT", "DERMATOLOG")
    test("3", "Prosim, lahko dobim termin za ortopeda?", "BOOKING_APPOINTMENT", "ORTOPED")
    test("4", "Ej, a je možn dobit termin?", "BOOKING_APPOINTMENT")
    test("5", "Boli me koleno, rad bi pregled", "BOOKING_APPOINTMENT", "ORTOPED")
    test("6", "Pozdravljeni, rad bi se naročil na dermatološki pregled", "BOOKING_APPOINTMENT", "DERMATOLOG")
    test("7", "Termin ortoped", "BOOKING_APPOINTMENT", "ORTOPED")
    test("8", "Rad bi termin za 15.3.2026", "BOOKING_APPOINTMENT")
    test("9", "Potrebujem kontrolo pri okulistu", "BOOKING_APPOINTMENT", "OKULIST")
    test("10", "Rezerviral bi termin za kozmetiko", "BOOKING_APPOINTMENT", "KOZMETIKA")

    # ============================================================
    # 11-20: SERVICE INFO (osnova)
    # ============================================================
    print("\n--- 11-20: SERVICE INFO OSNOVA ---")
    test("11", "Katere bolezni zdravite?", "SERVICE_INFO")
    test("12", "Kaj vse delate?", "SERVICE_INFO")
    test("13", "Kaj dela dermatolog?", "SERVICE_INFO")
    test("14", "Ali imate dermatologa?", "SERVICE_INFO")
    test("15", "Kakšne storitve ponujate?", "SERVICE_INFO")
    test("16", "Katere preglede izvajate?", "SERVICE_INFO")
    test("17", "Kdo je vaš ortoped?", "SERVICE_INFO")
    test("18", "Kako poteka pregled pri okulistu?", "SERVICE_INFO")
    test("19", "Kaj vključuje dermatološki pregled?", "SERVICE_INFO")
    test("20", "Kakšne izkušnje ima vaš dermatolog?", "SERVICE_INFO")

    # ============================================================
    # 21-30: CENE in INFO (osnova)
    # ============================================================
    print("\n--- 21-30: CENE in INFO ---")
    test("21", "Koliko stane pregled?", "PRICE")
    test("22", "Ali imate cenik?", "PRICE")
    test("23", "Koliko stane ortopedski pregled?", "PRICE")
    test("24", "Ali sprejemate zavarovanje?", "PRICE")
    test("25", "Kje se nahajate?", "INFO")
    test("26", "Kdaj ste odprti?", "INFO")
    test("27", "Ali imate parking?", "INFO")
    test("28", "Kako pridem do vas?", "INFO")
    test("29", "Kakšna je vaša telefonska številka?", "INFO")
    test("30", "Kakšen je vaš email?", "INFO")

    # ============================================================
    # 31-40: SIMPTOMI in AFFIRMATIVE/NEGATIVE
    # ============================================================
    print("\n--- 31-40: SIMPTOMI + YES/NO ---")
    test("31", "Boli me koleno", "SERVICE_INFO", "ORTOPED")
    test("32", "Imam izpuščaj na koži", "SERVICE_INFO", "DERMATOLOG")
    test("33", "Slabo vidim na daleč", "SERVICE_INFO", "OKULIST")
    test("34", "Že teden dni me boli hrbet", "SERVICE_INFO", "ORTOPED")
    test("35", "Imam gube, rada bi se naročila na botox", "BOOKING_APPOINTMENT", "ESTETSKI_POSEG")
    test("36", "da", "AFFIRMATIVE")
    test("37", "ja prosim", "AFFIRMATIVE")
    test("38", "ok", "AFFIRMATIVE")
    test("39", "ne", "NEGATIVE")
    test("40", "ne hvala", "NEGATIVE")

    # ============================================================
    # 41-50: EDGE CASES + KOMBINACIJE
    # ============================================================
    print("\n--- 41-50: EDGE CASES ---")
    test("41", "Zdravo!", "GREETING")
    test("42", "Dober dan", "GREETING")
    test("43", "Hvala za pomoč", "GOODBYE")
    test("44", "Rabim nujno pomoč!", "URGENCY")
    test("45", "Rabim termin danes, nujno!", "URGENCY")
    test("46", "Koliko stane in kako se naročim na ortopeda?", "BOOKING_APPOINTMENT", "ORTOPED")
    test("47", "Boli me koleno, koliko stane pregled?", "PRICE", "ORTOPED")
    test("48", "Zdravo, rad bi termin pri dermatologu", "BOOKING_APPOINTMENT", "DERMATOLOG")
    test("49", "Zanima me dermatolog in ortoped", "SERVICE_INFO")
    test("50", "Že dalj časa me boli koleno in bi rad vedel koliko stane ter dobil termin", "BOOKING_APPOINTMENT", "ORTOPED")

    # ============================================================
    # 51-60: TIPKARSKE NAPAKE (TYPOS)
    # ============================================================
    print("\n--- 51-60: TIPKARSKE NAPAKE ---")
    test("51", "rad bi se narocil", "BOOKING_APPOINTMENT")  # brez šumnikov
    test("52", "zelim termin", "BOOKING_APPOINTMENT")  # želim -> zelim
    test("53", "dermatolog pregled prosm", "BOOKING_APPOINTMENT", "DERMATOLOG")  # prosim -> prosm
    test("54", "ortopet termin", "BOOKING_APPOINTMENT", "ORTOPED")  # ortoped -> ortopet
    test("55", "okulsit pregled", "BOOKING_APPOINTMENT", "OKULIST")  # okulist -> okulsit
    test("56", "kdja ste odprti", "INFO")  # kdaj -> kdja
    test("57", "kje se nhajaet", "INFO")  # nahajate -> nhajaet
    test("58", "kolko stane", "PRICE")  # koliko -> kolko
    test("59", "hvaal", "GOODBYE")  # hvala -> hvaal
    test("60", "zdravjo", "GREETING")  # zdravo -> zdravjo

    # ============================================================
    # 61-70: BREZ ŠUMNIKOV (č, š, ž)
    # ============================================================
    print("\n--- 61-70: BREZ ŠUMNIKOV ---")
    test("61", "zelim se narociti na pregled", "BOOKING_APPOINTMENT")
    test("62", "kje se nahajate", "INFO")
    test("63", "koliko stane pregled pri dermatolgu", "PRICE")
    test("64", "kdaj ste odprti", "INFO")
    test("65", "imam tezave s kozo", "SERVICE_INFO", "DERMATOLOG")
    test("66", "boli me hrbet ze dolgo", "SERVICE_INFO", "ORTOPED")
    test("67", "slabo vidim na dalec", "SERVICE_INFO", "OKULIST")
    test("68", "kaj vkljucuje pregled", "SERVICE_INFO")
    test("69", "prosim za termin cimprej", "URGENCY")  # "čimprej" = urgentno
    test("70", "nujno rabim pomoc", "URGENCY")

    # ============================================================
    # 71-80: NEFORMALNO / SLENG
    # ============================================================
    print("\n--- 71-80: NEFORMALNO / SLENG ---")
    test("71", "ej lej a mam lohk termin", "BOOKING_APPOINTMENT")
    test("72", "kva morm prpelat sabo", "SERVICE_INFO")
    test("73", "kko pridm do vas", "INFO")
    test("74", "kolko stane to", "PRICE")  # kolko = koliko
    test("75", "a mate parkplac", "INFO")
    test("76", "imam vprašanje glede storitev", "SERVICE_INFO")  # jasno info
    test("77", "bom prsou", "AFFIRMATIVE")
    test("78", "nism zihr", "GENERAL")  # nejasno
    test("79", "sej to ni tok drago a", "PRICE")
    test("80", "mam problem z ocmi", "SERVICE_INFO", "OKULIST")

    # ============================================================
    # 81-90: DOLGI KOMPLEKSNI STAVKI
    # ============================================================
    print("\n--- 81-90: DOLGI KOMPLEKSNI STAVKI ---")
    test("81", "Prosim če mi lahko pomagate z informacijo glede terminov za dermatolog", "SERVICE_INFO", "DERMATOLOG")  # info request
    test("82", "Zanima me če je mogoče dobiti termin ta teden ker imam že dlje časa težave in bi rad da me pregleda specialist", "BOOKING_APPOINTMENT")
    test("83", "Imam več vprašanj glede storitev ki jih ponujate in bi rad vedel kaj vse delate in koliko to stane", "SERVICE_INFO")
    test("84", "Boli me koleno že približno tri tedne, kaj mi priporočate", "SERVICE_INFO", "ORTOPED")  # vprašanje
    test("85", "Želel bi se pozanimati o možnostih naročanja terminov in kakšni so prosti datumi v naslednjem tednu", "BOOKING_APPOINTMENT")
    test("86", "Kdaj imate odprto in kje se nahajate", "INFO")  # jasno info vprašanje
    test("87", "Katere estetske posege izvajate, predvsem me zanima botox", "SERVICE_INFO", "ESTETSKI_POSEG")  # info
    test("88", "Potreboval bi informacije o ortopedskem pregledu ker imam bolečine v hrbtu in kolenu že dlje časa", "SERVICE_INFO", "ORTOPED")
    test("89", "Prosim za pomoč pri naročanju na pregled pri okulistu ker slabo vidim in potrebujem nova očala", "BOOKING_APPOINTMENT", "OKULIST")
    test("90", "Živijo lahko dobim termin čim prej ker me res zelo boli in ne morem več čakat", "URGENCY")

    # ============================================================
    # 91-100: MEŠANICA SLOVENŠČINA + ANGLEŠČINA
    # ============================================================
    print("\n--- 91-100: SLOVENŠČINA + ANGLEŠČINA ---")
    test("91", "Hi, rad bi booking za dermatolog", "BOOKING_APPOINTMENT", "DERMATOLOG")
    test("92", "Need appointment please", "BOOKING_APPOINTMENT")
    test("93", "What are your prices", "PRICE")
    test("94", "Where are you located", "INFO")
    test("95", "Thanks for help", "GOODBYE")
    test("96", "Hello, potrebujem termin", "BOOKING_APPOINTMENT")
    test("97", "Rad bi appointment za ortoped", "BOOKING_APPOINTMENT", "ORTOPED")
    test("98", "A imate free slots ta teden", "BOOKING_APPOINTMENT")
    test("99", "My back hurts, kaj priporočate", "SERVICE_INFO", "ORTOPED")
    test("100", "Ok cool, book me in", "BOOKING_APPOINTMENT")

    # ============================================================
    # 101-110: POSEBNI ZNAKI, EMOJIJI, EDGE CASES
    # ============================================================
    print("\n--- 101-110: POSEBNI ZNAKI + EDGE CASES ---")
    test("101", "Zdravo 😊", "GREETING")
    test("102", "Hvala!! 🙏", "GOODBYE")
    test("103", "TERMIN ZA ORTOPEDA!!!", "BOOKING_APPOINTMENT", "ORTOPED")
    test("104", "termin...dermatolog...prosim", "BOOKING_APPOINTMENT", "DERMATOLOG")
    test("105", "???cena???", "PRICE")
    test("106", "   zdravo   ", "GREETING")  # whitespace
    test("107", "D A", "AFFIRMATIVE")  # spaces in da
    test("108", "n e", "NEGATIVE")  # spaces in ne
    test("109", "123 456 789", "GENERAL")  # samo številke
    test("110", "...", "GENERAL")  # samo pike

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print(f"REZULTAT: {passed}/110 PASSED, {failed}/110 FAILED")
    print("=" * 70)

    if failed > 0:
        print("\n❌ FAILED TESTI:")
        for name, msg, exp_int, exp_svc, got_int, got_svc in failed_tests:
            print(f"   {name}: '{msg[:40]}...' -> Expected {exp_int}, Got {got_int}")

    if failed == 0:
        print("\n🎉 VSI TESTI USPEŠNI!")
        return 0
    elif failed <= 10:
        print(f"\n⚠️  {failed} testov ni uspelo - manjše prilagoditve potrebne")
        return 1
    else:
        print(f"\n❌ {failed} testov ni uspelo - potreben pregled")
        return 1


if __name__ == "__main__":
    sys.exit(main())
