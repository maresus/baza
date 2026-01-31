"""
Input validation utilities - affirmative, negative, escape commands.
"""


def is_affirmative(message: str) -> bool:
    """Check if message is an affirmative response (yes, ok, etc.)."""
    lowered = message.strip().lower()
    return lowered in {
        "da",
        "ja",
        "seveda",
        "potrjujem",
        "potrdim",
        "potrdi",
        "zelim",
        "želim",
        "zelimo",
        "želimo",
        "rad bi",
        "rada bi",
        "bi",
        "yes",
        "oui",
        "ok",
        "okej",
        "okey",
        "sure",
        "yep",
        "yeah",
    }


def is_negative(message: str) -> bool:
    """Check if message is a negative response (no, cancel, etc.)."""
    lowered = message.strip().lower()
    if lowered in {"ne", "no", "ne hvala", "no thanks", "nič", "nima veze"}:
        return True
    return any(
        phrase in lowered
        for phrase in [
            "ne bom",
            "ne želim",
            "ne zelim",
            "ne rabim",
            "ne potrebujem",
            "ne naroč",
            "ne naroc",
            "prekliči",
            "preklici",
            "stop",
        ]
    )


def is_escape_command(message: str) -> bool:
    """Check if user wants to cancel/escape current flow."""
    lowered = message.lower()
    escape_words = {"prekliči", "preklici", "reset", "stop", "prekini"}
    return any(word in lowered for word in escape_words)


def is_switch_topic_command(message: str) -> bool:
    """Check if user wants to switch to a different topic."""
    lowered = message.lower()
    switch_words = {
        "zamenjaj temo",
        "menjaj temo",
        "nova tema",
        "spremeni temo",
        "gremo drugam",
        "druga tema",
    }
    return any(phrase in lowered for phrase in switch_words)


def is_confirmation_question(text: str) -> bool:
    """Check if text is asking for confirmation."""
    lowered = text.lower()
    return any(
        token in lowered
        for token in [
            "želite",
            "zelite",
            "potrdite",
            "potrdim",
            "potrdi",
            "potrditi",
            "confirm",
            "would you like",
            "can i",
        ]
    )
