from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List


class FlowType(str, Enum):
    IDLE = "idle"
    RESERVATION_TABLE = "reservation_table"
    RESERVATION_ROOM = "reservation_room"
    INQUIRY = "inquiry"


class FlowStep(str, Enum):
    DATE = "date"
    TIME = "time"
    GUESTS = "guests"
    CONTACT = "contact"
    CONFIRM = "confirm"


def blank_unified_state() -> Dict[str, Any]:
    return {
        "flow": FlowType.IDLE.value,
        "step": None,
        "data": {},
        "last_intent": None,
        "pending_question": None,
        "interrupts": [],
    }

unified_states: Dict[str, Dict[str, Any]] = {}


def get_unified_state(session_or_ctx: Any) -> Dict[str, Any]:
    if isinstance(session_or_ctx, dict):
        state = session_or_ctx.get("unified_state")
        if not isinstance(state, dict):
            state = blank_unified_state()
            session_or_ctx["unified_state"] = state
        return state
    session_id = str(session_or_ctx)
    if session_id not in unified_states:
        unified_states[session_id] = blank_unified_state()
    return unified_states[session_id]


def set_unified_flow(state: Dict[str, Any], flow: str, step: str | None = None) -> None:
    state["flow"] = flow
    if step is not None:
        state["step"] = step


def update_unified_state(state: Dict[str, Any], **kwargs: Any) -> None:
    for key, value in kwargs.items():
        state[key] = value


def reset_unified_state(state: Dict[str, Any]) -> None:
    state.clear()
    state.update(blank_unified_state())


def reset_flow(state: Dict[str, Any]) -> None:
    state["flow"] = FlowType.IDLE.value
    state["step"] = None


def is_in_flow(state: Dict[str, Any]) -> bool:
    return state.get("flow") not in (None, FlowType.IDLE.value)


def get_current_flow(state: Dict[str, Any]) -> str:
    return state.get("flow", FlowType.IDLE.value)


def get_current_step(state: Dict[str, Any]) -> str | None:
    return state.get("step")


def start_flow(state: Dict[str, Any], flow: FlowType | str) -> None:
    state["flow"] = flow.value if isinstance(flow, FlowType) else flow
    if state.get("step") is None:
        state["step"] = FlowStep.DATE.value


def advance_step(state: Dict[str, Any], step: FlowStep | str) -> None:
    state["step"] = step.value if isinstance(step, FlowStep) else step


def push_interrupt(state: Dict[str, Any], intent: str) -> None:
    interrupts: List[str] = state.setdefault("interrupts", [])
    interrupts.append(intent)


def pop_interrupt(state: Dict[str, Any]) -> str | None:
    interrupts: List[str] = state.get("interrupts", [])
    return interrupts.pop() if interrupts else None


def get_reservation_data(state: Dict[str, Any]) -> Dict[str, Any]:
    return state.setdefault("data", {}).setdefault("reservation", {})


def get_inquiry_data(state: Dict[str, Any]) -> Dict[str, Any]:
    return state.setdefault("data", {}).setdefault("inquiry", {})
