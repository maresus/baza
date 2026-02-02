"""
Unified Router for Health Center chatbot.
Single entry point for all intent classification.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from .confidence import (
    detect_intents,
    pick_primary_secondary,
    decide_action,
    SwitchAction,
    detect_service_type,
)


class IntentType(str, Enum):
    BOOKING_APPOINTMENT = "BOOKING_APPOINTMENT"
    SERVICE_INFO = "SERVICE_INFO"
    PRICE = "PRICE"
    INFO = "INFO"
    URGENCY = "URGENCY"
    GREETING = "GREETING"
    GOODBYE = "GOODBYE"
    AFFIRMATIVE = "AFFIRMATIVE"
    NEGATIVE = "NEGATIVE"
    GENERAL = "GENERAL"


@dataclass
class Decision:
    primary_intent: IntentType
    confidence: float
    action: SwitchAction
    secondary_intent: IntentType | None = None
    service_type: str | None = None
    resume_prompt: str | None = None


def _detect_affirmative_negative(message: str) -> IntentType | None:
    """Detect simple yes/no responses (exact match only)."""
    text = message.lower().strip()
    # Remove extra spaces
    text = " ".join(text.split())

    if text in {"da", "ja", "ok", "okej", "okay", "seveda", "res je", "tako je", "vredu", "v redu", "lahko",
                "ja prosim", "da prosim", "prosim", "seveda ja", "ja seveda", "grem", "gremo",
                "bom", "bom prišel", "bom prisla", "bom prsou", "pridem", "pridm",
                "yes", "yep", "sure", "cool", "d a"}:
        return IntentType.AFFIRMATIVE
    if text in {"ne", "ne hvala", "ne, hvala", "ne bom", "nočem", "nochem", "pustimo", "ne rabim", "ni treba",
                "ne želim", "ne zelim", "raje ne", "rajši ne", "n e", "no", "nope"}:
        return IntentType.NEGATIVE
    return None


def route(message: str, unified_state: Dict[str, Any]) -> Decision:
    """
    Main routing function for health center chatbot.

    Args:
        message: User's message
        unified_state: Current conversation state

    Returns:
        Decision object with intent, confidence, and recommended action
    """
    # 1. Check for simple yes/no (exact match)
    affneg = _detect_affirmative_negative(message)
    if affneg:
        return Decision(
            primary_intent=affneg,
            confidence=1.0,
            action=SwitchAction.IGNORE,
        )

    # 2. Score all intents through unified system
    scores = detect_intents(message)
    primary, secondary, confidence = pick_primary_secondary(scores)
    primary_intent = IntentType(primary) if primary in IntentType._value2member_map_ else IntentType.GENERAL
    secondary_intent = (
        IntentType(secondary) if secondary in IntentType._value2member_map_ else None
    )

    # 3. Detect service type if applicable
    service_type = detect_service_type(message)

    # 4. Determine action based on current flow
    flow = unified_state.get("flow", "idle")
    action = SwitchAction.IGNORE

    if flow != "idle":
        # INFO/PRICE/SERVICE_INFO during flow = soft interrupt (answer + continue)
        if primary_intent in {IntentType.INFO, IntentType.PRICE, IntentType.SERVICE_INFO}:
            action = SwitchAction.SOFT_INTERRUPT
        # URGENCY always gets priority
        elif primary_intent == IntentType.URGENCY:
            action = SwitchAction.HARD_SWITCH
        else:
            action = decide_action(confidence)

    return Decision(
        primary_intent=primary_intent,
        secondary_intent=secondary_intent,
        confidence=confidence,
        action=action,
        service_type=service_type,
    )


class InterruptManager:
    @staticmethod
    def should_interrupt(decision: Decision) -> bool:
        return decision.action == SwitchAction.SOFT_INTERRUPT


def format_interrupt_response(answer: str, resume: str | None) -> str:
    """Format response with optional resume prompt."""
    if resume:
        return f"{answer}\n\n---\n\n{resume}"
    return answer
