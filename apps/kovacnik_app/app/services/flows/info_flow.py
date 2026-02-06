import re
from datetime import datetime, timedelta
from typing import Optional

from app.brand.config import FARM_INFO, INFO_EMAIL, SHOP_BASE_URL
from app.rag.knowledge_base import KNOWLEDGE_CHUNKS

# ----- Wine list -----
WINE_LIST = {
    "penece": [
        {"name": "Doppler DIONA brut 2013", "type": "zelo suho", "grape": "100% Chardonnay", "price": 30.00, "desc": "Penina po klasični metodi, eleganca, lupinasto sadje, kruhova skorja"},
        {"name": "Opok27 NYMPHA rose brut 2022", "type": "izredno suho", "grape": "100% Modri pinot", "price": 26.00, "desc": "Rose frizzante, jagodni konfit, češnja, sveže"},
        {"name": "Leber MUŠKATNA PENINA demi sec", "type": "polsladko", "grape": "100% Rumeni muškat", "price": 26.00, "desc": "Klasična metoda, 18 mesecev zorenja, svež vonj limone in muškata"},
    ],
    "bela": [
        {"name": "Greif BELO zvrst 2024", "type": "suho", "grape": "Laški rizling + Sauvignon", "price": 14.00, "desc": "Mladostno, zeliščne in sadne note, visoke kisline"},
        {"name": "Frešer SAUVIGNON 2023", "type": "suho", "grape": "100% Sauvignon", "price": 19.00, "desc": "Aromatičen, zeliščen, črni ribez, koprive, mineralno"},
        {"name": "Frešer LAŠKI RIZLING 2023", "type": "suho", "grape": "100% Laški rizling", "price": 18.00, "desc": "Mladostno, mineralno, note jabolka in suhih zelišč"},
        {"name": "Greif LAŠKI RIZLING terase 2020", "type": "suho", "grape": "100% Laški rizling", "price": 23.00, "desc": "Zoreno 14 mesecev v hrastu, zrelo rumeno sadje, oljnata tekstura"},
        {"name": "Frešer RENSKI RIZLING Markus 2019", "type": "suho", "grape": "100% Renski rizling", "price": 22.00, "desc": "Breskev, petrolej, mineralno, zoreno v hrastu"},
        {"name": "Skuber MUŠKAT OTTONEL 2023", "type": "polsladko", "grape": "100% Muškat ottonel", "price": 17.00, "desc": "Elegantna muškatna cvetica, harmonično, ljubko"},
        {"name": "Greif RUMENI MUŠKAT 2023", "type": "polsladko", "grape": "100% Rumeni muškat", "price": 17.00, "desc": "Mladostno, sortno, note sena in limete"},
    ],
    "rdeca": [
        {"name": "Skuber MODRA FRANKINJA 2023", "type": "suho", "grape": "100% Modra frankinja", "price": 16.00, "desc": "Rubinasta, ribez, murva, malina, polni okus"},
        {"name": "Frešer MODRI PINOT Markus 2020", "type": "suho", "grape": "100% Modri pinot", "price": 23.00, "desc": "Višnje, češnje, maline, žametno, 12 mesecev v hrastu"},
        {"name": "Greif MODRA FRANKINJA črešnjev vrh 2019", "type": "suho", "grape": "100% Modra frankinja", "price": 26.00, "desc": "Zrela, temno sadje, divja češnja, zreli tanini"},
    ],
}

# ----- Seasonal menus -----
SEASONAL_MENUS = [
    {
        "months": {3, 4, 5},
        "label": "Marec–Maj (pomladna srajčka)",
        "items": [
            "Pohorska bunka in zorjen Frešerjev sir, hišna suha salama, paštetka iz domačih jetrc, zaseka, bučni namaz, hišni kruhek",
            "Juhe: goveja župca z rezanci in jetrnimi rolicami, koprivna juhica s čemažem",
            "Meso: pečenka iz pujskovega hrbta, hrustljavi piščanec, piščančje kroglice z zelišči, mlado goveje meso z rdečim vinom",
            "Priloge: štukelj s skuto, ričota s pirino kašo, pražen krompir, mini pita s porom, ocvrte hruške, pomladna solata",
            "Sladica: Pohorska gibanica babice Angelce",
            "Cena: 36 EUR odrasli, otroci 4–12 let -50%",
        ],
    },
    {
        "months": {6, 7, 8},
        "label": "Junij–Avgust (poletna srajčka)",
        "items": [
            "Pohorska bunka, zorjen sir, hišna suha salama, paštetka iz jetrc z žajbljem, bučni namaz, kruhek",
            "Juhe: goveja župca z rezanci, kremna juha poletnega vrta",
            "Meso: pečenka iz pujskovega hrbta, hrustljavi piščanec, piščančje kroglice, mlado goveje meso z rabarbaro in rdečim vinom",
            "Priloge: štukelj s skuto, ričota s pirino kašo, mlad krompir z rožmarinom, mini pita z bučkami, ocvrte hruške, poletna solata",
            "Sladica: Pohorska gibanica babice Angelce",
            "Cena: 36 EUR odrasli, otroci 4–12 let -50%",
        ],
    },
    {
        "months": {9, 10, 11},
        "label": "September–November (jesenska srajčka)",
        "items": [
            "Dobrodošlica s hišnim likerjem ali sokom; lesena deska s pohorsko bunko, salamo, namazi, Frešerjev sirček, kruhek",
            "Juhe: goveja župca z rezanci, bučna juha s kolerabo, sirne lizike z žajbljem",
            "Meso: pečenka iz pujskovega hrbta, hrustljavi piščanec, piščančje kroglice, mlado goveje meso z rabarbaro in rdečo peso",
            "Priloge: štukelj s skuto, ričota s pirino kašo, pražen krompir iz šporheta, mini pita s porom, ocvrte hruške, jesenska solatka",
            "Sladica: Pohorska gibanica (porcijsko)",
            "Cena: 36 EUR odrasli, otroci 4–12 let -50%",
        ],
    },
    {
        "months": {12, 1, 2},
        "label": "December–Februar (zimska srajčka)",
        "items": [
            "Pohorska bunka, zorjen sir, hišna suha salama, paštetka iz jetrc s čebulno marmelado, zaseka, bučni namaz, kruhek",
            "Juhe: goveja župca z rezanci, krompirjeva juha s krvavico",
            "Meso: pečenka iz pujskovega hrbta, hrustljavi piščanec, piščančje kroglice, mlado goveje meso z rdečim vinom",
            "Priloge: štukelj s skuto, ričota s pirino kašo, pražen krompir iz pečice, mini pita z bučkami, ocvrte hruške, zimska solata",
            "Sladica: Pohorska gibanica babice Angelce",
            "Cena: 36 EUR odrasli, otroci 4–12 let -50%",
        ],
    },
]

# Kulinarična doživetja (sreda–petek, skupine 6+)
WEEKLY_MENUS = {
    4: {
        "name": "4-HODNI DEGUSTACIJSKI MENI",
        "price": 36,
        "wine_pairing": 15,
        "wine_glasses": 4,
        "courses": [
            {"wine": "Penina Doppler Diona 2017 (zelo suho, 100% chardonnay)", "dish": "Pozdrav iz kuhinje"},
            {"wine": "Frešer Sauvignon 2024 (suho)", "dish": "Kiblflajš s prelivom, zelenjava s Kovačnikovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi"},
            {"wine": None, "dish": "Juha s kislim zeljem in krvavico"},
            {"wine": "Šumenjak Alter 2021 (suho)", "dish": "Krompir iz naše njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka iz vrta gospodinje Barbare"},
            {"wine": "Greif Rumeni muškat 2024 (polsladko)", "dish": "Pohorska gibanica babice Angelce ali domač jabolčni štrudl ali pita sezone, hišni sladoled"},
        ],
    },
    5: {
        "name": "5-HODNI DEGUSTACIJSKI MENI",
        "price": 43,
        "wine_pairing": 20,
        "wine_glasses": 5,
        "courses": [
            {"wine": "Penina Doppler Diona 2017 (zelo suho, 100% chardonnay)", "dish": "Pozdrav iz kuhinje"},
            {"wine": "Frešer Sauvignon 2024 (suho)", "dish": "Kiblflajš s prelivom, zelenjava s Kovačnikovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi"},
            {"wine": None, "dish": "Juha s kislim zeljem in krvavico"},
            {"wine": "Frešer Renski rizling 2019 (suho)", "dish": "Ričotka pirine kaše z jurčki in zelenjavo"},
            {"wine": "Šumenjak Alter 2021 (suho)", "dish": "Krompir iz naše njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka iz vrta gospodinje Barbare"},
            {"wine": "Greif Rumeni muškat 2024 (polsladko)", "dish": "Pohorska gibanica babice Angelce ali domač jabolčni štrudl ali pita sezone, hišni sladoled"},
        ],
    },
    6: {
        "name": "6-HODNI DEGUSTACIJSKI MENI",
        "price": 53,
        "wine_pairing": 25,
        "wine_glasses": 6,
        "courses": [
            {"wine": "Penina Doppler Diona 2017 (zelo suho, 100% chardonnay)", "dish": "Pozdrav iz kuhinje"},
            {"wine": "Frešer Sauvignon 2024 (suho)", "dish": "Kiblflajš s prelivom, zelenjava s Kovačnikovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi"},
            {"wine": None, "dish": "Juha s kislim zeljem in krvavico"},
            {"wine": "Frešer Renski rizling 2019 (suho)", "dish": "Ričotka pirine kaše z jurčki in zelenjavo"},
            {"wine": "Šumenjak Alter 2021 (suho)", "dish": "Krompir iz naše njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka iz vrta gospodinje Barbare"},
            {"wine": "Greif Modra frankinja 2020 (suho)", "dish": "Štrukelj s skuto naše krave Miške, goveje meso iz Kovačnikove proste reje, rdeča pesa, rabarbara, naravna omaka"},
            {"wine": "Greif Rumeni muškat 2024 (polsladko)", "dish": "Pohorska gibanica babice Angelce ali domač jabolčni štrudl ali pita sezone, hišni sladoled"},
        ],
    },
    7: {
        "name": "7-HODNI DEGUSTACIJSKI MENI",
        "price": 62,
        "wine_pairing": 29,
        "wine_glasses": 7,
        "courses": [
            {"wine": "Penina Doppler Diona 2017 (zelo suho, 100% chardonnay)", "dish": "Pozdrav iz kuhinje"},
            {"wine": "Frešer Sauvignon 2024 (suho)", "dish": "Kiblflajš s prelivom, zelenjava s Kovačnikovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi"},
            {"wine": None, "dish": "Juha s kislim zeljem in krvavico"},
            {"wine": "Greif Laški rizling Terase 2020 (suho)", "dish": "An ban en goban – Jurčki, ajda, ocvirki, korenček, peteršilj"},
            {"wine": "Frešer Renski rizling 2019 (suho)", "dish": "Ričotka pirine kaše z jurčki in zelenjavo"},
            {"wine": "Šumenjak Alter 2021 (suho)", "dish": "Krompir iz naše njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka iz vrta gospodinje Barbare"},
            {"wine": "Greif Modra frankinja 2020 (suho)", "dish": "Štrukelj s skuto naše krave Miške, goveje meso iz Kovačnikove proste reje, rdeča pesa, rabarbara, naravna omaka"},
            {"wine": "Greif Rumeni muškat 2024 (polsladko)", "dish": "Pohorska gibanica babice Angelce ali domač jabolčni štrudl ali pita sezone, hišni sladoled"},
        ],
    },
}

WEEKLY_INFO = {
    "days": "sreda, četrtek, petek",
    "time": "od 13:00 naprej",
    "min_people": 6,
    "contact": {"phone": "031 330 113", "email": "info@kovacnik.com"},
    "special_diet_extra": 8,
}

MENU_INTROS = [
    "Hej! Poglej, kaj kuhamo ta vikend:",
    "Z veseljem povem, kaj je na meniju:",
    "Daj, da ti razkrijem naš sezonski meni:",
    "Evo, vikend jedilnik:",
]
menu_intro_index = 0
last_shown_products: list[str] = []


def reset_info_state() -> None:
    global menu_intro_index, last_shown_products
    menu_intro_index = 0
    last_shown_products = []


def answer_wine_question(message: str) -> str:
    """Odgovarja na vprašanja o vinih SAMO iz WINE_LIST, z upoštevanjem followupov."""
    global last_shown_products

    lowered = message.lower()
    is_followup = any(word in lowered for word in ["še", "drug", "kaj pa", "še kaj", "še kater", "še kakšn", "še kakšno"])

    is_red = any(word in lowered for word in ["rdeč", "rdeca", "rdece", "rdeče", "frankinja", "pinot"])
    is_white = any(word in lowered for word in ["bel", "bela", "belo", "rizling", "sauvignon"])
    is_sparkling = any(word in lowered for word in ["peneč", "penina", "penece", "mehurčk", "brut"])
    is_sweet = any(word in lowered for word in ["sladk", "polsladk", "muškat", "muskat"])
    is_dry = any(word in lowered for word in ["suh", "suho", "suha"])

    def format_wines(wines: list, category_name: str, temp: str) -> str:
        if is_followup:
            wines = [w for w in wines if w["name"] not in last_shown_products]

        if not wines:
            return (
                f"To so vsa naša {category_name} vina. Imamo pa še:\n"
                "🥂 Bela vina (od 14€)\n"
                "🍾 Peneča vina (od 26€)\n"
                "🍯 Polsladka vina (od 17€)\n"
                "🍷 Rdeča vina (od 16€)\n"
                "Kaj vas zanima?"
            )

        lines = [f"Naša {category_name} vina:"]
        for w in wines:
            lines.append(f"• {w['name']} ({w['type']}, {w['price']:.0f}€) – {w['desc']}")
            if w["name"] not in last_shown_products:
                last_shown_products.append(w["name"])

        if len(last_shown_products) > 15:
            last_shown_products[:] = last_shown_products[-15:]

        return "\n".join(lines) + f"\n\nServiramo ohlajeno na {temp}."

    if is_red:
        wines = WINE_LIST["rdeca"]
        if is_dry:
            wines = [w for w in wines if "suho" in w["type"]]
        if is_followup:
            remaining = [w for w in wines if w["name"] not in last_shown_products]
            if not remaining:
                return (
                    "To so vsa naša rdeča vina. Imamo pa še:\n"
                    "🥂 Bela vina (od 14€)\n"
                    "🍾 Peneča vina (od 26€)\n"
                    "🍯 Polsladka vina (od 17€)\n"
                    "Kaj vas zanima?"
                )
        return format_wines(wines, "rdeča", "14°C")

    if is_sparkling:
        return format_wines(WINE_LIST["penece"], "peneča", "6°C")

    if is_white:
        wines = WINE_LIST["bela"]
        if is_dry:
            wines = [w for w in wines if "suho" in w["type"]]
        if is_sweet:
            wines = [w for w in wines if "polsladk" in w["type"]]
        return format_wines(wines[:5], "bela", "8–10°C")

    if is_sweet:
        wines = []
        for w in WINE_LIST["bela"]:
            if "polsladk" in w["type"]:
                wines.append(w)
        for w in WINE_LIST["penece"]:
            if "polsladk" in w["type"].lower() or "demi" in w["type"].lower():
                wines.append(w)
        return format_wines(wines, "polsladka", "8°C")

    return (
        "Ponujamo izbor lokalnih vin:\n\n"
        "🍷 **Rdeča** (suha): Modra frankinja (Skuber 16€, Greif 26€), Modri pinot Frešer (23€)\n"
        "🥂 **Bela** (suha): Sauvignon (19€), Laški rizling (18–23€), Renski rizling (22€)\n"
        "🍾 **Peneča**: Doppler Diona brut (30€), Opok27 rose (26€), Muškatna penina (26€)\n"
        "🍯 **Polsladka**: Rumeni muškat (17€), Muškat ottonel (17€)\n\n"
        "Povejte, kaj vas zanima – rdeče, belo, peneče ali polsladko?"
    )


def answer_weekly_menu(message: str) -> str:
    """Odgovarja na vprašanja o tedenski ponudbi (sreda-petek)."""
    lowered = message.lower()

    requested_courses = None
    if "4" in message or "štiri" in lowered or "stiri" in lowered:
        requested_courses = 4
    elif "5" in message or "pet" in lowered:
        requested_courses = 5
    elif "6" in message or "šest" in lowered or "sest" in lowered:
        requested_courses = 6
    elif "7" in message or "sedem" in lowered:
        requested_courses = 7

    if requested_courses is None:
        lines = [
            "**KULINARIČNA DOŽIVETJA** (sreda–petek, od 13:00, min. 6 oseb)\n",
            "Na voljo imamo degustacijske menije:",
            "",
            f"🍽️ **4-hodni meni**: {WEEKLY_MENUS[4]['price']}€/oseba (vinska spremljava +{WEEKLY_MENUS[4]['wine_pairing']}€ za {WEEKLY_MENUS[4]['wine_glasses']} kozarce)",
            f"🍽️ **5-hodni meni**: {WEEKLY_MENUS[5]['price']}€/oseba (vinska spremljava +{WEEKLY_MENUS[5]['wine_pairing']}€ za {WEEKLY_MENUS[5]['wine_glasses']} kozarcev)",
            f"🍽️ **6-hodni meni**: {WEEKLY_MENUS[6]['price']}€/oseba (vinska spremljava +{WEEKLY_MENUS[6]['wine_pairing']}€ za {WEEKLY_MENUS[6]['wine_glasses']} kozarcev)",
            f"🍽️ **7-hodni meni**: {WEEKLY_MENUS[7]['price']}€/oseba (vinska spremljava +{WEEKLY_MENUS[7]['wine_pairing']}€ za {WEEKLY_MENUS[7]['wine_glasses']} kozarcev)",
            "",
            f"🥗 Posebne zahteve (vege, brez glutena): +{WEEKLY_INFO['special_diet_extra']}€/hod",
            "",
            f"📞 Rezervacije: {WEEKLY_INFO['contact']['phone']} ali {WEEKLY_INFO['contact']['email']}",
            "",
            "Povejte kateri meni vas zanima (4, 5, 6 ali 7-hodni) za podrobnosti!",
        ]
        return "\n".join(lines)

    menu = WEEKLY_MENUS[requested_courses]
    lines = [
        f"**{menu['name']}**",
        f"📅 {WEEKLY_INFO['days'].upper()}, {WEEKLY_INFO['time']}",
        f"👥 Minimum {WEEKLY_INFO['min_people']} oseb",
        "",
    ]

    for i, course in enumerate(menu["courses"], 1):
        wine_text = f" 🍷 _{course['wine']}_" if course["wine"] else ""
        lines.append(f"**{i}.** {course['dish']}{wine_text}")

    lines.extend(
        [
            "",
            f"💰 **Cena: {menu['price']}€/oseba**",
            f"🍷 Vinska spremljava: +{menu['wine_pairing']}€ ({menu['wine_glasses']} kozarcev)",
            f"🥗 Vege/brez glutena: +{WEEKLY_INFO['special_diet_extra']}€/hod",
            "",
            f"📞 Rezervacije: {WEEKLY_INFO['contact']['phone']} ali {WEEKLY_INFO['contact']['email']}",
        ]
    )

    return "\n".join(lines)


def parse_month_from_text(message: str) -> Optional[int]:
    lowered = message.lower()
    month_map = {
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
    for key, val in month_map.items():
        if key in lowered:
            return val
    return None


def parse_relative_month(message: str) -> Optional[int]:
    lowered = message.lower()
    today = datetime.now()
    if "jutri" in lowered:
        target = today + timedelta(days=1)
        return target.month
    if "danes" in lowered:
        return today.month
    return None


def next_menu_intro() -> str:
    global menu_intro_index
    intro = MENU_INTROS[menu_intro_index % len(MENU_INTROS)]
    menu_intro_index += 1
    return intro


def is_hours_question(message: str) -> bool:
    lowered = message.lower()
    patterns = [
        "odprti",
        "odprt",
        "odpiralni",
        "obratovalni",
        "obratujete",
        "do kdaj",
        "kdaj lahko pridem",
        "kdaj ste",
        "kateri uri",
        "kosilo ob",
        "kosilo do",
        "kosila",
        "zajtrk",
        "breakfast",
        "večerj",
        "vecerj",
        "prijava",
        "odjava",
        "check-in",
        "check out",
        "kosilo",
        "večerja",
        "vecerja",
    ]
    return any(pat in lowered for pat in patterns)


def answer_farm_info(message: str) -> str:
    lowered = message.lower()

    if any(word in lowered for word in ["zajc", "zajček", "zajcka", "zajčki", "kunec", "zajce"]):
        return "Imamo prijazne zajčke, ki jih lahko obiskovalci božajo. Ob obisku povejte, pa vas usmerimo do njih."

    if any(word in lowered for word in ["ogled", "tour", "voden", "vodenje", "guid", "sprehod po kmetiji"]):
        return "Organiziranih vodenih ogledov pri nas ni. Ob obisku se lahko samostojno sprehodite in vprašate osebje, če želite videti živali."

    if any(word in lowered for word in ["navodila", "pot", "pot do", "pridem", "priti", "pot do vas", "avtom"]):
        return FARM_INFO["directions"]["from_maribor"]

    if any(word in lowered for word in ["kje", "naslov", "lokacija", "nahajate"]):
        return (
            f"Nahajamo se na: {FARM_INFO['address']} ({FARM_INFO['location_description']}). "
            f"Parking: {FARM_INFO['parking']}. Če želite navodila za pot, povejte, od kod prihajate."
        )

    if any(word in lowered for word in ["telefon", "številka", "stevilka", "poklicat", "klicat"]):
        return f"Telefon: {FARM_INFO['phone']}, mobitel: {FARM_INFO['mobile']}. Pišete lahko na {FARM_INFO['email']}."

    if "email" in lowered or "mail" in lowered:
        return f"E-mail: {FARM_INFO['email']}. Splet: {FARM_INFO['website']}."

    if any(word in lowered for word in ["odprt", "kdaj", "delovni", "ura"]):
        return (
            f"Kosila: {FARM_INFO['opening_hours']['restaurant']} | "
            f"Sobe: {FARM_INFO['opening_hours']['rooms']} | "
            f"Trgovina: {FARM_INFO['opening_hours']['shop']} | "
            f"Zaprto: {FARM_INFO['opening_hours']['closed']}"
        )

    if "parking" in lowered or "parkirišče" in lowered or "parkirisce" in lowered or "avto" in lowered:
        return f"{FARM_INFO['parking']}. Naslov za navigacijo: {FARM_INFO['address']}."

    if "wifi" in lowered or "internet" in lowered or "klima" in lowered:
        facilities = ", ".join(FARM_INFO["facilities"])
        return f"Na voljo imamo: {facilities}."

    if any(word in lowered for word in ["počet", "delat", "aktivnost", "izlet"]):
        activities = "; ".join(FARM_INFO["activities"])
        return f"Pri nas in v okolici lahko: {activities}."

    if is_hours_question(message):
        return (
            "Kosila: sobota/nedelja 12:00-20:00 (zadnji prihod 15:00). "
            "Zajtrk: 8:00–9:00 (za goste sob). "
            "Prijava 15:00–20:00, odjava do 11:00. "
            "Večerje za goste po dogovoru (pon/torki kuhinja zaprta)."
        )

    return (
        f"{FARM_INFO['name']} | Naslov: {FARM_INFO['address']} | Tel: {FARM_INFO['phone']} | "
        f"Email: {FARM_INFO['email']} | Splet: {FARM_INFO['website']}"
    )


def answer_food_question(message: str) -> str:
    lowered = message.lower()
    if "alerg" in lowered or "gob" in lowered or "glive" in lowered:
        return (
            "Alergije uredimo brez težav. Ob rezervaciji zapiši alergije (npr. brez gob) ali povej osebju ob prihodu, da lahko prilagodimo jedi. "
            "Želiš, da označim alergije v tvoji rezervaciji?"
        )
    return (
        "Pripravljamo tradicionalne pohorske jedi iz lokalnih sestavin.\n"
        "Vikend kosila (sob/ned): 36€ odrasli, otroci 4–12 let -50%, vključuje predjed, juho, glavno jed, priloge in sladico.\n"
        "Če želite videti aktualni sezonski jedilnik, recite 'jedilnik'. Posebne zahteve (vege, brez glutena) uredimo ob rezervaciji."
    )


def is_full_menu_request(message: str) -> bool:
    lowered = message.lower()
    return any(
        phrase in lowered
        for phrase in [
            "celoten meni",
            "celotni meni",
            "poln meni",
            "celoten jedilnik",
            "celotni jedilnik",
            "poln jedilnik",
        ]
    )


def format_current_menu(month_override: Optional[int] = None, force_full: bool = False, short_mode: bool = True) -> str:
    now = datetime.now()
    month = month_override or now.month
    current = None
    for menu in SEASONAL_MENUS:
        if month in menu["months"]:
            current = menu
            break
    if not current:
        current = SEASONAL_MENUS[0]
    lines = [
        next_menu_intro(),
        f"{current['label']}",
    ]
    items = [item for item in current["items"] if not item.lower().startswith("cena")]
    if short_mode and not force_full:
        for item in items[:4]:
            lines.append(f"- {item}")
        lines.append("Cena: 36 EUR odrasli, otroci 4–12 let -50%.")
        lines.append("")
        lines.append("Za celoten sezonski meni recite: \"celoten meni\".")
    else:
        for item in items:
            lines.append(f"- {item}")
        lines.append("Cena: 36 EUR odrasli, otroci 4–12 let -50%.")
        lines.append("")
        lines.append(
            "Jedilnik je sezonski; če želiš meni za drug mesec, samo povej mesec (npr. 'kaj pa novembra'). "
            "Vege ali brez glutena uredimo ob rezervaciji."
        )
    return "\n".join(lines)


# ----- Product helpers -----

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


def answer_product_question(message: str) -> str:
    lowered = message.lower()
    exact_slug_hints = {
        "cemazev-pesto": ["čemažev pesto", "cemazev pesto", "cemazev_pesto"],
        "bucni-namaz": ["bučni namaz", "bucni namaz", "bucni_namaz"],
        "jetrna-pastetka": ["jetrna paštet", "jetrna pastet", "jetrna_pastetka"],
    }
    for slug_hint, aliases in exact_slug_hints.items():
        if any(alias in lowered for alias in aliases):
            for c in KNOWLEDGE_CHUNKS:
                url_lower = (c.url or "").lower()
                if "/izdelek/" not in url_lower or slug_hint not in url_lower:
                    continue
                text = c.paragraph.strip() if c.paragraph else ""
                price = ""
                price_match = re.match(r'^(\d+[,\.]\d+\s*€)', text)
                if price_match:
                    price = price_match.group(1)
                title = c.title or "Izdelek"
                link = _product_link_from_url(c.url, title)
                if price:
                    return f"{title} ({price}). Najdete ga tukaj: {link}."
                return f"{title}. Najdete ga tukaj: {link}."
    category = None
    if "marmelad" in lowered or "džem" in lowered or "dzem" in lowered:
        category = "marmelad"
    elif (
        "liker" in lowered
        or "žganj" in lowered
        or "zganj" in lowered
        or "žgan" in lowered
        or "zgan" in lowered
        or "žgane" in lowered
        or "zganje" in lowered
        or "tepkovec" in lowered
        or "borovni" in lowered
    ):
        category = "liker"
    elif "bunk" in lowered:
        category = "bunka"
    elif "salam" in lowered or "klobas" in lowered or "mesn" in lowered:
        category = "mesn"
    elif "namaz" in lowered or "pašteta" in lowered or "pasteta" in lowered:
        category = "namaz"
    elif "sirup" in lowered or "sok" in lowered:
        category = "sirup"
    elif "čaj" in lowered or "caj" in lowered:
        category = "caj"
    elif "paket" in lowered or "daril" in lowered:
        category = "paket"

    results = []
    for c in KNOWLEDGE_CHUNKS:
        if "/izdelek/" not in c.url:
            continue

        url_lower = c.url.lower()
        title_lower = c.title.lower() if c.title else ""
        content_lower = c.paragraph.lower() if c.paragraph else ""

        if category:
            if category == "marmelad" and ("marmelad" in url_lower or "marmelad" in title_lower):
                if "paket" in url_lower or "paket" in title_lower:
                    continue
                results.append(c)
            elif category == "liker" and ("liker" in url_lower or "tepkovec" in url_lower):
                results.append(c)
            elif category == "bunka" and "bunka" in url_lower:
                results.append(c)
            elif category == "mesn" and ("salama" in url_lower or "klobas" in url_lower):
                results.append(c)
            elif category == "namaz" and ("namaz" in url_lower or "pastet" in url_lower):
                results.append(c)
            elif category == "sirup" and ("sirup" in url_lower or "sok" in url_lower):
                results.append(c)
            elif category == "caj" and "caj" in url_lower:
                results.append(c)
            elif category == "paket" and "paket" in url_lower:
                results.append(c)
        else:
            words = [w for w in lowered.split() if len(w) > 3]
            for word in words:
                if word in url_lower or word in title_lower or word in content_lower:
                    results.append(c)
                    break

    seen = set()
    unique = []
    for c in results:
        if c.url not in seen:
            seen.add(c.url)
            unique.append(c)
        if len(unique) >= 5:
            break

    if not unique:
        if category is None:
            fallback = []
            for c in KNOWLEDGE_CHUNKS:
                if "/izdelek/" in (c.url or ""):
                    fallback.append(c)
                if len(fallback) >= 3:
                    break
            if fallback:
                sentences = []
                for c in fallback:
                    text = c.paragraph.strip() if c.paragraph else ""
                    price = ""
                    price_match = re.match(r'^(\d+[,\.]\d+\s*€)', text)
                    if price_match:
                        price = price_match.group(1)
                    title = c.title or "Izdelek"
                    link = _product_link_from_url(c.url, title)
                    if price:
                        sentences.append(f"{title} ({price}). Najdete ga tukaj: {link}.")
                    else:
                        sentences.append(f"{title}. Najdete ga tukaj: {link}.")
                return " ".join(sentences)
        return f"Tega izdelka ni v spletni trgovini. Pišite na {INFO_EMAIL}."

    sentences: list[str] = []
    for c in unique[:3]:
        text = c.paragraph.strip() if c.paragraph else ""
        price = ""
        price_match = re.match(r'^(\d+[,\.]\d+\s*€)', text)
        if price_match:
            price = price_match.group(1)
        title = c.title or "Izdelek"
        link = _product_link_from_url(c.url, title)
        if price:
            sentences.append(f"{title} ({price}). Najdete ga tukaj: {link}.")
        else:
            sentences.append(f"{title}. Najdete ga tukaj: {link}.")

    return " ".join(sentences)
