"""
Inquiry state management.
"""

from typing import Optional


def blank_inquiry_state() -> dict[str, Optional[str]]:
    """Return a blank inquiry state dictionary."""
    return {
        "step": None,
        "details": "",
        "deadline": "",
        "contact_name": "",
        "contact_email": "",
        "contact_phone": "",
        "contact_raw": "",
    }


# Global inquiry states per session
inquiry_states: dict[str, dict[str, Optional[str]]] = {}


def get_inquiry_state(session_id: str) -> dict[str, Optional[str]]:
    """Get or create inquiry state for a session."""
    if session_id not in inquiry_states:
        inquiry_states[session_id] = blank_inquiry_state()
    return inquiry_states[session_id]


def reset_inquiry_state(state: dict[str, Optional[str]]) -> None:
    """Reset inquiry state to blank."""
    state.update(blank_inquiry_state())
