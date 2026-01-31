"""
Menu parsing utilities - month extraction from text.
"""

from datetime import datetime, timedelta
from typing import Optional


# Slovene month names mapping
MONTH_MAP = {
    "januar": 1,
    "januarja": 1,
    "februar": 2,
    "februarja": 2,
    "marec": 3,
    "marca": 3,
    "april": 4,
    "aprila": 4,
    "maj": 5,
    "maja": 5,
    "junij": 6,
    "junija": 6,
    "julij": 7,
    "julija": 7,
    "avgust": 8,
    "avgusta": 8,
    "september": 9,
    "septembra": 9,
    "oktober": 10,
    "oktobra": 10,
    "november": 11,
    "novembra": 11,
    "december": 12,
    "decembra": 12,
}


def parse_month_from_text(message: str) -> Optional[int]:
    """Extract month number from Slovene month name in message."""
    lowered = message.lower()
    for key, val in MONTH_MAP.items():
        if key in lowered:
            return val
    return None


def parse_relative_month(message: str) -> Optional[int]:
    """Extract month from relative date words (danes, jutri)."""
    lowered = message.lower()
    today = datetime.now()
    if "jutri" in lowered:
        target = today + timedelta(days=1)
        return target.month
    if "danes" in lowered:
        return today.month
    return None
