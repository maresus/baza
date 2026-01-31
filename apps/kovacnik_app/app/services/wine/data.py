"""
Wine data - wine list and keywords.
"""

# Vinski seznam
WINE_LIST = {
    "penece": [
        {
            "name": "Doppler DIONA brut 2013",
            "type": "zelo suho",
            "grape": "100% Chardonnay",
            "price": 30.00,
            "desc": "Penina po klasični metodi, eleganca, lupinasto sadje, kruhova skorja",
        },
        {
            "name": "Opok27 NYMPHA rose brut 2022",
            "type": "izredno suho",
            "grape": "100% Modri pinot",
            "price": 26.00,
            "desc": "Rose frizzante, jagodni konfit, češnja, sveže",
        },
        {
            "name": "Leber MUŠKATNA PENINA demi sec",
            "type": "polsladko",
            "grape": "100% Rumeni muškat",
            "price": 26.00,
            "desc": "Klasična metoda, 18 mesecev zorenja, svež vonj limone in muškata",
        },
    ],
    "bela": [
        {
            "name": "Greif BELO zvrst 2024",
            "type": "suho",
            "grape": "Laški rizling + Sauvignon",
            "price": 14.00,
            "desc": "Mladostno, zeliščne in sadne note, visoke kisline",
        },
        {
            "name": "Frešer SAUVIGNON 2023",
            "type": "suho",
            "grape": "100% Sauvignon",
            "price": 19.00,
            "desc": "Aromatičen, zeliščen, črni ribez, koprive, mineralno",
        },
        {
            "name": "Frešer LAŠKI RIZLING 2023",
            "type": "suho",
            "grape": "100% Laški rizling",
            "price": 18.00,
            "desc": "Mladostno, mineralno, note jabolka in suhih zelišč",
        },
        {
            "name": "Greif LAŠKI RIZLING terase 2020",
            "type": "suho",
            "grape": "100% Laški rizling",
            "price": 23.00,
            "desc": "Zoreno 14 mesecev v hrastu, zrelo rumeno sadje, oljnata tekstura",
        },
        {
            "name": "Frešer RENSKI RIZLING Markus 2019",
            "type": "suho",
            "grape": "100% Renski rizling",
            "price": 22.00,
            "desc": "Breskev, petrolej, mineralno, zoreno v hrastu",
        },
        {
            "name": "Skuber MUŠKAT OTTONEL 2023",
            "type": "polsladko",
            "grape": "100% Muškat ottonel",
            "price": 17.00,
            "desc": "Elegantna muškatna cvetica, harmonično, ljubko",
        },
        {
            "name": "Greif RUMENI MUŠKAT 2023",
            "type": "polsladko",
            "grape": "100% Rumeni muškat",
            "price": 17.00,
            "desc": "Mladostno, sortno, note sena in limete",
        },
    ],
    "rdeca": [
        {
            "name": "Skuber MODRA FRANKINJA 2023",
            "type": "suho",
            "grape": "100% Modra frankinja",
            "price": 16.00,
            "desc": "Rubinasta, ribez, murva, malina, polni okus",
        },
        {
            "name": "Frešer MODRI PINOT Markus 2020",
            "type": "suho",
            "grape": "100% Modri pinot",
            "price": 23.00,
            "desc": "Višnje, češnje, maline, žametno, 12 mesecev v hrastu",
        },
        {
            "name": "Greif MODRA FRANKINJA črešnjev vrh 2019",
            "type": "suho",
            "grape": "100% Modra frankinja",
            "price": 26.00,
            "desc": "Zrela, temno sadje, divja češnja, zreli tanini",
        },
    ],
}

# Keywords za prepoznavo vinskih vprašanj
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
