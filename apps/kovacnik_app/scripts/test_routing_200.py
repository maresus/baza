#!/usr/bin/env python3
"""
200 scenarios for unified routing (advanced).
Run: python scripts/test_routing_200.py
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
    scenarios = []

    # Idle intents (50)
    idle_msgs = [
        ("greet", "zdravo", IntentType.GREETING),
        ("bye", "hvala", IntentType.GOODBYE),
        ("info-hours", "kdaj ste odprti", IntentType.INFO),
        ("info-parking", "ali imate parking", IntentType.INFO),
        ("info-address", "kje se nahajate", IntentType.INFO),
        ("info-breakfast", "ali je zajtrk vključen", IntentType.INFO),
        ("info-rooms", "koliko sob imate", IntentType.INFO),
        ("info-children", "ali imate igrišče", IntentType.INFO),
        ("tour-ski", "je kje v bližini smučišče", IntentType.INFO),
        ("tour-therme", "katere terme so v bližini", IntentType.INFO),
        ("product-pesto", "imate čemažev pesto", IntentType.PRODUCT),
        ("product-namaz", "kakšne namaze imate", IntentType.PRODUCT),
        ("product-marmelada", "marmelada", IntentType.PRODUCT),
        ("product-catalog", "katalog izdelkov", IntentType.PRODUCT),
        ("product-buy", "rad bi kupil sirup", IntentType.PRODUCT),
        ("wine-red", "katera rdeča vina imate", IntentType.WINE),
        ("wine-sparkling", "imate penino", IntentType.WINE),
        ("menu-weekend", "kaj ponujate za vikend kosila", IntentType.MENU),
        ("menu-today", "meni za vikend", IntentType.MENU),
        ("inq-team", "teambuilding", IntentType.INQUIRY),
        ("inq-wedding", "poroka", IntentType.INQUIRY),
        ("book-table", "rad bi rezerviral mizo", IntentType.BOOKING_TABLE),
        ("book-room", "rad bi rezerviral sobo", IntentType.BOOKING_ROOM),
    ]
    while len(idle_msgs) < 50:
        idx = len(idle_msgs) + 1
        idle_msgs.append((f"info-var-{idx}", f"kakšen je vaš kontakt {idx}", IntentType.INFO))

    for name, msg, intent in idle_msgs:
        scenarios.append((f"idle-{name}", msg, FlowType.IDLE.value, intent, SwitchAction.IGNORE))

    # Active room flow (75)
    room_flow_msgs = [
        ("info", "ali imate wifi", IntentType.INFO, SwitchAction.SOFT_INTERRUPT),
        ("product", "imate pesto", IntentType.PRODUCT, SwitchAction.SOFT_INTERRUPT),
        ("wine", "rdeče vino", IntentType.WINE, SwitchAction.SOFT_INTERRUPT),
        ("menu", "meni", IntentType.MENU, SwitchAction.SOFT_INTERRUPT),
        ("switch-table", "rad bi rezerviral mizo", IntentType.BOOKING_TABLE, SwitchAction.HARD_SWITCH),
        ("switch-inq", "teambuilding", IntentType.INQUIRY, SwitchAction.HARD_SWITCH),
        ("same-room", "rad bi rezerviral sobo", IntentType.BOOKING_ROOM, SwitchAction.IGNORE),
    ]
    for i in range(1, 69):
        if i % 7 == 0:
            room_flow_msgs.append((f"room-inq-{i}", "poroka", IntentType.INQUIRY, SwitchAction.HARD_SWITCH))
        elif i % 5 == 0:
            room_flow_msgs.append((f"room-table-{i}", "rezerviral bi mizo", IntentType.BOOKING_TABLE, SwitchAction.HARD_SWITCH))
        elif i % 4 == 0:
            room_flow_msgs.append((f"room-product-{i}", "marmelada", IntentType.PRODUCT, SwitchAction.SOFT_INTERRUPT))
        elif i % 3 == 0:
            room_flow_msgs.append((f"room-info-{i}", "kdaj ste odprti", IntentType.INFO, SwitchAction.SOFT_INTERRUPT))
        else:
            room_flow_msgs.append((f"room-wine-{i}", "belo vino", IntentType.WINE, SwitchAction.SOFT_INTERRUPT))

    for name, msg, intent, action in room_flow_msgs[:75]:
        scenarios.append((f"room-{name}", msg, FlowType.RESERVATION_ROOM.value, intent, action))

    # Active table flow (75)
    table_flow_msgs = [
        ("info", "kje ste", IntentType.INFO, SwitchAction.SOFT_INTERRUPT),
        ("product", "namaz", IntentType.PRODUCT, SwitchAction.SOFT_INTERRUPT),
        ("wine", "penina", IntentType.WINE, SwitchAction.SOFT_INTERRUPT),
        ("menu", "kaj ponujate", IntentType.MENU, SwitchAction.SOFT_INTERRUPT),
        ("switch-room", "rad bi rezerviral sobo", IntentType.BOOKING_ROOM, SwitchAction.HARD_SWITCH),
        ("switch-inq", "catering", IntentType.INQUIRY, SwitchAction.HARD_SWITCH),
        ("same-table", "rad bi rezerviral mizo", IntentType.BOOKING_TABLE, SwitchAction.IGNORE),
    ]
    for i in range(1, 69):
        if i % 7 == 0:
            table_flow_msgs.append((f"table-inq-{i}", "dogodek", IntentType.INQUIRY, SwitchAction.HARD_SWITCH))
        elif i % 5 == 0:
            table_flow_msgs.append((f"table-room-{i}", "rezerviral bi sobo", IntentType.BOOKING_ROOM, SwitchAction.HARD_SWITCH))
        elif i % 4 == 0:
            table_flow_msgs.append((f"table-product-{i}", "sirup", IntentType.PRODUCT, SwitchAction.SOFT_INTERRUPT))
        elif i % 3 == 0:
            table_flow_msgs.append((f"table-info-{i}", "ali imate parking", IntentType.INFO, SwitchAction.SOFT_INTERRUPT))
        else:
            table_flow_msgs.append((f"table-wine-{i}", "rdečo vino", IntentType.WINE, SwitchAction.SOFT_INTERRUPT))

    for name, msg, intent, action in table_flow_msgs[:75]:
        scenarios.append((f"table-{name}", msg, FlowType.RESERVATION_TABLE.value, intent, action))

    # Trim to 200
    scenarios = scenarios[:200]

    print(f"Running {len(scenarios)} scenarios...")
    for name, msg, flow, intent, action in scenarios:
        ok_all = expect(name, msg, flow, intent, action) and ok_all

    print("\nRESULT:", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(run())
