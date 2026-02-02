from __future__ import annotations

from typing import Any, Dict, Optional


def _blank_unified_state() -> Dict[str, Any]:
    return {
        "flow": "idle",  # idle | reservation_table | reservation_room | inquiry
        "step": None,
        "data": {},  # reservation, inquiry, availability
        "last_intent": "",
        "pending_question": "",
    }


_SESSION_STATES: Dict[str, Dict[str, Any]] = {}


def get_unified_state(session_id: str) -> Dict[str, Any]:
    if session_id not in _SESSION_STATES:
        _SESSION_STATES[session_id] = _blank_unified_state()
    return _SESSION_STATES[session_id]


def reset_unified_state(state: Dict[str, Any]) -> None:
    state.update(_blank_unified_state())


def set_flow(state: Dict[str, Any], flow: str, step: Optional[str] = None) -> None:
    state["flow"] = flow
    state["step"] = step


def ensure_flow_data(state: Dict[str, Any], key: str, default: Any) -> Any:
    if key not in state["data"]:
        state["data"][key] = default
    return state["data"][key]


def set_last_intent(state: Dict[str, Any], intent: str) -> None:
    state["last_intent"] = intent


def set_pending_question(state: Dict[str, Any], question: str) -> None:
    state["pending_question"] = question
