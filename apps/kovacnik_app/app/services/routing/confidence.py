from __future__ import annotations

from typing import Dict

from app.services.intent_helpers import (
    detect_info_intent,
    detect_product_intent,
    is_inquiry_trigger,
    is_reservation_related,
    is_reservation_typo,
)


INTENTS = [
    "BOOKING_TABLE",
    "BOOKING_ROOM",
    "INFO",
    "PRODUCT",
    "INQUIRY",
    "GREETING",
    "GOODBYE",
    "GENERAL",
]


def _has_any(text: str, tokens: set[str]) -> bool:
    return any(tok in text for tok in tokens)


def _greeting_score(text: str) -> float:
    greetings = {"zdravo", "živjo", "pozdrav", "dober dan", "hello", "hi"}
    return 1.0 if _has_any(text, greetings) else 0.0


def _goodbye_score(text: str) -> float:
    goodbyes = {"adijo", "nasvidenje", "hvala", "lep dan", "bye", "se vidimo", "lp"}
    return 1.0 if _has_any(text, goodbyes) else 0.0


def _booking_room_score(text: str) -> float:
    if not is_reservation_related(text):
        return 0.0
    room_tokens = {"soba", "sobo", "sobe", "room", "zimmer", "nočitev", "nocitev", "nastanitev", "preno"}
    if _has_any(text, room_tokens):
        return 0.9
    if is_reservation_typo(text):
        return 0.6
    return 0.5


def _booking_table_score(text: str) -> float:
    if not is_reservation_related(text):
        return 0.0
    table_tokens = {"miza", "mizo", "mize", "kosilo", "večerja", "vecerja", "table"}
    if _has_any(text, table_tokens):
        return 0.9
    if is_reservation_typo(text):
        return 0.6
    return 0.5


def _info_score(text: str) -> float:
    if detect_info_intent(text):
        return 0.8
    info_words = {"kdaj", "kje", "kako", "koliko", "kakšne", "kakšen", "ali imate", "a imate"}
    return 0.5 if _has_any(text, info_words) else 0.0


def _product_score(text: str) -> float:
    if detect_product_intent(text):
        return 0.8
    product_words = {"izdelek", "katalog", "trgovina", "pesto", "marmelada", "namaz", "paket"}
    return 0.5 if _has_any(text, product_words) else 0.0


def _inquiry_score(text: str) -> float:
    if is_inquiry_trigger(text):
        return 0.9
    inquiry_words = {"povpraš", "ponudb", "poroka", "teambuilding", "catering"}
    return 0.6 if _has_any(text, inquiry_words) else 0.0


def score_intent_confidence(message: str) -> Dict[str, float]:
    text = message.lower().strip()
    return {
        "BOOKING_TABLE": _booking_table_score(text),
        "BOOKING_ROOM": _booking_room_score(text),
        "INFO": _info_score(text),
        "PRODUCT": _product_score(text),
        "INQUIRY": _inquiry_score(text),
        "GREETING": _greeting_score(text),
        "GOODBYE": _goodbye_score(text),
        "GENERAL": 0.1,
    }
