#!/usr/bin/env python3
"""
100 scenarios for unified routing (smoke + complex).
Run: python scripts/test_routing_100.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared_core"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared_core.app.services.routing import IntentType, SwitchAction, route
from shared_core.app.services.session import blank_unified_state, FlowType


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"


def expect(name, message, flow, intent, action):
    state = blank_unified_state()
    state["flow"] = flow
    decision = route(message, state)
    ok = decision.primary_intent == intent and decision.action == action
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if ok else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    if not ok:
        print(
            f"{status} | {name}\n"
            f"   msg={message}\n"
            f"   got={decision.primary_intent}/{decision.action} conf={decision.confidence:.2f}\n"
            f"   exp={intent}/{action}"
        )
    else:
        print(f"{status} | {name}")
    return ok


def run():
    ok_all = True

    # --- SMOKE (idle) ---
    smoke = [
        ("greet-1", "zdravo", FlowType.IDLE.value, IntentType.GREETING, SwitchAction.IGNORE),
        ("greet-2", "dober dan", FlowType.IDLE.value, IntentType.GREETING, SwitchAction.IGNORE),
        ("bye-1", "hvala", FlowType.IDLE.value, IntentType.GOODBYE, SwitchAction.IGNORE),
        ("info-1", "kdaj ste odprti", FlowType.IDLE.value, IntentType.INFO, SwitchAction.IGNORE),
        ("info-2", "kje se nahajate", FlowType.IDLE.value, IntentType.INFO, SwitchAction.IGNORE),
        ("info-3", "ali imate parking", FlowType.IDLE.value, IntentType.INFO, SwitchAction.IGNORE),
        ("tour-1", "je v bližini smučišče", FlowType.IDLE.value, IntentType.INFO, SwitchAction.IGNORE),
        ("prod-1", "imate čemažev pesto", FlowType.IDLE.value, IntentType.PRODUCT, SwitchAction.IGNORE),
        ("prod-2", "kakšne namaze imate", FlowType.IDLE.value, IntentType.PRODUCT, SwitchAction.IGNORE),
        ("prod-3", "katalog izdelkov", FlowType.IDLE.value, IntentType.PRODUCT, SwitchAction.IGNORE),
        ("wine-1", "katera rdeča vina imate", FlowType.IDLE.value, IntentType.WINE, SwitchAction.IGNORE),
        ("menu-1", "kaj ponujate za kosilo", FlowType.IDLE.value, IntentType.MENU, SwitchAction.IGNORE),
        ("inq-1", "teambuilding", FlowType.IDLE.value, IntentType.INQUIRY, SwitchAction.IGNORE),
        ("book-t-1", "rad bi rezerviral mizo", FlowType.IDLE.value, IntentType.BOOKING_TABLE, SwitchAction.IGNORE),
        ("book-r-1", "rad bi rezerviral sobo", FlowType.IDLE.value, IntentType.BOOKING_ROOM, SwitchAction.IGNORE),
    ]

    # --- COMPLEX (active flow) ---
    complex_cases = [
        ("room->info", "ali imate wifi", FlowType.RESERVATION_ROOM.value, IntentType.INFO, SwitchAction.SOFT_INTERRUPT),
        ("room->product", "imate čemažev pesto", FlowType.RESERVATION_ROOM.value, IntentType.PRODUCT, SwitchAction.SOFT_INTERRUPT),
        ("room->wine", "rdeče vino?", FlowType.RESERVATION_ROOM.value, IntentType.WINE, SwitchAction.SOFT_INTERRUPT),
        ("room->menu", "kakšen meni je danes", FlowType.RESERVATION_ROOM.value, IntentType.MENU, SwitchAction.SOFT_INTERRUPT),
        ("room->inq", "teambuilding", FlowType.RESERVATION_ROOM.value, IntentType.INQUIRY, SwitchAction.HARD_SWITCH),
        ("room->table", "rad bi rezerviral mizo", FlowType.RESERVATION_ROOM.value, IntentType.BOOKING_TABLE, SwitchAction.HARD_SWITCH),
        ("room->room", "rad bi rezerviral sobo", FlowType.RESERVATION_ROOM.value, IntentType.BOOKING_ROOM, SwitchAction.IGNORE),
        ("table->info", "kje ste", FlowType.RESERVATION_TABLE.value, IntentType.INFO, SwitchAction.SOFT_INTERRUPT),
        ("table->product", "marmelada", FlowType.RESERVATION_TABLE.value, IntentType.PRODUCT, SwitchAction.SOFT_INTERRUPT),
        ("table->inq", "poroka", FlowType.RESERVATION_TABLE.value, IntentType.INQUIRY, SwitchAction.HARD_SWITCH),
        ("table->room", "rad bi rezerviral sobo", FlowType.RESERVATION_TABLE.value, IntentType.BOOKING_ROOM, SwitchAction.HARD_SWITCH),
        ("table->table", "rad bi rezerviral mizo", FlowType.RESERVATION_TABLE.value, IntentType.BOOKING_TABLE, SwitchAction.IGNORE),
    ]

    # Add variants to reach 100
    variants = []
    for i, msg in enumerate(
        [
            "ali imate parkirišče",
            "kje ste",
            "kakšen je jedilnik",
            "imate suho salamo",
            "bi kupil marmelado",
            "kateri termi so v bližini",
            "ali je zajtrk vključen",
            "kakšne sobe imate",
            "kolikšna je cena sobe",
            "kakšne namaze imate",
            "ali imate penino",
            "meni za vikend",
            "naročil bi pesto",
            "rad bi rezerviral mizo za 4",
            "rad bi rezerviral sobo za 3 nočitve",
            "ali imate otroško igrišče",
            "ali imate wifi",
            "koliko sob imate",
            "ali ste odprti ob ponedeljkih",
            "kje se nahajate",
        ],
        1,
    ):
        # per-message expected intent
        if msg == "kakšen je jedilnik":
            expected = IntentType.MENU
        elif msg == "imate suho salamo":
            expected = IntentType.PRODUCT
        elif msg == "bi kupil marmelado":
            expected = IntentType.PRODUCT
        elif msg == "kakšne namaze imate":
            expected = IntentType.PRODUCT
        elif msg == "ali imate penino":
            expected = IntentType.WINE
        elif msg == "meni za vikend":
            expected = IntentType.MENU
        elif msg == "naročil bi pesto":
            expected = IntentType.PRODUCT
        elif msg.startswith("rad bi rezerviral mizo"):
            expected = IntentType.BOOKING_TABLE
        elif msg.startswith("rad bi rezerviral sobo"):
            expected = IntentType.BOOKING_ROOM
        else:
            expected = IntentType.INFO
        variants.append((f"idle-var-{i}", msg, FlowType.IDLE.value, expected, SwitchAction.IGNORE))

    # ensure product variants are classified as product
    prod_variants = [
        ("idle-prod-1", "pesto cena", FlowType.IDLE.value, IntentType.PRODUCT, SwitchAction.IGNORE),
        ("idle-prod-2", "marmelada", FlowType.IDLE.value, IntentType.PRODUCT, SwitchAction.IGNORE),
        ("idle-prod-3", "sirup", FlowType.IDLE.value, IntentType.PRODUCT, SwitchAction.IGNORE),
        ("idle-prod-4", "katalog", FlowType.IDLE.value, IntentType.PRODUCT, SwitchAction.IGNORE),
        ("idle-prod-5", "izdelki", FlowType.IDLE.value, IntentType.PRODUCT, SwitchAction.IGNORE),
    ]

    # complex flow variants
    complex_more = []
    for i, msg in enumerate(
        [
            "ali imate parking",
            "kje je naslov",
            "kakšna je večerja",
            "rdeče vino",
            "meni",
            "teambuilding",
            "poroka",
            "rad bi rezerviral mizo",
            "rad bi rezerviral sobo",
            "marmelada",
        ],
        1,
    ):
        complex_more.append((f"flow-room-var-{i}", msg, FlowType.RESERVATION_ROOM.value,
                             IntentType.INFO if i in {1,2,3} else
                             IntentType.WINE if i == 4 else
                             IntentType.MENU if i == 5 else
                             IntentType.INQUIRY if i in {6,7} else
                             IntentType.BOOKING_TABLE if i == 8 else
                             IntentType.BOOKING_ROOM if i == 9 else
                             IntentType.PRODUCT,
                             SwitchAction.SOFT_INTERRUPT if i in {1,2,3,4,5,10} else
                             SwitchAction.HARD_SWITCH if i in {6,7,8} else
                             SwitchAction.IGNORE))

    scenarios = smoke + complex_cases + variants + prod_variants + complex_more

    # Pad to 100 with simple neutral cases
    while len(scenarios) < 100:
        idx = len(scenarios) + 1
        scenarios.append((f"idle-neutral-{idx}", "kako deluje rezervacija", FlowType.IDLE.value, IntentType.INFO, SwitchAction.IGNORE))

    print(f"Running {len(scenarios)} scenarios...")
    for name, msg, flow, intent, action in scenarios[:100]:
        ok_all = expect(name, msg, flow, intent, action) and ok_all

    print("\nRESULT:", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(run())
