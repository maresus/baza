"""
Interrupt Handler - Handle INFO/PRODUCT questions during active flows.

Key principles:
- Answer the interrupt question
- Continue the current flow automatically
- No "želiš nadaljevati?" questions - act like a waiter
"""

from typing import Any, Optional, Callable
from dataclasses import dataclass

from .confidence import IntentType, SwitchAction
from .unified_router import Decision


@dataclass
class InterruptResponse:
    """Response structure for handled interrupts."""
    answer: str
    resume_message: Optional[str]
    should_resume: bool


def handle_interrupt(
    decision: Decision,
    state: dict[str, Any],
    get_info_answer: Callable[[str], Optional[str]],
    get_product_answer: Callable[[str], Optional[str]],
    get_menu_answer: Callable[[str], Optional[str]],
    get_wine_answer: Callable[[str], Optional[str]],
    message: str,
) -> Optional[InterruptResponse]:
    """
    Handle an interrupt during an active flow.

    If decision.action is SOFT_INTERRUPT, this function:
    1. Gets the appropriate answer for the interrupt type
    2. Generates a resume message to continue the flow
    3. Returns both combined

    Args:
        decision: Router decision
        state: Current session state
        get_info_answer: Function to get INFO answers
        get_product_answer: Function to get PRODUCT answers
        get_menu_answer: Function to get MENU answers
        get_wine_answer: Function to get WINE answers
        message: Original user message

    Returns:
        InterruptResponse or None if not an interrupt
    """
    if decision.action != SwitchAction.SOFT_INTERRUPT:
        return None

    current_flow = state.get("flow", "idle")
    if current_flow == "idle":
        return None

    # Get the appropriate answer
    answer = None
    intent = decision.primary_intent

    if intent == IntentType.INFO:
        answer = get_info_answer(message)
    elif intent == IntentType.PRODUCT:
        answer = get_product_answer(message)
    elif intent == IntentType.MENU:
        answer = get_menu_answer(message)
    elif intent == IntentType.WINE:
        answer = get_wine_answer(message)

    if not answer:
        return None

    # Generate resume message based on current flow step
    resume_message = decision.resume_prompt

    return InterruptResponse(
        answer=answer,
        resume_message=resume_message,
        should_resume=True,
    )


def format_interrupt_response(interrupt: InterruptResponse) -> str:
    """
    Format the interrupt response for display.

    Combines the answer with the resume prompt in a natural way.
    No "želiš nadaljevati?" - just continue smoothly.
    """
    if not interrupt.resume_message:
        return interrupt.answer

    # Combine answer with resume, using a natural separator
    return f"{interrupt.answer}\n\n---\n\n{interrupt.resume_message}"


def should_handle_as_interrupt(
    decision: Decision,
    state: dict[str, Any],
) -> bool:
    """
    Determine if the current message should be handled as an interrupt.

    Returns True if:
    - Currently in a flow
    - Decision action is SOFT_INTERRUPT
    - Intent is interruptible (INFO, PRODUCT, MENU, WINE)
    """
    if state.get("flow", "idle") == "idle":
        return False

    if decision.action != SwitchAction.SOFT_INTERRUPT:
        return False

    interruptible_intents = [
        IntentType.INFO,
        IntentType.PRODUCT,
        IntentType.MENU,
        IntentType.WINE,
    ]

    return decision.primary_intent in interruptible_intents


def handle_mixed_intent(
    decision: Decision,
    state: dict[str, Any],
    get_product_answer: Callable[[str], Optional[str]],
    message: str,
) -> Optional[str]:
    """
    Handle mixed intent messages (e.g., "miza + marmelada").

    If both primary and secondary intents are present:
    1. Answer the secondary intent (e.g., product question)
    2. Return combined with booking continuation

    Args:
        decision: Router decision with primary and secondary intents
        state: Current session state
        get_product_answer: Function to get product answers
        message: Original user message

    Returns:
        Combined response or None if not a mixed intent
    """
    if not decision.secondary_intent:
        return None

    # Handle product as secondary to booking
    if decision.secondary_intent == IntentType.PRODUCT:
        product_answer = get_product_answer(message)
        if product_answer:
            return product_answer

    return None


class InterruptManager:
    """
    Manager class for handling interrupts in a conversation flow.

    Usage:
        manager = InterruptManager(
            get_info_answer=my_info_func,
            get_product_answer=my_product_func,
            get_menu_answer=my_menu_func,
            get_wine_answer=my_wine_func,
        )

        response = manager.process(decision, state, message)
        if response:
            return response.answer + response.resume_message
    """

    def __init__(
        self,
        get_info_answer: Callable[[str], Optional[str]],
        get_product_answer: Callable[[str], Optional[str]],
        get_menu_answer: Callable[[str], Optional[str]],
        get_wine_answer: Callable[[str], Optional[str]],
    ):
        self.get_info_answer = get_info_answer
        self.get_product_answer = get_product_answer
        self.get_menu_answer = get_menu_answer
        self.get_wine_answer = get_wine_answer

    def process(
        self,
        decision: Decision,
        state: dict[str, Any],
        message: str,
    ) -> Optional[InterruptResponse]:
        """
        Process a potential interrupt.

        Returns InterruptResponse if this is an interrupt, None otherwise.
        """
        if not should_handle_as_interrupt(decision, state):
            return None

        return handle_interrupt(
            decision=decision,
            state=state,
            get_info_answer=self.get_info_answer,
            get_product_answer=self.get_product_answer,
            get_menu_answer=self.get_menu_answer,
            get_wine_answer=self.get_wine_answer,
            message=message,
        )

    def format_response(self, interrupt: InterruptResponse) -> str:
        """Format interrupt response for display."""
        return format_interrupt_response(interrupt)
