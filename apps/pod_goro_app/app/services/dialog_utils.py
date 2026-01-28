import random
import re

GREETING_KEYWORDS = {"živjo", "zdravo", "hej", "hello", "dober dan", "pozdravljeni"}
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
GREETINGS = [
    "Pozdravljeni! 😊 Kako vam lahko pomagam?",
    "Lepo pozdravljeni s Pohorja! Kako vam lahko pomagam danes?",
    "Dober dan! Vesela sem, da ste nas obiskali. S čim vam lahko pomagam?",
    "Pozdravljeni pri Kmetiji Pod Goro! 🏔️ Kaj vas zanima?",
]
THANKS_RESPONSES = [
    "Ni za kaj! Če boste imeli še kakšno vprašanje, sem tu. 😊",
    "Z veseljem! Lep pozdrav s Pohorja! 🏔️",
    "Ni problema! Vesela sem, če sem vam lahko pomagala.",
    "Hvala vam! Se vidimo pri nas! 😊",
]


def is_greeting(message: str) -> bool:
    lowered = message.lower()
    return any(greeting in lowered for greeting in GREETING_KEYWORDS)


def get_greeting_response() -> str:
    return random.choice(GREETINGS)


def get_goodbye_response() -> str:
    return random.choice(THANKS_RESPONSES)


def is_goodbye(message: str) -> bool:
    lowered = message.lower().strip()
    if lowered in GOODBYE_KEYWORDS:
        return True
    if any(keyword in lowered for keyword in ["hvala", "adijo", "nasvidenje", "čao", "ciao", "bye"]):
        return True
    return False


def detect_reset_request(message: str) -> bool:
    lowered = message.lower()
    reset_words = [
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
    exit_words = [
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
    return any(word in lowered for word in reset_words + exit_words)


def is_escape_command(message: str) -> bool:
    lowered = message.lower()
    escape_words = {"prekliči", "preklici", "reset", "stop", "prekini"}
    return any(word in lowered for word in escape_words)


def is_switch_topic_command(message: str) -> bool:
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


def is_affirmative(message: str) -> bool:
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
    lowered = message.strip().lower()
    return lowered in {"ne", "no", "ne hvala", "no thanks"}


def is_confirmation_question(text: str) -> bool:
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


def detect_language(message: str) -> str:
    """Zazna jezik sporočila. Vrne 'si', 'en' ali 'de'."""
    lowered = message.lower()

    # Slovenske besede, ki vsebujejo angleške nize (izjeme), odstranimo pred detekcijo
    slovak_exceptions = ["liker", "likerj", " like ", "slike"]
    for exc in slovak_exceptions:
        lowered = lowered.replace(exc, "")

    german_words = [
        "ich",
        "sie",
        "wir",
        "haben",
        "möchte",
        "möchten",
        "können",
        "bitte",
        "zimmer",
        "tisch",
        "reservierung",
        "reservieren",
        "buchen",
        "wann",
        "wie",
        "was",
        "wo",
        "gibt",
        "guten tag",
        "hallo",
        "danke",
        "preis",
        "kosten",
        "essen",
        "trinken",
        "wein",
        "frühstück",
        "abendessen",
        "mittag",
        "nacht",
        "übernachtung",
    ]
    german_count = sum(1 for word in german_words if word in lowered)

    # posebna obravnava angleškega zaimka "I" kot samostojne besede
    english_pronoun = 1 if re.search(r"\bi\b", lowered) else 0

    english_words = [
        " we ",
        "you",
        "have",
        "would",
        " like ",
        "want",
        "can",
        "room",
        "table",
        "reservation",
        "reserve",
        "book",
        "booking",
        "when",
        "how",
        "what",
        "where",
        "there",
        "hello",
        "hi ",
        "thank",
        "price",
        "cost",
        "food",
        "drink",
        "wine",
        "menu",
        "breakfast",
        "dinner",
        "lunch",
        "night",
        "stay",
        "please",
    ]
    english_count = english_pronoun + sum(1 for word in english_words if word in lowered)

    if german_count >= 2:
        return "de"
    if english_count >= 2:
        return "en"
    if german_count == 1 and english_count == 0:
        return "de"
    if english_count == 1 and german_count == 0:
        return "en"

    return "si"
