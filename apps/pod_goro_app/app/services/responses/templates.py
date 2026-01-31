"""
Response templates - greetings, goodbyes, unknown responses.
"""

import random

# Greeting responses
GREETINGS = [
    "Pozdravljeni! Kako vam lahko pomagam?",
    "Lepo pozdravljeni s Pohorja! Kako vam lahko pomagam danes?",
    "Dober dan! Vesela sem, da ste nas obiskali. S čim vam lahko pomagam?",
    "Pozdravljeni pri Kovačniku! Kaj vas zanima?",
]

# Thank you / goodbye responses
THANKS_RESPONSES = [
    "Ni za kaj! Če boste imeli še kakšno vprašanje, sem tu.",
    "Z veseljem! Lep pozdrav s Pohorja!",
    "Ni problema! Vesela sem, če sem vam lahko pomagala.",
    "Hvala vam! Se vidimo pri nas!",
]

# Unknown / fallback responses
UNKNOWN_RESPONSES = [
    "Tega žal ne vem. Če želite, mi pustite e-pošto in preverim.",
]


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
