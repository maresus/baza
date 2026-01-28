from app.services.intent_helpers import PRODUCT_STEMS, is_reservation_related
from app.services.parsing import extract_date, extract_date_range, parse_people_count


def get_last_assistant_message(history: list[dict]) -> str:
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return ""


def get_last_user_message(history: list[dict]) -> str:
    for msg in reversed(history):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def get_last_reservation_user_message(history: list[dict]) -> str:
    for msg in reversed(history):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if (
            is_reservation_related(content)
            or extract_date(content)
            or extract_date_range(content)
            or parse_people_count(content).get("total")
        ):
            return content
    return ""


def last_bot_mentions_reservation(last_bot: str) -> bool:
    text = last_bot.lower()
    return any(token in text for token in ["rezerv", "reserve", "booking", "zimmer", "room", "mizo", "table"])


def last_bot_mentions_product_order(last_bot: str) -> bool:
    text = last_bot.lower()
    if "naroč" in text or "naroc" in text:
        return True
    if "trgovin" in text or "izdelek" in text or "katalog" in text:
        return True
    if any(stem in text for stem in PRODUCT_STEMS):
        return True
    return False
