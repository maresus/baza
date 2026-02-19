from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.services.routing.confidence import score_intent_confidence


class SwitchAction(str, Enum):
    HARD_SWITCH = "hard_switch"
    SOFT_INTERRUPT = "soft_interrupt"
    IGNORE = "ignore"


@dataclass
class Decision:
    primary_intent: str
    secondary_intent: Optional[str]
    confidence: float
    action: SwitchAction


INTENTS = [
    "BOOKING_TABLE",
    "BOOKING_ROOM",
    "INFO",
    "PRODUCT",
    "INQUIRY",
    "GREETING",
    "GOODBYE",
    "GENERAL",
]


def decide_action(confidence: float) -> SwitchAction:
    if confidence >= 0.8:
        return SwitchAction.HARD_SWITCH
    if confidence >= 0.5:
        return SwitchAction.SOFT_INTERRUPT
    return SwitchAction.IGNORE


def decide_route(message: str) -> Decision:
    scores = score_intent_confidence(message)
    primary_intent = max(scores, key=scores.get)
    confidence = scores[primary_intent]
    action = decide_action(confidence)

    secondary_intent: Optional[str] = None
    if primary_intent in {"BOOKING_TABLE", "BOOKING_ROOM", "INQUIRY"}:
        info_score = scores.get("INFO", 0.0)
        product_score = scores.get("PRODUCT", 0.0)
        if product_score >= 0.5 and product_score >= info_score:
            secondary_intent = "PRODUCT"
        elif info_score >= 0.5:
            secondary_intent = "INFO"

    return Decision(
        primary_intent=primary_intent,
        secondary_intent=secondary_intent,
        confidence=confidence,
        action=action,
    )
