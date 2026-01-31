"""
Unified Router - Single decision point for all message routing.

Replaces: detect_intent(), route_message(), smart_route(), detect_*_intent()

Input:
- message: User message
- session_state: Current unified session state

Output:
- Decision object with primary_intent, secondary_intent, confidence, action
"""

from dataclasses import dataclass
from typing import Any, Optional
import logging

from .confidence import (
    IntentType,
    SwitchAction,
    compute_confidence,
    compute_hard_match,
    compute_soft_score,
    is_affirmative_response,
    is_negative_response,
    PRODUCT_KEYWORDS,
    INFO_KEYWORDS,
    MENU_KEYWORDS,
    WINE_KEYWORDS,
)

logger = logging.getLogger("unified_router")


@dataclass
class Decision:
    """Router decision output."""
    primary_intent: IntentType
    secondary_intent: Optional[IntentType]
    confidence: float
    action: SwitchAction
    should_reset_flow: bool
    resume_prompt: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/debugging."""
        return {
            "primary_intent": self.primary_intent.value,
            "secondary_intent": self.secondary_intent.value if self.secondary_intent else None,
            "confidence": self.confidence,
            "action": self.action.value,
            "should_reset_flow": self.should_reset_flow,
            "resume_prompt": self.resume_prompt,
        }


def detect_secondary_intent(message: str, primary: IntentType) -> Optional[IntentType]:
    """
    Detect secondary intent for mixed-intent messages.

    Example: "rezerviraj mizo, a imate pesto?" -> primary=BOOKING_TABLE, secondary=PRODUCT
    """
    lowered = message.lower()

    # If primary is booking, check for product/info
    if primary in [IntentType.BOOKING_TABLE, IntentType.BOOKING_ROOM]:
        if any(kw in lowered for kw in PRODUCT_KEYWORDS):
            return IntentType.PRODUCT
        if any(kw in lowered for kw in INFO_KEYWORDS):
            return IntentType.INFO
        if any(kw in lowered for kw in MENU_KEYWORDS):
            return IntentType.MENU

    # If primary is product, check for booking
    if primary == IntentType.PRODUCT:
        if any(kw in lowered for kw in ["mizo", "miza", "sobo", "soba", "rezerv"]):
            if "mizo" in lowered or "miza" in lowered:
                return IntentType.BOOKING_TABLE
            if "sobo" in lowered or "soba" in lowered:
                return IntentType.BOOKING_ROOM

    return None


def get_resume_prompt(state: dict[str, Any], step: Optional[str]) -> Optional[str]:
    """
    Generate a prompt to resume the current flow after an interrupt.
    """
    flow = state.get("flow", "idle")

    if flow == "idle":
        return None

    # Reservation flow prompts
    if flow in ["reservation_table", "reservation_room"]:
        res_type = "mizo" if flow == "reservation_table" else "sobo"
        prompts = {
            "date": f"Za kateri datum bi želeli {res_type}?",
            "time": "Ob kateri uri bi prišli?",
            "guests": "Koliko vas bo?",
            "contact": "Lahko dobim vaš email ali telefon za potrditev?",
            "confirm": "Ali potrjujete rezervacijo?",
        }
        return prompts.get(step)

    # Inquiry flow prompts
    if flow == "inquiry":
        prompts = {
            "details": "Povejte mi več o vašem povpraševanju.",
            "deadline": "Ali imate željen datum?",
            "contact_info": "Lahko dobim vaš kontakt za odgovor?",
        }
        return prompts.get(step)

    return None


def route(message: str, state: dict[str, Any]) -> Decision:
    """
    Main routing function - single decision point.

    Rules:
    1. If state.step != null → check for interrupt (INFO/PRODUCT)
    2. If primary_intent different and confidence > 0.8 → reset current flow
    3. If mixed intent (product + reservation) → answer product + continue reservation
    4. If unclear → fallback to GENERAL
    5. Never return generic fallback for INFO/PRODUCT

    Args:
        message: User message
        state: Unified session state

    Returns:
        Decision object
    """
    current_flow = state.get("flow", "idle")
    current_step = state.get("step", "none")
    is_in_flow = current_flow != "idle" and current_step != "none"

    # Check for affirmative/negative responses first (important during flows)
    if is_affirmative_response(message):
        return Decision(
            primary_intent=IntentType.AFFIRMATIVE,
            secondary_intent=None,
            confidence=1.0,
            action=SwitchAction.IGNORE,  # Stay in flow, process affirmative
            should_reset_flow=False,
            resume_prompt=None,
        )

    if is_negative_response(message):
        # Negative during flow = might want to cancel
        action = SwitchAction.SOFT_INTERRUPT if is_in_flow else SwitchAction.IGNORE
        return Decision(
            primary_intent=IntentType.NEGATIVE,
            secondary_intent=None,
            confidence=1.0,
            action=action,
            should_reset_flow=False,
            resume_prompt=None,
        )

    # Compute confidence and intent
    primary_intent, confidence, action = compute_confidence(message)

    # Detect secondary intent for mixed messages
    secondary_intent = detect_secondary_intent(message, primary_intent)

    # If currently in a flow, apply interrupt logic
    if is_in_flow:
        return _handle_in_flow_routing(
            message, state, primary_intent, secondary_intent, confidence, action
        )

    # Not in flow - standard routing
    should_reset = False  # Nothing to reset if not in flow
    resume_prompt = None

    logger.debug(
        f"Route decision: intent={primary_intent.value}, confidence={confidence:.2f}, "
        f"action={action.value}, secondary={secondary_intent.value if secondary_intent else None}"
    )

    return Decision(
        primary_intent=primary_intent,
        secondary_intent=secondary_intent,
        confidence=confidence,
        action=action,
        should_reset_flow=should_reset,
        resume_prompt=resume_prompt,
    )


def _handle_in_flow_routing(
    message: str,
    state: dict[str, Any],
    primary_intent: IntentType,
    secondary_intent: Optional[IntentType],
    confidence: float,
    action: SwitchAction,
) -> Decision:
    """
    Handle routing when user is currently in a flow (reservation/inquiry).

    Logic:
    - If confidence >= 0.8 and different intent → HARD_SWITCH (reset flow)
    - If confidence 0.5-0.8 and INFO/PRODUCT → SOFT_INTERRUPT (answer + continue)
    - If confidence < 0.5 → IGNORE (stay in flow)
    """
    current_flow = state.get("flow", "idle")
    current_step = state.get("step", "none")

    # Determine if this is a flow-relevant intent
    flow_intents = {
        "reservation_table": IntentType.BOOKING_TABLE,
        "reservation_room": IntentType.BOOKING_ROOM,
        "inquiry": IntentType.INQUIRY,
    }
    current_flow_intent = flow_intents.get(current_flow)

    # If same intent as current flow, just continue
    if primary_intent == current_flow_intent:
        return Decision(
            primary_intent=primary_intent,
            secondary_intent=secondary_intent,
            confidence=confidence,
            action=SwitchAction.IGNORE,  # Continue current flow
            should_reset_flow=False,
            resume_prompt=None,
        )

    # High confidence different intent → reset flow
    if confidence >= 0.8:
        # Check if it's a completely new booking intent
        is_new_booking = primary_intent in [IntentType.BOOKING_TABLE, IntentType.BOOKING_ROOM]
        should_reset = is_new_booking or primary_intent == IntentType.INQUIRY

        return Decision(
            primary_intent=primary_intent,
            secondary_intent=secondary_intent,
            confidence=confidence,
            action=SwitchAction.HARD_SWITCH,
            should_reset_flow=should_reset,
            resume_prompt=None,
        )

    # Medium confidence INFO/PRODUCT/MENU → soft interrupt
    if confidence >= 0.5 and primary_intent in [IntentType.INFO, IntentType.PRODUCT, IntentType.MENU, IntentType.WINE]:
        resume_prompt = get_resume_prompt(state, current_step)
        return Decision(
            primary_intent=primary_intent,
            secondary_intent=secondary_intent,
            confidence=confidence,
            action=SwitchAction.SOFT_INTERRUPT,
            should_reset_flow=False,
            resume_prompt=resume_prompt,
        )

    # Low confidence → ignore, stay in flow
    resume_prompt = get_resume_prompt(state, current_step)
    return Decision(
        primary_intent=IntentType.GENERAL,  # Treat as general/continue flow
        secondary_intent=None,
        confidence=confidence,
        action=SwitchAction.IGNORE,
        should_reset_flow=False,
        resume_prompt=resume_prompt,
    )


def route_with_llm_fallback(
    message: str,
    state: dict[str, Any],
    llm_classifier: Optional[callable] = None,
) -> Decision:
    """
    Route with optional LLM fallback for unclear cases.

    Args:
        message: User message
        state: Unified session state
        llm_classifier: Optional function to call LLM for classification

    Returns:
        Decision object
    """
    # First try rule-based routing
    decision = route(message, state)

    # If low confidence and LLM available, use it
    if decision.confidence < 0.5 and llm_classifier:
        try:
            llm_result = llm_classifier(message)
            if llm_result and llm_result.get("confidence", 0) > 0.7:
                intent_str = llm_result.get("intent", "general")
                try:
                    llm_intent = IntentType(intent_str)
                except ValueError:
                    llm_intent = IntentType.GENERAL

                llm_confidence = llm_result.get("confidence", 0.5)
                llm_action = SwitchAction.HARD_SWITCH if llm_confidence >= 0.8 else (
                    SwitchAction.SOFT_INTERRUPT if llm_confidence >= 0.5 else SwitchAction.IGNORE
                )

                return Decision(
                    primary_intent=llm_intent,
                    secondary_intent=None,
                    confidence=llm_confidence,
                    action=llm_action,
                    should_reset_flow=llm_confidence >= 0.8,
                    resume_prompt=decision.resume_prompt,
                )
        except Exception as e:
            logger.warning(f"LLM fallback failed: {e}")

    return decision
