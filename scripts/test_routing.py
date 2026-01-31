import sys
from pathlib import Path

# Add kovacnik app to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "kovacnik_app"))

from app.services.routing import decide


def _state(step=None, type_=None):
    return {"step": step, "type": type_}


def _inquiry(step=None):
    return {"step": step}


CASES = [
    # INFO only
    ("info_opening", "Kdaj ste odprti?", _state(), _inquiry(), "ignore", "INFO"),
    ("info_monday", "Ali ste odprti ob ponedeljkih?", _state(), _inquiry(), "ignore", "INFO"),
    ("info_last", "Kdaj je zadnji prihod na kosilo?", _state(), _inquiry(), "ignore", "INFO"),
    ("info_address", "Kje ste doma?", _state(), _inquiry(), "ignore", "INFO"),
    ("info_parking", "A imate parking?", _state(), _inquiry(), "ignore", "INFO"),
    ("info_tourism", "Je v bližini smučišče?", _state(), _inquiry(), "ignore", "INFO"),

    # PRODUCT
    ("product_pesto", "Imate čemažev pesto?", _state(), _inquiry(), "ignore", "PRODUCT"),
    ("product_marmelada", "Kakšne marmelade prodajate?", _state(), _inquiry(), "ignore", "PRODUCT"),
    ("product_liker", "Kateri likerji so na voljo?", _state(), _inquiry(), "ignore", "PRODUCT"),
    ("product_link", "Daj link do trgovine", _state(), _inquiry(), "ignore", "PRODUCT"),

    # Booking table
    ("booking_table", "Rad bi rezerviral mizo", _state(), _inquiry(), "ignore", "BOOKING_TABLE"),
    ("booking_table_alt", "Bi rezerviral mizo za jutri", _state(), _inquiry(), "ignore", "BOOKING_TABLE"),
    ("booking_table_inquiry", "Rezervacija mize", _state(), _inquiry(), "ignore", "BOOKING_TABLE"),

    # Booking room
    ("booking_room", "Rad bi rezerviral sobo", _state(), _inquiry(), "ignore", "BOOKING_ROOM"),
    ("booking_room_alt", "Potrebujem sobo za vikend", _state(), _inquiry(), "ignore", "BOOKING_ROOM"),

    # Inquiry
    ("inquiry_teambuilding", "Bi organiziral teambuilding", _state(), _inquiry(), "ignore", "INQUIRY"),
    ("inquiry_wedding", "Ali imate prostor za poroko?", _state(), _inquiry(), "ignore", "INQUIRY"),

    # Mixed: booking + product in flow
    ("mix_pesto_in_booking", "Imate pesto?", _state(step="awaiting_table_time", type_="table"), _inquiry(), "soft_interrupt", "PRODUCT"),
    ("mix_info_in_booking", "A imate parking?", _state(step="awaiting_room_date", type_="room"), _inquiry(), "soft_interrupt", "INFO"),
    ("mix_tourism_in_booking", "Je smučišče v bližini?", _state(step="awaiting_room_date", type_="room"), _inquiry(), "soft_interrupt", "INFO"),

    # Inquiry in booking -> hard switch
    ("teambuilding_switch", "Bi organiziral teambuilding", _state(step="awaiting_table_date", type_="table"), _inquiry(), "hard_switch", "INQUIRY"),

    # Switch booking type
    ("switch_room_from_table", "Rad bi rezerviral sobo", _state(step="awaiting_table_date", type_="table"), _inquiry(), "hard_switch", "BOOKING_ROOM"),
    ("switch_table_from_room", "Rad bi rezerviral mizo", _state(step="awaiting_room_date", type_="room"), _inquiry(), "hard_switch", "BOOKING_TABLE"),

    # Greetings/Goodbye
    ("greeting", "Živjo", _state(), _inquiry(), "ignore", "GREETING"),
    ("goodbye", "Hvala, adijo", _state(), _inquiry(), "ignore", "GOODBYE"),

    # Edge: short date/time during flow should ignore
    ("date_only_in_flow", "21.2.2026", _state(step="awaiting_table_date", type_="table"), _inquiry(), "ignore", "GENERAL"),
    ("time_only_in_flow", "14:00", _state(step="awaiting_table_time", type_="table"), _inquiry(), "ignore", "GENERAL"),

    # Mixed single message (product + booking)
    ("mixed_single", "Rezerviral bi mizo in kupil marmelado", _state(), _inquiry(), "ignore", "BOOKING_TABLE"),

    # Explicit product typo
    ("product_typo", "cemazev pesto bi mel", _state(), _inquiry(), "ignore", "PRODUCT"),

    # General
    ("general", "Kako si?", _state(), _inquiry(), "ignore", "GENERAL"),
]

if len(CASES) < 30:
    print("Need 30 scenarios, only have", len(CASES))
    sys.exit(1)

FAILED = []

for name, message, state, inquiry_state, expected_action, expected_primary in CASES:
    decision = decide(message, state, inquiry_state)
    if decision["action"] != expected_action:
        FAILED.append((name, "action", expected_action, decision["action"]))
    if expected_primary and decision["primary_intent"] != expected_primary:
        FAILED.append((name, "primary", expected_primary, decision["primary_intent"]))

if FAILED:
    print("FAILED:")
    for item in FAILED:
        print(item)
    sys.exit(1)

print("OK: all routing scenarios passed")
