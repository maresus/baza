import re
import random
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple
import uuid
import threading
import numpy as np

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ChatResponse
from app.services.reservation_service import ReservationService
from app.services.email_service import send_guest_confirmation, send_admin_notification
from app.services.health_center_extensions import (
    validate_appointment_rules,
    format_appointment_summary,
    get_available_time_slots,
    get_service_info,
    format_all_services_summary,
    SERVICES,
    SERVICE_NAME_MAP,
)
from app.rag.rag_engine import rag_engine
from app.rag.knowledge_base import (
    CONTACT,
    generate_llm_answer,
    search_knowledge,
)
from app.core.config import Settings
from app.core.llm_client import get_llm_client
from app.rag.chroma_service import answer_tourist_question, is_tourist_query
from app.services.router_agent import route_message
from app.services.executor_v2 import execute_decision

router = APIRouter(prefix="/chat", tags=["chat"])
USE_ROUTER_V2 = True
USE_FULL_KB_LLM = True
SHORT_MODE = os.getenv("SHORT_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}

# ========== ANTI-LOOP & CACHE MECHANISMS ==========

class ConversationTracker:
    """Track recent questions to detect loops"""
    def __init__(self):
        self.recent_messages: dict[str, list[str]] = {}  # session_id -> [messages]
        self.loop_count: dict[str, int] = {}  # session_id -> count

    def add_message(self, session_id: str, message: str):
        """Add message to tracking"""
        if session_id not in self.recent_messages:
            self.recent_messages[session_id] = []
        self.recent_messages[session_id].append(message.lower().strip())
        # Keep only last 3
        if len(self.recent_messages[session_id]) > 3:
            self.recent_messages[session_id].pop(0)

    def detect_loop(self, session_id: str, message: str) -> bool:
        """Detect if message is repeating (simple token overlap)"""
        if session_id not in self.recent_messages:
            return False

        recent = self.recent_messages.get(session_id, [])
        if len(recent) < 2:
            return False

        # Check token overlap with last 2-3 messages
        msg_tokens = set(message.lower().split())
        for prev_msg in recent[-3:]:
            prev_tokens = set(prev_msg.split())
            if len(msg_tokens & prev_tokens) / len(msg_tokens) > 0.7:  # 70% overlap
                self.loop_count[session_id] = self.loop_count.get(session_id, 0) + 1
                return True

        # Reset loop count if no loop detected
        self.loop_count[session_id] = 0
        return False

    def get_loop_count(self, session_id: str) -> int:
        """Get current loop count"""
        return self.loop_count.get(session_id, 0)

    def reset_loop_count(self, session_id: str):
        """Reset loop counter"""
        self.loop_count[session_id] = 0


class SimpleCache:
    """Simple in-memory cache for LLM responses"""
    def __init__(self, ttl_seconds: int = 86400):  # 24h default
        self.cache: dict[str, tuple[str, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, query: str, context: str = "") -> Optional[str]:
        """Get cached response"""
        key = self._hash_key(query, context)
        if key in self.cache:
            response, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return response
            else:
                del self.cache[key]  # Expired
        return None

    def set(self, query: str, response: str, context: str = ""):
        """Cache response"""
        key = self._hash_key(query, context)
        self.cache[key] = (response, datetime.now())

    def _hash_key(self, query: str, context: str) -> str:
        """Generate cache key"""
        combined = f"{query}:{context}"
        return hashlib.md5(combined.encode()).hexdigest()


# Initialize trackers
conversation_tracker = ConversationTracker()
response_cache = SimpleCache()

# Affirmative keywords
AFFIRMATIVE_KEYWORDS = {
    "da", "ja", "yes", "seveda", "lahko", "ok", "okay",
    "v redu", "sure", "dobro", "prosim", "please", "grem naprej", "nadaljuj"
}

# Greeting keywords
GREETING_KEYWORDS = {"pozdrav", "zdravo", "hej", "hello", "hi", "dober dan", "živjo"}


def is_affirmative(message: str) -> bool:
    """Check if message is an affirmative response"""
    tokens = message.lower().strip().split()
    if len(tokens) <= 2:  # Short response
        return any(word in AFFIRMATIVE_KEYWORDS for word in tokens)
    return False


def is_greeting(message: str) -> bool:
    """Check if message is a greeting"""
    lowered = message.lower()
    return any(greet in lowered for greet in GREETING_KEYWORDS)

# ========== ZDRAVSTVENI CENTER INFO ODGOVORI ==========
INFO_RESPONSES = {
    "pozdrav": """Pozdravljeni! 😊

Sem vaš digitalni pomočnik za naročanje pregledov. Lahko vam pomagam z naročilom na:
- Dermatološki pregled
- Ortopedski pregled
- Okulistični pregled
- Laserski poseg
- Estetski poseg
- Kozmetični salon

Kako vam lahko pomagam?""",

    "kdo_si": """Sem digitalni pomočnik zdravstvenega centra.

Z veseljem odgovorim na vprašanja o naših storitvah, cenah in razpoložljivih terminih.""",

    "kontakt": """📞 Telefon: [Telefonska številka]
📧 Email: [Email naslov]
📍 Lokacija: [Naslov zdravstvenega centra]""",

    "lokacija": """📍 [Naslov zdravstvenega centra]

Za navigacijo vpišite naslov v Google Maps.""",

    "delovni_cas": """Delovni čas:
**Ponedeljek – Petek**: 8:00 – 18:00

Termini so na voljo vsak 30 minut.
Če želite, lahko preverim proste termine za določen datum.""",

    "storitve": """Naše storitve:

🔬 **Dermatologija** (30 min, 25-150 €)
Pregledi kožnih bolezni, laserski in estetski posegi

🦴 **Ortopedija** (30 min, 40-80 €)
Pregledi sklepov, hrbtenice, športne poškodbe

👁️ **Oftalmologija** (30 min, 35-70 €)
Očesni pregledi, predpis očal in kontaktnih leč

⚡ **Laserski posegi** (30 min, 50-200 €)
Odstranjevanje žilic, bradavic, zdravljenje glivic nohtov

💉 **Estetski posegi** (30 min, 80-300 €)
Botox, fillerji, biorevitalizacija kože

💆 **Kozmetični salon** (60 min, 40-100 €)
Profesionalna nega obraza, tretmaji kože

Če želite naročilo, mi povejte kateri pregled vas zanima.""",

    "dermatolog": """**Dermatološki pregled**
Trajanje: 30 minut
Cena: 25-150 € (odvisno od posega)

Storitve:
- Pregledi kožnih bolezni in sprememb
- Lasersko odstranjevanje žilic in bradavic
- Lasersko zdravljenje glivic nohtov
- Estetski posegi na koži

Željte naročilo na dermatološki pregled?""",

    "ortoped": """**Ortopedski pregled**
Trajanje: 30 minut
Cena: 40-80 €

Storitve:
- Pregledi sklepov in hrbtenice
- Športne poškodbe
- Bolečine v kolenih, ramenih, vratu
- Preventivni ortopedski pregledi

Želite naročilo na ortopedski pregled?""",

    "okulist": """**Okulistični pregled**
Trajanje: 30 minut
Cena: 35-70 €

Storitve:
- Pregled vida in očesnega ozadja
- Predpis očal in kontaktnih leč
- Merjenje očesnega pritiska
- Kontrolni pregledi

Želite naročilo na okulistični pregled?""",

    "laserski_poseg": """**Laserski posegi**
Trajanje: 30 minut
Cena: 50-200 € (odvisno od posega)

Posegi:
- Odstranjevanje žilic na nogah
- Odstranjevanje bradavic
- Lasersko zdravljenje glivic nohtov

Želite naročilo za laserski poseg?""",

    "estetski_poseg": """**Estetski posegi**
Trajanje: 30 minut
Cena: 80-300 € (odvisno od posega)

Posegi:
- Botox proti gubam
- Fillerji za volumen
- Biorevitalizacija kože
- Tretmaji s hialuronsko kislino

Želite naročilo za estetski poseg?""",

    "kozmetika": """**Kozmetični salon**
Trajanje: 60 minut
Cena: 40-100 €

Storitve:
- Profesionalna nega obraza
- Globinsko čiščenje kože
- Anti-age tretmaji
- Hidratacija in regeneracija

Želite naročilo v kozmetični salon?""",

    "cene": """**Cenik storitev:**

🔬 Dermatološki pregled: 25-150 €
🦴 Ortopedski pregled: 40-80 €
👁️ Okulistični pregled: 35-70 €
⚡ Laserski posegi: 50-200 €
💉 Estetski posegi: 80-300 €
💆 Kozmetični salon: 40-100 €

Cene se razlikujejo glede na vrsto pregleda/posega.
Za točno ceno nas kontaktirajte ali mi povejte kateri pregled vas zanima.""",

    "placilo": """Načini plačila:
- Gotovina
- Kartica (Mastercard, Visa)
- Bančno nakazilo (za podjetja)

Plačilo poteka po opravljenem pregledu/posegu.""",

    "zdravstvena_kartica": """Za preglede prosim prinesite s seboj:
- Veljavno osebno izkaznico
- Zdravstveno kartico (če imate napotnico)
- Dokumentacijo predhodnih pregledov (če obstaja)

Večina naših storitev je samoplačniških, vendar nekatere lahko krijete preko ZZZS napotnice.""",

    "parkiranje": """Brezplačno parkiranje je na voljo za vse paciente pred zdravstvenim centrom.

Parkirišče je označeno in dostopno.""",

    "prosti_termini": """Za pregled prostih terminov mi prosim povejte:
1. Kateri pregled vas zanima? (dermatolog, ortoped, okulist, ...)
2. Kateri datum? (npr. 15.3.2026)

Preveril bom razpoložljivost.""",
}

# Variante odgovorov
INFO_RESPONSES_VARIANTS = {key: [value] for key, value in INFO_RESPONSES.items()}

# Kritični ključi
BOOKING_RELEVANT_KEYS = {"dermatolog", "ortoped", "okulist", "laserski_poseg", "estetski_poseg", "kozmetika", "storitve", "prosti_termini"}
CRITICAL_INFO_KEYS = {
    "delovni_cas", "kontakt", "cene", "storitve", "prosti_termini",
    "dermatolog", "ortoped", "okulist", "laserski_poseg", "estetski_poseg", "kozmetika"
}

def _send_reservation_emails_async(payload: dict) -> None:
    """Send appointment confirmation emails asynchronously"""
    def _worker() -> None:
        try:
            send_guest_confirmation(payload)
            send_admin_notification(payload)
        except Exception as exc:
            print(f"[EMAIL] Async send failed: {exc}")
    threading.Thread(target=_worker, daemon=True).start()

# Load full knowledge base
FULL_KB_TEXT = ""
try:
    kb_path = Path(__file__).resolve().parents[2] / "knowledge.jsonl"
    if kb_path.exists():
        chunks = []
        for line in kb_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                text = obj.get("text", "")
                if text:
                    chunks.append(text)
            except Exception:
                pass
        FULL_KB_TEXT = "\n\n".join(chunks)
except Exception as e:
    print(f"[KB] Failed to load knowledge base: {e}")

def _blank_appointment_state() -> dict[str, Optional[str | int]]:
    """Blank state for appointment booking"""
    return {
        "step": None,
        "service_type": None,  # dermatolog, ortoped, okulist, ...
        "date": None,
        "time": None,
        "name": None,
        "phone": None,
        "email": None,
        "reason": None,  # Razlog obiska
        "patient_age": None,
        "patient_health_card": None,
        "note": None,
    }

# Session states
appointment_states: dict[str, dict[str, Optional[str | int]]] = {}
conversation_history: list[dict[str, str]] = []
last_interaction: Optional[datetime] = None
chat_session_id: str = str(uuid.uuid4())[:8]

def get_appointment_state(session_id: str) -> dict[str, Optional[str | int]]:
    """Get or create appointment state for session"""
    if session_id not in appointment_states:
        appointment_states[session_id] = _blank_appointment_state()
    return appointment_states[session_id]

def reset_appointment_state(state: dict[str, Optional[str | int]]) -> None:
    """Reset appointment state"""
    state.update(_blank_appointment_state())

INTENT_CLASSIFIER_PROMPT = """Si Intent Classifier za zdravstveni center. Analiziraj SAMO trenutno sporočilo.

STORITVE:
- ortoped: hrbet, koleno, rama, noga, stopalo, roka, gleženj, vrat, sklep
- dermatolog: koža, izpuščaj, akne, mozolj, znamenje, bradavica
- okulist: oči, vid
- kozmetika: obraz, nega obraza
- estetski_poseg: gube, botox, fillerji
- laserski_poseg: žilice, bradavice, glivice

VRNI SAMO JSON (brez markdown):
{"intent": "...", "service": "...", "reason": "..."}

INTENTI:
- "health_advice": uporabnik opisuje simptome/bolečine in potrebuje nasvet
- "booking": uporabnik želi naročiti pregled/termin/naročilo
- "info_services": SAMO splošna vprašanja "kaj nudite" ali "katere storitve imate"
- "info_prices": sprašuje o cenah/ceniku
- "info_contact": sprašuje o lokaciji/kontaktu/naslovu/telefonu
- "info_hours": sprašuje o delovnem času/kdaj ste odprti
- "greeting": pozdrav (zdravo, dober dan, hej)
- "question": SPECIFIČNA vprašanja o storitvah (kdo dela, kako poteka, kakšne izkušnje, kaj vključuje pregled, itd.)

KRITIČNO - RAZLIKUJ MED:
- "info_services" → SAMO "kaj nudite?", "katere storitve imate?", "seznam storitev"
- "question" → VSA specifična vprašanja: "kdo dela kot ortoped?", "kako poteka pregled?", "kaj vključuje?", "kakšna je oprema?", itd.

KRITIČNO - PRAVILA ZA SERVICE:
1. Service vrni SAMO če je storitev EKSPLICITNO omenjena v TRENUTNEM sporočilu
2. Če user reče samo "rad bi se naročil" ali "želim termin" BREZ omembe storitve → service: null
3. NE inferirati storitve iz prejšnjih sporočil ali konteksta!
4. Primeri:
   - "rad bi se naročil na ortopedski pregled" → intent: "booking", service: "ortoped"
   - "rad bi se naročil" → intent: "booking", service: null
   - "kdo dela kot ortoped?" → intent: "question", service: null
   - "kako poteka ortopedski pregled?" → intent: "question", service: null
   - "katere storitve nudite?" → intent: "info_services", service: null
"""

def classify_intent_llm(message: str, history: list = None) -> dict:
    """Use LLM to classify intent - focuses on current message only"""
    from app.core.llm_client import get_llm_client

    prompt = f"""{INTENT_CLASSIFIER_PROMPT}

TRENUTNO SPOROČILO: {message}

JSON:"""

    try:
        client = get_llm_client()
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
            max_output_tokens=100,
            temperature=0.1,
        )

        # Extract response text
        answer = getattr(response, "output_text", None)
        if not answer:
            for block in getattr(response, "output", []) or []:
                for content in getattr(block, "content", []) or []:
                    text = getattr(content, "text", None)
                    if text:
                        answer = text
                        break

        # Parse JSON
        if answer:
            # Clean up response
            answer = answer.strip()
            if answer.startswith("```"):
                answer = answer.split("```")[1]
                if answer.startswith("json"):
                    answer = answer[4:]
            result = json.loads(answer)
            return result

    except Exception as e:
        print(f"[INTENT_LLM] Error: {e}")

    # Fallback
    return {"intent": "other", "service": None, "reason": None}


def _service_mentioned_in_message(message: str, service: str) -> bool:
    """Check if service is explicitly mentioned in the message (word boundary check)"""
    import re
    lowered = message.lower()
    service_keywords = {
        "ortoped": ["ortoped", "ortopedski", "ortopedija"],
        "dermatolog": ["dermatolog", "dermatološki", "dermatologija"],
        "okulist": ["okulist", "okulistični", "oftalmolog", "očesni"],  # Removed "oči" - too short, matches "naročil"
        "kozmetika": ["kozmetik", "kozmetični"],
        "estetski_poseg": ["estetski", "botox", "filer"],
        "laserski_poseg": ["laser", "laserski"],
    }
    keywords = service_keywords.get(service, [])
    # Use word boundary matching to avoid substring issues
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw), lowered):
            return True
    return False


def classify_intent(message: str, history: list = None) -> str:
    """Classify intent using LLM"""
    result = classify_intent_llm(message, history)

    intent = result.get("intent", "other")
    service = result.get("service")

    # Map to internal intent format
    if intent == "booking":
        # KRITIČNO: Samo sprejmi storitev če je dejansko omenjena v sporočilu
        if service and _service_mentioned_in_message(message, service):
            return f"book_{service}"
        return "book_general"
    elif intent == "health_advice":
        return "question"
    elif intent == "question":
        return "question"
    elif intent == "info_services":
        return "info_services"
    elif intent == "info_prices":
        return "info_prices"
    elif intent == "info_contact":
        return "info_contact"
    elif intent == "info_hours":
        return "info_hours"
    elif intent == "greeting":
        return "greeting"
    else:
        return "question"  # Default to LLM for unknown


# Keep for backward compatibility - booking keywords
def _has_booking_keywords(message: str) -> bool:
    lowered = message.lower()
    return any(word in lowered for word in ["naroči", "naročilo", "naroci", "narocilo", "termin", "rezerv"])


# Old rule-based classify_intent kept as fallback
def classify_intent_rules(message: str, history: list = None) -> str:
    """Rule-based fallback for intent classification"""
    lowered = message.lower()

    # Appointment booking intents (with and without diacritics)
    if any(word in lowered for word in ["naroči", "naročilo", "naroci", "narocilo", "termin", "rezerv", "želim", "zelim", "potrebujem"]):
        # Check which service
        for service_key, variations in SERVICE_NAME_MAP.items():
            if any(var in lowered for var in variations):
                return f"book_{service_key}"
        return "book_general"

    # Working hours - check BEFORE availability because "kdaj ste odprti" contains "kdaj"
    if any(word in lowered for word in ["delovni čas", "delovni cas", "odprto", "odprti", "kdaj ste odprti", "do kdaj", "od kdaj"]):
        return "info_hours"

    # Check available slots
    if any(word in lowered for word in ["prost", "razpoložljiv", "razpolozljiv", "kdaj", "termin"]):
        return "check_availability"

    # Service information
    for service_key in SERVICES.keys():
        if service_key in lowered or any(var in lowered for var in SERVICE_NAME_MAP.get(service_key, [])):
            return f"info_{service_key}"

    # General service list
    if any(word in lowered for word in ["storitve", "pregled", "ponudba", "kaj ponujate"]):
        return "info_services"

    # Prices
    if any(word in lowered for word in ["cena", "cene", "cenik", "koliko", "stane"]):
        return "info_prices"

    # Contact / Location
    if any(word in lowered for word in ["kontakt", "telefon", "email", "naslov", "lokacija", "nahaja", "kje ste", "kje se", "naslovom", "pridi", "pridem"]):
        return "info_contact"

    # Greeting (with and without diacritics)
    if any(word in lowered for word in ["pozdravljeni", "živjo", "zivjo", "dober dan", "zdravo", "hej", "halo", "bok"]):
        return "greeting"

    return "question"

def extract_date_from_message(message: str) -> Optional[str]:
    """Extract date from message (DD.MM.YYYY format)"""
    # Try DD.MM.YYYY or D.M.YYYY format
    match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', message)
    if match:
        day, month, year = match.groups()
        return f"{day.zfill(2)}.{month.zfill(2)}.{year}"

    # Try relative dates like "jutri", "danes", "naslednji teden"
    lowered = message.lower()
    today = datetime.now()

    if "danes" in lowered:
        return today.strftime("%d.%m.%Y")
    if "jutri" in lowered:
        return (today + timedelta(days=1)).strftime("%d.%m.%Y")
    if "pojutrišnjem" in lowered:
        return (today + timedelta(days=2)).strftime("%d.%m.%Y")

    return None

def extract_time_from_message(message: str) -> Optional[str]:
    """Extract time from message (HH:MM format)"""
    match = re.search(r'(\d{1,2}):(\d{2})', message)
    if match:
        hour, minute = match.groups()
        return f"{hour.zfill(2)}:{minute}"

    # Try HH format (e.g., "ob 10")
    match = re.search(r'ob\s+(\d{1,2})', message.lower())
    if match:
        hour = match.group(1)
        return f"{hour.zfill(2)}:00"

    return None

def extract_service_type(message: str) -> Optional[str]:
    """Extract service type from message using word boundary matching"""
    import re
    lowered = message.lower()

    # Skip short keywords that cause false positives
    skip_keywords = {"oči", "oci"}  # "oči" matches "naročil"

    for service_key, variations in SERVICE_NAME_MAP.items():
        for var in variations:
            # Skip problematic short keywords
            if var in skip_keywords:
                continue
            # Use word boundary to avoid substring matches
            if re.search(r'\b' + re.escape(var), lowered):
                return service_key

    return None

def handle_appointment_booking(message: str, session_id: str) -> str:
    """Handle multi-step appointment booking conversation"""
    state = get_appointment_state(session_id)
    lowered = message.lower()

    # Check for cancellation
    if any(word in lowered for word in ["prekliči", "prekini", "ne želim", "nazaj"]):
        reset_appointment_state(state)
        return "Naročilo preklicano. Če želite ponovno naročilo, mi samo povejte!"

    # Če je service_type že nastavljen (iz classify_intent) ampak step je None -> preskoči na datum
    if state["service_type"] is not None and state["step"] is None:
        service_info = get_service_info(state["service_type"])
        # Če service_type ni veljaven, ponudi izbiro
        if service_info is None:
            state["service_type"] = None
            return """Na kateri pregled se želite naročiti?

- Dermatološki pregled
- Ortopedski pregled
- Okulistični pregled
- Laserski poseg
- Estetski poseg
- Kozmetični salon"""
        state["step"] = "date"
        return f"""Super! 🩺 Naročilo na **{service_info['name']}**.

📋 Trajanje: {service_info['duration_minutes']} minut
💰 Cena: {service_info['price_range']}

Kateri datum vas zanima? (npr. 15.3.2026)"""

    # Step 1: Service type (select_service or None)
    if state["step"] in (None, "select_service") or state["service_type"] is None:
        service_type = extract_service_type(message)
        if service_type:
            state["service_type"] = service_type
            state["step"] = "date"
            service_info = get_service_info(service_type)
            return f"""Odlično! Naročilo na **{service_info['name']}**.

Trajanje: {service_info['duration_minutes']} minut
Cena: {service_info['price_range']}

Kateri datum vas zanima? (npr. 15.3.2026)"""
        else:
            state["step"] = "select_service"  # Mark that we're waiting for service selection
            return """Na kateri pregled se želite naročiti?

- Dermatološki pregled
- Ortopedski pregled
- Okulistični pregled
- Laserski poseg
- Estetski poseg
- Kozmetični salon"""

    # Step 2: Date
    if state["step"] == "date" or state["date"] is None:
        date_str = extract_date_from_message(message)
        if date_str:
            # Validate date
            valid, error = validate_appointment_rules(
                date_str=date_str,
                time_str="10:00",  # Dummy time for date validation
                service_type=state["service_type"],
                patient_name="",
                patient_phone=""
            )

            if not valid and "datum" in error.lower():
                return f"❌ {error}\n\nProsim izberite drug datum."

            state["date"] = date_str
            state["step"] = "time"

            # Show available slots
            slots = get_available_time_slots(date_str, state["service_type"])
            if not slots:
                return f"""Žal za {date_str} ni prostih terminov.

Prosim izberite drug datum."""

            slots_str = ", ".join(slots[:10])  # Show first 10 slots
            if len(slots) > 10:
                slots_str += f" ... (še {len(slots) - 10} terminov)"

            return f"""Prosti termini za {date_str}:

{slots_str}

Katera ura vam ustreza?"""
        else:
            return "Kateri datum vas zanima? (Prosim v formatu DD.MM.YYYY, npr. 15.03.2026)"

    # Step 3: Time
    if state["step"] == "time" or state["time"] is None:
        time_str = extract_time_from_message(message)
        if time_str:
            # Validate time
            valid, error = validate_appointment_rules(
                date_str=state["date"],
                time_str=time_str,
                service_type=state["service_type"],
                patient_name="",
                patient_phone=""
            )

            if not valid:
                return f"❌ {error}\n\nProsim izberite drug termin."

            state["time"] = time_str
            state["step"] = "name"

            return f"""Termin {state['date']} ob {time_str} je prost! ✅

Kako je vaše ime in priimek?"""
        else:
            return "Prosim povejte uro termina (npr. 10:00 ali ob 10)"

    # Step 4: Name
    if state["step"] == "name" or state["name"] is None:
        # Extract name (assume everything that's not obviously other data is name)
        if len(message.strip()) > 2 and not any(char.isdigit() for char in message[:5]):
            state["name"] = message.strip()
            state["step"] = "phone"
            return "Hvala! Kakšna je vaša telefonska številka?"
        else:
            return "Prosim vnesite vaše ime in priimek."

    # Step 5: Phone
    if state["step"] == "phone" or state["phone"] is None:
        # Extract phone number
        phone = re.sub(r'[^\d+]', '', message)
        if len(phone) >= 8:
            state["phone"] = phone
            state["step"] = "email"
            return "Odlično! Kakšen je vaš email naslov? (za potrditev termina)"
        else:
            return "Prosim vnesite veljavno telefonsko številko."

    # Step 6: Email
    if state["step"] == "email" or state["email"] is None:
        # Validate email
        if "@" in message and "." in message.split("@")[1]:
            state["email"] = message.strip()
            state["step"] = "reason"
            return "Kakšen je razlog vašega obiska? (npr. pregled kožnega znamenja, bolečine v kolenu, ...)"
        else:
            return "Prosim vnesite veljaven email naslov."

    # Step 7: Reason
    if state["step"] == "reason" or state["reason"] is None:
        state["reason"] = message.strip()
        state["step"] = "confirm"

        # Show summary
        summary = format_appointment_summary(
            state["date"],
            state["time"],
            state["service_type"],
            state["name"]
        )

        return f"""{summary}

Razlog obiska: {state['reason']}
Telefon: {state['phone']}
Email: {state['email']}

Ali so podatki pravilni? (DA / NE)"""

    # Step 8: Confirmation
    if state["step"] == "confirm":
        # STRICT CONFIRMATION: use is_affirmative instead of simple keyword match
        if is_affirmative(message):
            # Create appointment
            try:
                rs = ReservationService()
                service_info = get_service_info(state["service_type"])

                res_id = rs.create_reservation(
                    date=state["date"],
                    people=1,
                    reservation_type="table",  # "table" type za kompatibilnost z admin panelom
                    time=state["time"],
                    location=service_info["name"],  # Za admin panel slot picker
                    service_type=state["service_type"].upper(),
                    duration_minutes=service_info["duration_minutes"],
                    name=state["name"],
                    phone=state["phone"],
                    email=state["email"],
                    reason=state["reason"],
                    source="chat",
                )

                # Send confirmation emails
                appointment_data = {
                    "id": res_id,
                    "name": state["name"],
                    "email": state["email"],
                    "phone": state["phone"],
                    "date": state["date"],
                    "time": state["time"],
                    "location": service_info["name"],
                    "service_type": state["service_type"],
                    "service_name": service_info["name"],
                    "duration_minutes": service_info["duration_minutes"],
                    "reason": state["reason"],
                    "reservation_type": "table",
                }
                _send_reservation_emails_async(appointment_data)

                # Save values before reset
                email = state["email"]
                date = state["date"]
                time = state["time"]

                # Reset state
                reset_appointment_state(state)

                return f"""✅ **Naročilo uspešno ustvarjeno!**

Številka naročila: #{res_id}

Potrditev smo poslali na {email}.
Vidimo se {date} ob {time}!

Če imate še kakšna vprašanja, mi jih lahko zastavite."""

            except Exception as e:
                print(f"[BOOKING] Error creating appointment: {e}")
                return f"""❌ Prišlo je do napake pri ustvarjanju naročila.

Prosim kontaktirajte nas na [telefonska številka] ali [email].

Napaka: {str(e)}"""

        elif any(word in lowered for word in ["ne", "no", "popravi"]):
            reset_appointment_state(state)
            return "Podatki razveljavljeni. Začnimo znova - na kateri pregled se želite naročiti?"

        else:
            return "Prosim odgovorite z DA ali NE."

    return "Oprostite, nisem razumel. Lahko ponovite?"

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Main chat endpoint for health center assistant"""
    global conversation_history, last_interaction, chat_session_id

    message = request.message.strip()
    session_id = request.session_id or chat_session_id
    lowered = message.lower()

    # Update last interaction time
    now = datetime.now()
    if last_interaction and (now - last_interaction).total_seconds() > 3600:
        # Reset session after 1 hour of inactivity
        conversation_history = []
        if session_id in appointment_states:
            reset_appointment_state(appointment_states[session_id])
    last_interaction = now

    # ===== ANTI-LOOP DETECTION =====
    conversation_tracker.add_message(session_id, message)
    if conversation_tracker.detect_loop(session_id, message):
        loop_count = conversation_tracker.get_loop_count(session_id)
        if loop_count >= 2:
            # 2nd loop detected -> handoff
            conversation_tracker.reset_loop_count(session_id)
            return ChatResponse(
                reply="Za dodatno pomoč me prosim kontaktirajte:\n📞 [Telefon]\n📧 info@zdravstveni-center.si",
                session_id=session_id
            )
        else:
            # 1st loop detected -> clarification
            return ChatResponse(
                reply="Vidim, da se vrtiva. Prosím, povejte samo:\n- Storitev (npr. ortoped)\n- Datum (npr. 15.2.)\n- Ura (npr. 14:00)",
                session_id=session_id
            )

    # Check if user is in booking flow
    state = get_appointment_state(session_id)

    # ===== GREETING/HELP PRESERVATION =====
    # If booking flow is active, don't reset on greeting
    if state["step"] is not None:
        if is_greeting(message) or is_affirmative(message):
            # Ignore greeting, continue flow
            response_text = handle_appointment_booking(message, session_id)
            return ChatResponse(reply=response_text, session_id=session_id)

        # Normal booking flow
        response_text = handle_appointment_booking(message, session_id)
        return ChatResponse(reply=response_text, session_id=session_id)

    # Classify intent with conversation context
    intent = classify_intent(message, conversation_history)

    # Handle different intents
    if intent == "greeting":
        response_text = INFO_RESPONSES["pozdrav"]

    elif intent == "info_services":
        response_text = INFO_RESPONSES["storitve"]

    elif intent == "info_prices":
        response_text = INFO_RESPONSES["cene"]

    elif intent == "info_contact":
        response_text = INFO_RESPONSES["kontakt"]

    elif intent == "info_hours":
        response_text = INFO_RESPONSES["delovni_cas"]

    elif intent.startswith("info_"):
        service_key = intent.replace("info_", "")
        if service_key in INFO_RESPONSES:
            response_text = INFO_RESPONSES[service_key]
        else:
            response_text = INFO_RESPONSES["storitve"]

    elif intent.startswith("book_"):
        # Start booking flow
        if intent == "book_general":
            # Reset celoten state za novo naročilo
            reset_appointment_state(state)
            response_text = handle_appointment_booking(message, session_id)
        else:
            service_key = intent.replace("book_", "")
            reset_appointment_state(state)
            state["service_type"] = service_key
            response_text = handle_appointment_booking(message, session_id)

    elif intent == "check_availability":
        # Extract date and service
        date_str = extract_date_from_message(message)
        service_type = extract_service_type(message)

        if not date_str:
            response_text = "Za kateri datum želite preveriti proste termine? (npr. 15.3.2026)"
        elif not service_type:
            response_text = f"""Za {date_str} - kateri pregled vas zanima?

- Dermatolog
- Ortoped
- Okulist
- Laserski poseg
- Estetski poseg
- Kozmetika"""
        else:
            slots = get_available_time_slots(date_str, service_type)
            if not slots:
                response_text = f"Žal za {date_str} ni prostih terminov za {service_type}."
            else:
                slots_str = ", ".join(slots[:15])
                if len(slots) > 15:
                    slots_str += f" ... (še {len(slots) - 15} terminov)"
                response_text = f"""Prosti termini za {service_type} na {date_str}:

{slots_str}

Želite naročilo?"""

    else:
        # General question - use RAG/LLM
        try:
            # ===== CACHE CHECK =====
            cached_response = response_cache.get(message)
            if cached_response:
                response_text = cached_response
            else:
                # Try Chroma RAG first
                if is_tourist_query(message):
                    rag_answer = answer_tourist_question(message)
                    response_text = rag_answer
                else:
                    # Use generate_llm_answer which handles context gathering internally
                    response_text = generate_llm_answer(message, history=conversation_history)

                    # ===== CONFIDENCE GATING =====
                    # If response is too short or generic, ask for clarification
                    if not response_text or len(response_text.strip()) < 20:
                        response_text = """Nisem prepričan, da pravilno razumem. Lahko pojasnite:
- Za katero storitev vas zanima? (dermatolog / ortoped / okulist / ...)
- Za kateri datum?

Ali lahko zastavite vprašanje drugače?"""
                    else:
                        # ===== CACHE RESPONSE =====
                        response_cache.set(message, response_text)

        except Exception as e:
            print(f"[RAG] Error: {e}")
            response_text = """Lahko vam pomagam z:
- Naročilom na pregled
- Informacijami o storitvah
- Cenami
- Prostimi termini

Kaj vas zanima?"""

    # Add to conversation history
    conversation_history.append({"role": "user", "content": message})
    conversation_history.append({"role": "assistant", "content": response_text})

    # Keep only last 20 messages
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]

    return ChatResponse(reply=response_text, session_id=session_id)
