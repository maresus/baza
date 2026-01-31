"""
Farm info answer functions.
"""

from .data import FARM_INFO
from app.services.validators import is_hours_question


def answer_farm_info(message: str) -> str:
    """Answer questions about the farm (location, contact, hours, etc.)."""
    lowered = message.lower()

    # Zajčki / živali
    if any(word in lowered for word in ["zajc", "zajček", "zajcka", "zajčki", "kunec", "zajce"]):
        return "Imamo prijazne zajčke, ki jih lahko obiskovalci božajo. Ob obisku povejte, pa vas usmerimo do njih."

    # Ogledi / ture
    if any(word in lowered for word in ["ogled", "tour", "voden", "vodenje", "guid", "sprehod po kmetiji"]):
        return "Organiziranih vodenih ogledov pri nas ni. Ob obisku se lahko samostojno sprehodite in vprašate osebje, če želite videti živali."

    # Navodila za pot
    if any(word in lowered for word in ["navodila", "pot", "pot do", "pridem", "priti", "pot do vas", "avtom"]):
        return FARM_INFO["directions"]["from_maribor"]

    # Lokacija / naslov
    if any(word in lowered for word in ["kje", "naslov", "lokacija", "nahajate"]):
        return (
            f"Nahajamo se na: {FARM_INFO['address']} ({FARM_INFO['location_description']}). "
            f"Parking: {FARM_INFO['parking']}. Če želite navodila za pot, povejte, od kod prihajate."
        )

    # Telefon
    if any(word in lowered for word in ["telefon", "številka", "stevilka", "poklicat", "klicat"]):
        return f"Telefon: {FARM_INFO['phone']}, mobitel: {FARM_INFO['mobile']}. Pišete lahko na {FARM_INFO['email']}."

    # Email
    if "email" in lowered or "mail" in lowered:
        return f"E-mail: {FARM_INFO['email']}. Splet: {FARM_INFO['website']}."

    # Delovni čas
    if any(word in lowered for word in ["odprt", "kdaj", "delovni", "ura"]):
        return (
            f"Kosila: {FARM_INFO['opening_hours']['restaurant']} | "
            f"Sobe: {FARM_INFO['opening_hours']['rooms']} | "
            f"Trgovina: {FARM_INFO['opening_hours']['shop']} | "
            f"Zaprto: {FARM_INFO['opening_hours']['closed']}"
        )

    # Parking
    if "parking" in lowered or "parkirišče" in lowered or "parkirisce" in lowered or "avto" in lowered:
        return f"{FARM_INFO['parking']}. Naslov za navigacijo: {FARM_INFO['address']}."

    # WiFi / facilities
    if "wifi" in lowered or "internet" in lowered or "klima" in lowered:
        facilities = ", ".join(FARM_INFO["facilities"])
        return f"Na voljo imamo: {facilities}."

    # Aktivnosti
    if any(word in lowered for word in ["počet", "delat", "aktivnost", "izlet"]):
        activities = "; ".join(FARM_INFO["activities"])
        return f"Pri nas in v okolici lahko: {activities}."

    # Delovni čas (detailed)
    if is_hours_question(message):
        return (
            "Kosila: sobota/nedelja 12:00-20:00 (zadnji prihod 15:00). "
            "Zajtrk: 8:00-9:00 (za goste sob). "
            "Prijava 15:00-20:00, odjava do 11:00. "
            "Večerje za goste po dogovoru (pon/torki kuhinja zaprta)."
        )

    # Splošni info
    return (
        f"{FARM_INFO['name']} | Naslov: {FARM_INFO['address']} | Tel: {FARM_INFO['phone']} | "
        f"Email: {FARM_INFO['email']} | Splet: {FARM_INFO['website']}"
    )
