from __future__ import annotations

from typing import Optional
import re
import difflib

from app.rag.chroma_service import answer_tourist_question, is_tourist_query
from app.services.flows.info_flow import is_hours_question
from app.services.intent_helpers import (
    INFO_KEYWORDS,
    PRODUCT_FOLLOWUP_PHRASES,
    PRODUCT_STEMS,
    RESERVATION_START_PHRASES,
    detect_info_intent,
    detect_product_intent,
    is_reservation_related,
    is_reservation_typo,
)
from app.services.parsing import extract_date, extract_date_range, extract_time, parse_people_count

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

FARM_INFO_KEYWORDS = {
    "kje",
    "naslov",
    "lokacija",
    "kako pridem",
    "priti",
    "parking",
    "telefon",
    "številka",
    "stevilka",
    "email",
    "kontakt",
    "odprti",
    "odprto",
    "delovni čas",
    "ura",
    "kdaj",
    "wifi",
    "internet",
    "klima",
    "nahajate",
    "navodila",
    "pot",
    "avtom",
    "parkirišče",
    "parkirisce",
}

FOOD_GENERAL_KEYWORDS = {"hrana", "jest", "jesti", "ponujate", "kuhate", "jedilnik?"}

HELP_KEYWORDS = {"pomoč", "help", "kaj znaš", "kaj znate", "kaj lahko", "možnosti"}

WEEKLY_KEYWORDS = {
    "teden",
    "tedensk",
    "čez teden",
    "med tednom",
    "sreda",
    "četrtek",
    "petek",
    "degustacij",
    "kulinarično",
    "doživetje",
    "4-hodn",
    "5-hodn",
    "6-hodn",
    "7-hodn",
    "4 hodn",
    "5 hodn",
    "6 hodn",
    "7 hodn",
    "štiri hod",
    "stiri hod",
    "pet hod",
    "šest hod",
    "sest hod",
    "sedem hod",
    "4-hodni meni",
    "5-hodni meni",
    "6-hodni meni",
    "7-hodni meni",
}

PRICE_KEYWORDS = {
    "cena",
    "cene",
    "cenika",
    "cenik",
    "koliko stane",
    "koliko stal",
    "koliko košta",
    "koliko kosta",
    "ceno",
    "cenah",
}

WINE_KEYWORDS = {
    "vino",
    "vina",
    "vin",
    "rdec",
    "rdeca",
    "rdeče",
    "rdece",
    "belo",
    "bela",
    "penin",
    "penina",
    "peneč",
    "muskat",
    "muškat",
    "rizling",
    "sauvignon",
    "frankinja",
    "pinot",
}


def is_goodbye(message: str) -> bool:
    lowered = message.lower().strip()
    if lowered in GOODBYE_KEYWORDS:
        return True
    if any(keyword in lowered for keyword in ["hvala", "adijo", "nasvidenje", "čao", "ciao", "bye"]):
        return True
    return False


def is_menu_query(message: str) -> bool:
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


def parse_reservation_type(message: str) -> Optional[str]:
    lowered = message.lower()

    def _has_term(term: str) -> bool:
        if " " in term:
            return term in lowered
        return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered) is not None

    room_keywords = [
        "soba",
        "sobe",
        "sobo",
        "sob",
        "nočitev",
        "prenocitev",
        "noč",
        "prenočiti",
        "prespati",
        "room",
        "rooms",
        "stay",
        "overnight",
        "night",
        "accommodation",
        "sleep",
        "zimmer",
        "übernachtung",
        "übernachten",
        "nacht",
        "schlafen",
        "unterkunft",
    ]
    if any(_has_term(word) for word in room_keywords):
        return "room"

    table_keywords = [
        "miza",
        "mizo",
        "mize",
        "rezervacija mize",
        "kosilo",
        "večerja",
        "kosilu",
        "mizico",
        "jest",
        "jesti",
        "table",
        "lunch",
        "dinner",
        "meal",
        "eat",
        "dining",
        "restaurant",
        "tisch",
        "mittagessen",
        "abendessen",
        "essen",
        "speisen",
        "restaurant",
    ]
    if any(_has_term(word) for word in table_keywords):
        return "table"
    return None


def is_booking_intent(message: str) -> bool:
    lowered = message.lower()
    if any(phrase in lowered for phrase in RESERVATION_START_PHRASES):
        return True
    intent_tokens = ["rad bi", "rada bi", "želim", "zelim", "hočem", "hocem", "imel bi", "imela bi"]
    has_intent = any(tok in lowered for tok in intent_tokens)
    has_type = parse_reservation_type(message) in {"room", "table"}
    return has_intent and has_type




AFFIRMATIVE_KEYWORDS = {
    "da",
    "ja",
    "ok",
    "okej",
    "v redu",
    "seveda",
    "lahko",
    "yes",
    "y",
}

NEGATIVE_KEYWORDS = {"ne", "no", "ne hvala", "no thanks"}


def is_affirmative(message: str) -> bool:
    lowered = message.strip().lower()
    return lowered in AFFIRMATIVE_KEYWORDS


def is_negative(message: str) -> bool:
    lowered = message.strip().lower()
    return lowered in NEGATIVE_KEYWORDS


def is_explicit_cancel_command(message: str) -> bool:
    lowered = message.lower().strip()
    if lowered in {"stop", "konec", "prekini", "cancel", "quit", "exit"}:
        return True
    return any(token in lowered for token in {"pustimo", "pozabi", "ne rabim", "ni treba", "prekin"})


def should_switch_from_reservation(message: str, state: dict[str, Optional[str | int]]) -> bool:
    lowered = message.lower()
    step = state.get("step")
    if is_tourist_query(message) and step not in {"awaiting_name", "awaiting_phone", "awaiting_email"}:
        return True
    if is_reservation_related(message):
        return False
    if is_affirmative(message) or lowered in {"ne", "no"}:
        return False
    if extract_date(message) or extract_date_range(message) or extract_time(message):
        return False
    if parse_people_count(message).get("total"):
        return False
    if state.get("step") in {"awaiting_phone", "awaiting_email"}:
        return False
    if detect_info_intent(message) or detect_product_intent(message) or is_menu_query(message) or is_hours_question(message):
        return True
    if is_tourist_query(message):
        return True
    return False


def tourist_answer(message: str) -> Optional[str]:
    if not is_tourist_query(message):
        return None
    try:
        answer = answer_tourist_question(message)
    except Exception as exc:
        print(f"[TOURIST] Failed to answer tourist question: {exc}")
        answer = None
    if answer:
        return answer
    return "Žal nimam turističnih informacij o tem kraju. Lahko vprašate kaj drugega ali nas pokličete za priporočila."

def classify_intent(
    message: str,
    state: dict[str, Optional[str | int]],
    last_product_query: Optional[str] = None,
    last_wine_query: Optional[str] = None,
) -> str:
    lower_message = message.lower()

    if state["step"] is not None:
        critical_steps = {"awaiting_name", "awaiting_phone", "awaiting_email"}
        if state.get("step") not in critical_steps:
            if is_tourist_query(message):
                return "tourist_info"
            if is_menu_query(message):
                return "menu"
            if is_hours_question(message):
                return "farm_info"
            if detect_info_intent(message):
                return "info"
            if detect_product_intent(message):
                return "product"
        return "reservation"

    if is_hours_question(message):
        return "farm_info"

    if re.search(r"koliko\s+soba", lower_message) or re.search(r"koliko\s+sob", lower_message):
        return "room_info"

    rezerv_patterns = ["rezerv", "rezev", "rezer", "book", "buking", "bokking", "reserve", "reservation"]
    soba_patterns = ["sobo", "sobe", "soba", "room"]
    miza_patterns = ["mizo", "mize", "miza", "table"]
    has_rezerv = any(p in lower_message for p in rezerv_patterns)
    has_soba = any(p in lower_message for p in soba_patterns)
    has_miza = any(p in lower_message for p in miza_patterns)
    if has_rezerv and (has_soba or has_miza or "nočitev" in lower_message or "nocitev" in lower_message):
        return "reservation"
    if is_reservation_typo(message) and (has_soba or has_miza):
        return "reservation"
    if any(phrase in lower_message for phrase in RESERVATION_START_PHRASES):
        return "reservation"

    if is_goodbye(message):
        return "goodbye"

    if is_menu_query(message):
        return "menu"

    sobe_keywords = [
        "sobe",
        "soba",
        "sobo",
        "nastanitev",
        "prenočitev",
        "nočitev nočitve",
        "rooms",
        "room",
        "accommodation",
    ]
    if any(kw in lower_message for kw in sobe_keywords) and "rezerv" not in lower_message and "book" not in lower_message:
        return "room_info"

    if any(keyword in lower_message for keyword in WINE_KEYWORDS):
        return "wine"

    if last_wine_query and (
        any(phrase in lower_message for phrase in ["še", "še kakšn", "še kater", "kaj pa", "drug", "katera", "katere"])
        or re.search(r"\bkater[aeio]\b", lower_message)
    ):
        return "wine_followup"

    if any(word in lower_message for word in PRICE_KEYWORDS):
        if any(word in lower_message for word in ["sob", "nočitev", "nocitev", "noč", "spanje", "bivanje"]):
            return "room_pricing"

    if any(word in lower_message for word in WEEKLY_KEYWORDS):
        return "weekly_menu"
    if re.search(r"\b[4-7]\s*-?\s*hodn", lower_message):
        return "weekly_menu"

    if any(keyword in lower_message for keyword in FARM_INFO_KEYWORDS):
        return "farm_info"

    if is_tourist_query(message):
        return "tourist_info"

    if any(stem in lower_message for stem in PRODUCT_STEMS):
        return "product"

    if last_product_query and any(phrase in lower_message for phrase in PRODUCT_FOLLOWUP_PHRASES):
        return "product_followup"

    if any(keyword in lower_message for keyword in INFO_KEYWORDS):
        return "info"

    if any(word in lower_message for word in FOOD_GENERAL_KEYWORDS) and not is_menu_query(message):
        return "food_general"

    if any(word in lower_message for word in HELP_KEYWORDS):
        return "help"

    if any(word in lower_message for word in WEEKLY_KEYWORDS):
        return "weekly_menu"

    return "default"




RESET_WORDS = [
    "reset",
    "začni znova",
    "zacni znova",
    "od začetka",
    "od zacetka",
    "zmota",
    "zmoto",
    "zmotu",
    "zmotil",
    "zmotila",
    "zgresil",
    "zgrešil",
    "zgrešila",
    "zgresila",
    "napačno",
    "narobe",
    "popravi",
    "nova rezervacija",
]

EXIT_WORDS = [
    "konec",
    "stop",
    "prekini",
    "nehaj",
    "pustimo",
    "pozabi",
    "ne rabim",
    "ni treba",
    "drugič",
    "drugic",
    "cancel",
    "quit",
    "exit",
    "pusti",
]


def detect_reset_request(message: str) -> bool:
    lowered = message.lower()
    return any(word in lowered for word in RESET_WORDS + EXIT_WORDS)



def is_event_inquiry_request(message: str) -> bool:
    lowered = message.lower()
    if re.search(r"(team\w*build|teamb\w*|porok\w*|cater\w*|pogost\w*|dogod\w*)", lowered):
        return True
    words = re.findall(r"[a-zA-ZčšžČŠŽ]+", lowered)
    for word in words:
        if difflib.SequenceMatcher(None, word, "teambuilding").ratio() >= 0.65:
            return True
    return False



def is_product_followup(message: str, last_product_query: str | None = None) -> bool:
    lowered = message.lower()
    if not last_product_query:
        return False
    if any(phrase in lowered for phrase in PRODUCT_FOLLOWUP_PHRASES):
        return True
    return False


def detect_intent(
    message: str,
    state: dict[str, Optional[str | int]],
    last_product_query: Optional[str] = None,
    last_wine_query: Optional[str] = None,
) -> str:
    return classify_intent(
        message,
        state,
        last_product_query=last_product_query,
        last_wine_query=last_wine_query,
    )
