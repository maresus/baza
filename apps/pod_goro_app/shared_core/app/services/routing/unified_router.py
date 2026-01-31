from __future__ import annotations

from typing import Any, Dict

from .confidence import detect_intents, pick_primary_secondary, decide_action, SwitchAction


def _active_flow(state: Dict[str, Any], inquiry_state: Dict[str, Any]) -> str:
    if inquiry_state.get("step") is not None:
        return "inquiry"
    if state.get("step") is not None:
        if state.get("type") == "room":
            return "reservation_room"
        if state.get("type") == "table":
            return "reservation_table"
        return "reservation"
    return "idle"


def decide(message: str, state: Dict[str, Any], inquiry_state: Dict[str, Any]) -> Dict[str, Any]:
    scores = detect_intents(message)
    primary, secondary, confidence = pick_primary_secondary(scores)
    flow = _active_flow(state, inquiry_state)

    action = SwitchAction.IGNORE
    if flow != "idle":
        if primary in {"INFO", "PRODUCT"}:
            action = SwitchAction.SOFT_INTERRUPT
        elif primary == "INQUIRY":
            action = decide_action(confidence)
        elif primary in {"BOOKING_TABLE", "BOOKING_ROOM"}:
            if flow == "reservation_table" and primary == "BOOKING_TABLE":
                action = SwitchAction.IGNORE
            elif flow == "reservation_room" and primary == "BOOKING_ROOM":
                action = SwitchAction.IGNORE
            else:
                action = decide_action(confidence)
        else:
            action = decide_action(confidence)

    return {
        "primary_intent": primary,
        "secondary_intent": secondary,
        "confidence": confidence,
        "action": action.value,
    }
