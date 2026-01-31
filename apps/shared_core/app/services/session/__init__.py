"""
Session module - reservation, inquiry, and unified state management.
"""

from .reservation_state import (
    blank_reservation_state,
    get_reservation_state,
    reset_reservation_state,
    reservation_states,
)
from .inquiry_state import (
    blank_inquiry_state,
    get_inquiry_state,
    reset_inquiry_state,
    inquiry_states,
)
from .unified_state import (
    FlowType,
    FlowStep,
    blank_unified_state,
    unified_states,
    get_unified_state,
    reset_unified_state,
    reset_flow,
    is_in_flow,
    get_current_flow,
    get_current_step,
    start_flow,
    advance_step,
    push_interrupt,
    pop_interrupt,
    get_reservation_data,
    get_inquiry_data,
)

__all__ = [
    # Reservation state (legacy)
    "blank_reservation_state",
    "get_reservation_state",
    "reset_reservation_state",
    "reservation_states",
    # Inquiry state (legacy)
    "blank_inquiry_state",
    "get_inquiry_state",
    "reset_inquiry_state",
    "inquiry_states",
    # Unified state (new)
    "FlowType",
    "FlowStep",
    "blank_unified_state",
    "unified_states",
    "get_unified_state",
    "reset_unified_state",
    "reset_flow",
    "is_in_flow",
    "get_current_flow",
    "get_current_step",
    "start_flow",
    "advance_step",
    "push_interrupt",
    "pop_interrupt",
    "get_reservation_data",
    "get_inquiry_data",
]
