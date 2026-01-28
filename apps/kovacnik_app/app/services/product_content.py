import random
from typing import Optional


PRODUCT_RESPONSES = {
    "marmelada": [
        "Imamo **domače marmelade**: jagodna, marelična, borovničeva, malinova, stara brajda, božična. Cena od 5,50 €.\n\nKupite ob obisku ali naročite v spletni trgovini: https://kovacnik.com/katalog (sekcija Marmelade).",
        "Ponujamo več vrst **domačih marmelad** – jagoda, marelica, borovnica, malina, božična, stara brajda. Cena 5,50 €/212 ml.\n\nNa voljo ob obisku ali v spletni trgovini: https://kovacnik.com/katalog.",
    ],
    "liker": [
        "Imamo **domače likerje**: borovničev, žajbljev, aronija, smrekovi vršički (3 cl/5 cl) in za domov 350 ml (13–15 €), tepkovec 15 €.\n\nKupite ob obisku ali naročite: https://kovacnik.com/katalog (sekcija Likerji in žganje).",
        "Naši **domači likerji** (žajbelj, smrekovi vršički, aronija, borovničevec) in žganja (tepkovec, tavžentroža). Cene za 350 ml od 13 €.\n\nNa voljo v spletni trgovini: https://kovacnik.com/katalog ali ob obisku.",
    ],
    "bunka": [
        "Imamo **pohorsko bunko** (18–21 €) ter druge mesnine.\n\nNa voljo ob obisku ali v spletni trgovini: https://kovacnik.com/katalog (sekcija Mesnine).",
        "Pohorska bunka je na voljo (18–21 €), skupaj s suho klobaso in salamo.\n\nNaročilo: https://kovacnik.com/katalog.",
    ],
    "izdelki_splosno": [
        "Prodajamo **domače izdelke** (marmelade, likerji/žganja, mesnine, čaji, sirupi, paketi) ob obisku ali v spletni trgovini: https://kovacnik.com/katalog.",
        "Na voljo so **marmelade, likerji/žganja, mesnine, čaji, sirupi, darilni paketi**. Naročite na spletu (https://kovacnik.com/katalog) ali kupite ob obisku.",
    ],
    "gibanica_narocilo": """Za naročilo gibanice za domov:
- Pohorska gibanica s skuto: 40 € za 10 kosov
- Pohorska gibanica z orehi: 45 € za 10 kosov

Napišite, koliko kosov in za kateri datum želite prevzem. Ob večjih količinah (npr. 40 kosov) potrebujemo predhodni dogovor. Naročilo: info@kovacnik.com""",
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
    "bunk",
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


def detect_product_intent(message: str) -> Optional[str]:
    text = message.lower()
    if any(w in text for w in ["liker", "žgan", "zgan", "borovnič", "orehov", "alkohol"]):
        return "liker"
    if any(w in text for w in ["marmelad", "džem", "dzem", "jagod", "marelič"]):
        return "marmelada"
    if "gibanica" in text:
        return "gibanica_narocilo"
    if any(w in text for w in ["bunka", "bunko", "bunke"]):
        return "bunka"
    if any(w in text for w in ["izdelk", "prodaj", "kupiti", "kaj imate", "trgovin"]):
        return "izdelki_splosno"
    return None


def get_product_response(key: str) -> str:
    if key in PRODUCT_RESPONSES:
        return random.choice(PRODUCT_RESPONSES[key])
    return PRODUCT_RESPONSES["izdelki_splosno"][0]
