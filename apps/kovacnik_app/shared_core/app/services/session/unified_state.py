from __future__ import annotations

from typing import Any, Dict


def blank_unified_state() -> Dict[str, Any]:
    return {
        "flow": "idle",
        "step": None,
        "data": {},
        "last_intent": None,
        "pending_question": None,
    }


def get_unified_state(ctx: Dict[str, Any]) -> Dict[str, Any]:
    state = ctx.get("unified_state")
    if not isinstance(state, dict):
        state = blank_unified_state()
        ctx["unified_state"] = state
    return state


def set_unified_flow(state: Dict[str, Any], flow: str, step: str | None = None) -> None:
    state["flow"] = flow
    if step is not None:
        state["step"] = step


def update_unified_state(state: Dict[str, Any], **kwargs: Any) -> None:
    for key, value in kwargs.items():
        state[key] = value
