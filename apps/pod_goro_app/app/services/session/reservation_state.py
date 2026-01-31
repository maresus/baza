"""
Reservation state management.
"""

from typing import Optional


def blank_reservation_state() -> dict[str, Optional[str | int]]:
    """Return a blank reservation state dictionary."""
    return {
        "step": None,
        "type": None,
        "date": None,
        "time": None,
        "nights": None,
        "rooms": None,
        "people": None,
        "adults": None,
        "kids": None,
        "kids_ages": None,
        "name": None,
        "phone": None,
        "email": None,
        "location": None,
        "available_locations": None,
        "language": None,
        "dinner_people": None,
        "note": None,
        "availability": None,
    }


# Global reservation states per session
reservation_states: dict[str, dict[str, Optional[str | int]]] = {}


def get_reservation_state(session_id: str) -> dict[str, Optional[str | int]]:
    """Get or create reservation state for a session."""
    if session_id not in reservation_states:
        reservation_states[session_id] = blank_reservation_state()
    return reservation_states[session_id]


def reset_reservation_state(state: dict[str, Optional[str | int]]) -> None:
    """Reset reservation state to blank."""
    state.clear()
    state.update(blank_reservation_state())
