import os
import random
import re
import difflib
import json
from pathlib import Path
from typing import Optional

from app.brand.config import (
    BRAND_NAME,
    BRAND_SHORT,
    FARM_INFO,
    INFO_EMAIL,
    INFO_RESPONSES,
    INFO_RESPONSES_VARIANTS,
    SHOP_BASE_URL,
    SHOP_URL,
)

from app.services.product_service import find_products

SHORT_MODE = os.getenv("SHORT_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
STRICT_POLICY = os.getenv("STRICT_POLICY", "true").strip().lower() in {"1", "true", "yes", "on"}
DISABLE_INQUIRY = os.getenv("DISABLE_INQUIRY", "true").strip().lower() in {"1", "true", "yes", "on"}

_TOPIC_RESPONSES: dict[str, str] = {}
_topics_path = Path(__file__).resolve().parents[2] / "data" / "knowledge_topics.json"
if _topics_path.exists():
    try:
        for item in json.loads(_topics_path.read_text(encoding="utf-8")):
            key = item.get("key")
            answer = item.get("answer")
            if key and answer:
                _TOPIC_RESPONSES[key] = answer
    except Exception:
        _TOPIC_RESPONSES = {}

PRODUCT_RESPONSES = {
    "marmelada": [
        "Imamo **domače marmelade**: jagodna, marelična, borovničeva, malinova, stara brajda, božična. Cena od 5,50 €.\n\nKupite ob obisku ali naročite v spletni trgovini: https://kmetijapodgoro.si/katalog (sekcija Marmelade).",
        "Ponujamo več vrst **domačih marmelad** – jagoda, marelica, borovnica, malina, božična, stara brajda. Cena 5,50 €/212 ml.\n\nNa voljo ob obisku ali v spletni trgovini: https://kmetijapodgoro.si/katalog.",
    ],
    "liker": [
        "Imamo **domače likerje**: borovničev, žajbljev, aronija, smrekovi vršički (3 cl/5 cl) in za domov 350 ml (13–15 €), tepkovec 15 €.\n\nKupite ob obisku ali naročite: https://kmetijapodgoro.si/katalog (sekcija Likerji in žganje).",
        "Naši **domači likerji** (žajbelj, smrekovi vršički, aronija, borovničevec) in žganja (tepkovec, tavžentroža). Cene za 350 ml od 13 €.\n\nNa voljo v spletni trgovini: https://kmetijapodgoro.si/katalog ali ob obisku.",
    ],
    "bunka": [
        "Imamo **pohorsko bunko** (18–21 €) ter druge mesnine.\n\nNa voljo ob obisku ali v spletni trgovini: https://kmetijapodgoro.si/katalog (sekcija Mesnine).",
        "Pohorska bunka je na voljo (18–21 €), skupaj s suho klobaso in salamo.\n\nNaročilo: https://kmetijapodgoro.si/katalog.",
    ],
    "izdelki_splosno": [
        "Prodajamo **domače izdelke** (marmelade, likerji/žganja, mesnine, čaji, sirupi, paketi). Trgovina: https://kmetijapodgoro.si/katalog.",
        "Na voljo so **marmelade, likerji/žganja, mesnine, čaji, sirupi, darilni paketi**. Trgovina: https://kmetijapodgoro.si/katalog.",
    ],
    "gibanica_narocilo": """Za naročilo gibanice za domov:
- Pohorska gibanica s skuto: 40 € za 10 kosov
- Pohorska gibanica z orehi: 45 € za 10 kosov

Napišite, koliko kosov in za kateri datum želite prevzem. Ob večjih količinah (npr. 40 kosov) potrebujemo predhodni dogovor. Naročilo: info@kmetijapodgoro.si""",
}

PRODUCT_STEMS = {
    "salam",
    "klobas",
    "sir",
    "izdelek",
    "paket",
    "marmelad",
    "džem",
    "dzem",
    "liker",
    "namaz",
    "pesto",
    "cemaz",
    "čemaž",
    "bunk",
}

RESERVATION_START_PHRASES = {
    "rezervacija sobe",
    "rad bi rezerviral sobo",
    "rad bi rezervirala sobo",
    "želim rezervirati sobo",
    "bi rezerviral sobo",
    "bi rezervirala sobo",
    "rezerviral bi sobo",
    "rezerviraj sobo",
    "rabim sobo",
    "iščem sobo",
    "sobo prosim",
    "prenočitev",
    "nastanitev",
    "nočitev",
    "rezervacija mize",
    "rad bi rezerviral mizo",
    "rad bi rezervirala mizo",
    "rad bi imel mizo",
    "rad bi imela mizo",
    "zelim mizo",
    "želim mizo",
    "hocem mizo",
    "hočem mizo",
    "mizo bi",
    "mizo za",
    "mize za",
    "rezerviram mizo",
    "rezervirala bi mizo",
    "rezerviral bi mizo",
    "book a room",
    "booking",
    "i want to book",
    "i would like to book",
    "i'd like to book",
    "room reservation",
    "i need a room",
    "accommodation",
    "stay for",
    "book a table",
    "table reservation",
    "lunch reservation",
    "dinner reservation",
    "zimmer reservieren",
    "ich möchte ein zimmer",
    "ich möchte buchen",
    "ich möchte reservieren",
    "ich will buchen",
    "übernachtung",
    "unterkunft",
    "buchen",
    "tisch reservieren",
    "mittagessen",
    "abendessen",
    "prenotare una camera",
    "prenotazione",
    "camera",
    "alloggio",
}

INFO_KEYWORDS = {
    "kje",
    "lokacija",
    "naslov",
    "kosilo",
    "vikend kosilo",
    "vikend",
    "hrana",
    "sob",
    "soba",
    "sobe",
    "nočitev",
    "nočitve",
    "zajtrk",
    "večerja",
    "otroci",
    "popust",
}

PRODUCT_FOLLOWUP_PHRASES = {
    "kaj pa",
    "kaj še",
    "katere",
    "katere pa",
    "kakšne",
    "še kaj",
    "kje naročim",
    "kje lahko naročim",
    "kako naročim",
    "kako lahko naročim",
}

INFO_FOLLOWUP_PHRASES = {
    "še kaj",
    "še kero",
    "še kero drugo",
    "kaj pa še",
    "pa še",
    "še kakšna",
    "še kakšno",
    "še kakšne",
    "še kaj drugega",
}


def get_info_response(key: str) -> str:
    if key.startswith("topic:"):
        topic_key = key.split(":", 1)[1]
        if STRICT_POLICY and topic_key in INFO_RESPONSES:
            return maybe_shorten_response(_apply_policy(INFO_RESPONSES[topic_key]))
        if topic_key in _TOPIC_RESPONSES:
            return maybe_shorten_response(_apply_policy(_TOPIC_RESPONSES[topic_key]))
    if key in INFO_RESPONSES_VARIANTS:
        variants = INFO_RESPONSES_VARIANTS[key]
        chosen = min(variants, key=len) if SHORT_MODE else random.choice(variants)
        # Keep rich formatting for long structured answers.
        if key in {
            "jedilnik",
            "menu_info",
            "menu_full",
            "sobe",
            "sobe_info",
            "tedenska_ponudba",
            "tedenski_5hodni",
            "tedenski_6hodni",
        }:
            return chosen
        # Keep manual formatting (lists/line-breaks) for info texts.
        if "\n" in chosen or "•" in chosen or "- **" in chosen or "***" in chosen:
            return chosen
        return maybe_shorten_response(_apply_policy(chosen))
    return maybe_shorten_response(_apply_policy(INFO_RESPONSES.get(key, "Kako vam lahko pomagam?")))


def maybe_shorten_response(text: str) -> str:
    if not SHORT_MODE:
        return text
    if not text:
        return text
    if len(text) <= 520:
        return text
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > 4:
        return "\n".join(lines[:4]) + "\n\nZa več informacij vprašajte naprej."
    clipped = text[:520]
    if ". " in clipped:
        clipped = clipped.rsplit(". ", 1)[0] + "."
    return clipped


def _apply_policy(text: str) -> str:
    """Apply strict policy: no questions, no unsolicited offers, keep short."""
    if not STRICT_POLICY or not text:
        return text
    # Normalize whitespace
    normalized = " ".join(text.replace("\n", " ").split())
    normalized = re.sub(r"(?i)trgovina:\s*https?://\\S+", "", normalized).strip()
    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    filtered = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        low = s_clean.lower()
        # Remove questions or unsolicited offers
        if s_clean.endswith("?"):
            continue
        if any(p in low for p in ["če želite", "vas zanima", "lahko vam", "priporočam", "predlagam", "sporočite", "povejte"]):
            continue
        filtered.append(s_clean)
    # Keep max 4 sentences
    if not filtered:
        return normalized[:300].rstrip(".") + "."
    return " ".join(filtered[:4])


def _slugify(text: str) -> str:
    slug = text.lower()
    slug = slug.replace("č", "c").replace("š", "s").replace("ž", "z")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def _product_link_from_url(url: str, title: str | None) -> str:
    if url and "/izdelek/" in url:
        slug = url.split("/izdelek/")[1].split("/")[0]
        return f"{SHOP_BASE_URL}/izdelek/{slug}/"
    if title:
        return f"{SHOP_BASE_URL}/izdelek/{_slugify(title)}/"
    return f"{SHOP_BASE_URL}/izdelek/"


def detect_info_intent(message: str) -> Optional[str]:
    text = message.lower().strip()
    text = text.replace("‑", "-").replace("–", "-").replace("—", "-")
    if text in {"zdravo", "živjo", "hej", "hello", "dober dan", "pozdrav", "pozdravljeni"}:
        return "pozdrav"
    if any(w in text for w in ["kako ste", "kako si", "kako gre", "kako vam gre", "kako vam grejo stvari"]):
        return "smalltalk"
    if any(
        w in text
        for w in [
            "kdaj ste odprti",
            "odpiralni",
            "delovni čas",
            "kdaj odprete",
            "zadnji prihod",
            "ponedelj",
            "torek",
            "ob ponedeljkih",
            "ob torkih",
        ]
    ):
        return "odpiralni_cas"
    if "zajtrk" in text and "večerj" not in text:
        return "zajtrk"
    if any(w in text for w in ["koliko stane večerja", "cena večerje", "večerja", "vecerja", "večerjo"]):
        return "vecerja"
    if any(
        w in text
        for w in [
            "cena sobe",
            "cena nočit",
            "cena nocit",
            "koliko stane noč",
            "koliko stane noc",
            "cenik",
            "koliko stane soba",
            "koliko stane nočitev",
        ]
    ):
        return "cena_sobe"
    if any(w in text for w in ["koliko sob", "kakšne sobe", "koliko oseb v sobo", "kolko oseb v sobo", "kapaciteta sob"]):
        return "sobe"
    if "klim" in text:
        return "klima"
    if "wifi" in text or "wi-fi" in text or "internet" in text:
        return "wifi"
    if any(w in text for w in ["prijava", "odjava", "check in", "check out"]):
        return "prijava_odjava"
    if any(w in text for w in ["parkir", "parking"]):
        return "parking"
    if re.search(r"(?<!\w)(pes|psa|psi|psov|kuž|kuz|dog)(?!\w)", text) or any(
        w in text for w in ["mačk", "ljubljenč", "hišni ljubljen"]
    ):
        return "pets_policy"
    if any(w in text for w in ["jah", "jaha", "jahan", "jahanje", "jahamo", "jahati"]):
        return "jahanje"
    if any(
        w in text
        for w in [
            "žival",
            "zival",
            "konj",
            "poni",
            "zajc",
            "zajček",
            "zajcek",
            "zajčk",
            "zajck",
            "kunec",
            "bož",
            "boz",
        ]
    ):
        return "zivali"
    if any(w in text for w in ["gospodar", "gosp", "lastnik", "kdo vodi", "vodi kmetijo", "vodi domačijo"]):
        return "gospodar"
    if any(w in text for w in ["plačilo", "kartic", "gotovina"]):
        return "placilo"
    if any(w in text for w in ["kontakt", "telefon", "telefonsko", "številka", "stevilka", "gsm", "mobitel", "mobile", "phone"]):
        return "kontakt"
    if any(w in text for w in ["email", "e-mail", "epošta", "e-pošta", "mail"]):
        return "kontakt"
    if re.search(r"kako\\s+.*pridem", text):
        return "lokacija"
    if any(
        w in text
        for w in [
            "kje ste",
            "kje se nahajate",
            "naslov",
            "lokacija",
            "kje ste doma",
            "kje ste locirani",
            "kako pridem",
            "kako pridem do vas",
            "kako pridem do domačije",
            "kako pridem do kmetije",
            "navodila za pot",
        ]
    ):
        return "lokacija"
    if any(w in text for w in ["minimal", "najmanj noči", "najmanj nočitev", "min nočitev"]):
        return "min_nocitve"
    if any(w in text for w in ["koliko miz", "kapaciteta"]):
        return "kapaciteta_mize"
    if any(w in text for w in ["alergij", "gluten", "lakto", "vegan"]):
        return "alergije"
    if text.strip() in {"katera", "katere", "katera vina", "katere vina"}:
        return "vina"
    if any(w in text for w in ["vino", "vina", "vinsko", "vinska", "wine", "wein", "vinci"]):
        return "vina"
    if (
        any(w in text for w in ["smučišče", "smucisce", "smučišč", "smucisc", "smučanje", "smucanje"])
        or re.search(r"\bski\b", text)
    ):
        return "smucisce"
    if any(w in text for w in ["terme", "termal", "wellness"]) or re.search(r"(?<!\w)spa(?!\w)", text):
        return "terme"
    if any(w in text for w in ["dež", "dez", "dezuje", "dežuje", "slabo vreme", "slabo vreme", "če dežuje", "ce dez"]):
        return "dez"
    if any(
        w in text
        for w in [
            "izlet",
            "izleti",
            "znamenitost",
            "naravne",
            "narava",
            "pohod",
            "pohodni",
            "okolici",
            "bližini",
            "pohorje",
            "slap",
            "jezero",
            "vintgar",
            "razgled",
            "bistriški",
            "ščrno jezero",
            "šumik",
        ]
    ):
        return "turizem"
    if any(w in text for w in ["kolo", "koles", "kolesar", "bike", "e-kolo", "ekolo", "bicikl"]):
        return "kolesa"
    if "traktor" in text:
        return "traktor"
    if "skalca" in text or ("slap" in text and "skalc" in text):
        return "skalca"
    if "darilni bon" in text or ("bon" in text and "daril" in text):
        return "darilni_boni"
    if re.search(r"(?<!\d)5\s*-?\s*hod", text):
        return "tedenski_5hodni"
    if re.search(r"(?<!\d)6\s*-?\s*hod", text):
        return "tedenski_6hodni"
    if any(w in text for w in ["čez teden", "cez teden", "med tednom", "tedenska ponudba", "tedenski meni", "tedenski", "degustacijski", "degustacija", "4-hodni", "5-hodni", "6-hodni", "7-hodni", "koliko hodov"]):
        return "tedenska_ponudba"
    if ("vikend" in text or "ponudba" in text) and any(
        w in text for w in ["vikend", "ponudba", "kosilo", "meni", "menu", "jedil"]
    ):
        return "jedilnik"
    if any(
        w in text
        for w in [
            "jedilnik",
            "jedilnk",
            "jedilnku",
            "jedlnik",
            "meni",
            "menij",
            "meniju",
            "menu",
            "kaj imate za jest",
            "kaj imate za kosilo",
            "kaj ponujate",
            "kaj strežete",
            "kaj je za kosilo",
            "kaj je za večerjo",
            "kaj je za vecerjo",
            "koslo",
        ]
    ):
        return "jedilnik"
    if any(w in text for w in ["zadnji prihod", "zadnji prihod na kosilo"]):
        return "odpiralni_cas"
    if any(w in text for w in ["družin", "druzina", "druzino"]):
        return "druzina"
    if "kmetij" in text or "kmetijo" in text:
        return "kmetija"
    if "gibanic" in text:
        if any(tok in text for tok in ["kaj je", "pohorska gibanica", "kaj pomeni"]) and "imate" not in text:
            return "gibanica"
        return None
    if any(w in text for w in ["izdelk", "trgovin", "katalog", "prodajate"]):
        return None
    if "priporoč" in text or "priporoc" in text:
        return "priporocilo"
    return None


def detect_product_intent(message: str) -> Optional[str]:
    text = message.lower()
    if "čemažev pesto" in text or "cemazev pesto" in text:
        return "cemazev_pesto"
    if "bučni namaz" in text or "bucni namaz" in text:
        return "bucni_namaz"
    if "jetrna paštet" in text or "jetrna pastet" in text:
        return "jetrna_pastetka"
    if any(w in text for w in ["liker", "žgan", "zgan", "borovnič", "orehov", "alkohol"]):
        return "liker"
    if any(w in text for w in ["marmelad", "džem", "dzem", "jagod", "marelič"]):
        return "marmelada"
    if "gibanic" in text:
        return "gibanica_narocilo"
    if any(w in text for w in ["bunka", "bunko", "bunke"]):
        return "bunka"
    if any(w in text for w in ["paštet", "pastet", "namaz", "pesto"]):
        return "namaz"
    if any(w in text for w in ["salam", "klobas", "mesnin"]):
        return "mesn"
    if any(w in text for w in ["čaj", "caj"]):
        return "caj"
    if any(w in text for w in ["sirup", "sok"]):
        return "sirup"
    if any(w in text for w in ["izdelk", "prodaj", "kupiti", "kupim", "trgovin", "katalog"]):
        return "izdelki_splosno"
    return None


def get_product_response(key: str) -> str:
    if key == "gibanica_narocilo":
        return f"Tega izdelka ni v spletni trgovini. Pišite na {INFO_EMAIL}."
    key_map = {
        "cemazev_pesto": "čemažev pesto",
        "bucni_namaz": "bučni namaz",
        "jetrna_pastetka": "jetrna paštetka",
    }
    # Use KB-driven product answer to return price + direct link
    return answer_product_question(key_map.get(key, key or ""))


def is_food_question_without_booking_intent(message: str) -> bool:
    text = message.lower()
    food_words = [
        "meni",
        "menu",
        "hrana",
        "jed",
        "kosilo",
        "večerja",
        "kaj ponujate",
        "kaj strežete",
        "kaj imate za kosilo",
        "jedilnik",
    ]
    booking_words = ["rezerv", "book", "želim", "rad bi", "radi bi", "za datum", "oseb", "mizo", "rezervacijo"]
    has_food = any(w in text for w in food_words)
    has_booking = any(w in text for w in booking_words)
    return has_food and not has_booking


def is_info_only_question(message: str) -> bool:
    text = message.lower()
    info_words = [
        "koliko",
        "kakšn",
        "kakšen",
        "kdo",
        "ali imate",
        "a imate",
        "kaj je",
        "kdaj",
        "kje",
        "kako",
        "cena",
        "stane",
        "vključen",
    ]
    booking_words = [
        "rezervir",
        "book",
        "bi rad",
        "bi radi",
        "želim",
        "želimo",
        "za datum",
        "nocitev",
        "nočitev",
        "oseb",
    ]
    has_info = any(w in text for w in info_words)
    has_booking = any(w in text for w in booking_words)
    return has_info and not has_booking


def is_reservation_typo(message: str) -> bool:
    words = re.findall(r"[a-zA-ZčšžČŠŽ]+", message.lower())
    targets = ["rezervacija", "rezervirati", "rezerviram", "rezerviraj"]
    for word in words:
        for target in targets:
            if difflib.SequenceMatcher(None, word, target).ratio() >= 0.75:
                return True
    return False


def is_ambiguous_reservation_request(message: str) -> bool:
    lowered = message.lower()
    reserv_words = ["rezerv", "book", "booking", "reserve", "reservation", "zimmer", "buchen"]
    type_words = ["soba", "sobo", "sobe", "room", "miza", "mizo", "table", "nočitev", "nocitev"]
    has_reserv = any(w in lowered for w in reserv_words)
    has_type = any(w in lowered for w in type_words)
    return has_reserv and not has_type


def is_ambiguous_inquiry_request(message: str) -> bool:
    if DISABLE_INQUIRY:
        return False
    lowered = message.lower()
    if any(w in lowered for w in ["večerj", "vecerj"]):
        return False
    explicit = ["povpraš", "ponudb", "naročil", "naročilo", "naroč", "količin"]
    has_explicit = any(w in lowered for w in explicit)
    has_number = re.search(r"\d", lowered) is not None
    has_product = any(stem in lowered for stem in PRODUCT_STEMS) or any(
        word in lowered for word in ["potica", "potic", "torta", "darilni paket"]
    )
    return has_explicit and not (has_number and has_product)


def is_inquiry_trigger(message: str) -> bool:
    if DISABLE_INQUIRY:
        return False
    lowered = message.lower()
    if any(w in lowered for w in ["večerj", "vecerj"]):
        return False
    explicit = [
        "povpraš",
        "ponudb",
        "naročil",
        "naročilo",
        "naroč",
        "količin",
        "večja količina",
        "vecja kolicina",
        "teambuilding",
        "poroka",
        "porok",
        "pogrebščina",
        "pogrebscina",
        "pogostitev",
        "catering",
    ]
    if any(t in lowered for t in explicit):
        return True
    has_number = re.search(r"\d", lowered) is not None
    has_product = any(stem in lowered for stem in PRODUCT_STEMS) or any(
        word in lowered for word in ["potica", "potic", "torta", "darilni paket"]
    )
    return has_number and has_product


def is_strong_inquiry_request(message: str) -> bool:
    return is_inquiry_trigger(message)


def is_reservation_related(message: str) -> bool:
    lowered = message.lower()
    if re.search(r"\b(presp\w*|prenoč\w*|prenoc\w*)\b", lowered):
        return True
    reserv_tokens = ["rezerv", "book", "booking", "reserve", "reservation", "zimmer"]
    if any(t in lowered for t in reserv_tokens):
        return True
    # Type-only vprašanja ("koliko stane nočitev", "imate mize?") naj ne sprožijo bookinga.
    # Brez rezervacijskega glagola jih obravnavamo kot informativna.
    type_tokens = ["soba", "sobo", "sobe", "room", "miza", "mizo", "table", "nočitev", "nocitev", "noči"]
    intent_verbs = ["rad bi", "rada bi", "želim", "zelim", "hočem", "hocem", "rezerviral", "rezervirala"]
    return any(t in lowered for t in type_tokens) and any(v in lowered for v in intent_verbs)


def is_bulk_order_request(message: str) -> bool:
    nums = re.findall(r"\d+", message)
    if nums and any(int(n) >= 20 for n in nums):
        return True
    bulk_words = ["večja količina", "veliko", "na zalogo", "zalogo", "bulk", "škatl", "karton", "več paketov"]
    return any(w in message.lower() for w in bulk_words)


def _fuzzy_contains(text: str, patterns: set[str]) -> bool:
    return any(pat in text for pat in patterns)


def detect_router_intent(message: str, state: dict[str, Optional[str | int]]) -> str:
    lower = message.lower()
    if state.get("step") is not None:
        return "booking_continue"

    booking_tokens = {
        "rezerv",
        "rezev",
        "rezer",
        "rezeriv",
        "rezerver",
        "rezerveru",
        "rezr",
        "rezrv",
        "rezrvat",
        "rezerveir",
        "reserv",
        "reservier",
        "book",
        "buking",
        "booking",
        "bukng",
    }
    room_tokens = {
        "soba",
        "sobe",
        "sobo",
        "room",
        "zimmer",
        "zimmern",
        "rum",
        "camer",
        "camera",
        "accom",
        "nocit",
        "nočit",
        "nočitev",
        "nocitev",
    }
    table_tokens = {
        "miza",
        "mize",
        "mizo",
        "miz",
        "table",
        "tabl",
        "tabel",
        "tble",
        "tablle",
        "tafel",
        "tisch",
        "koslo",
        "kosilo",
        "vecerj",
        "veceja",
        "vecher",
    }

    has_booking = _fuzzy_contains(lower, booking_tokens)
    has_room = _fuzzy_contains(lower, room_tokens)
    has_table = _fuzzy_contains(lower, table_tokens)

    if has_booking and has_room:
        return "booking_room"
    if has_booking and has_table:
        return "booking_table"
    if has_room and ("nocit" in lower or "noč" in lower or "night" in lower):
        return "booking_room"
    if has_table and any(tok in lower for tok in ["oseb", "ob ", ":00"]):
        return "booking_table"

    return "none"


def format_products(query: str) -> str:
    products = find_products(query)
    if not products:
        return f"Tega izdelka ni v spletni trgovini. Pišite na {INFO_EMAIL}."

    product_lines = [
        f"- {product.name}: {product.price:.2f} EUR, {product.weight:.2f} kg"
        for product in products
    ]
    header = "Na voljo imamo naslednje izdelke: "
    return _apply_policy(header + " ".join(product_lines) + ".")


def answer_product_question(message: str) -> str:
    from app.services.flows.info_flow import answer_product_question as _answer_product_question

    return _answer_product_question(message)

def is_product_query(message: str) -> bool:
    lowered = message.lower()
    return any(stem in lowered for stem in PRODUCT_STEMS)


def is_info_query(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in INFO_KEYWORDS)
