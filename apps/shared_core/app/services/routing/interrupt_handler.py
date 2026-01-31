from __future__ import annotations

from typing import Any, Dict, Optional


def build_resume_prompt(get_booking_continuation, state: Dict[str, Any]) -> Optional[str]:
    step = state.get("step")
    if not step:
        return None
    return get_booking_continuation(step, state)


def build_interrupt_response(answer: str, resume_prompt: Optional[str]) -> str:
    if resume_prompt:
        return f"{answer}\n\n---\n\n📝 **Nadaljujemo z rezervacijo:**\n{resume_prompt}"
    return answer
