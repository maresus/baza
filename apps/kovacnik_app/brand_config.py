"""
Brand Configuration - Turistična kmetija Kovačnik

Vsi podatki specifični za to kmetijo. Logika bere iz tega configa,
kar omogoča enostavno dodajanje novih kmetij.
"""

# =============================================================================
# OSNOVNI PODATKI
# =============================================================================

BRAND_NAME = "Turistična kmetija Kovačnik"
BRAND_SHORT = "Kovačnik"
DOMAIN = "kovacnik.com"

# =============================================================================
# KONTAKTNI PODATKI
# =============================================================================

FARM_INFO = {
    "name": "Turistična kmetija Kovačnik",
    "address": "Planica 9, 2313 Fram",
    "phone": "02 601 54 00",
    "mobile": "031 330 113",
    "email": "info@kovacnik.com",
    "website": "www.kovacnik.com",
    "location_description": "Na pohorski strani, nad Framom, približno 15 min iz doline",
    "parking": "Brezplačen parking ob hiši za 10+ avtomobilov",
    "directions": {
        "from_maribor": (
            "Iz avtoceste A1 (smer Maribor/Ljubljana) izvoz Fram. Pri semaforju v Framu proti cerkvi sv. Ane, "
            "naravnost skozi vas proti Kopivniku. V Kopivniku na glavni cesti zavijete desno (tabla Kmetija Kovačnik) "
            "in nadaljujete še približno 10 minut. Od cerkve v Framu do kmetije je slabih 15 minut."
        ),
    },
}

# Spletna trgovina
SHOP_URL = "https://kovacnik.com/katalog"

# =============================================================================
# DRUŽINA IN OSEBNI PODATKI
# =============================================================================

FAMILY = {
    "owner": "Danilo",
    "grandmother": "Angelca",
    "members": ["Danilo", "Barbara", "Aljaž", "Julija", "Ana"],
    "partner": "Kaja",  # Aljaževa partnerka
    "horses": ["Malajka", "Marsij"],
    "cow": "Miška",
}

# Primer imena za validacijo (npr. "Prosim napišite ime in priimek (npr. 'Ana Kovačnik').")
EXAMPLE_NAME = "Ana Kovačnik"

# =============================================================================
# SOBE
# =============================================================================

ROOMS = {
    "ALJAZ": {
        "name": "Soba ALJAŽ",
        "description": "soba z balkonom",
        "capacity": "2+2 osebi",
    },
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

ROOM_NAMES = list(ROOMS.keys())  # ['ALJAZ', 'JULIJA', 'ANA']

# =============================================================================
# POZDRAVI IN SPOROČILA
# =============================================================================

GREETINGS = [
    "Pozdravljeni! Kako vam lahko pomagam?",
    "Pozdravljeni! Kako vam lahko pomagam?",
    "Lepo pozdravljeni s Pohorja! Kako vam lahko pomagam danes?",
    "Dober dan! Vesela sem, da ste nas obiskali. S čim vam lahko pomagam?",
    f"Pozdravljeni pri {BRAND_SHORT}u! Kaj vas zanima?",
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
            FAMILY['members'][2],  # Aljaž
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
    "kiblflajš": f"Kiblflajš s prelivom, zelenjava s {BRAND_SHORT}ovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi",
    "štrukelj": f"Štrukelj s skuto naše krave {FAMILY['cow']}, goveje meso iz {BRAND_SHORT}ove proste reje, rdeča pesa, rabarbara, naravna omaka",
    "gibanica": f"Pohorska gibanica babice {FAMILY['grandmother']}",
}
