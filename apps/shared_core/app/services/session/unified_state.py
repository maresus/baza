"""
Unified Session State - Single source of truth for all conversation state.

Replaces: reservation_states, inquiry_states, availability_context
"""

from typing import Any, Optional
from enum import Enum


class FlowType(str, Enum):
    """Active conversation flow type."""
    IDLE = "idle"
    RESERVATION_TABLE = "reservation_table"
    RESERVATION_ROOM = "reservation_room"
    INQUIRY = "inquiry"


class FlowStep(str, Enum):
    """Steps within a flow."""
    # Common
    NONE = "none"

    # Reservation steps
    DATE = "date"
    TIME = "time"
    GUESTS = "guests"
    CONTACT = "contact"
    CONFIRM = "confirm"

    # Inquiry steps
    DETAILS = "details"
    DEADLINE = "deadline"
    CONTACT_INFO = "contact_info"


def blank_unified_state() -> dict[str, Any]:
    """Return a blank unified session state."""
    return {
        # Flow control
        "flow": FlowType.IDLE.value,
        "step": FlowStep.NONE.value,

        # Reservation data (used for both table and room)
        "reservation": {
            "type": None,          # "table" or "room"
            "date": None,
            "end_date": None,      # For room multi-night stays
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
            "dinner_people": None,
            "note": None,
            "availability": None,
        },

        # Inquiry data
        "inquiry": {
            "details": "",
            "deadline": "",
            "contact_name": "",
            "contact_email": "",
            "contact_phone": "",
            "contact_raw": "",
        },

        # Context tracking
        "last_intent": None,
        "pending_question": None,
        "language": "si",

        # Interrupt handling
        "interrupt_stack": [],  # Stack of interrupted flows

        # Conversation context
        "last_product_query": None,
        "last_wine_query": None,
        "last_info_query": None,
        "last_menu_query": False,
        "last_shown_products": [],
    }


# Global unified states per session
unified_states: dict[str, dict[str, Any]] = {}


def get_unified_state(session_id: str) -> dict[str, Any]:
    """Get or create unified state for a session."""
    if session_id not in unified_states:
        unified_states[session_id] = blank_unified_state()
    return unified_states[session_id]


def reset_unified_state(state: dict[str, Any]) -> None:
    """Reset unified state to blank."""
    state.clear()
    state.update(blank_unified_state())


def reset_flow(state: dict[str, Any]) -> None:
    """Reset only the current flow, keeping context."""
    state["flow"] = FlowType.IDLE.value
    state["step"] = FlowStep.NONE.value
    state["reservation"] = blank_unified_state()["reservation"]
    state["inquiry"] = blank_unified_state()["inquiry"]
    state["pending_question"] = None
    state["interrupt_stack"] = []


def is_in_flow(state: dict[str, Any]) -> bool:
    """Check if currently in an active flow."""
    return state.get("flow") != FlowType.IDLE.value


def get_current_flow(state: dict[str, Any]) -> Optional[str]:
    """Get the current flow type, or None if idle."""
    flow = state.get("flow", FlowType.IDLE.value)
    return flow if flow != FlowType.IDLE.value else None


def get_current_step(state: dict[str, Any]) -> Optional[str]:
    """Get the current step, or None if not in a flow."""
    if not is_in_flow(state):
        return None
    step = state.get("step", FlowStep.NONE.value)
    return step if step != FlowStep.NONE.value else None


def start_flow(state: dict[str, Any], flow_type: FlowType, initial_step: FlowStep = FlowStep.DATE) -> None:
    """Start a new flow."""
    state["flow"] = flow_type.value
    state["step"] = initial_step.value
    state["interrupt_stack"] = []


def advance_step(state: dict[str, Any], new_step: FlowStep) -> None:
    """Move to the next step in the current flow."""
    state["step"] = new_step.value


def push_interrupt(state: dict[str, Any]) -> None:
    """Save current flow state before handling interrupt."""
    if is_in_flow(state):
        state["interrupt_stack"].append({
            "flow": state["flow"],
            "step": state["step"],
            "pending_question": state.get("pending_question"),
        })


def pop_interrupt(state: dict[str, Any]) -> Optional[dict]:
    """Restore previous flow state after handling interrupt."""
    if state["interrupt_stack"]:
        interrupted = state["interrupt_stack"].pop()
        state["flow"] = interrupted["flow"]
        state["step"] = interrupted["step"]
        state["pending_question"] = interrupted.get("pending_question")
        return interrupted
    return None


# Backwards compatibility functions
def get_reservation_data(state: dict[str, Any]) -> dict:
    """Get reservation data from unified state (backwards compat)."""
    data = state.get("reservation", {}).copy()
    data["step"] = state.get("step") if state.get("flow") in [FlowType.RESERVATION_TABLE.value, FlowType.RESERVATION_ROOM.value] else None
    data["type"] = "table" if state.get("flow") == FlowType.RESERVATION_TABLE.value else ("room" if state.get("flow") == FlowType.RESERVATION_ROOM.value else None)
    return data


def get_inquiry_data(state: dict[str, Any]) -> dict:
    """Get inquiry data from unified state (backwards compat)."""
    data = state.get("inquiry", {}).copy()
    data["step"] = state.get("step") if state.get("flow") == FlowType.INQUIRY.value else None
    return data
