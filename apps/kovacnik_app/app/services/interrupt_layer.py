"""
Interrupt Layer - omogoča odgovor na INFO/PRODUCT vprašanja med aktivnim flowom.

Namesto: "Pesto imamo! Želiš nadaljevati? (da/ne)"
Zdaj:    "Pesto imamo! Za vašo mizo pa – koliko gostov pričakujete?"

Logika:
1. check_for_interrupt() - preveri če je sporočilo INFO/PRODUCT vprašanje
2. handle_interrupt() - odgovori na vprašanje
3. get_resume_prompt() - vrne nadaljevanje za trenutni booking step
4. build_interrupt_response() - kombinira odgovor + resume prompt
"""

from typing import Optional, Tuple, Dict, Any

# INFO ključne besede (vprašanja o kmetiji, lokaciji, urnikih...)
INFO_INTERRUPT_KEYWORDS = {
    # Živali
    "zajc", "zajček", "zajčk", "zajce", "kunec", "kunček",
    "konj", "konji", "žival", "živali", "krava", "krave",
    # Lokacija/kontakt
    "kje", "naslov", "lokacija", "telefon", "email", "kontakt",
    "kako pridem", "pot do", "parking", "parkirišče",
    # Ura/odpiralno
    "kdaj", "odprt", "odprto", "ura", "do kdaj",
    # Splošno o kmetiji
    "kdo", "družin", "gospodar", "lastnik", "babic",
    "wifi", "klima", "igrišče", "otroško",
}

# PRODUCT ključne besede (izdelki, trgovina)
PRODUCT_INTERRUPT_KEYWORDS = {
    "pesto", "čemaž", "cemaz",
    "marmelad", "džem", "dzem",
    "liker", "žganj", "zganj",
    "med", "sir", "salam", "klobas", "bunk", "mesnin",
    "sirup", "čaj", "caj",
    "izdelk", "katalog", "trgovin", "kupit",
    "gibanica", "štrukelj", "strukelj",
}

# Besede ki kažejo na pravo vprašanje (ne samo omemba)
QUESTION_INDICATORS = {
    "?", "a mate", "ali mate", "imate", "a imate",
    "kaj pa", "kako je z", "kaj je z",
    "ali je", "a je", "koliko stane", "cena",
    "kje je", "kje so", "ali so",
    "povejte", "povej", "mi lahko",
}


def check_for_interrupt(message: str, state: Dict[str, Any]) -> Optional[str]:
    """
    Preveri če je sporočilo interrupt med aktivnim booking flowom.

    Returns:
        - "INFO" če je info vprašanje
        - "PRODUCT" če je product vprašanje
        - None če ni interrupt (normalno nadaljuj flow)
    """
    # Če ni aktivnega flowa, ni interrupta
    if state.get("step") is None:
        return None

    lowered = message.lower()

    # Preveri če je to sploh vprašanje (ne samo omemba)
    is_question = any(ind in lowered for ind in QUESTION_INDICATORS)

    # Tudi brez vprašalnih indikatorjev lahko detectamo jasne primere
    # npr. "zajčke bi videl" ali "pesto me zanima"
    interest_words = {"zanima", "videl", "videt", "rad bi", "rada bi", "bi rad", "bi rada"}
    shows_interest = any(word in lowered for word in interest_words)

    # Če ni niti vprašanje niti interes, ni interrupt
    if not is_question and not shows_interest:
        # Ampak še vedno preveri za eksplicitne "a mate X" oblike
        if not any(f"a mate {kw}" in lowered or f"ali mate {kw}" in lowered
                   for kw in list(INFO_INTERRUPT_KEYWORDS) + list(PRODUCT_INTERRUPT_KEYWORDS)):
            return None

    # Preveri INFO keywords
    for keyword in INFO_INTERRUPT_KEYWORDS:
        if keyword in lowered:
            return "INFO"

    # Preveri PRODUCT keywords
    for keyword in PRODUCT_INTERRUPT_KEYWORDS:
        if keyword in lowered:
            return "PRODUCT"

    return None


def get_resume_prompt(state: Dict[str, Any]) -> str:
    """
    Vrne prijazno nadaljevanje za trenutni booking step.

    Namesto: "Trenutno čakamo: datum"
    Zdaj:    "Za vašo mizo pa – za kateri datum bi rezervirali?"
    """
    step = state.get("step")
    booking_type = state.get("type", "table")

    # Zberemo kaj že imamo
    has_date = bool(state.get("date"))
    has_guests = bool(state.get("guests"))
    has_time = bool(state.get("time"))
    has_name = bool(state.get("name"))
    has_email = bool(state.get("email"))
    has_phone = bool(state.get("phone"))

    is_room = booking_type == "room"
    type_word = "sobo" if is_room else "mizo"

    # Glede na step vrnemo ustrezni prompt
    prompts = {
        # Table booking steps
        "awaiting_table_date": f"Za vašo {type_word} pa – za kateri datum bi rezervirali?",
        "awaiting_table_time": "Ob kateri uri bi prišli?",
        "awaiting_table_guests": "Koliko gostov pričakujete?",
        "awaiting_table_name": "Lahko dobim vaše ime za rezervacijo?",
        "awaiting_table_email": "In vaš e-mail za potrditev?",
        "awaiting_table_phone": "Še telefonsko številko za vsak primer?",

        # Room booking steps
        "awaiting_room_date": "Za sobe – od katerega datuma bi se nastanili?",
        "awaiting_room_nights": "Koliko noči bi ostali?",
        "awaiting_room_guests": "Koliko vas bo? (odrasli + otroci)",
        "awaiting_room_name": "Lahko dobim vaše ime za rezervacijo?",
        "awaiting_room_email": "In vaš e-mail za potrditev?",
        "awaiting_room_phone": "Še telefonsko številko?",

        # Shared/other
        "awaiting_name": "Lahko dobim vaše ime za rezervacijo?",
        "awaiting_email": "In vaš e-mail za potrditev?",
        "awaiting_phone": "Še telefonsko številko?",
        "awaiting_consent": "Se strinjate z obdelavo podatkov? (da/ne)",
    }

    if step in prompts:
        return prompts[step]

    # Fallback - kaj še manjka?
    if is_room:
        if not has_date:
            return "Za sobe – od katerega datuma bi se nastanili?"
        if not has_guests:
            return "Koliko vas bo? (odrasli + otroci)"
        if not has_name:
            return "Lahko dobim vaše ime?"
        if not has_email:
            return "In vaš e-mail?"
    else:
        if not has_date:
            return "Za mizo – za kateri datum?"
        if not has_time:
            return "Ob kateri uri?"
        if not has_guests:
            return "Koliko gostov?"
        if not has_name:
            return "Lahko dobim vaše ime?"
        if not has_email:
            return "In vaš e-mail?"

    return "Nadaljujemo z rezervacijo?"


def build_interrupt_response(
    interrupt_answer: str,
    state: Dict[str, Any],
    separator: str = "\n\n"
) -> str:
    """
    Kombinira odgovor na interrupt z resume promptom.

    Primer:
        interrupt_answer: "Seveda, pesto imamo! Čemažev pesto stane 5€."
        resume_prompt: "Za vašo mizo pa – koliko gostov pričakujete?"

        Result: "Seveda, pesto imamo! Čemažev pesto stane 5€.

                Za vašo mizo pa – koliko gostov pričakujete?"
    """
    resume = get_resume_prompt(state)
    return f"{interrupt_answer}{separator}{resume}"
