"""
Language detection for user messages.
"""

import re


# German keywords for detection
GERMAN_WORDS = [
    "ich", "sie", "wir", "haben", "möchte", "möchten", "können", "bitte",
    "zimmer", "tisch", "reservierung", "reservieren", "buchen", "wann",
    "wie", "was", "wo", "gibt", "guten tag", "hallo", "danke", "preis",
    "kosten", "essen", "trinken", "wein", "frühstück", "abendessen",
    "mittag", "nacht", "übernachtung",
]

# English keywords for detection
ENGLISH_WORDS = [
    " we ", "you", "have", "would", " like ", "want", "can", "room",
    "table", "reservation", "reserve", "book", "booking", "when", "how",
    "what", "where", "there", "hello", "hi ", "thank", "price", "cost",
    "food", "drink", "wine", "menu", "breakfast", "dinner", "lunch",
    "night", "stay", "please",
]

# Slovenian words that contain English substrings (exceptions)
SLOVAK_EXCEPTIONS = ["liker", "likerj", " like ", "slike"]


def detect_language(message: str) -> str:
    """
    Detect language of user message.

    Returns:
        'si' for Slovenian (default)
        'en' for English
        'de' for German
    """
    lowered = message.lower()

    # Remove Slovenian exceptions before detection
    for exc in SLOVAK_EXCEPTIONS:
        lowered = lowered.replace(exc, "")

    # Count German words
    german_count = sum(1 for word in GERMAN_WORDS if word in lowered)

    # Special handling for English pronoun "I" as standalone word
    english_pronoun = 1 if re.search(r"\bi\b", lowered) else 0
    english_count = english_pronoun + sum(1 for word in ENGLISH_WORDS if word in lowered)

    # Decision logic
    if german_count >= 2:
        return "de"
    if english_count >= 2:
        return "en"
    if german_count == 1 and english_count == 0:
        return "de"
    if english_count == 1 and german_count == 0:
        return "en"

    return "si"
