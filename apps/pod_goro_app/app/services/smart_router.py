"""
Smart Router - LLM-based intent classification

Namesto keyword matchinga LLM odloči:
1. Kaj uporabnik hoče (INFO, PRODUCT, BOOKING, COMPOSITE)
2. Če je aktiven booking: ali je to interrupt ali booking podatek
3. Generira ustrezen odgovor z resume promptom

Primer:
  User: "a mate pesto?" (med booking flowom)
  Router: {
    "intent": "PRODUCT",
    "is_interrupt": True,
    "answer": "Seveda, čemažev pesto imamo!",
    "resume": "Za vašo mizo - za kateri datum?"
  }
"""

import json
import logging
from typing import Any, Dict, Optional
from openai import OpenAI
from app.core.config import Settings

logger = logging.getLogger("smart_router")

# Prompt za routing - kratek in jasen
ROUTER_SYSTEM_PROMPT = """Ti si intent classifier za turistično kmetijo Kmetija Pod Goro.

Analiziraj uporabnikovo sporočilo in vrni JSON z naslednjimi polji:

{
  "intent": "INFO|PRODUCT|BOOKING|GREETING|GOODBYE|UNCLEAR",
  "is_interrupt": true/false,
  "info_topic": "lokacija|ura|zivali|druzina|splosno|null",
  "product_topic": "pesto|marmelada|liker|sir|salama|izdelki|null",
  "booking_data": {
    "type": "room|table|null",
    "date": "DD.MM.YYYY ali null",
    "time": "HH:MM ali null",
    "guests": число ali null,
    "name": "string ali null",
    "email": "string ali null",
    "phone": "string ali null"
  },
  "confidence": 0.0-1.0
}

PRAVILA:
1. "is_interrupt" = true če uporabnik vpraša INFO/PRODUCT vprašanje MED aktivnim bookingom
2. Če sporočilo vsebuje OBOJE (npr. "2 gosta, a mate pesto?"), nastavi intent="COMPOSITE"
3. Izvleci booking podatke tudi če so v "interrupt" sporočilu
4. Pri nejasnih sporočilih (npr. samo "ja", "ok") nastavi intent="UNCLEAR"

VRNI SAMO VELJAVEN JSON, BREZ RAZLAGE."""


ANSWER_SYSTEM_PROMPT = """Ti si prijazen asistent turistične kmetije Kmetija Pod Goro.

Odgovori na uporabnikovo vprašanje kratko in prijazno (1-2 stavka).
Če je to interrupt med rezervacijo, na koncu dodaj nadaljevanje rezervacije.

Kontekst kmetije:
- Lokacija: Planica 9, 2313 Fram (Pohorje)
- Telefon: 02 601 54 00, 031 330 113
- Odprto: sobota/nedelja 12:00-20:00
- Sobe: GOZD, RAZGLED, SONCE (vse 2+2)
- Izdelki: čemažev pesto, marmelade, likerji, pohorska bunka
- Živali: konja Malajka in Marsij, zajčki
- Družina: gospodar Marko, babica Marija

Ton: topel, domač, brez pretiranih emojijev."""


def get_client() -> OpenAI:
    """Vrni OpenAI klienta."""
    settings = Settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY ni nastavljen")
    return OpenAI(api_key=settings.openai_api_key)


def classify_intent(
    message: str,
    state: Dict[str, Any],
    history: list[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Klasificiraj intent uporabnikovega sporočila.

    Args:
        message: Uporabnikovo sporočilo
        state: Trenutni booking state (step, type, date, guests, itd.)
        history: Prejšnja sporočila (opcijsko)

    Returns:
        Dict z intent, is_interrupt, booking_data, itd.
    """
    client = get_client()

    # Zgradi kontekst
    context_parts = []

    # Aktivni booking?
    if state.get("step"):
        context_parts.append(f"AKTIVNI BOOKING: type={state.get('type')}, step={state.get('step')}")
        if state.get("date"):
            context_parts.append(f"  - datum: {state.get('date')}")
        if state.get("time"):
            context_parts.append(f"  - ura: {state.get('time')}")
        if state.get("guests"):
            context_parts.append(f"  - gosti: {state.get('guests')}")
    else:
        context_parts.append("NI AKTIVNEGA BOOKINGA")

    # Zgodovina
    if history and len(history) > 0:
        recent = history[-3:]  # Zadnja 3 sporočila
        context_parts.append("ZADNJA SPOROČILA:")
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:100]
            context_parts.append(f"  {role}: {content}")

    context = "\n".join(context_parts)

    user_prompt = f"""KONTEKST:
{context}

UPORABNIKOVO SPOROČILO:
"{message}"

Vrni JSON klasifikacijo:"""

    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Nizka temperatura za konsistentnost
            max_tokens=300,
            response_format={"type": "json_object"}  # Prisili JSON
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        logger.info(f"SmartRouter: '{message}' -> {result.get('intent')} (confidence: {result.get('confidence')})")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"SmartRouter JSON parse error: {e}")
        return {
            "intent": "UNCLEAR",
            "is_interrupt": False,
            "confidence": 0.0,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"SmartRouter error: {e}")
        return {
            "intent": "UNCLEAR",
            "is_interrupt": False,
            "confidence": 0.0,
            "error": str(e)
        }


def generate_smart_response(
    message: str,
    classification: Dict[str, Any],
    state: Dict[str, Any]
) -> str:
    """
    Generiraj odgovor glede na klasifikacijo.

    Če je interrupt, odgovori na vprašanje IN dodaj resume prompt.
    """
    client = get_client()

    intent = classification.get("intent", "UNCLEAR")
    is_interrupt = classification.get("is_interrupt", False)

    # Zgradi prompt za odgovor
    prompt_parts = [f"Uporabnik je rekel: \"{message}\""]

    if is_interrupt and state.get("step"):
        prompt_parts.append(f"\nTo je INTERRUPT med rezervacijo ({state.get('type')}).")
        prompt_parts.append(f"Trenutni korak: {state.get('step')}")
        prompt_parts.append("\nOdgovori na vprašanje, nato nadaljuj z rezervacijo.")
        prompt_parts.append("Format: [odgovor na vprašanje]\\n\\n[nadaljevanje rezervacije]")

        # Dodaj info kaj še manjka
        step = state.get("step", "")
        if "date" in step:
            prompt_parts.append("Naslednje vprašanje: Za kateri datum?")
        elif "time" in step:
            prompt_parts.append("Naslednje vprašanje: Ob kateri uri?")
        elif "guest" in step:
            prompt_parts.append("Naslednje vprašanje: Koliko gostov?")
        elif "name" in step:
            prompt_parts.append("Naslednje vprašanje: Vaše ime?")
        elif "email" in step:
            prompt_parts.append("Naslednje vprašanje: Vaš email?")

    elif intent == "PRODUCT":
        prompt_parts.append("\nTo je vprašanje o IZDELKIH.")
        prompt_parts.append("Odgovori kratko o izdelku in omeni spletno trgovino.")

    elif intent == "INFO":
        topic = classification.get("info_topic", "splosno")
        prompt_parts.append(f"\nTo je INFO vprašanje o: {topic}")

    elif intent == "BOOKING":
        prompt_parts.append("\nTo je BOOKING sporočilo.")
        prompt_parts.append("Ne generiraj odgovora - booking flow bo obdelal.")
        return None  # Naj booking flow obdela

    elif intent == "GREETING":
        return "Pozdravljeni! Kako vam lahko pomagam? Zanima vas rezervacija mize, sobe, ali informacije o kmetiji?"

    elif intent == "GOODBYE":
        return "Hvala za pogovor! Lep pozdrav s Pohorja in se vidimo pri nas! 🏔️"

    prompt = "\n".join(prompt_parts)

    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"SmartRouter generate error: {e}")
        return None


def smart_route(
    message: str,
    state: Dict[str, Any],
    history: list[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Glavna funkcija - klasificiraj in generiraj odgovor.

    Returns:
        {
            "handled": True/False,  # Ali smo obdelali sporočilo
            "response": "...",      # Odgovor za uporabnika
            "intent": "...",        # Detektiran intent
            "booking_data": {...},  # Izvlečeni booking podatki
            "continue_booking": True/False  # Ali naj booking flow nadaljuje
        }
    """
    # 1. Klasificiraj
    classification = classify_intent(message, state, history)

    intent = classification.get("intent", "UNCLEAR")
    is_interrupt = classification.get("is_interrupt", False)
    booking_data = classification.get("booking_data", {})

    result = {
        "handled": False,
        "response": None,
        "intent": intent,
        "booking_data": booking_data,
        "continue_booking": False,
        "classification": classification
    }

    # 2. Če je BOOKING intent (brez interrupta), prepusti booking flowu
    if intent == "BOOKING" and not is_interrupt:
        result["continue_booking"] = True
        return result

    # 3. Če je UNCLEAR med bookingom, prepusti booking flowu (morda je odgovor na vprašanje)
    if intent == "UNCLEAR" and state.get("step"):
        result["continue_booking"] = True
        return result

    # 4. Generiraj odgovor za INFO, PRODUCT, GREETING, GOODBYE, ali INTERRUPT
    response = generate_smart_response(message, classification, state)

    if response:
        result["handled"] = True
        result["response"] = response

        # Če je interrupt, booking flow naj nadaljuje z izvlečenimi podatki
        if is_interrupt:
            result["continue_booking"] = True

    return result
