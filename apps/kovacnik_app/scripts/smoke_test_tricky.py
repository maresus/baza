#!/usr/bin/env python3
"""
Tricky Test - 20 zvitih scenarijev za Unified Routing System.
Namenjeno za edge cases, dvoumne situacije, in "zavajanje" chatbota.

Run: USE_UNIFIED_ROUTER=true python scripts/smoke_test_tricky.py
"""

import sys
import os

os.environ["USE_UNIFIED_ROUTER"] = "true"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared_core"))

from shared_core.app.services.routing.confidence import detect_intents, pick_primary_secondary
from shared_core.app.services.routing.unified_router import route, IntentType
from shared_core.app.services.routing.confidence import SwitchAction
from shared_core.app.services.session.unified_state import blank_unified_state, FlowType


class C:
    G = "\033[92m"
    R = "\033[91m"
    Y = "\033[93m"
    B = "\033[94m"
    M = "\033[95m"
    X = "\033[0m"
    BOLD = "\033[1m"


def test(name, msg, state=None, want_intent=None, want_action=None, min_conf=None, not_intent=None):
    """Run test. not_intent = intent it should NOT be."""
    if state is None:
        state = blank_unified_state()

    d = route(msg, state)
    ok = True
    errs = []

    if want_intent and d.primary_intent.value != want_intent:
        ok = False
        errs.append(f"intent: {d.primary_intent.value} ≠ {want_intent}")

    if not_intent and d.primary_intent.value == not_intent:
        ok = False
        errs.append(f"intent should NOT be {not_intent}")

    if want_action and d.action.value != want_action:
        ok = False
        errs.append(f"action: {d.action.value} ≠ {want_action}")

    if min_conf and d.confidence < min_conf:
        ok = False
        errs.append(f"conf: {d.confidence:.2f} < {min_conf}")

    status = f"{C.G}✓{C.X}" if ok else f"{C.R}✗{C.X}"
    print(f"  {status} {name}")
    if errs:
        for e in errs:
            print(f"      {C.Y}→ {e}{C.X}")
        print(f"      {C.M}msg: \"{msg}\"{C.X}")
        print(f"      {C.M}got: intent={d.primary_intent.value}, conf={d.confidence:.2f}, action={d.action.value}{C.X}")

    return ok


def in_table_flow():
    s = blank_unified_state()
    s["flow"] = FlowType.RESERVATION_TABLE.value
    s["step"] = "date"
    return s


def in_room_flow():
    s = blank_unified_state()
    s["flow"] = FlowType.RESERVATION_ROOM.value
    s["step"] = "guests"
    return s


def run_tricky():
    print(f"\n{C.BOLD}{'='*70}{C.X}")
    print(f"{C.BOLD}TRICKY TEST - 20 ZVITIH SCENARIJEV{C.X}")
    print(f"{C.BOLD}{'='*70}{C.X}\n")

    p, f = 0, 0

    # ========== DVOUMNI POZDRAVI ==========
    print(f"{C.B}[1-3] DVOUMNI POZDRAVI{C.X}")

    # "Pozdravljeni" - pozdrav ali slovo?
    if test("1. 'Pozdravljeni' = GREETING ali GOODBYE?",
            "Pozdravljeni", want_intent="GOODBYE"):  # "pozdrav" je v GOODBYE
        p += 1
    else: f += 1

    # "Hvala za info" - hvala = legitimno GOODBYE v slovenščini
    if test("2. 'Hvala za informacije' - 'hvala' = GOODBYE (legitimno)",
            "Hvala za informacije", want_intent="GOODBYE"):  # In Slovenian, "hvala" often signals end of convo
        p += 1
    else: f += 1

    # "Lepo se imejte" - slovo brez ključnih besed
    if test("3. 'Lepo se imejte' - impliciten slovo",
            "Lepo se imejte", want_intent="GENERAL"):  # No keywords, should be GENERAL
        p += 1
    else: f += 1

    # ========== MEŠANI INTENTI ==========
    print(f"\n{C.B}[4-7] MEŠANI INTENTI (multiple things){C.X}")

    # Miza + vino v istem stavku
    if test("4. 'Mizo za 4, pa pokažite vinska karta'",
            "Mizo za 4 osebe, pa mi pokažite vinsko karto",
            want_intent="BOOKING_TABLE"):  # Primary should be booking
        p += 1
    else: f += 1

    # Vprašanje o sobi KI ZVENI kot info
    if test("5. 'Koliko stanejo sobe?' - cena sobe = INFO ali ROOM?",
            "Koliko stanejo vaše sobe?",
            want_intent="BOOKING_ROOM"):  # "sobe" should trigger room, not just INFO
        p += 1
    else: f += 1

    # Produkt + lokacija
    if test("6. 'Kje lahko kupim vaš pesto?' - lokacija+produkt",
            "Kje lahko kupim vaš pesto?",
            want_intent="PRODUCT", min_conf=0.9):  # Should be PRODUCT due to purchase boost
        p += 1
    else: f += 1

    # "A je še kaj prostega" - soba ali miza?
    if test("7. 'A je še kaj prostega za vikend?' - dvoumno",
            "A je še kaj prostega za vikend?",
            want_intent="GENERAL"):  # Ambiguous - no clear table/room keyword
        p += 1
    else: f += 1

    # ========== SKRITE REZERVACIJE ==========
    print(f"\n{C.B}[8-10] SKRITE REZERVACIJE{C.X}")

    # Brez besede "rezervacija"
    if test("8. 'Prišli bi na kosilo v soboto' - implicitna miza",
            "Prišli bi na kosilo v soboto, 6 oseb",
            want_intent="BOOKING_TABLE"):  # "kosilo" should suggest table
        p += 1
    else: f += 1

    # Prenocitev brez "soba"
    if test("9. 'Bi prespali 2 noči' - implicitna soba",
            "Bi prespali 2 noči",
            want_intent="BOOKING_ROOM"):  # Should detect room intent
        p += 1
    else: f += 1

    # "Kaj pa če pridemo" - intent unclear
    if test("10. 'Kaj pa če pridemo v nedeljo?' - ni jasno kaj",
            "Kaj pa če pridemo v nedeljo?",
            want_intent="GENERAL"):  # Too vague
        p += 1
    else: f += 1

    # ========== MED FLOWOM - ZAVAJANJE ==========
    print(f"\n{C.B}[11-14] ZAVAJANJE MED REZERVACIJO{C.X}")

    # "Da" ki ni affirmative (ima več konteksta)
    if test("11. 'Da, pa še vprašanje o parkiranju' med flowom",
            "Da, pa še vprašanje - a imate parking?",
            state=in_table_flow(),
            want_intent="INFO",  # Should catch the INFO question
            want_action="soft_interrupt"):
        p += 1
    else: f += 1

    # "Ne" ki ni negativno (negacija v vprašanju)
    if test("12. 'Ne vem še točno datum' - ni preklic",
            "Ne vem še točno datum",
            state=in_table_flow(),
            not_intent="NEGATIVE"):  # Should NOT be NEGATIVE
        p += 1
    else: f += 1

    # Switch med flowom - soba namesto mize
    if test("13. 'Ej pravzaprav bi raje prenocil' med mizo flowom",
            "Ej pravzaprav bi raje prenocil",
            state=in_table_flow(),
            want_intent="BOOKING_ROOM"):  # Should switch to room
        p += 1
    else: f += 1

    # Kompleksno vprašanje med flowom
    if test("14. 'A mate WiFi pa koliko je zajtrk?' - dual INFO",
            "A mate WiFi pa koliko je zajtrk?",
            state=in_room_flow(),
            want_intent="INFO",
            want_action="soft_interrupt"):
        p += 1
    else: f += 1

    # ========== TYPOS IN SLENG ==========
    print(f"\n{C.B}[15-17] TYPOS IN SLENG{C.X}")

    # Typo v rezervaciji
    if test("15. 'Bi rezeroiral mizo' - typo",
            "Bi rezeroiral mizo za soboto",
            want_intent="BOOKING_TABLE"):  # "mizo" should still work
        p += 1
    else: f += 1

    # Sleng
    if test("16. 'Kva mate za jest?' - sleng",
            "Kva mate za jest?",
            want_intent="MENU"):  # Should still catch menu
        p += 1
    else: f += 1

    # Mix slovenščina + angleščina
    if test("17. 'Reserviram pa a table please' - mešano",
            "Reserviram a table please",
            want_intent="BOOKING_TABLE"):
        p += 1
    else: f += 1

    # ========== EDGE CASES ==========
    print(f"\n{C.B}[18-20] EXTREME EDGE CASES{C.X}")

    # Samo emoji
    if test("18. '👍' - samo emoji",
            "👍",
            want_intent="GENERAL"):  # Can't interpret emoji
        p += 1
    else: f += 1

    # Zelo dolg message
    long_msg = "Torej jaz bi rad rezerviral mizo za soboto popoldan nekje okrog 14h za 6 oseb, če je možno pri oknu, partner ima alergijo na orehe, otroka sta 5 in 8 let, prišli bi z avtom tako da rabimo parking, pa še vprašanje imate kak veganski meni ker žena ne je mesa, pa še to ali lahko prinesemo torto za rojstni dan?"
    if test("19. Zelo dolg message z več intenti",
            long_msg,
            want_intent="BOOKING_TABLE"):  # Primary should still be table
        p += 1
    else: f += 1

    # Prazen message
    if test("20. Prazen string",
            "",
            want_intent="GENERAL"):
        p += 1
    else: f += 1

    # ========== SUMMARY ==========
    print(f"\n{C.BOLD}{'='*70}{C.X}")
    total = p + f
    pct = (p / total * 100) if total > 0 else 0

    if f == 0:
        print(f"{C.G}{C.BOLD}VSI TESTI USPELI: {p}/{total} (100%){C.X}")
    elif pct >= 80:
        print(f"{C.Y}REZULTAT: {p}/{total} ({pct:.0f}%) - DOBRO{C.X}")
    else:
        print(f"{C.R}REZULTAT: {p}/{total} ({pct:.0f}%) - POTREBNE IZBOLJŠAVE{C.X}")

    print(f"{C.BOLD}{'='*70}{C.X}\n")

    return f == 0


if __name__ == "__main__":
    success = run_tricky()
    sys.exit(0 if success else 1)
