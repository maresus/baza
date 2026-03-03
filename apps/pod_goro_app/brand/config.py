import os

from shared_core.app.brand.schema import BrandConfig

FARM_INFO = {
    "name": "Kmetija Pod Goro",
    "address": "Planica 9, 2313 Fram",
    "phone": "02 601 54 00",
    "mobile": "031 330 113",
    "email": "info@kmetijapodgoro.si",
    "website": "www.kmetijapodgoro.si",
    "location_description": "Na pohorski strani, nad Framom, približno 15 min iz doline",
    "parking": "Brezplačen parking ob hiši za 10+ avtomobilov",
    "directions": {
        "from_maribor": (
            "Iz avtoceste A1 (smer Maribor/Ljubljana) izvoz Fram. Pri semaforju v Framu proti cerkvi sv. Nike, "
            "naravnost skozi vas proti Kopivniku. V Kopivniku na glavni cesti zavijete desno (tabla Kmetija Pod Goro) "
            "in nadaljujete še približno 10 minut. Od cerkve v Framu do kmetije je slabih 15 minut."
        ),
        "coordinates": "46.5234, 15.6123",
    },
    "opening_hours": {
        "restaurant": "Sobota in nedelja 12:00-20:00 (zadnji prihod na kosilo 15:00)",
        "rooms": "Sobe: prijava 14:00, odjava 10:00 (pon/torki kuhinja zaprta)",
        "shop": "Po dogovoru ali spletna trgovina 24/7",
        "closed": "Ponedeljek in torek (kuhinja zaprta, večerje za nočitvene goste po dogovoru)",
    },
    "facilities": [
        "Brezplačen WiFi",
        "Klimatizirane sobe",
        "Brezplačen parking",
        "Vrt s pogledom na Pohorje",
        "Otroško igrišče",
    ],
    "activities": [
        "Sprehodi po Pohorju",
        "Kolesarjenje (izposoja koles možna)",
        "Ogled kmetije in živali",
        "Degustacija domačih izdelkov",
    ],
}

# =============================================================================
# BRAND KONSTANTE (za uporabo v logiki)
# =============================================================================

BRAND_NAME = FARM_INFO["name"]
BRAND_SHORT = "Kmetija Pod Goro"

SHOP_BASE_URL = os.getenv("SHOP_BASE_URL", "https://kmetijapodgoro.si").rstrip("/")
SHOP_URL = os.getenv("SHOP_URL", f"{SHOP_BASE_URL}/katalog")
INFO_EMAIL = os.getenv("INFO_EMAIL", FARM_INFO["email"])

EXAMPLE_NAME = "Nika Kmetija Pod Goro"

FAMILY = {
    "owner": "Marko",
    "grandmother": "Marija",
    "members": ["Marko", "Sara", "Jakob", "Lana", "Nika"],
    "partner": "Maja",
    "horses": ["Malajka", "Marsij"],
    "cow": "Miška",
}

ROOMS = {
    "GOZD": {"name": "Soba GOZD", "capacity": "2+2"},
    "RAZGLED": {"name": "Soba RAZGLED", "capacity": "2+2"},
    "SONCE": {"name": "Soba SONCE", "capacity": "2+2"},
}
ROOM_NAMES = list(ROOMS.keys())
ROOM_DISPLAY_NAMES = [room["name"].replace("Soba ", "") for room in ROOMS.values()]

GREETINGS = [
    "Pozdravljeni! Kako vam lahko pomagam?",
    "Lepo pozdravljeni s Pohorja! Kako vam lahko pomagam danes?",
    "Dober dan! Vesela sem, da ste nas obiskali. S čim vam lahko pomagam?",
    "Pozdravljeni pri Kmetiji Pod Goro! Kaj vas zanima?",
]

THANKS_RESPONSES = [
    "Ni za kaj! Če boste imeli še kakšno vprašanje, sem tu.",
    "Z veseljem! Lep pozdrav s Pohorja!",
    "Ni problema! Vesela sem, če sem vam lahko pomagala.",
    "Hvala vam! Se vidimo pri nas!",
]

UNKNOWN_RESPONSES = [
    "Tega žal ne vem. Če želite, mi pustite e-pošto in preverim.",
    "Trenutno nimam podatkov o tem.",
    "Za to trenutno nimam zanesljivega podatka.",
    "Tega podatka trenutno nimam pri roki.",
]

MENU_INTROS = [
    "Hej! Poglej, kaj kuhamo ta vikend:",
    "Z veseljem povem, kaj je na meniju:",
    "Daj, da ti razkrijem naš sezonski meni:",
    "Evo, vikend jedilnik:",
]

SEASONAL_MENUS = [
    {
        "months": {3, 4, 5},
        "label": "Marec-Maj (pomladna srajčka)",
        "items": [
            "Pohorska bunka in zorjen Frešerjev sir, hišna suha salama, paštetka iz domačih jetrc, zaseka, bučni namaz, hišni kruhek",
            "Juhe: goveja župca z rezanci in jetrnimi rolicami, koprivna juhica s čemažem",
            "Meso: pečenka iz pujskovega hrbta, hrustljavi piščanec, piščančje kroglice z zelišči, mlado goveje meso z rdečim vinom",
            "Priloge: štukelj s skuto, ričota s pirino kašo, pražen krompir, mini pita s porom, ocvrte hruške, pomladna solata",
            "Sladica: Pohorska gibanica babice Marije",
            "Cena: 36 EUR odrasli, otroci 4-12 let -50%",
        ],
    },
    {
        "months": {6, 7, 8},
        "label": "Junij-Avgust (poletna srajčka)",
        "items": [
            "Pohorska bunka, zorjen sir, hišna suha salama, paštetka iz jetrc z žajbljem, bučni namaz, kruhek",
            "Juhe: goveja župca z rezanci, kremna juha poletnega vrta",
            "Meso: pečenka iz pujskovega hrbta, hrustljavi piščanec, piščančje kroglice, mlado goveje meso z rabarbaro in rdečim vinom",
            "Priloge: štukelj s skuto, ričota s pirino kašo, mlad krompir z rožmarinom, mini pita z bučkami, ocvrte hruške, poletna solata",
            "Sladica: Pohorska gibanica babice Marije",
            "Cena: 36 EUR odrasli, otroci 4-12 let -50%",
        ],
    },
    {
        "months": {9, 10, 11},
        "label": "September-November (jesenska srajčka)",
        "items": [
            "Dobrodošlica s hišnim likerjem ali sokom; lesena deska s pohorsko bunko, salamo, namazi, Frešerjev sirček, kruhek",
            "Juhe: goveja župca z rezanci, bučna juha s kolerabo, sirne lizike z žajbljem",
            "Meso: pečenka iz pujskovega hrbta, hrustljavi piščanec, piščančje kroglice, mlado goveje meso z rabarbaro in rdečo peso",
            "Priloge: štukelj s skuto, ričota s pirino kašo, pražen krompir iz šporheta, mini pita s porom, ocvrte hruške, jesenska solatka",
            "Sladica: Pohorska gibanica (porcijsko)",
            "Cena: 36 EUR odrasli, otroci 4-12 let -50%",
        ],
    },
    {
        "months": {12, 1, 2},
        "label": "December-Februar (zimska srajčka)",
        "items": [
            "Pohorska bunka, zorjen sir, hišna suha salama, paštetka iz jetrc s čebulno marmelado, zaseka, bučni namaz, kruhek",
            "Juhe: goveja župca z rezanci, krompirjeva juha s krvavico",
            "Meso: pečenka iz pujskovega hrbta, hrustljavi piščanec, piščančje kroglice, mlado goveje meso z rdečim vinom",
            "Priloge: štukelj s skuto, ričota s pirino kašo, pražen krompir iz pečice, mini pita z bučkami, ocvrte hruške, zimska solata",
            "Sladica: Pohorska gibanica babice Marije",
            "Cena: 36 EUR odrasli, otroci 4-12 let -50%",
        ],
    },
]

WEEKLY_EXPERIENCES = [
    {
        "label": "Kulinarično doživetje (36 EUR, vinska spremljava 15 EUR / 4 kozarci)",
        "menu": [
            "Penina Doppler Diona 2017, pozdrav iz kuhinje",
            "Sauvignon Frešer 2024, kiblflajš, zelenjava z vrta, zorjen sir, kruh z drožmi",
            "Juha s kislim zeljem in krvavico",
            "Alter Šumenjak 2021, krompir z njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka",
            "Rumeni muškat Greif 2024, Pohorska gibanica ali štrudl ali pita sezone, hišni sladoled",
        ],
    },
    {
        "label": "Kulinarično doživetje (43 EUR)",
        "menu": [
            "Penina Doppler Diona 2017, pozdrav iz kuhinje",
            "Sauvignon Frešer 2024, kiblflajš, zelenjava, zorjen sir, kruh z drožmi",
            "Juha s kislim zeljem in krvavico",
            "Renski rizling Frešer 2019, ričotka pirine kaše z jurčki",
            "Alter Šumenjak 2021, krompir, zelenjavni pire, pohan pišek, solatka",
            "Rumeni muškat Greif 2024, Pohorska gibanica ali štrudl ali pita sezone, hišni sladoled",
        ],
    },
    {
        "label": "Kulinarično doživetje (53 EUR, vinska spremljava 25 EUR / 6 kozarcev)",
        "menu": [
            "Penina Doppler Diona 2017, pozdrav iz kuhinje",
            "Sauvignon Frešer 2024, kiblflajš, zelenjava, zorjen sir, kruh z drožmi",
            "Juha s kislim zeljem in krvavico",
            "Renski rizling Frešer 2019, ričota z jurčki in zelenjavo",
            "Alter Šumenjak 2021, krompir, zelenjavni pire, pohan pišek, solatka",
            "Modra frankinja Greif 2020, štrukelj s skuto, goveje meso, rdeča pesa, rabarbara, naravna omaka",
            "Rumeni muškat Greif 2024, Pohorska gibanica ali štrudl ali pita sezone, hišni sladoled",
        ],
    },
    {
        "label": "Kulinarično doživetje (62 EUR, vinska spremljava 29 EUR / 7 kozarcev)",
        "menu": [
            "Penina Doppler Diona 2017, pozdrav iz kuhinje",
            "Sauvignon Frešer 2024, kiblflajš, zelenjava, zorjen sir, kruh z drožmi",
            "Juha s kislim zeljem in krvavico",
            "Renski rizling Frešer 2019, ričota pirine kaše z jurčki",
            "Alter Šumenjak 2021, krompir, zelenjavni pire, pohan pišek, solatka",
            "Modra frankinja Greif 2020, štrukelj s skuto, goveje meso, rdeča pesa, rabarbara, naravna omaka",
            "Rumeni muškat Greif 2024, Pohorska gibanica ali štrudl ali pita sezone, hišni sladoled",
        ],
    },
]

INFO_RESPONSES = {
    "pozdrav": f"""Pozdravljeni pri {BRAND_NAME}! 😊

Lahko pomagam z vprašanji o sobah, kosilih, izletih ali domačih izdelkih.""",
    "smalltalk": "Hvala, dobro.",
    "kdo_si": f"""Sem vaš digitalni pomočnik {BRAND_NAME}.

Z veseljem odgovorim na vprašanja o nastanitvi, kosilih, izletih ali izdelkih.""",
    "odpiralni_cas": """Odprti smo ob **sobotah in nedeljah med 12:00 in 20:00**.

Zadnji prihod na kosilo je ob **15:00**.
Ob ponedeljkih in torkih smo zaprti.

Za skupine (15+ oseb) pripravljamo tudi med tednom od srede do petka – pokličite nas! 📞""",
    "zajtrk": """Zajtrk servíramo med **8:00 in 9:00** in je **vključen v ceno nočitve**.

Kaj vas čaka? 🥐
- Sveže pomolzeno mleko
- Zeliščni čaj babice Marije
- Kruh iz krušne peči
- Pohorska bunka, salama, pašteta
- Domača marmelada in med od čebelarja Pislak
- Skuta, maslo, sir iz kravjega mleka
- Jajca z domače reje
- Kislo mleko, jogurt z malinami po receptu gospodinje Sare

Vse domače, vse sveže! ☕""",
    "vecerja": """Večerja se streže ob **18:00** in stane **25 €/osebo**.

Kaj dobite?
- **Juha** – česnova, bučna, gobova, goveja, čemaževa ali topinambur
- **Glavna jed** – meso s prilogami (skutni štruklji, narastki, krompir)
- **Sladica** – specialiteta hiše: pohorska gibanica babice Marije

Prilagodimo za vegetarijance, vegane in celiakijo! 🌿

⚠️ **Ob ponedeljkih in torkih večerje ne strežemo** – takrat priporočamo bližnji gostilni Framski hram ali Karla.""",
    "sobe": """Imamo **3 sobe**, vse poimenovane po naših otrocih:

🛏️ **GOZD** – soba z balkonom (2+2)
🛏️ **RAZGLED** – družinska soba z balkonom (2 odrasla + 2 otroka)  
🛏️ **SONCE** – družinska soba z dvema spalnicama (2+2)

Vsaka soba ima:
✅ Predprostor, spalnico, kopalnico s tušem
✅ Pohištvo iz lastnega lesa
✅ Klimatizacijo
✅ Brezplačen Wi-Fi
✅ Satelitsko TV
✅ Igrače za otroke

Zajtrk je vključen v ceno! 🥐""",
    "cena_sobe": """**Cenik nastanitve:**

🛏️ **Nočitev z zajtrkom:** 50 €/osebo/noč (min. 2 noči)
🍽️ **Večerja:** 25 €/osebo
🏷️ **Turistična taksa:** 1,50 €

**Popusti:**
- Otroci do 5 let: **brezplačno** (z zajtrkom in večerjo)
- Otroci 5-12 let: **50% popust**
- Otroška posteljica: **brezplačno**
- Doplačilo za enoposteljno: **+30%**""",
    "klima": """Da, vse naše sobe so **klimatizirane** in udobne tudi v poletni vročini.""",
    "wifi": """Da, na voljo imamo **brezplačen Wi-Fi** v vseh sobah in skupnih prostorih.""",
    "prijava_odjava": """**Prijava (check-in):** od 14:00
**Odjava (check-out):** do 10:00""",
    "parking": """Parkirišče je brezplačno in na voljo neposredno pri domačiji.""",
    "zivali": """Ob 40‑glavi goveji čredi imamo na kmetiji še svinje, račke in kokoši.

Najmlajši uživajo ob naših živalih: konjička Malajko in Marsi, pujska Pepa ter ovna Čarlija. Imamo tudi psičko Luno in mucke.""",
    "traktor": """Da, na kmetiji imamo traktor in drugo kmetijsko mehanizacijo za delo na posestvu.""",
    "jahanje": """Jahanje je možno po dogovoru in ob primernem vremenu. Običajno nudimo krajši krog s ponijem za otroke (5 € / krog). Pred obiskom priporočamo predhodno najavo.""",
    "pets_policy": """Hišni ljubljenčki na naši domačiji niso dovoljeni.""",
    "placilo": """Sprejemamo gotovino in večino plačilnih kartic.""",
    "kontakt": f"""Kontakt: **{FARM_INFO['phone']}** / **{FARM_INFO['mobile']}**
Email: **{FARM_INFO['email']}**""",
    "lokacija": f"""Nahajamo se na: **{FARM_INFO['address']}** ({FARM_INFO['location_description']}). 
Parking je brezplačen pri domačiji.""",
    "zgodovina": """Naša domačija ima dolgo tradicijo na Planici nad Framom. Prvi zapisi o rodu segajo v 19. stoletje (po nekaterih virih celo v 1770), današnja družina pa je kmetijo prevzela in jo močno razvila po letu 2008.""",
    "min_nocitve": """Minimalno bivanje je:
- **3 nočitve** v juniju, juliju in avgustu
- **2 nočitvi** v ostalih mesecih""",
    "kapaciteta_mize": """Jedilnica 'Pri peči' sprejme do 15 oseb, 'Pri vrtu' pa do 35 oseb.""",
    "alergije": """Seveda, prilagodimo jedi za alergije (gluten, laktoza) in posebne prehrane (vegan/vegetarijan).""",
    "vina": """Ponujamo lokalna pohorska vina: bela, rdeča in penine. Izbor je sezonski in ga z veseljem predstavimo ob obisku.""",
    "turizem": """V okolici so odlične možnosti za izlete (Pohorje, slapovi, razgledišča).""",
    "smucisce": """Najbližja smučišča so Mariborsko Pohorje in Areh (približno 25–35 minut vožnje).""",
    "terme": """Najbližje terme so Terme Zreče in Terme Ptuj (približno 30–40 minut vožnje).""",
    "dez": """Če dežuje, priporočamo notranje aktivnosti: degustacija domačih izdelkov, obisk term (Zreče/Ptuj), ogled gradu Rače ali sproščen obisk lokalnih gostiln v okolici.""",
    "kolesa": """Izposoja koles je možna po dogovoru. Za več informacij nas kontaktirajte.""",
    "skalca": """Slap Skalca je prijeten izlet v bližini – priporočamo sprehod ob potočku.""",
    "darilni_boni": """Na voljo imamo darilne bone. Sporočite znesek in pripravimo bon za vas.""",
    "jedilnik": """AKTUALNI SEZONSKI MENI

Pohorska bunka in zorjen Freserjev sir
Hisna suha salama
Pastetka iz domacih jetrc
Zaseka
Bucni namaz
Hisni kruhek

***

Goveja zupca z rezanci in jetrnimi rolicami
Koprivna juhica s cemazem in sirne lizike

***

Meso servirano na plosci

Socna pecenka iz domacega pujskovega hrbta
Hrustljavi piscanec s kmetije Pesek
Piscancje kroglice z zelisci
Mlado goveje meso iz Kmetije Pod Goro proste reje in jabolka z rdecim vinom

Priloge servirane loceno od mesa

Stukelj s skuto nase krave Miske
Ricota s pirino kaso, jurcki in zelenjava
Prazen krompir iz sporheta na drva
Mini pita s porom
Ocvrte hruske "Debeluske" z zdrobom
Pomladna solatka iz vrta gospodinje Sare

***

Pohorska gibanica babice Marije s skuto

CENA po ODRASLI osebi: 36 EUR
Otroci (4 - 12 let): - 50 %

Prosimo, najavite morebitna odstopanja od klasicnega mesnega jedilnika (vegi, vegansko, brez glutena, mleka, jajc).""",
    "tedenska_ponudba": """CEZ TEDEN (SREDA-PETEK)

Na voljo so degustacijski meniji:
- 4-hodni degustacijski meni
- 5-hodni degustacijski meni
- 6-hodni degustacijski meni

Tedenski meniji so na predhodno rezervacijo in se prilagodijo sezoni.""",
    "tedenski_5hodni": """KULINARICNO DOZIVETJE
SREDA - PETEK
Penina Doppler, Diona 2017, zelo suho, 100 % chardonnay
Pozdrav iz kuhinje
***
Freser, sauvignon, suho, 2024
Kiblflajs s prelivom, zelenjava s Kmetije Pod Goro vrta, zorjen Freserjev sir, hisni kruh z drozmi
***
Juha s kislim zeljem in krvavico
***
Freser, renski rizling, suho, 2019
Ricotka pirine kase z jurcki in zelenjavo
***
Sumenjak, Alter, suho, 2021
Krompir iz nase njive, zelenjavni pire, pohan pisek s kmetije Pesek, solatka iz vrta gospodinje Sare
***
Greif, rumeni muskat, polsladko, 2024
Pohorska gibanica babice Marije ali domac jabolcni strudl ali pita sezone, hisni sladoled

CENA PO ODRASLI OSEBI: 43 EUR
Cena vinske spremljave: 20 EUR za 5 kozarcev""",
    "tedenski_6hodni": """KULINARICNO DOZIVETJE
SREDA - PETEK
Penina Doppler, Diona 2017, zelo suho, 100 % chardonnay
Pozdrav iz kuhinje
***
Freser, sauvignon, suho, 2024
Kiblflajs s prelivom, zelenjava s Kmetije Pod Goro vrta, zorjen Freserjev sir, hisni kruh z drozmi
***
Juha s kislim zeljem in krvavico
***
Freser, renski rizling, suho, 2019
Ricotka pirine kase z jurcki in zelenjavo
***
Sumenjak, Alter, suho, 2021
Krompir iz nase njive, zelenjavni pire, pohan pisek s kmetije Pesek, solatka iz vrta gospodinje Sare
***
Greif, modra frankinja, suho, 2020
Strukelj s skuto nase krave Miske, goveje meso iz Kmetije Pod Goro proste reje, rdeca pesa, rabarbara, naravna omaka
***
Greif, rumeni muskat, polsladko, 2024
Pohorska gibanica babice Marije ali domac jabolcni strudl ali pita sezone, hisni sladoled

CENA PO ODRASLI OSEBI: 53 EUR
Cena vinske spremljave: 25 EUR za 6 kozarcev""",
    "druzina": """Pri nas smo družinska domačija in radi sprejmemo družine. Imamo tudi igrala za otroke.""",
    "gospodar": """Gospodar kmetije je Marko.""",
    "kmetija": """Kmetija Pod Goro je turistična kmetija na Pohorju z nastanitvijo, kosili in domačimi izdelki.""",
    "gibanica": """Pohorska gibanica je naša specialiteta. Priporočam, da jo poskusite ob obisku!""",
    "izdelki": """Imamo domače izdelke: marmelade, likerje/žganja, mesnine, čaje, sirupe in darilne pakete.""",
    "priporocilo": """Trenutno nimam priporočil brez dodatnih informacij.""",
}

INFO_RESPONSES_VARIANTS = {key: [value] for key, value in INFO_RESPONSES.items()}
INFO_RESPONSES_VARIANTS["menu_info"] = [INFO_RESPONSES["jedilnik"]]
INFO_RESPONSES_VARIANTS["menu_full"] = [INFO_RESPONSES["jedilnik"]]
INFO_RESPONSES["menu_info"] = INFO_RESPONSES["jedilnik"]
INFO_RESPONSES["menu_full"] = INFO_RESPONSES["jedilnik"]
INFO_RESPONSES["sobe_info"] = INFO_RESPONSES["sobe"]

CONFIG = BrandConfig(
    name=FARM_INFO["name"],
    address=FARM_INFO["address"],
    phone=FARM_INFO["phone"],
    mobile=FARM_INFO["mobile"],
    email=FARM_INFO["email"],
    website=FARM_INFO["website"],
    location_description=FARM_INFO["location_description"],
    parking=FARM_INFO["parking"],
    opening_hours=FARM_INFO["opening_hours"],
    facilities=FARM_INFO["facilities"],
    activities=FARM_INFO["activities"],
    greetings=GREETINGS,
    thanks_responses=THANKS_RESPONSES,
    unknown_responses=UNKNOWN_RESPONSES,
    menu_intros=MENU_INTROS,
    seasonal_menus=SEASONAL_MENUS,
    weekly_experiences=WEEKLY_EXPERIENCES,
)
