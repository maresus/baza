from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from .confidence import detect_intents, pick_primary_secondary, decide_action, SwitchAction


class IntentType(str, Enum):
    BOOKING_TABLE = "BOOKING_TABLE"
    BOOKING_ROOM = "BOOKING_ROOM"
    INFO = "INFO"
    PRODUCT = "PRODUCT"
    INQUIRY = "INQUIRY"
    GREETING = "GREETING"
    GOODBYE = "GOODBYE"
    MENU = "MENU"
    WINE = "WINE"
    AFFIRMATIVE = "AFFIRMATIVE"
    NEGATIVE = "NEGATIVE"
    GENERAL = "GENERAL"


@dataclass
class Decision:
    primary_intent: IntentType
    confidence: float
    action: SwitchAction
    secondary_intent: IntentType | None = None
    resume_prompt: str | None = None


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


def _detect_special_intent(message: str) -> IntentType | None:
    text = message.lower()
    if text.strip() in {"da", "ja", "ok", "seveda", "res je"}:
        return IntentType.AFFIRMATIVE
    if text.strip() in {"ne", "ne hvala", "ne, hvala", "ne bom"}:
        return IntentType.NEGATIVE
    if any(k in text for k in {"meni", "jedilnik", "menu"}):
        return IntentType.MENU
    if any(k in text for k in {"vino", "vinska", "rdeča vina", "bela vina"}):
        return IntentType.WINE
    return None


def route(message: str, unified_state: Dict[str, Any]) -> Decision:
    special = _detect_special_intent(message)
    if special in {IntentType.AFFIRMATIVE, IntentType.NEGATIVE, IntentType.MENU, IntentType.WINE}:
        return Decision(primary_intent=special, confidence=1.0, action=SwitchAction.IGNORE)

    scores = detect_intents(message)
    primary, secondary, confidence = pick_primary_secondary(scores)
    primary_intent = IntentType(primary) if primary in IntentType._value2member_map_ else IntentType.GENERAL
    secondary_intent = (
        IntentType(secondary) if secondary in IntentType._value2member_map_ else None
    )

    flow = unified_state.get("flow", "idle")
    action = SwitchAction.IGNORE
    if flow != "idle":
        if primary_intent in {IntentType.INFO, IntentType.PRODUCT}:
            action = SwitchAction.SOFT_INTERRUPT
        else:
            action = decide_action(confidence)

    return Decision(
        primary_intent=primary_intent,
        secondary_intent=secondary_intent,
        confidence=confidence,
        action=action,
    )


class InterruptManager:
    @staticmethod
    def should_interrupt(decision: Decision) -> bool:
        return decision.action == SwitchAction.SOFT_INTERRUPT


def format_interrupt_response(answer: str, resume: str | None) -> str:
    if resume:
        return f"{answer}\n\n---\n\n{resume}"
    return answer
