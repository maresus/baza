from __future__ import annotations

from enum import Enum
from typing import Dict, Tuple
import re


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
    "rezer",
    "reser",
    "reserv",
    "book",
    "booking",
    "reservation",
}

BOOKING_HINTS = {
    "rad bi",
    "rada bi",
    "bi rad",
    "želim",
    "zelim",
    "prišli bi",
    "prisli bi",
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
    "wifi",
    "wi-fi",
    "rezervacija",
    "rezervacije",
    "rezerviran",
    "zajtrk",
    "večerja",
    "vecerja",
    "soba",
    "sobe",
    "koliko sob",
    "kakšne sobe",
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
    "salamo",
    "klobasa",
    "klobaso",
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
    "peneč", "penina", "penino", "penece",
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
PRICING_MARKERS = {"koliko stane", "cena", "cenik", "price", "cost"}


def _score_from_keywords(message: str, keywords: set[str]) -> float:
    return 0.4 if any(k in message for k in keywords) else 0.0


def _score_question_marker(message: str) -> float:
    return 0.3 if any(m in message for m in QUESTION_MARKERS) else 0.0


def _contains_word(message: str, words: set[str]) -> bool:
    # word-boundary match to avoid "sobota" -> "soba"
    return any(re.search(rf"\b{re.escape(w)}\b", message) for w in words)


def compute_confidence(message: str, intent: str) -> float:
    text = message.lower()

    if intent == "GREETING":
        return 1.0 if any(k in text for k in GREETING_KEYWORDS) else 0.0
    if intent == "GOODBYE":
        return 1.0 if any(k in text for k in GOODBYE_KEYWORDS) else 0.0

    if intent == "BOOKING_TABLE":
        has_table_kw = _contains_word(text, TABLE_KEYWORDS)
        has_booking_hint = any(k in text for k in RESERVATION_KEYWORDS) or any(k in text for k in BOOKING_HINTS)
        has_people_hint = any(p in text for p in ["oseb", "osebe", "oseba", "ljudi", "nas bo", "za 2", "za 3", "za 4", "za 5", "za 6"])
        has_date_hint = any(d in text for d in ["sobot", "nedelj", "vikend", "danes", "jutri"]) or bool(
            re.search(r"\b\d{1,2}[./]\d{1,2}([./]\d{2,4})?\b", text)
        )
        if not has_table_kw:
            return 0.0
        # Cenovna/info vprašanja o kosilu naj ostanejo INFO.
        if any(m in text for m in PRICING_MARKERS) and "rezerv" not in text and "book" not in text:
            return 0.0
        base = 0.45
        if has_booking_hint:
            base += 0.30
        if has_people_hint:
            base += 0.30
        if has_date_hint:
            base += 0.20
        base += _score_question_marker(text)
        return min(base, 1.0)

    if intent == "BOOKING_ROOM":
        has_room_kw = _contains_word(text, ROOM_KEYWORDS)
        has_booking_hint = any(k in text for k in RESERVATION_KEYWORDS) or any(k in text for k in BOOKING_HINTS)
        has_people_or_nights = any(p in text for p in ["oseb", "osebe", "za 2", "za 3", "za 4", "noč", "noc", "vikend", "prosto", "presp", "družin", "druz"])
        if not has_room_kw:
            return 0.0
        # Cenovna/info vprašanja o sobah naj ostanejo INFO.
        if any(m in text for m in PRICING_MARKERS) and "rezerv" not in text and "book" not in text:
            return 0.0
        base = 0.45
        if has_booking_hint:
            base += 0.30
        if has_people_or_nights:
            base += 0.30
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
