"""
Unified Routing Module - Single decision point for all message routing.

This module replaces the scattered routing logic:
- detect_intent()
- route_message()
- smart_route()
- detect_*_intent()

Main components:
- unified_router: Main routing logic
- confidence: Confidence scoring and intent detection
- interrupt_handler: Handle interrupts during active flows
"""

from .confidence import (
    IntentType,
    SwitchAction,
    compute_confidence,
    compute_hard_match,
    compute_soft_score,
    decide_action,
    is_affirmative_response,
    is_negative_response,
)

from .unified_router import (
    Decision,
    route,
    route_with_llm_fallback,
    detect_secondary_intent,
    get_resume_prompt,
)

from .interrupt_handler import (
    InterruptResponse,
    InterruptManager,
    handle_interrupt,
    format_interrupt_response,
    should_handle_as_interrupt,
    handle_mixed_intent,
)

__all__ = [
    # Confidence
    "IntentType",
    "SwitchAction",
    "compute_confidence",
    "compute_hard_match",
    "compute_soft_score",
    "decide_action",
    "is_affirmative_response",
    "is_negative_response",
    # Router
    "Decision",
    "route",
    "route_with_llm_fallback",
    "detect_secondary_intent",
    "get_resume_prompt",
    # Interrupt Handler
    "InterruptResponse",
    "InterruptManager",
    "handle_interrupt",
    "format_interrupt_response",
    "should_handle_as_interrupt",
    "handle_mixed_intent",
]
