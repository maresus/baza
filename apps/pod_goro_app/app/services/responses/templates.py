"""Response templates - greetings, goodbyes, unknown responses."""

import random

from app.brand.config import GREETINGS, THANKS_RESPONSES, UNKNOWN_RESPONSES


def get_greeting_response() -> str:
    """Return a random greeting response."""
    return random.choice(GREETINGS)


def get_goodbye_response() -> str:
    """Return a random goodbye/thank you response."""
    return random.choice(THANKS_RESPONSES)


def get_unknown_response(language: str = "si") -> str:
    """Return a response for unknown queries.

    Args:
        language: Target language ('si', 'en', or 'de')

    Returns:
        Localized unknown response
    """
    if language == "si":
        return random.choice(UNKNOWN_RESPONSES)
    responses = {
        "en": "Unfortunately, I cannot answer this question.\n\nIf you share your email address, I will inquire and get back to you.",
        "de": "Leider kann ich diese Frage nicht beantworten.\n\nWenn Sie mir Ihre E-Mail-Adresse mitteilen, werde ich mich erkundigen und Ihnen antworten.",
    }
    return responses.get(language, "Na to vprašanje žal ne morem odgovoriti.")
