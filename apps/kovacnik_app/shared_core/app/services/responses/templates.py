"""
Shared response templates (brand-config driven).
"""

import random
from app.brand.config import GREETINGS, THANKS_RESPONSES, UNKNOWN_RESPONSES


def get_greeting_response() -> str:
    return random.choice(GREETINGS)


def get_goodbye_response() -> str:
    return random.choice(THANKS_RESPONSES)


def get_unknown_response() -> str:
    return random.choice(UNKNOWN_RESPONSES)
