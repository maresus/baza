"""
Intent checking utilities - greeting, goodbye, menu, booking intent checks.
"""

from typing import Optional

# Keywords for greetings
GREETING_KEYWORDS = {"živjo", "zdravo", "hej", "hello", "dober dan", "pozdravljeni"}

# Keywords for goodbyes
GOODBYE_KEYWORDS = {
    "hvala",
    "najlepša hvala",
    "hvala lepa",
    "adijo",
    "nasvidenje",
    "na svidenje",
    "čao",
    "ciao",
    "bye",
    "goodbye",
    "lp",
    "lep pozdrav",
    "se vidimo",
    "vidimo se",
    "srečno",
    "vse dobro",
    "lahko noč",
}


def is_greeting(message: str) -> bool:
    """Check if message is a greeting."""
    lowered = message.lower()
    return any(greeting in lowered for greeting in GREETING_KEYWORDS)


def is_goodbye(message: str) -> bool:
    """Check if message is a goodbye/thank you."""
    lowered = message.lower().strip()
    if lowered in GOODBYE_KEYWORDS:
        return True
    if any(keyword in lowered for keyword in ["hvala", "adijo", "nasvidenje", "čao", "ciao", "bye"]):
        return True
    return False


def is_booking_intent(
    message: str,
    reservation_start_phrases: set[str],
    parse_reservation_type_func: callable,
) -> bool:
    """
    Check if message indicates booking intent.

    Args:
        message: User message
        reservation_start_phrases: Set of phrases that start reservations
        parse_reservation_type_func: Function to parse reservation type
    """
    lowered = message.lower()
    if any(phrase in lowered for phrase in reservation_start_phrases):
        return True
    intent_tokens = ["rad bi", "rada bi", "želim", "zelim", "hočem", "hocem", "imel bi", "imela bi"]
    has_intent = any(tok in lowered for tok in intent_tokens)
    has_type = parse_reservation_type_func(message) in {"room", "table"}
    return has_intent and has_type


def is_hours_question(message: str) -> bool:
    """Check if message is asking about opening hours."""
    lowered = message.lower()
    patterns = [
        "odprti",
        "odprt",
        "odpiralni",
        "obratovalni",
        "obratujete",
        "do kdaj",
        "kdaj lahko pridem",
        "kdaj ste",
        "kateri uri",
        "kosilo ob",
        "kosilo do",
        "kosila",
        "zajtrk",
        "breakfast",
        "večerj",
        "vecerj",
        "prijava",
        "odjava",
        "check-in",
        "check out",
        "kosilo",
        "večerja",
        "vecerja",
    ]
    return any(pat in lowered for pat in patterns)


def is_menu_query(message: str) -> bool:
    """Check if message is asking about menu."""
    lowered = message.lower()
    reservation_indicators = ["rezerv", "sobo", "sobe", "mizo", "nočitev", "nočitve", "nocitev"]
    if any(indicator in lowered for indicator in reservation_indicators):
        return False
    weekly_indicators = [
        "teden",
        "tedensk",
        "čez teden",
        "med tednom",
        "sreda",
        "četrtek",
        "petek",
        "hodni",
        "hodn",
        "hodov",
        "degustacij",
        "kulinarično",
        "doživetje",
    ]
    if any(indicator in lowered for indicator in weekly_indicators):
        return False
    menu_keywords = ["jedilnik", "meni", "meniju", "jedo", "kuhate"]
    if any(word in lowered for word in menu_keywords):
        return True
    if "vikend kosilo" in lowered or "vikend kosila" in lowered:
        return True
    if "kosilo" in lowered and "rezerv" not in lowered and "mizo" not in lowered:
        return True
    return False


def is_full_menu_request(message: str) -> bool:
    """Check if user is asking for full menu."""
    lowered = message.lower()
    return any(
        phrase in lowered
        for phrase in [
            "celoten meni",
            "celotni meni",
            "poln meni",
            "celoten jedilnik",
            "celotni jedilnik",
            "poln jedilnik",
        ]
    )


def is_unknown_response(response: str) -> bool:
    """Check if response indicates unknown information."""
    unknown_indicators = [
        "žal ne morem",
        "nimam informacij",
        "ne vem",
        "nisem prepričan",
        "ni na voljo",
        "podatka nimam",
    ]
    response_lower = response.lower()
    return any(ind in response_lower for ind in unknown_indicators)
