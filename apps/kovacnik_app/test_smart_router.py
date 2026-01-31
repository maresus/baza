"""
Test Smart Router z realnimi primeri ki so prej failali.
"""

import os
import sys

# Dodaj path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.smart_router import classify_intent, generate_smart_response, smart_route

def test_scenarios():
    """Testiraj scenarije ki so prej failali."""

    print("=" * 60)
    print("SMART ROUTER TEST")
    print("=" * 60)

    # === SCENARIJ 1: Pesto vprašanje med booking flowom ===
    print("\n--- SCENARIJ 1: 'a mate pesto?' med booking flowom ---")
    state1 = {
        "step": "awaiting_table_date",
        "type": "table"
    }
    result1 = smart_route("a mate pesto?", state1)
    print(f"Intent: {result1['intent']}")
    print(f"Handled: {result1['handled']}")
    print(f"Response:\n{result1['response']}")
    print(f"Continue booking: {result1['continue_booking']}")

    # === SCENARIJ 2: "zanima me" po vprašanju o pestu ===
    print("\n--- SCENARIJ 2: 'zanima me' po vprašanju o pestu ---")
    state2 = {
        "step": "awaiting_table_date",
        "type": "table"
    }
    history2 = [
        {"role": "user", "content": "Rad bi rezerviral mizo"},
        {"role": "assistant", "content": "Za kateri datum?"},
        {"role": "user", "content": "a mate pesto?"},
        {"role": "assistant", "content": "Pesto imamo! Vas zanima?"}
    ]
    result2 = smart_route("zanima me", state2, history2)
    print(f"Intent: {result2['intent']}")
    print(f"Handled: {result2['handled']}")
    print(f"Response:\n{result2['response']}")

    # === SCENARIJ 3: Zajčki med room bookingom ===
    print("\n--- SCENARIJ 3: 'a imate zajčke?' med room bookingom ---")
    state3 = {
        "step": "awaiting_room_guests",
        "type": "room",
        "date": "15.02.2025"
    }
    result3 = smart_route("a imate zajčke?", state3)
    print(f"Intent: {result3['intent']}")
    print(f"Handled: {result3['handled']}")
    print(f"Response:\n{result3['response']}")
    print(f"Continue booking: {result3['continue_booking']}")

    # === SCENARIJ 4: Composite - "2 gosta, a mate pesto?" ===
    print("\n--- SCENARIJ 4: '2 gosta, a mate pesto?' (composite) ---")
    state4 = {
        "step": "awaiting_table_guests",
        "type": "table",
        "date": "15.02.2025",
        "time": "12:00"
    }
    result4 = smart_route("2 gosta, a mate pesto?", state4)
    print(f"Intent: {result4['intent']}")
    print(f"Booking data: {result4['booking_data']}")
    print(f"Response:\n{result4['response']}")

    # === SCENARIJ 5: Normalen booking odgovor (ni interrupt) ===
    print("\n--- SCENARIJ 5: '15.02.2025' (booking odgovor, ni interrupt) ---")
    state5 = {
        "step": "awaiting_table_date",
        "type": "table"
    }
    result5 = smart_route("15.02.2025", state5)
    print(f"Intent: {result5['intent']}")
    print(f"Handled: {result5['handled']}")
    print(f"Continue booking: {result5['continue_booking']}")
    print(f"Booking data: {result5['booking_data']}")

    # === SCENARIJ 6: "mizo bi" med room bookingom (type switch) ===
    print("\n--- SCENARIJ 6: 'mizo bi rezerviral' med room bookingom ---")
    state6 = {
        "step": "awaiting_room_date",
        "type": "room"
    }
    result6 = smart_route("mizo bi rezerviral", state6)
    print(f"Intent: {result6['intent']}")
    print(f"Booking data: {result6['booking_data']}")

    print("\n" + "=" * 60)
    print("TEST KONČAN")
    print("=" * 60)


if __name__ == "__main__":
    test_scenarios()
