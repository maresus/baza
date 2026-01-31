"""
Confidence Calculator - Deterministic scoring for intent detection.

Uses 3-level confidence system:
- > 0.8: HARD_SWITCH (reset current flow)
- 0.5-0.8: SOFT_INTERRUPT (answer + continue flow)
- < 0.5: IGNORE (stay in current flow)
"""

from enum import Enum
from typing import Optional
import re


class SwitchAction(str, Enum):
    """Action to take based on confidence score."""
    HARD_SWITCH = "hard_switch"      # > 0.8: Reset flow, start new intent
    SOFT_INTERRUPT = "soft_interrupt"  # 0.5-0.8: Answer question, continue flow
    IGNORE = "ignore"                 # < 0.5: Stay in current flow


class IntentType(str, Enum):
    """Possible intent types."""
    BOOKING_TABLE = "booking_table"
    BOOKING_ROOM = "booking_room"
    INFO = "info"
    PRODUCT = "product"
    INQUIRY = "inquiry"
    GREETING = "greeting"
    GOODBYE = "goodbye"
    MENU = "menu"
    WINE = "wine"
    HELP = "help"
    GENERAL = "general"
    AFFIRMATIVE = "affirmative"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


# Hard match keywords (confidence = 1.0)
HARD_MATCH_KEYWORDS = {
    IntentType.BOOKING_TABLE: [
        "rezerviraj mizo", "rezervacija mize", "rezerviral mizo",
        "book a table", "table reservation", "tisch reservieren",
        "rad bi rezerviral mizo", "rada bi rezervirala mizo",
        "želim rezervirati mizo", "zelim rezervirati mizo",
    ],
    IntentType.BOOKING_ROOM: [
        "rezerviraj sobo", "rezervacija sobe", "rezerviral sobo",
        "book a room", "room reservation", "zimmer reservieren",
        "rad bi rezerviral sobo", "rada bi rezervirala sobo",
        "želim rezervirati sobo", "zelim rezervirati sobo",
        "rad bi nocil", "rada bi nocila", "prenočitev",
    ],
    IntentType.GREETING: [
        "živjo", "zdravo", "hej", "hello", "hi", "dober dan",
        "pozdravljeni", "dobro jutro", "dober večer", "guten tag",
    ],
    IntentType.GOODBYE: [
        "adijo", "nasvidenje", "na svidenje", "čao", "ciao", "bye",
        "goodbye", "lep pozdrav", "se vidimo", "hvala in adijo",
    ],
}

# Keywords for soft scoring
BOOKING_KEYWORDS = [
    "rezerv", "book", "buking", "mizo", "miza", "mize",
    "sobo", "soba", "sobe", "nočitev", "nocitev", "prenočitev",
]

PRODUCT_KEYWORDS = [
    "pesto", "marmelad", "salam", "bunka", "izdelk", "naroč",
    "kupiti", "kupim", "prodajate", "imate v prodaji", "katalog",
    "liker", "likerj", "žganje", "zganje", "slivovka", "medenica",
]

INFO_KEYWORDS = [
    "kje", "naslov", "lokacija", "kako pridem", "parking",
    "telefon", "email", "kontakt", "odprt", "odprto", "kdaj",
    "delovni čas", "ura", "wifi", "cena", "cenika",
]

MENU_KEYWORDS = [
    "jedilnik", "menu", "meni", "jedi", "ponujate", "sezonsk",
    "zimski", "poletni", "jesenski", "pomladni", "hrana",
]

WINE_KEYWORDS = [
    "vino", "vina", "vin", "rdec", "rdeca", "rdeč", "rdečo", "belo", "bela",
    "penin", "peneč", "muskat", "muškat", "rizling", "sauvignon", "frankinja", "pinot",
]

QUESTION_INDICATORS = [
    "ali", "a imate", "kdaj", "koliko", "kje", "kako", "kaj",
    "a je", "a so", "a lahko", "ali lahko", "a veste",
]

INTENT_EXPRESSIONS = [
    "rad bi", "rada bi", "želim", "zelim", "hočem", "hocem",
    "imel bi", "imela bi", "hotel bi", "hotela bi", "bi rad",
]


def compute_hard_match(message: str) -> tuple[Optional[IntentType], float]:
    """
    Check for exact hard matches (confidence = 1.0).

    Returns:
        Tuple of (intent_type, confidence) or (None, 0.0) if no match
    """
    lowered = message.lower().strip()

    for intent_type, keywords in HARD_MATCH_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lowered:
                return (intent_type, 1.0)

    return (None, 0.0)


def compute_soft_score(message: str) -> tuple[Optional[IntentType], float]:
    """
    Compute soft confidence score using heuristics.

    Scoring:
    - +0.4 if contains intent keyword
    - +0.3 if contains question indicator
    - +0.3 if contains intent expression

    Returns:
        Tuple of (detected_intent, confidence_score)
    """
    lowered = message.lower()
    score = 0.0
    detected_intent = IntentType.GENERAL

    # Check for booking keywords
    booking_match = any(kw in lowered for kw in BOOKING_KEYWORDS)
    if booking_match:
        score += 0.4
        # Determine table vs room
        if any(kw in lowered for kw in ["mizo", "miza", "mize", "table", "kosilo"]):
            detected_intent = IntentType.BOOKING_TABLE
        elif any(kw in lowered for kw in ["sobo", "soba", "sobe", "room", "nočitev", "nocitev"]):
            detected_intent = IntentType.BOOKING_ROOM

    # Check for product keywords
    product_match = any(kw in lowered for kw in PRODUCT_KEYWORDS)
    if product_match:
        if score < 0.4:  # Only set if no booking match
            score = 0.4
            detected_intent = IntentType.PRODUCT
        elif detected_intent == IntentType.GENERAL:
            detected_intent = IntentType.PRODUCT

    # Check for info keywords
    info_match = any(kw in lowered for kw in INFO_KEYWORDS)
    if info_match and detected_intent == IntentType.GENERAL:
        score = max(score, 0.4)
        detected_intent = IntentType.INFO

    # Check for menu keywords
    menu_match = any(kw in lowered for kw in MENU_KEYWORDS)
    if menu_match and detected_intent == IntentType.GENERAL:
        score = max(score, 0.4)
        detected_intent = IntentType.MENU

    # Check for wine keywords
    wine_match = any(kw in lowered for kw in WINE_KEYWORDS)
    if wine_match and detected_intent == IntentType.GENERAL:
        score = max(score, 0.4)
        detected_intent = IntentType.WINE

    # Add question indicator score
    if any(q in lowered for q in QUESTION_INDICATORS):
        score += 0.3

    # Add intent expression score
    if any(i in lowered for i in INTENT_EXPRESSIONS):
        score += 0.3

    return (detected_intent, min(score, 1.0))


def compute_confidence(message: str) -> tuple[IntentType, float, SwitchAction]:
    """
    Main confidence computation function.

    Logic:
    1. Check hard matches first (1.0 confidence)
    2. If no hard match, compute soft score
    3. Return intent, confidence, and recommended action

    Returns:
        Tuple of (intent_type, confidence, action)
    """
    # 1. Check hard match
    hard_intent, hard_confidence = compute_hard_match(message)
    if hard_intent:
        return (hard_intent, hard_confidence, SwitchAction.HARD_SWITCH)

    # 2. Compute soft score
    soft_intent, soft_confidence = compute_soft_score(message)

    # 3. Determine action
    if soft_confidence >= 0.8:
        action = SwitchAction.HARD_SWITCH
    elif soft_confidence >= 0.5:
        action = SwitchAction.SOFT_INTERRUPT
    else:
        action = SwitchAction.IGNORE

    return (soft_intent, soft_confidence, action)


def decide_action(confidence: float) -> SwitchAction:
    """
    Determine action based on confidence score.

    Args:
        confidence: Score between 0.0 and 1.0

    Returns:
        SwitchAction enum value
    """
    if confidence >= 0.8:
        return SwitchAction.HARD_SWITCH
    elif confidence >= 0.5:
        return SwitchAction.SOFT_INTERRUPT
    else:
        return SwitchAction.IGNORE


def is_affirmative_response(message: str) -> bool:
    """Check if message is an affirmative response."""
    lowered = message.lower().strip()
    affirmatives = [
        "da", "ja", "yes", "ok", "okej", "okay", "seveda", "prav",
        "vredu", "v redu", "super", "odlično", "odlicno", "dobr",
        "tako je", "tocno", "točno", "mhm", "aha", "yep", "yup",
    ]
    # Exact match or starts with affirmative
    if lowered in affirmatives:
        return True
    if any(lowered.startswith(a + " ") or lowered.startswith(a + ",") for a in affirmatives):
        return True
    return False


def is_negative_response(message: str) -> bool:
    """Check if message is a negative response."""
    lowered = message.lower().strip()
    negatives = [
        "ne", "no", "nope", "nikakor", "nikoli", "nein",
        "ne bi", "ne želim", "ne zelim", "ne rabim", "ni treba",
    ]
    if lowered in negatives:
        return True
    if any(lowered.startswith(n + " ") or lowered.startswith(n + ",") for n in negatives):
        return True
    return False
