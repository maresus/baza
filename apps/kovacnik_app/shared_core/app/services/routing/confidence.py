from __future__ import annotations

from enum import Enum
from typing import Dict, Tuple


class SwitchAction(str, Enum):
    HARD_SWITCH = "hard_switch"
    SOFT_INTERRUPT = "soft_interrupt"
    IGNORE = "ignore"


def decide_action(confidence: float) -> SwitchAction:
    if confidence >= 0.8:
        return SwitchAction.HARD_SWITCH
    if confidence >= 0.5:
        return SwitchAction.SOFT_INTERRUPT
    return SwitchAction.IGNORE


RESERVATION_KEYWORDS = {
    "rezerv",
    "rezervir",
    "book",
    "booking",
    "reservation",
}

TABLE_KEYWORDS = {"miza", "mizo", "mize", "table", "kosilo", "večerja", "vecerja"}
ROOM_KEYWORDS = {
    "soba", "sobo", "sobe",
    "nočitev", "nocitev", "prenočitev", "prenocitev",
    "prenocil", "prenočil", "prespati", "prespali", "prespim",
    "room", "overnight",
}

INFO_KEYWORDS = {
    "kdaj",
    "kje",
    "kam",
    "odprto",
    "odprti",
    "ura",
    "urnik",
    "naslov",
    "lokacija",
    "parking",
    "parkirišče",
    "kontakt",
    "telefon",
    "email",
    "zajtrk",
    "večerja",
    "vecerja",
    "otroci",
    "igrišče",
}

TOURISM_KEYWORDS = {
    "smučišče",
    "smucisce",
    "izlet",
    "okolica",
    "blizu",
    "bližini",
    "aktivnosti",
    "pohorje",
}

PRODUCT_KEYWORDS = {
    "pesto",
    "čemaž",
    "cemaz",
    "namaz",
    "paštet",
    "pastet",
    "marmelad",
    "džem",
    "dzem",
    "liker",
    "žgan",
    "zgan",
    "sirup",
    "čaj",
    "caj",
    "salama",
    "klobasa",
    "bunka",
    "izdelk",
    "trgovin",
    "katalog",
    "kupit",
}

INQUIRY_KEYWORDS = {
    "teambuilding",
    "poroka",
    "porok",
    "dogodek",
    "povpraševanje",
    "povprasevanje",
    "skupina",
    "catering",
}

GREETING_KEYWORDS = {"zdravo", "živjo", "dobro jutro", "dober dan", "hello", "hi"}
GOODBYE_KEYWORDS = {"hvala", "adijo", "nasvidenje", "lep pozdrav", "pozdrav", "bye", "čao", "ciao"}

WINE_KEYWORDS = {
    "vino", "vina", "vin",
    "rdeč", "rdečo", "rdeca", "rdece",
    "belo", "bela",
    "peneč", "penina", "penece",
    "frankinja", "pinot", "rizling", "sauvignon", "muškat", "muskat",
    "vinska karta", "vinsko",
}

MENU_KEYWORDS = {
    "jedilnik", "meni", "menu",
    "kaj ponujate", "kaj imate za jest", "kva mate za jest",
    "hrana", "jedi",
    "sezonski meni", "dnevni meni",
}

QUESTION_MARKERS = {"?", "ali", "a ", "a imate", "imate", "kaj", "koliko", "kdaj"}


def _score_from_keywords(message: str, keywords: set[str]) -> float:
    return 0.4 if any(k in message for k in keywords) else 0.0


def _score_question_marker(message: str) -> float:
    return 0.3 if any(m in message for m in QUESTION_MARKERS) else 0.0


def compute_confidence(message: str, intent: str) -> float:
    text = message.lower()

    if intent == "GREETING":
        return 1.0 if any(k in text for k in GREETING_KEYWORDS) else 0.0
    if intent == "GOODBYE":
        return 1.0 if any(k in text for k in GOODBYE_KEYWORDS) else 0.0

    if intent == "BOOKING_TABLE":
        base = _score_from_keywords(text, RESERVATION_KEYWORDS)
        has_table_kw = any(k in text for k in TABLE_KEYWORDS)
        base += 0.6 if has_table_kw else 0.0
        base += _score_question_marker(text)
        # Boost when people count mentioned (e.g., "za 4 osebe")
        if has_table_kw and any(p in text for p in ["oseb", "osebe", "oseba", "ljudi", "nas bo"]):
            base += 0.3
        # Boost for intent expressions (rad bi, želim, prišli bi)
        if has_table_kw and any(i in text for i in ["rad bi", "rada bi", "želim", "zelim", "prišli bi", "prisli bi"]):
            base += 0.3
        return min(base, 1.0)

    if intent == "BOOKING_ROOM":
        base = _score_from_keywords(text, RESERVATION_KEYWORDS)
        base += 0.6 if any(k in text for k in ROOM_KEYWORDS) else 0.0
        base += _score_question_marker(text)
        return min(base, 1.0)

    if intent == "INQUIRY":
        if any(k in text for k in INQUIRY_KEYWORDS):
            return 0.9
        base = _score_question_marker(text)
        return min(base, 1.0)

    if intent == "PRODUCT":
        if any(k in text for k in PRODUCT_KEYWORDS):
            # Boost if purchase intent present
            if any(p in text for p in ["kupi", "naroč", "naroci", "cena", "cenik"]):
                return 0.95
            return 0.8
        base = _score_question_marker(text)
        return min(base, 1.0)

    if intent == "INFO":
        if any(k in text for k in INFO_KEYWORDS) or any(k in text for k in TOURISM_KEYWORDS):
            return 0.8
        base = _score_question_marker(text)
        return min(base, 1.0)

    if intent == "WINE":
        if any(k in text for k in WINE_KEYWORDS):
            return 0.9
        return 0.0

    if intent == "MENU":
        if any(k in text for k in MENU_KEYWORDS):
            return 0.9
        return 0.0

    return 0.0


def detect_intents(message: str) -> Dict[str, float]:
    intents = [
        "BOOKING_TABLE",
        "BOOKING_ROOM",
        "INFO",
        "PRODUCT",
        "INQUIRY",
        "GREETING",
        "GOODBYE",
        "WINE",
        "MENU",
    ]
    return {intent: compute_confidence(message, intent) for intent in intents}


def pick_primary_secondary(scores: Dict[str, float]) -> Tuple[str, str | None, float]:
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    primary, primary_conf = sorted_scores[0]
    if primary_conf < 0.5:
        return "GENERAL", None, 0.0
    secondary = None
    if len(sorted_scores) > 1 and sorted_scores[1][1] >= 0.5:
        secondary = sorted_scores[1][0]
    return primary, secondary, primary_conf
