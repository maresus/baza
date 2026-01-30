"""
Brand Configuration - Kmetija Pod Goro

Vsi podatki specifični za to kmetijo. Logika bere iz tega configa,
kar omogoča enostavno dodajanje novih kmetij.

OPOMBA: To je demo/showcase verzija z anonimiziranimi podatki.
"""

# =============================================================================
# OSNOVNI PODATKI
# =============================================================================

BRAND_NAME = "Kmetija Pod Goro"
BRAND_SHORT = "Pod Goro"
DOMAIN = "kmetijapodgoro.si"

# =============================================================================
# KONTAKTNI PODATKI
# =============================================================================

FARM_INFO = {
    "name": "Kmetija Pod Goro",
    "address": "Gorska cesta 7, 2315 Zeleno Polje",
    "phone": "02 700 12 34",
    "mobile": "031 777 888",
    "email": "info@kmetijapodgoro.si",
    "website": "www.kmetijapodgoro.si",
    "location_description": "Na pohorski strani, nad Zelenim Poljem, približno 15 min iz doline",
    "parking": "Brezplačen parking ob hiši za 10+ avtomobilov",
    "directions": {
        "from_maribor": (
            "Iz avtoceste A1 (smer Maribor/Ljubljana) izvoz Zeleno Polje. Pri semaforju v Zeleno Poljeu proti cerkvi sv. Nike, "
            "naravnost skozi vas proti Kopivniku. V Kopivniku na glavni cesti zavijete desno (tabla Kmetija Pod Goro) "
            "in nadaljujete še približno 10 minut. Od cerkve v Zeleno Poljeu do kmetije je slabih 15 minut."
        ),
        "coordinates": "46.5234, 15.6123",
    },
}

# Spletna trgovina
SHOP_URL = "https://kmetijapodgoro.si/katalog"

# =============================================================================
# DRUŽINA IN OSEBNI PODATKI
# =============================================================================

FAMILY = {
    "owner": "Jure",
    "grandmother": "Ivanka",
    "members": ["Jure", "Maja", "Tine", "Lara", "Nika"],
    "partner": "Kaja",  # Tinetova partnerka
    "horses": ["Malajka", "Marsij"],
    "cow": "Miška",
}

# Primer imena za validacijo (npr. "Prosim napišite ime in priimek (npr. 'Lara Novak').")
EXAMPLE_NAME = "Lara Novak"

# =============================================================================
# SOBE
# =============================================================================

ROOMS = {
    "JULIJA": {
        "name": "Soba JULIJA",
        "description": "družinska soba z balkonom",
        "capacity": "2 odrasla + 2 otroka",
    },
    "ANA": {
        "name": "Soba ANA",
        "description": "družinska soba z dvema spalnicama",
        "capacity": "2 odrasla + 2 otroka",
    },
}

ROOM_NAMES = list(ROOMS.keys())  # ['JULIJA', 'ANA']

# =============================================================================
# POZDRAVI IN SPOROČILA
# =============================================================================

GREETINGS = [
    "Pozdravljeni! Kako vam lahko pomagam?",
    "Pozdravljeni! Kako vam lahko pomagam?",
    "Lepo pozdravljeni s Pohorja! Kako vam lahko pomagam danes?",
    "Dober dan! Vesela sem, da ste nas obiskali. S čim vam lahko pomagam?",
    f"Pozdravljeni pri Kmetiji {BRAND_SHORT}! Kaj vas zanima?",
]

# =============================================================================
# EMAIL PREDMETI
# =============================================================================

EMAIL_SUBJECTS = {
    "inquiry": f"Novo povpraševanje – {BRAND_SHORT}",
    "reservation": f"Zadeva: Rezervacija – {BRAND_NAME}",
}

# =============================================================================
# LLM SYSTEM PROMPTS
# =============================================================================

def get_system_prompt_intro(language: str = "si") -> str:
    """Vrne uvod za system prompt glede na jezik."""
    family_str = f"Babica {FAMILY['grandmother']}, {', '.join(FAMILY['members'])}"
    if FAMILY.get('partner'):
        family_str = family_str.replace(
            FAMILY['members'][2],  # Tine
            f"{FAMILY['members'][2]} (partnerka {FAMILY['partner']})"
        )

    base = (
        f"- Gospodar kmetije: {FAMILY['owner']}\n"
        f"- Družina: {family_str}\n"
        f"- Konjička: {' in '.join(FAMILY['horses'])}\n\n"
    )

    if language == "en":
        return f"You are the assistant for {BRAND_NAME}. Respond in English.\n" + base
    elif language == "de":
        return f"Du bist der Assistent für {BRAND_NAME}. Antworte auf Deutsch.\n" + base
    else:
        return f"Ti si asistent Domačije {BRAND_SHORT}. Upoštevaj te potrjene podatke kot glavne:\n" + base

# =============================================================================
# FEATURES (funkcionalnosti)
# =============================================================================

FEATURES = {
    "shop": True,              # Spletna trgovina
    "room_booking": True,      # Rezervacija sob
    "table_booking": True,     # Rezervacija miz
    "products": True,          # Izdelki (salame, med, itd.)
    "wine_list": True,         # Vinska karta
    "inquiry": True,           # Povpraševanja (teambuilding, itd.)
    "email_notifications": True,
    "dinner_booking": True,    # Večerje ob sobah
}

# =============================================================================
# DODATNI SPECIFIČNI PODATKI
# =============================================================================

# Za wine pairing in jedi
FARM_SPECIFIC_DISHES = {
    "kiblflajš": f"Kiblflajš s prelivom, zelenjava s {BRAND_SHORT}vega vrta, zorjen Frešerjev sir, hišni kruh z drožmi",
    "štrukelj": f"Štrukelj s skuto naše krave {FAMILY['cow']}, goveje meso iz {BRAND_SHORT}e proste reje, rdeča pesa, rabarbara, naravna omaka",
    "gibanica": f"Pohorska gibanica babice {FAMILY['grandmother']}",
}
