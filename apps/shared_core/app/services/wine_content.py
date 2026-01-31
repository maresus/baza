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


def answer_wine_question(message: str, ctx: dict) -> str:
    """Odgovarja na vprašanja o vinih SAMO iz WINE_LIST, z upoštevanjem followupov."""
    last_shown_products = ctx.get("last_shown_products", [])

    lowered = message.lower()
    is_followup = any(word in lowered for word in ["še", "drug", "kaj pa", "še kaj", "še kater", "še kakšn", "še kakšno"])

    is_red = any(word in lowered for word in ["rdeč", "rdeca", "rdece", "rdeče", "frankinja", "pinot"])
    is_white = any(word in lowered for word in ["bel", "bela", "belo", "rizling", "sauvignon"])
    is_sparkling = any(word in lowered for word in ["peneč", "penina", "penece", "mehurčk", "brut"])
    is_sweet = any(word in lowered for word in ["sladk", "polsladk", "muškat", "muskat"])
    is_dry = any(word in lowered for word in ["suh", "suho", "suha"])

    def format_wines(wines: list, category_name: str, temp: str) -> str:
        # ob followupu skrij že prikazane
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

        ctx["last_shown_products"] = last_shown_products

        return "\n".join(lines) + f"\n\nServiramo ohlajeno na {temp}."

    # Rdeča
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

    # Peneča
    if is_sparkling:
        return format_wines(WINE_LIST["penece"], "peneča", "6°C")

    # Bela
    if is_white:
        wines = WINE_LIST["bela"]
        if is_dry:
            wines = [w for w in wines if "suho" in w["type"]]
        if is_sweet:
            wines = [w for w in wines if "polsladk" in w["type"]]
        return format_wines(wines[:5], "bela", "8–10°C")

    # Polsladka
    if is_sweet:
        wines = []
        for w in WINE_LIST["bela"]:
            if "polsladk" in w["type"]:
                wines.append(w)
        for w in WINE_LIST["penece"]:
            if "polsladk" in w["type"].lower() or "demi" in w["type"].lower():
                wines.append(w)
        return format_wines(wines, "polsladka", "8°C")

    # Splošno vprašanje
    return (
        "Ponujamo izbor lokalnih vin:\n\n"
        "🍷 **Rdeča** (suha): Modra frankinja (Skuber 16€, Greif 26€), Modri pinot Frešer (23€)\n"
        "🥂 **Bela** (suha): Sauvignon (19€), Laški rizling (18–23€), Renski rizling (22€)\n"
        "🍾 **Peneča**: Doppler Diona brut (30€), Opok27 rose (26€), Muškatna penina (26€)\n"
        "🍯 **Polsladka**: Rumeni muškat (17€), Muškat ottonel (17€)\n\n"
        "Povejte, kaj vas zanima – rdeče, belo, peneče ali polsladko?"
    )
