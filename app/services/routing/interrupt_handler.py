"""
Interrupt Handler for Health Center chatbot.
Handles soft interrupts during appointment booking flow.
"""
from __future__ import annotations

from typing import Any, Dict

from .unified_router import IntentType


# Resume prompts for appointment flow steps
RESUME_PROMPTS = {
    "service": "Kateri termin bi radi naročili?",
    "date": "Kateri datum vam ustreza?",
    "time": "Ob kateri uri bi želeli priti?",
    "name": "Potrebujem vaše ime in priimek.",
    "phone": "Potrebujem še vašo telefonsko številko.",
    "email": "Ali želite prejeti potrditev po e-pošti? Če da, mi prosim sporočite vaš email.",
    "confirm": "Ali potrjujete termin?",
}


def build_resume_prompt(step: str | None) -> str | None:
    """Build a prompt to resume the interrupted flow."""
    if step and step in RESUME_PROMPTS:
        return f"Nadaljujemo z naročilom. {RESUME_PROMPTS[step]}"
    return None


def build_interrupt_response(answer: str, step: str | None, include_resume: bool = True) -> str:
    """
    Build a complete response that answers the interrupt and optionally prompts to continue.

    Args:
        answer: The answer to the user's interrupting question
        step: The current step in the booking flow
        include_resume: Whether to include the resume prompt

    Returns:
        Formatted response string
    """
    if not include_resume:
        return answer

    resume = build_resume_prompt(step)
    if resume:
        return f"{answer}\n\n---\n\n{resume}"
    return answer


def get_service_type_name(service_type: str) -> str:
    """Get human-readable name for service type."""
    names = {
        "DERMATOLOG": "dermatolog",
        "ORTOPED": "ortoped",
        "OKULIST": "okulist",
        "FIZIOTERAPIJA": "fizioterapija",
        "ESTETSKI_POSEG": "estetski poseg",
        "LASERSKI_POSEG": "laserski poseg",
        "KOZMETIKA": "kozmetika",
    }
    return names.get(service_type, service_type.lower())


def format_appointment_summary(appointment_data: Dict[str, Any]) -> str:
    """Format appointment data for confirmation."""
    service = get_service_type_name(appointment_data.get("service_type", ""))
    date = appointment_data.get("date", "")
    time = appointment_data.get("time", "")
    name = appointment_data.get("name", "")
    phone = appointment_data.get("phone", "")

    lines = [
        f"**Storitev:** {service}",
        f"**Datum:** {date}",
        f"**Ura:** {time}",
        f"**Ime:** {name}",
        f"**Telefon:** {phone}",
    ]

    if appointment_data.get("email"):
        lines.append(f"**Email:** {appointment_data['email']}")

    return "\n".join(lines)
