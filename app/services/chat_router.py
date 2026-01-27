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
from app.services.chat_history_service import get_chat_history_service
from app.services import knowledge_base as kb_module

router = APIRouter(prefix="/chat", tags=["chat"])
USE_ROUTER_V2 = True
USE_FULL_KB_LLM = True
SHORT_MODE = os.getenv("SHORT_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}

# ========== ANTI-LOOP & CACHE MECHANISMS ==========

# Slovenian stop words - ignore these in loop detection
STOP_WORDS = {
    "je", "in", "za", "na", "se", "so", "ali", "kako", "kdaj", "kje", "kaj", "katere",
    "kateri", "kakšen", "kakšna", "ima", "imate", "imajo", "bi", "bo", "bom", "boste",
    "ste", "sem", "smo", "si", "lahko", "tudi", "mi", "te", "me", "ga", "jo", "jim",
    "iz", "do", "pri", "od", "po", "ta", "te", "to", "ta", "ti", "teh", "tem",
    "a", "ali", "ampak", "vendar", "ker", "če", "ko", "da", "ki"
}

class ConversationTracker:
    """Track recent questions to detect loops with stop word filtering"""
    def __init__(self):
        self.recent_messages: dict[str, list[str]] = {}  # session_id -> [messages]
        self.loop_count: dict[str, int] = {}  # session_id -> count

    def _tokenize_meaningful(self, message: str) -> set[str]:
        """Extract meaningful tokens (remove stop words and punctuation)"""
        # Remove punctuation and lowercase
        cleaned = re.sub(r'[^\w\s]', '', message.lower())
        tokens = cleaned.split()
        # Filter out stop words and very short tokens
        meaningful = {t for t in tokens if len(t) > 2 and t not in STOP_WORDS}
        return meaningful

    def add_message(self, session_id: str, message: str):
        """Add message to tracking"""
        if session_id not in self.recent_messages:
            self.recent_messages[session_id] = []
        self.recent_messages[session_id].append(message.lower().strip())
        # Keep only last 3
        if len(self.recent_messages[session_id]) > 3:
            self.recent_messages[session_id].pop(0)

    def detect_loop(self, session_id: str, message: str) -> bool:
        """Detect if message is repeating (improved with stop word filtering)"""
        if session_id not in self.recent_messages:
            return False

        recent = self.recent_messages.get(session_id, [])
        if len(recent) < 2:
            return False

        # Get meaningful tokens from current message
        msg_tokens = self._tokenize_meaningful(message)

        # Need at least 2 meaningful tokens to check
        if len(msg_tokens) < 2:
            return False

        # Check similarity with last 2-3 messages
        for prev_msg in recent[-3:]:
            prev_tokens = self._tokenize_meaningful(prev_msg)

            if len(prev_tokens) < 2:
                continue

            # Calculate overlap
            overlap = msg_tokens & prev_tokens
            overlap_ratio = len(overlap) / len(msg_tokens)

            # STRICT: Need 85%+ overlap AND at least 2 shared tokens
            if overlap_ratio > 0.85 and len(overlap) >= 2:
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

# Chat history service (for persistent storage)
def save_chat_message(
    session_id: str,
    role: str,
    content: str,
    intent: Optional[str] = None,
    service_mentioned: Optional[str] = None,
    booking_step: Optional[str] = None,
    response_cached: bool = False,
    metadata: Optional[dict] = None
):
    """
    Save chat message to persistent storage (non-blocking)

    Args:
        session_id: Session ID
        role: "user" or "assistant"
        content: Message content
        intent: Classified intent
        service_mentioned: Service mentioned
        booking_step: Current booking step
        response_cached: Whether response was cached
        metadata: Additional metadata (e.g., confidence scores)
    """
    try:
        history_service = get_chat_history_service()
        history_service.save_message(
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            service_mentioned=service_mentioned,
            booking_step=booking_step,
            response_cached=response_cached,
            metadata=metadata
        )
    except Exception as e:
        # Non-blocking - don't fail request if storage fails
        print(f"[CHAT_HISTORY] Failed to save message: {e}")

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

Sem vaš digitalni pomočnik in lahko vas **takoj naročim na pregled**!

Na voljo imam termine za:
- Dermatološki pregled
- Ortopedski pregled
- Okulistični pregled
- Laserski poseg
- Estetski poseg
- Kozmetični salon

**Začnimo z naročilom** - kateri pregled vas zanima?""",

    "kdo_si": """Sem digitalni pomočnik zdravstvenega centra.

Z veseljem odgovorim na vprašanja o naših storitvah, cenah in razpoložljivih terminih.""",

    "narocanje": """**Naročanje poteka zelo enostavno - TUKAJ, z menoj!** 🎯

✅ **Kako se naročite:**
1. Poveste mi, kateri pregled vas zanima (dermatolog, ortoped, okulist...)
2. Izberete želeni datum
3. Izberete ustrezen termin
4. Podate svoje podatke (ime, email, telefon)
5. Potrдите naročilo ✅

**To je to!** Celoten postopek traja manj kot 2 minuti.

🚀 **Začnimo ZDAJ** - kateri pregled vas zanima?""",

    "kontakt": """📍 **Naslov**:
Zdravstveni center Ljubljana
Zdraviliška ulica 12
1000 Ljubljana

🕒 **Delovni čas**:
   Pon-Pet: 8:00 - 18:00
   Sobota: 9:00 - 13:00 (samo nujni primeri)

🚗 **Parking**: Brezplačen parking pred objektom
🚌 **Javni prevoz**: Avtobusne linije 6, 11, 20 (postaja "Zdravstveni center")

📞 **Telefon**: 01 234 56 78
📧 **Email**: info@zdravstveni-center.si

💬 **Naročanje terminov**: Lahko se naročite **TUKAJ, z menoj** - samo povejte kateri pregled vas zanima!""",

    "lokacija": """📍 **Zdravstveni center Ljubljana**

**Naslov**:
Zdraviliška ulica 12
1000 Ljubljana

**Kako do nas**:
🚗 Z avtomobilom: Sledite smeri "Center" → Izvoz "Zdravstveni center"
   Brezplačen parking pred objektom za paciente

🚌 Z javnim prevozom:
   - Avtobusne linije: 6, 11, 20
   - Postaja: "Zdravstveni center" (100m od objekta)
   - LPP mestni avtobus

🚶 Peš iz centra: približno 15 minut hoje

📍 Google Maps: Poiščite "Zdravstveni center Ljubljana, Zdraviliška 12"

💬 **Naročite se TUKAJ** - preverim lahko proste termine za vas!""",

    "delovni_cas": """🕒 **Delovni čas**:

**Ponedeljek – Petek**: 8:00 – 18:00
**Sobota**: 9:00 – 13:00 (samo nujni primeri)
**Nedelja in prazniki**: Zaprto

📅 **Termini**:
- Pregledi so na voljo vsak 30 minut
- Priporočamo naročanje vsaj 2 dni vnaprej
- Nujne primere obravnavamo isti dan

💬 **Naročite se ZDAJ** - povejte mi datum in preverim proste termine za vas!

ℹ️ Za druga vprašanja: 01 234 56 78 ali info@zdravstveni-center.si""",

    "storitve": """**Naše storitve** - na voljo za takojšnje naročanje:

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

🎯 **Naročite se TAKOJ** - samo povejte kateri pregled vas zanima in začnimo!""",

    "dermatolog": """**Dermatološki pregled**
Trajanje: 30 minut
Cena: 25-150 € (odvisno od posega)

Storitve:
- Pregledi kožnih bolezni in sprememb
- Lasersko odstranjevanje žilic in bradavic
- Lasersko zdravljenje glivic nohtov
- Estetski posegi na koži

🎯 **Naročite se ZDAJ** - povejte mi želeni datum!""",

    "ortoped": """**Ortopedski pregled**
Trajanje: 30 minut
Cena: 40-80 €

Storitve:
- Pregledi sklepov in hrbtenice
- Športne poškodbe
- Bolečine v kolenih, ramenih, vratu
- Preventivni ortopedski pregledi

🎯 **Naročite se ZDAJ** - povejte mi želeni datum!""",

    "okulist": """**Okulistični pregled**
Trajanje: 30 minut
Cena: 35-70 €

Storitve:
- Pregled vida in očesnega ozadja
- Predpis očal in kontaktnih leč
- Merjenje očesnega pritiska
- Kontrolni pregledi

🎯 **Naročite se ZDAJ** - povejte mi želeni datum!""",

    "laserski_poseg": """**Laserski posegi**
Trajanje: 30 minut
Cena: 50-200 € (odvisno od posega)

Posegi:
- Odstranjevanje žilic na nogah
- Odstranjevanje bradavic
- Lasersko zdravljenje glivic nohtov

🎯 **Naročite se ZDAJ** - povejte mi želeni datum!""",

    "estetski_poseg": """**Estetski posegi**
Trajanje: 30 minut
Cena: 80-300 € (odvisno od posega)

Posegi:
- Botox proti gubam
- Fillerji za volumen
- Biorevitalizacija kože
- Tretmaji s hialuronsko kislino

🎯 **Naročite se ZDAJ** - povejte mi želeni datum!""",

    "kozmetika": """**Kozmetični salon**
Trajanje: 60 minut
Cena: 40-100 €

Storitve:
- Profesionalna nega obraza
- Globinsko čiščenje kože
- Anti-age tretmaji
- Hidratacija in regeneracija

🎯 **Naročite se ZDAJ** - povejte mi želeni datum!""",

    "cene": """**Cenik storitev:**

🔬 Dermatološki pregled: 25-150 €
🦴 Ortopedski pregled: 40-80 €
👁️ Okulistični pregled: 35-70 €
⚡ Laserski posegi: 50-200 €
💉 Estetski posegi: 80-300 €
💆 Kozmetični salon: 40-100 €

Cene se razlikujejo glede na vrsto pregleda/posega.

🎯 **Povejte mi kateri pregled vas zanima** in vas takoj naročim!""",

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

    "parkiranje": """🚗 **Parkiranje za paciente**:

✅ Brezplačno parkiranje pred zdravstvenim centrom
✅ 50 parkirnih mest
✅ Parkirišče je označeno in dostopno
✅ Prostor za invalide

**Lokacija**: Zdraviliška ulica 12, 1000 Ljubljana

Za navigacijo uporabite Google Maps: "Zdravstveni center Ljubljana".""",

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

# ===== HYBRID KNOWLEDGE BASE INITIALIZATION =====
# Initialize knowledge base with INFO_RESPONSES using hybrid retrieval (BM25 + OpenAI embeddings)
# This runs once at module import time
_kb_initialized = False

def _ensure_kb_initialized():
    """Lazy initialization of knowledge base to avoid startup delays"""
    global _kb_initialized
    if not _kb_initialized:
        try:
            print("[KB] Initializing hybrid knowledge base with INFO_RESPONSES...")
            kb_module.initialize_knowledge_base(
                documents=INFO_RESPONSES,
                alpha=0.5,  # Equal weight to BM25 and vector search
                use_reranker=True  # Enable cross-encoder re-ranking
            )
            _kb_initialized = True
            print("[KB] Hybrid knowledge base initialized successfully!")
        except Exception as e:
            print(f"[KB] Failed to initialize knowledge base: {e}")
            print("[KB] Will fall back to direct INFO_RESPONSES lookup")

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
        "waiting_resume_confirmation": False,  # Flag for OFF-TOPIC pause
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
- "info_narocanje": sprašuje KAJ JE/KAKO POTEKA proces naročanja ("kako se naročim?", "kako poteka naročanje?", "kako rezerviram?")
- "info_services": SAMO splošna vprašanja "kaj nudite" ali "katere storitve imate"
- "info_prices": sprašuje o cenah/ceniku
- "info_contact": sprašuje o lokaciji/kontaktu/naslovu/telefonu
- "info_hours": sprašuje o delovnem času/kdaj ste odprti
- "greeting": pozdrav (zdravo, dober dan, hej)
- "question": SPECIFIČNA vprašanja o storitvah (kdo dela, kakšne izkušnje, kaj vključuje pregled, kakšna je oprema, itd.)

KRITIČNO - RAZLIKUJ MED:
- "info_services" → SAMO "kaj nudite?", "katere storitve imate?", "seznam storitev"
- "info_narocanje" → "kako poteka naročanje?", "kako se naročim?", "kako rezerviram termin?"
- "question" → Specifična vprašanja o storitvah: "kdo dela kot ortoped?", "kaj vključuje pregled?", "kakšna je oprema?", itd.

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
    elif intent == "info_narocanje":
        return "info_narocanje"
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
    if any(word in lowered for word in ["kontakt", "telefon", "email", "naslov", "lokacija", "nahaja", "kje ste", "kje se", "naslovom", "pridi", "pridem", "parkir", "parking", "parkiri"]):
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
    """Extract time from message (HH:MM, HH-MM, or HHMM format)"""
    # Try HH:MM format
    match = re.search(r'(\d{1,2}):(\d{2})', message)
    if match:
        hour, minute = match.groups()
        return f"{hour.zfill(2)}:{minute}"

    # Try HH.MM format (e.g., "15.00")
    match = re.search(r'(\d{1,2})\.(\d{2})', message)
    if match:
        hour, minute = match.groups()
        return f"{hour.zfill(2)}:{minute}"

    # Try HH-MM format (e.g., "15-00")
    match = re.search(r'(\d{1,2})-(\d{2})', message)
    if match:
        hour, minute = match.groups()
        return f"{hour.zfill(2)}:{minute}"

    # Try HHMM format without separator (e.g., "1500")
    match = re.search(r'\b(\d{3,4})\b', message)
    if match:
        time_str = match.group(1)
        if len(time_str) == 4:
            hour, minute = time_str[:2], time_str[2:]
            return f"{hour}:{minute}"
        elif len(time_str) == 3:
            hour, minute = time_str[0], time_str[1:]
            return f"{hour.zfill(2)}:{minute}"

    # Try HH format (e.g., "ob 10")
    match = re.search(r'ob\s+(\d{1,2})', message.lower())
    if match:
        hour = match.group(1)
        return f"{hour.zfill(2)}:00"

    return None


def is_likely_full_name(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 3 or "?" in stripped:
        return False
    lowered = stripped.lower()
    blocked_tokens = [
        "koliko",
        "stane",
        "cena",
        "cenik",
        "parking",
        "park",
        "kako",
        "kje",
        "kontakt",
        "ura",
        "termin",
        "pregled",
        "storitev",
        "delate",
        "sobota",
        "nedelja",
    ]
    if any(token in lowered for token in blocked_tokens):
        return False
    if any(char.isdigit() for char in stripped):
        return False
    parts = [p for p in stripped.split() if p]
    return len(parts) >= 2


def _short_contact_info() -> str:
    return (
        "🚗 Parking: brezplačen pred objektom\n"
        "📞 Telefon: 01 234 56 78\n"
        "📧 Email: info@zdravstveni-center.si"
    )


def _service_price_info(service_type: Optional[str]) -> str:
    info = get_service_info(service_type or "")
    if not info:
        return INFO_RESPONSES["cene"]
    return f"💰 {info['name']}: {info['price_range']} · {info['duration_minutes']} min"


def _analyze_query_type(query: str) -> dict:
    """
    Analyze query to determine type and required confidence level

    Returns dict with:
        - type: "booking", "price", "contact", "info", "general"
        - required_confidence: minimum confidence threshold (0-1)
        - priority: "critical", "high", "medium", "low"
    """
    query_lower = query.lower()

    # Booking queries (critical - must be accurate)
    booking_keywords = ["naroč", "termin", "rezerv", "prostem", "prosta", "prosth"]
    if any(kw in query_lower for kw in booking_keywords):
        return {"type": "booking", "required_confidence": 0.7, "priority": "critical"}

    # Price queries (high priority - must be accurate)
    price_keywords = ["cena", "cene", "ceník", "stane", "stroški", "plačil", "koliko"]
    if any(kw in query_lower for kw in price_keywords):
        return {"type": "price", "required_confidence": 0.65, "priority": "high"}

    # Contact/location queries (medium priority)
    contact_keywords = ["naslov", "lokacij", "kako do", "kje", "parking", "telefon", "email", "kontakt"]
    if any(kw in query_lower for kw in contact_keywords):
        return {"type": "contact", "required_confidence": 0.5, "priority": "medium"}

    # Service info queries (medium priority)
    service_keywords = ["dermatolog", "ortoped", "okulist", "lasersk", "estetsk", "kozmetik", "storitev"]
    if any(kw in query_lower for kw in service_keywords):
        return {"type": "info", "required_confidence": 0.55, "priority": "medium"}

    # General queries (lower threshold)
    return {"type": "general", "required_confidence": 0.45, "priority": "low"}


def answer_with_hybrid_kb(query: str, history: list = None, session_id: str = None) -> str:
    """
    Answer question using hybrid knowledge base with enhanced confidence gating

    Uses multi-signal confidence scoring:
    - Search score (hybrid BM25 + vector)
    - Score gap between top results
    - BM25/vector agreement
    - Query type analysis
    - Response validation

    Args:
        query: User question
        history: Conversation history (optional, for future context-aware answers)

    Returns:
        Answer text with confidence-based response strategy
    """
    # Ensure KB is initialized
    _ensure_kb_initialized()

    if not _kb_initialized:
        # Fallback to old method if KB initialization failed
        return generate_llm_answer(query, history=history or [])

    try:
        # ===== QUERY ANALYSIS =====
        query_analysis = _analyze_query_type(query)
        required_confidence = query_analysis["required_confidence"]

        print(f"[CONFIDENCE] Query type: {query_analysis['type']} (priority: {query_analysis['priority']})")
        print(f"[CONFIDENCE] Required confidence threshold: {required_confidence:.2f}")

        # Search knowledge base with hybrid retrieval
        results = kb_module.search_knowledge_base(
            query=query,
            top_k=3,
            min_score=0.0  # Get all results, we'll filter by confidence
        )

        # Store confidence metadata in session state for analytics
        if session_id and results:
            state = conversation_state.get(session_id, {})
            confidence_meta = results[0].get("confidence_metadata", {}) if results else {}
            state["last_confidence_metadata"] = {
                "query_type": query_analysis["type"],
                "query_priority": query_analysis["priority"],
                "required_confidence": required_confidence,
                "overall_confidence": confidence_meta.get("confidence", 0),
                "top_score": confidence_meta.get("top_score", 0),
                "score_gap_ratio": confidence_meta.get("score_gap_ratio", 0),
                "bm25_vector_agreement": confidence_meta.get("bm25_vector_agreement", 0),
                "reranker_used": confidence_meta.get("reranker_used", False),
                "num_results": len(results)
            }

        if not results:
            # No results found - ask for clarification
            return """Nisem prepričan, da pravilno razumem. Lahko pojasnite:
- Za katero storitev vas zanima? (dermatolog / ortoped / okulist / ...)
- Za kateri datum?

Ali lahko zastavite vprašanje drugače?"""

        # Get top result and confidence metadata
        top_result = results[0]
        top_score = top_result["score"]
        confidence_meta = top_result.get("confidence_metadata", {})
        overall_confidence = confidence_meta.get("confidence", top_score)

        # Debug logging
        print(f"[KB_SEARCH] Query: {query[:50]}...")
        print(f"[KB_SEARCH] Top result: {top_result['doc_id']} (score: {top_score:.3f})")
        print(f"[KB_SEARCH] BM25: {top_result['bm25_score']:.3f}, Vector: {top_result['vector_score']:.3f}")

        if confidence_meta:
            print(f"[CONFIDENCE] Overall confidence: {overall_confidence:.3f}")
            print(f"[CONFIDENCE] Score gap ratio: {confidence_meta.get('score_gap_ratio', 0):.3f}")
            print(f"[CONFIDENCE] BM25/Vector agreement: {confidence_meta.get('bm25_vector_agreement', 0):.3f}")
            print(f"[CONFIDENCE] Re-ranker used: {confidence_meta.get('reranker_used', False)}")

        # ===== ENHANCED CONFIDENCE GATING =====

        # Strategy 1: Very high confidence + clear winner
        # Return result directly if confidence is strong and there's clear winner
        score_gap_ratio = confidence_meta.get("score_gap_ratio", 0)
        if overall_confidence >= 0.75 and score_gap_ratio > 0.3:
            print(f"[CONFIDENCE] ✓ Very high confidence + clear winner - returning directly")
            return top_result["text"]

        # Strategy 2: High confidence for query type
        # Return result if it meets the query-specific threshold
        if overall_confidence >= required_confidence:
            # Additional validation for critical queries
            if query_analysis["priority"] == "critical":
                # For critical queries, also check agreement between methods
                agreement = confidence_meta.get("bm25_vector_agreement", 0)
                if agreement < 0.5:
                    print(f"[CONFIDENCE] ⚠ Critical query but low method agreement - using LLM")
                    # Fall through to LLM strategy
                else:
                    print(f"[CONFIDENCE] ✓ High confidence for critical query - returning directly")
                    return top_result["text"]
            else:
                print(f"[CONFIDENCE] ✓ Meets query-type threshold - returning directly")
                return top_result["text"]

        # Strategy 3: Medium confidence - Use LLM with context
        # If confidence is moderate, use LLM to synthesize answer from retrieved docs
        if overall_confidence >= 0.35:
            print(f"[CONFIDENCE] ~ Medium confidence - using LLM with retrieved context")

            # Gather context from top 2-3 results depending on confidence
            num_context_docs = 2 if overall_confidence >= 0.45 else 3
            context_docs = [r["text"] for r in results[:num_context_docs]]
            context = "\n\n---\n\n".join(context_docs)

            # Generate answer using LLM with context
            llm_client = get_llm_client()

            system_prompt = """Si digitalni pomočnik zdravstvenega centra.
Odgovarjaj na podlagi danega konteksta. Če kontekst ne vsebuje informacij za odgovor, reci to prijazno.
Odgovori naj bodo kratki in jedrnati."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""Kontekst:
{context}

Vprašanje: {query}

Odgovori na slovenščini na podlagi konteksta zgoraj."""}
            ]

            response = llm_client.chat(messages, temperature=0.3)
            answer = response.strip()

            # Validate LLM response quality
            if len(answer) < 20:
                print(f"[CONFIDENCE] ⚠ LLM response too short - returning top result instead")
                return top_result["text"]

            # Check if LLM declined to answer (common phrases)
            decline_phrases = ["ne vem", "nimam informacij", "ne najdem", "ne morem", "žal ne"]
            if any(phrase in answer.lower() for phrase in decline_phrases):
                print(f"[CONFIDENCE] ⚠ LLM declined - returning top result instead")
                return top_result["text"]

            return answer

        # Strategy 4: Low confidence - Ask for clarification
        # If confidence is too low, ask user to clarify their question
        print(f"[CONFIDENCE] ✗ Low confidence ({overall_confidence:.3f}) - asking for clarification")

        # Provide contextual clarification based on query type
        if query_analysis["type"] == "booking":
            return """Za naročanje potrebujem naslednje podatke:
- Kateri pregled vas zanima? (dermatolog, ortoped, okulist, laserski poseg, estetski poseg, kozmetika)
- Kateri datum vas zanima?

Prosim, navedite obe informaciji."""

        elif query_analysis["type"] == "price":
            return """Za točne cene mi prosim povejte katera storitev vas zanima:

🔬 Dermatologija
🦴 Ortopedija
👁️ Oftalmologija
⚡ Laserski posegi
💉 Estetski posegi
💆 Kozmetični salon

Katero storitev želite?"""

        else:
            # General clarification
            return """Lahko vam pomagam z:
- Naročilom na pregled (dermatolog, ortoped, okulist...)
- Informacijami o storitvah in cenah
- Delovnim časom in lokacijo
- Prostimi termini

Kaj vas zanima?"""

    except Exception as e:
        print(f"[KB_SEARCH] Error: {e}")
        import traceback
        traceback.print_exc()

        # Fallback to old method
        return generate_llm_answer(query, history=history or [])


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

def get_resume_prompt(state: dict) -> str:
    """Get prompt for current booking step (used when resuming after OFF-TOPIC)"""
    step = state.get("step")

    if step == "date":
        return "Kateri datum vas zanima? (npr. 15.3.2026)"
    elif step == "time":
        return "Katero uro si želite? (npr. 14:00)"
    elif step == "name":
        return "Prosim vnesite vaše ime in priimek."
    elif step == "phone":
        return "Odlično! Kakšna je vaša telefonska številka?"
    elif step == "email":
        return "Kakšen je vaš email naslov? (za potrditev termina)"
    elif step == "reason":
        return "Kakšen je razlog vašega obiska? (npr. pregled kožnega znamenja, bolečine v kolenu, ...)"
    elif step == "confirm":
        service_info = get_service_info(state.get("service_type", "dermatolog"))
        summary = format_appointment_summary(
            state.get("date", ""),
            state.get("time", ""),
            state.get("service_type", ""),
            state.get("name", "")
        )
        return f"""{summary}

Razlog obiska: {state.get('reason', '-')}
Telefon: {state.get('phone', '-')}
Email: {state.get('email', '-')}

Ali so podatki pravilni? (DA / NE)"""
    else:
        # Default: ask for service
        return """Na kateri pregled se želite naročiti?

- Dermatološki pregled
- Ortopedski pregled
- Okulistični pregled
- Laserski poseg
- Estetski poseg
- Kozmetični salon"""


def handle_appointment_booking(message: str, session_id: str) -> str:
    """Handle multi-step appointment booking conversation"""
    state = get_appointment_state(session_id)
    lowered = message.lower()

    # Check for cancellation
    if any(word in lowered for word in ["prekliči", "prekini", "ne želim", "nazaj"]):
        reset_appointment_state(state)
        conversation_tracker.reset_loop_count(session_id)  # Reset loop detection on cancel
        return "V redu, rezervacije ne bom nadaljeval. Kaj vas še zanima?"

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
        if is_likely_full_name(message):
            state["name"] = message.strip()
            state["step"] = "phone"
            return "Hvala! Kakšna je vaša telefonska številka?"
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
    # Check for loop BEFORE adding message (to avoid comparing with itself)
    if conversation_tracker.detect_loop(session_id, message):
        loop_count = conversation_tracker.get_loop_count(session_id)
        conversation_tracker.add_message(session_id, message)  # Track even if loop

        if loop_count >= 2:
            # 2nd loop detected -> reset and offer restart
            conversation_tracker.reset_loop_count(session_id)
            return ChatResponse(
                reply="""Mislim, da je prišlo do nesporazuma. Začniva znova! 🔄

**Kako vam lahko pomagam danes?**
- 🗓️ Naročilo na pregled (povejte kateri pregled + datum)
- ℹ️ Informacije o storitvah in cenah
- 📍 Lokacija in kontakt

Za dodatno pomoč pokličite: 📞 01 234 56 78""",
                session_id=session_id
            )
        else:
            # 1st loop detected -> clarification
            return ChatResponse(
                reply="Opazil sem, da ponavljate vprašanje. Pomagam vam z veseljem! Prosim povejte konkretno:\n- Kateri pregled vas zanima?\n- Želeni datum in ura?",
                session_id=session_id
            )

    # No loop detected, add message to tracking
    conversation_tracker.add_message(session_id, message)

    # Check if user is in booking flow
    state = get_appointment_state(session_id)

    # ===== OFF-TOPIC DETECTION IN BOOKING FLOW =====
    if state["step"] is not None:
        # Check if waiting for resume confirmation
        if state.get("waiting_resume_confirmation"):
            if is_affirmative(message):
                # User wants to continue booking
                state["waiting_resume_confirmation"] = False

                # Use variation of prompt to avoid repetition
                step = state.get("step")
                if step == "date":
                    prompt = "Odlično, nadaljujmo! 😊 Prosim vnesite datum (npr. 15.3.2026)."
                elif step == "time":
                    prompt = "Odlično, nadaljujmo! 😊 Prosim povejte uro (npr. 14:00)."
                elif step == "name":
                    prompt = "Odlično, nadaljujmo! 😊 Prosim vnesite vaše ime in priimek."
                elif step == "phone":
                    prompt = "Odlično, nadaljujmo! 😊 Prosim vnesite vašo telefonsko številko."
                elif step == "email":
                    prompt = "Odlično, nadaljujmo! 😊 Prosim vnesite vaš email naslov."
                elif step == "reason":
                    prompt = "Odlično, nadaljujmo! 😊 Prosim opišite razlog vašega obiska."
                else:
                    prompt = "Odlično, nadaljujmo! 😊"

                return ChatResponse(
                    reply=prompt,
                    session_id=session_id
                )
            else:
                # User doesn't want to continue - reset booking
                reset_appointment_state(state)
                conversation_tracker.reset_loop_count(session_id)  # Reset loop detection on cancel
                return ChatResponse(
                    reply="V redu, naročilo je preklicano. Če potrebujete pomoč, sem tukaj!",
                    session_id=session_id
                )

        # ===== FIRST: Try to extract expected input based on current step =====
        # This prevents valid input from being misclassified as OFF-TOPIC
        current_step = state.get("step")
        input_matches_expected_format = False

        if current_step == "date":
            # Check if message looks like a date
            date_str = extract_date_from_message(message)
            if date_str:
                input_matches_expected_format = True
        elif current_step == "time":
            # Check if message looks like a time
            time_str = extract_time_from_message(message)
            if time_str:
                input_matches_expected_format = True
        elif current_step == "select_service":
            # Check if message mentions a service
            service_type = detect_service_from_message(message)
            if service_type:
                input_matches_expected_format = True
        elif current_step == "name":
            # Check if message looks like a name (2+ words or 3+ chars without digits in first part)
            if is_likely_full_name(message):
                input_matches_expected_format = True
        elif current_step == "phone":
            # Check if message contains mostly digits
            digits_only = re.sub(r'[^\d]', '', message)
            if len(digits_only) >= 8:
                input_matches_expected_format = True
        elif current_step == "email":
            # Check if message looks like email
            if "@" in message and "." in message.split("@")[-1]:
                input_matches_expected_format = True
        elif current_step == "reason":
            # Check if message is descriptive text (not a question about pricing/services)
            if len(message.strip()) > 5 and "?" not in message:
                input_matches_expected_format = True

        # If input matches expected format, skip OFF-TOPIC detection
        if input_matches_expected_format:
            response_text = handle_appointment_booking(message, session_id)
            return ChatResponse(reply=response_text, session_id=session_id)

        # ===== SECOND: Check OFF-TOPIC only if input didn't match expected format =====
        # Detect if message is OFF-TOPIC (info question during booking)
        # Now enabled for ALL steps (not just date/time)
        intent = classify_intent_rules(message, conversation_history)
        lowered_message = message.lower()
        is_question_like = "?" in message or any(token in lowered_message for token in ["boli", "boleč", "bolec"])

        # OFF-TOPIC intents: info queries that are not part of booking flow
        OFF_TOPIC_INTENTS = ["info_services", "info_prices", "info_contact", "info_hours", "info_location"]

        if intent in OFF_TOPIC_INTENTS or intent.startswith("info_") or (intent == "question" and is_question_like):
            # Handle OFF-TOPIC question
            if intent == "info_services":
                if state.get("service_type"):
                    info = get_service_info(state["service_type"])
                    info_response = f"{info['name']}: {info['description']}" if info else INFO_RESPONSES["storitve"]
                else:
                    info_response = INFO_RESPONSES["storitve"]
            elif intent == "info_prices":
                info_response = _service_price_info(state.get("service_type"))
            elif intent == "info_contact":
                info_response = _short_contact_info()
            elif intent == "info_hours":
                info_response = INFO_RESPONSES["delovni_cas"]
            elif intent == "question" and is_question_like:
                info_response = (
                    "Za medicinska vprašanja (npr. bolečina) ne morem dati zanesljivega odgovora. "
                    "Za podrobnosti pokličite 01 234 56 78."
                )
            else:
                info_response = INFO_RESPONSES.get(intent.replace("info_", ""), "Prosim, pojasnite vprašanje.")

            # Check if booking really started (service selected)
            if state.get("service_type") is None:
                # Booking hasn't really started - just answer, no resume prompt
                return ChatResponse(
                    reply=info_response,
                    session_id=session_id
                )

            # Booking is active - build resume prompt
            service_name = get_service_info(state["service_type"])["name"]
            date_str = state.get("date", "")
            time_str = state.get("time", "")

            resume_prompt = "\n\nAli želite nadaljevati z naročilom"
            if service_name:
                resume_prompt += f" za {service_name}"
            if date_str:
                resume_prompt += f" na {date_str}"
            if time_str:
                resume_prompt += f" ob {time_str}"
            resume_prompt += "? (DA / NE)"

            # Set flag to wait for resume confirmation
            state["waiting_resume_confirmation"] = True

            return ChatResponse(
                reply=info_response + resume_prompt,
                session_id=session_id
            )

        # ===== GREETING/HELP PRESERVATION =====
        # If greeting or affirmative, continue flow
        if is_greeting(message) or is_affirmative(message):
            # Ignore greeting, continue flow
            response_text = handle_appointment_booking(message, session_id)
            return ChatResponse(reply=response_text, session_id=session_id)

        # Normal booking flow (ON-TOPIC)
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
                    # ===== HYBRID KNOWLEDGE BASE =====
                    # Use hybrid retrieval (BM25 + vector embeddings) with confidence gating
                    response_text = answer_with_hybrid_kb(
                        message,
                        history=conversation_history,
                        session_id=session_id
                    )

                    # ===== CACHE RESPONSE =====
                    # Only cache if not a clarification request
                    if len(response_text) > 50 and "Nisem prepričan" not in response_text:
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

    # ===== PERSISTENT STORAGE =====
    # Save both user message and assistant response to database
    try:
        # Determine current booking step
        current_step = state.get("step") if state["step"] is not None else None

        # Check if response was cached
        was_cached = (cached_response == response_text) if 'cached_response' in locals() else False

        # Extract service mentioned (if in booking intent)
        service_mentioned = None
        if intent.startswith("book_"):
            service_mentioned = intent.replace("book_", "")
            if service_mentioned == "general":
                service_mentioned = None

        # Save user message
        save_chat_message(
            session_id=session_id,
            role="user",
            content=message,
            intent=intent,
            service_mentioned=service_mentioned,
            booking_step=current_step,
            response_cached=False
        )

        # Get confidence metadata if available
        confidence_metadata = None
        if session_id in conversation_state:
            confidence_metadata = conversation_state[session_id].get("last_confidence_metadata")

        # Save assistant response with confidence metadata
        save_chat_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            intent=None,  # Only user messages have intent
            service_mentioned=service_mentioned,
            booking_step=current_step,
            response_cached=was_cached,
            metadata=confidence_metadata
        )

        # Clear confidence metadata after saving
        if session_id in conversation_state and "last_confidence_metadata" in conversation_state[session_id]:
            del conversation_state[session_id]["last_confidence_metadata"]
    except Exception as e:
        # Non-critical - don't fail the request
        print(f"[CHAT_HISTORY] Failed to save conversation: {e}")

    return ChatResponse(reply=response_text, session_id=session_id)
