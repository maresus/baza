from app.logic.orchestrator import classify_intent as detect_intent, is_booking_intent, is_menu_query, parse_reservation_type, is_affirmative, is_negative, is_explicit_cancel_command, should_switch_from_reservation, tourist_answer, is_event_inquiry_request, is_product_followup, detect_reset_request
import re
import random
import json
import os
import logging
import difflib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple
import uuid
import threading

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.chat import ActionButton, ChatRequest, ChatResponse, UIBlock
from app.services.reservation_service import ReservationService
from app.services.email_service import send_guest_confirmation, send_admin_notification, send_custom_message
from app.rag.rag_engine import rag_engine
from app.rag.knowledge_base import (
    CONTACT,
    KNOWLEDGE_CHUNKS,
    generate_llm_answer,
    search_knowledge,
    search_knowledge_scored,
)
from app.core.config import Settings
from app.core.llm_client import get_llm_client
from app.services.router_agent import route_message
from app.services.executor_v2 import execute_decision
from app.services.routing import decide_route, SwitchAction, handle_interrupt
from app.services.session.unified_state import (
    get_unified_state,
    reset_unified_state,
    set_flow,
    ensure_flow_data,
    set_last_intent,
    set_pending_question,
)
from app.services.session.state_writer import set_state_field
from app.services.intent_helpers import (
    INFO_FOLLOWUP_PHRASES,
    INFO_KEYWORDS,
    INFO_RESPONSES,
    PRODUCT_FOLLOWUP_PHRASES,
    PRODUCT_STEMS,
    RESERVATION_START_PHRASES,
    answer_product_question,
    detect_info_intent,
    detect_product_intent,
    detect_router_intent,
    format_products,
    get_info_response,
    get_product_response,
    is_ambiguous_inquiry_request,
    is_ambiguous_reservation_request,
    is_bulk_order_request,
    is_food_question_without_booking_intent,
    is_info_only_question,
    is_info_query,
    is_inquiry_trigger,
    is_product_query,
    is_reservation_related,
    is_reservation_typo,
    is_strong_inquiry_request,
)
from app.brand.config import (
    BRAND_NAME,
    BRAND_SHORT,
    FARM_INFO,
    GREETINGS as BRAND_GREETINGS,
    INFO_EMAIL,
    SHOP_BASE_URL,
    SHOP_URL,
    THANKS_RESPONSES as BRAND_THANKS,
    UNKNOWN_RESPONSES as BRAND_UNKNOWN,
)
from app.services.availability_flow import (
    get_availability_state,
    handle_availability_followup,
    handle_availability_query,
    is_availability_query,
    reset_availability_state,
    start_reservation_from_availability,
)
from app.services.reservation_flow import (
    advance_after_room_people as reservation_advance_after_room_people,
    get_booking_continuation,
    handle_reservation_flow as reservation_flow_handle_reservation_flow,
    handle_room_reservation as reservation_flow_handle_room_reservation,
    handle_table_reservation as reservation_flow_handle_table_reservation,
    reservation_prompt_for_state,
    validate_reservation_rules as reservation_validate_reservation_rules,
)
from app.services.parsing import (
    extract_date,
    extract_date_range,
    extract_time,
    parse_people_count,
)
from app.services.flows.info_flow import (
    answer_farm_info,
    answer_wine_question,
    format_current_menu,
    is_full_menu_request,
    parse_month_from_text,
    parse_relative_month,
)

router = APIRouter(prefix="/chat", tags=["chat"])
USE_ROUTER_V2 = True
USE_FULL_KB_LLM = False
USE_UNIFIED_ROUTER = os.getenv("USE_UNIFIED_ROUTER", "true").strip().lower() in {"1", "true", "yes", "on"}
if USE_UNIFIED_ROUTER:
    USE_ROUTER_V2 = False
INQUIRY_RECIPIENT = os.getenv("INQUIRY_RECIPIENT", "satlermarko@gmail.com")
SHORT_MODE = os.getenv("SHORT_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
DISABLE_INQUIRY = os.getenv("DISABLE_INQUIRY", "true").strip().lower() in {"1", "true", "yes", "on"}
_router_logger = logging.getLogger("router_v2")

# ========== CENTRALIZIRANI INFO ODGOVORI (brez LLM!) ==========
BOOKING_RELEVANT_KEYS = {"sobe", "vecerja", "cena_sobe", "min_nocitve", "kapaciteta_mize"}
CRITICAL_INFO_KEYS = {
    "odpiralni_cas",
    "prazniki",
    "rezervacija_vnaprej",
    "zajtrk",
    "vecerja",
    "jedilnik",
    "cena_sobe",
    "min_nocitve",
    "prijava_odjava",
    "placilo",
    "parking",
    "kontakt",
    "sobe",
    "kapaciteta_mize",
}

AVAILABILITY_TOOL_SCHEMA = {
    "name": "check_availability",
    "description": "Preveri razpolozljivost sobe ali mize v bazi za izbran datum.",
    "parameters": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["room", "table"]},
            "date": {"type": "string", "description": "Format: DD.MM.YYYY"},
            "time": {"type": "string", "description": "Format: HH:MM (samo za mize)"},
            "people": {"type": "integer"},
            "nights": {"type": "integer"},
        },
        "required": ["type", "date"],
    },
}

def _send_reservation_emails_async(payload: dict) -> None:
    def _worker() -> None:
        try:
            send_guest_confirmation(payload)
            send_admin_notification(payload)
        except Exception as exc:
            print(f"[EMAIL] Async send failed: {exc}")
    threading.Thread(target=_worker, daemon=True).start()

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
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = record.get("url", "")
            title = record.get("title", "")
            content = record.get("content", "")
            if not (url or title or content):
                continue
            chunks.append(
                f"URL: {url}\nNaslov: {title}\nVsebina: {content}\n"
            )
        FULL_KB_TEXT = "\n---\n".join(chunks)
except Exception as exc:
    print(f"[KB] Full KB load failed: {exc}")

def _llm_system_prompt_full_kb(language: str = "si") -> str:
    common = (
        f"Ti si asistent Domačije {BRAND_SHORT}. Upoštevaj te potrjene podatke kot glavne:\n"
        "- Gospodar kmetije: Marko\n"
        "- Družina: Babica Marija, Marko, Sara, Jakob (partnerka Maja), Lana, Nika\n"
        "- Konjička: Malajka in Marsij\n\n"
        "Preverjeni meniji (uporabi dobesedno, brez dodajanja novih jedi):\n"
        "Zimska srajčka (dec–feb):\n"
        "- Pohorska bunka in zorjen Frešerjev sir, hišna salama, paštetka iz domačih jetrc, zaseka, bučni namaz, hišni kruhek\n"
        "- Goveja župca z rezanci in jetrnimi rolicami ali koprivna juhica s čemažem in sirne lizike\n"
        "- Meso na plošči: pujskov hrbet, hrustljavi piščanec Pesek, piščančje kroglice z zelišči, mlado goveje meso z jabolki in rdečim vinom\n"
        "- Priloge: štukelj s skuto, ričota s pirino kašo in jurčki, pražen krompir iz šporheta na drva, mini pita s porom, ocvrte hruške “Debeluške”, pomladna/zimska solata\n"
        "- Sladica: Pohorska gibanica babice Marije\n\n"
        "Tukaj so VSE informacije o domačiji:\n"
        f"{FULL_KB_TEXT}\n\n"
        "Ne izmišljuj si podatkov.\n"
        "Odgovarjaj kratko (2–4 stavke), razen če uporabnik izrecno želi podrobnosti ali meni.\n"
        "Če nisi prepričan, postavi kratko pojasnitveno vprašanje.\n"
        "Ton naj bo topel, domač in človeški, brez robotiziranih ponovitev.\n"
        "Ne ponavljaj istih stavkov dobesedno – raje variiraj besedilo.\n"
        "Omenjaj družinske člane ali živali samo, ko je to vsebinsko relevantno (npr. vprašanje o družini, kmetiji, otrocih, živalih).\n"
        "Ne pretiravaj z emojiji: največ 1 na odgovor, po potrebi tudi brez.\n"
        "Če uporabnik želi TOČEN meni, ga podaš samo, če je v podatkih ali preverjenih menijih.\n"
        "Če ni podatka o točnem meniju ali sezoni, to povej in vprašaj za mesec/termin.\n"
        "Če se podatki v virih razlikujejo, uporabi potrjene podatke zgoraj.\n"
        "Ne navajaj oseb, ki niso v potrjenih podatkih.\n"
        "Če uporabnik želi rezervirati sobo ali mizo, OBVEZNO pokliči funkcijo "
        "`reservation_intent` in nastavi ustrezen action.\n"
    )
    if language == "en":
        return (
            f"You are the assistant for {BRAND_NAME}. Respond in English.\n"
            + common
        )
    if language == "de":
        return (
            f"Du bist der Assistent für {BRAND_NAME}. Antworte auf Deutsch.\n"
            + common
        )
    return (
        common
        + "Odgovarjaj prijazno, naravno in slovensko.\n"
    )

def _llm_route_reservation(message: str) -> dict:
    client = get_llm_client()
    settings = Settings()
    tools = [
        {
            "type": "function",
            "name": "reservation_intent",
            "description": "Ugotovi ali uporabnik želi rezervacijo sobe ali mize. Vrni action.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["NONE", "BOOKING_ROOM", "BOOKING_TABLE"],
                    },
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                    "people_count": {"type": "integer"},
                    "nights": {"type": "integer"},
                },
                "required": ["action"],
            },
        }
    ]
    try:
        response = client.responses.create(
            model=getattr(settings, "openai_model", "gpt-4.1-mini"),
            input=[
                {"role": "system", "content": "Ugotovi, ali uporabnik želi rezervacijo sobe ali mize."},
                {"role": "user", "content": message},
            ],
            tools=tools,
            tool_choice={"type": "function", "name": "reservation_intent"},
            temperature=0.2,
            max_output_tokens=120,
        )
    except Exception as exc:
        print(f"[LLM] reservation route error: {exc}")
        return {"action": "NONE"}

    for block in getattr(response, "output", []) or []:
        for content in getattr(block, "content", []) or []:
            content_type = getattr(content, "type", "")
            if content_type not in {"tool_call", "function_call"}:
                continue
            name = getattr(content, "name", "") or getattr(getattr(content, "function", None), "name", "")
            if name != "reservation_intent":
                continue
            args = getattr(content, "arguments", None)
            if args is None and getattr(content, "function", None):
                args = getattr(content.function, "arguments", None)
            args = args or "{}"
            try:
                return json.loads(args)
            except json.JSONDecodeError:
                return {"action": "NONE"}
    return {"action": "NONE"}

def _llm_answer_full_kb(message: str, language: str = "si") -> str:
    client = get_llm_client()
    settings = Settings()
    try:
        response = client.responses.create(
            model=getattr(settings, "openai_model", "gpt-4.1-mini"),
            input=[
                {"role": "system", "content": _llm_system_prompt_full_kb(language)},
                {"role": "user", "content": message},
            ],
            max_output_tokens=450,
            temperature=getattr(settings, "openai_temperature", 0.8),
            top_p=0.9,
        )
    except Exception as exc:
        print(f"[LLM] answer error: {exc}")
        return "Oprostite, trenutno ne morem odgovoriti. Poskusite znova čez trenutek."
    answer = getattr(response, "output_text", None)
    if not answer:
        outputs = []
        for block in getattr(response, "output", []) or []:
            for content in getattr(block, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    outputs.append(text)
        answer = "\n".join(outputs).strip()
    if not answer:
        return "Seveda, z veseljem pomagam. Kaj vas zanima?"
    # Strip accidental tool-call artifacts.
    answer = re.sub(r"(?mi)^\s*`?reservation_intent`?\s*$", "", answer).strip()
    return answer or "Seveda, z veseljem pomagam. Kaj vas zanima?"


def _stream_text_chunks(text: str, chunk_size: int = 80):
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


def _llm_answer_full_kb_stream(message: str, settings: Settings, language: str = "si"):
    client = get_llm_client()
    try:
        stream = client.responses.create(
            model=getattr(settings, "openai_model", "gpt-4.1-mini"),
            input=[
                {"role": "system", "content": _llm_system_prompt_full_kb(language)},
                {"role": "user", "content": message},
            ],
            max_output_tokens=450,
            temperature=getattr(settings, "openai_temperature", 0.8),
            top_p=0.9,
            stream=True,
        )
    except Exception as exc:
        fallback = "Oprostite, trenutno ne morem odgovoriti. Poskusite znova čez trenutek."
        print(f"[LLM] stream error: {exc}")
        for chunk in _stream_text_chunks(fallback):
            yield chunk
        return fallback

    collected: list[str] = []
    for event in stream:
        event_type = getattr(event, "type", "")
        if event_type == "response.output_text.delta":
            delta = getattr(event, "delta", "")
            if delta:
                collected.append(delta)
                yield delta
        elif event_type == "response.error":
            error_message = getattr(getattr(event, "error", None), "message", "")
            if error_message:
                print(f"[LLM] stream error event: {error_message}")
    final_text = "".join(collected).strip()
    return final_text or "Seveda, z veseljem pomagam. Kaj vas zanima?"

def _llm_answer(question: str, history: list[dict[str, str]]) -> Optional[str]:
    try:
        return generate_llm_answer(question, history=history)
    except Exception as exc:
        print(f"[LLM] Failed to answer: {exc}")
        return None


def get_mini_rag_answer(question: str) -> Optional[str]:
    chunks = search_knowledge(question, top_k=1)
    if not chunks:
        return None
    chunk = chunks[0]
    snippet = chunk.paragraph.strip()
    if len(snippet) > 500:
        snippet = snippet[:500].rsplit(". ", 1)[0] + "."
    url_line = f"\n\nVeč: {chunk.url}" if chunk.url else ""
    return f"{snippet}{url_line}"

UNKNOWN_RESPONSES = [
    "Za to nimam podatka.",
    "Tega žal ne vem.",
    "Nimam informacije o tem.",
]

SEMANTIC_THRESHOLD = 0.75
GLOBAL_CONFIDENCE_THRESHOLD = 0.2
SEMANTIC_STOPWORDS = {
    "a", "ali", "al", "pa", "in", "na", "za", "se", "so", "je", "smo", "ste",
    "sem", "biti", "bo", "bi", "da", "ne", "ni", "niso", "si", "mi", "ti",
    "vi", "vas", "vam", "nas", "ga", "jo", "jih", "te", "to", "ta", "tisto",
    "kdo", "kaj", "kdaj", "kje", "kako", "kolik", "koliko", "ker", "pač",
    "pri", "od", "do", "v", "iz", "z", "ob", "kot", "naj", "tudi", "lahko",
    "moj", "moja", "moje", "tvoj", "tvoja", "tvoje", "njihov", "njihova",
    "the", "and", "or", "to", "is", "are", "a", "an", "for", "in", "of",
}


def _tokenize_text(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-zČŠŽčšžĐđĆć0-9]+", text.lower())
    return {t for t in tokens if len(t) >= 3 and t not in SEMANTIC_STOPWORDS}


def get_low_confidence_reply() -> str:
    return "Nisem povsem prepričan, kaj točno iščete. Prosim, povejte bolj konkretno (npr. sobe, kosila, izdelki, lokacija)."


def _semantic_overlap_ok(question: str, chunk: Any) -> bool:
    q_tokens = _tokenize_text(question)
    if not q_tokens:
        return True
    c_tokens = _tokenize_text(f"{chunk.title or ''} {chunk.paragraph or ''}")
    overlap = q_tokens & c_tokens
    if len(q_tokens) >= 6:
        return len(overlap) >= 2 and (len(overlap) / len(q_tokens)) >= 0.25
    return len(overlap) >= 2 or (len(overlap) / len(q_tokens)) >= 0.5


def _format_semantic_snippet(chunk: Any) -> str:
    snippet = chunk.paragraph.strip()
    if len(snippet) > 500:
        snippet = snippet[:500].rsplit(". ", 1)[0] + "."
    url_line = f"\n\nVeč: {chunk.url}" if chunk.url else ""
    return f"{snippet}{url_line}"


def semantic_info_answer(question: str) -> Optional[str]:
    scored = search_knowledge_scored(question, top_k=1)
    if not scored:
        return None
    score, chunk = scored[0]
    if score < SEMANTIC_THRESHOLD:
        try:
            with open("data/semantic_low_score.log", "a", encoding="utf-8") as handle:
                handle.write(f"{datetime.utcnow().isoformat()} score={score:.2f} q={question}\n")
        except Exception:
            pass
        return None
    if not _semantic_overlap_ok(question, chunk):
        try:
            q_tokens = _tokenize_text(question)
            c_tokens = _tokenize_text(chunk.paragraph or "")
            overlap = q_tokens & c_tokens
            ratio = (len(overlap) / len(q_tokens)) if q_tokens else 0.0
            with open("data/semantic_low_score.log", "a", encoding="utf-8") as handle:
                handle.write(
                    f"{datetime.utcnow().isoformat()} score={score:.2f} overlap={len(overlap)} "
                    f"ratio={ratio:.2f} q={question}\n"
                )
        except Exception:
            pass
        return None
    return _format_semantic_snippet(chunk)
# Fiksni zaključek rezervacije
RESERVATION_PENDING_MESSAGE = """
✅ **Vaše povpraševanje je PREJETO** in čaka na potrditev.

📧 Potrditev boste prejeli po e-pošti.
⏳ Odgovorili vam bomo v najkrajšem možnem času.

⚠️ Preverite tudi **SPAM/VSILJENO POŠTO**.
"""


class ChatRequestWithSession(ChatRequest):
    session_id: Optional[str] = None


last_wine_query: Optional[str] = None
SESSION_TIMEOUT_HOURS = 48
GREETING_KEYWORDS = {"živjo", "zdravo", "hej", "hello", "dober dan", "pozdravljeni"}
GREETINGS = BRAND_GREETINGS
THANKS_RESPONSES = BRAND_THANKS
UNKNOWN_RESPONSES = BRAND_UNKNOWN

reservation_service = ReservationService()

# Spletna trgovina (policy)
STRICT_POLICY = os.getenv("STRICT_POLICY", "true").strip().lower() in {"1", "true", "yes", "on"}

LOCATION_KEYWORDS = {
    "kje",
    "naslov",
    "lokacija",
    "kako pridem",
    "priti",
    "parking",
    "telefon",
    "številka",
    "stevilka",
    "email",
    "kontakt",
    "odprti",
    "odprto",
    "delovni čas",
    "ura",
    "kdaj",
    "wifi",
    "internet",
    "klima",
    "parkirišče",
    "parkirisce",
}





GREETING_RESPONSES = [
    # Uporabljamo GREETINGS za variacije v prijaznih uvodih
] + GREETINGS
GOODBYE_RESPONSES = THANKS_RESPONSES
EXIT_KEYWORDS = {
    "konec",
    "stop",
    "prekini",
    "nehaj",
    "pustimo",
    "pozabi",
    "ne rabim",
    "ni treba",
    "drugič",
    "drugic",
    "cancel",
    "quit",
    "exit",
    "pusti",
}

ROOM_PRICING = {
    "base_price": 50,  # EUR na nočitev na odraslo osebo
    "min_adults": 2,  # minimalno 2 odrasli osebi
    "min_nights_summer": 3,  # jun/jul/avg
    "min_nights_other": 2,  # ostali meseci
    "dinner_price": 25,  # penzionska večerja EUR/oseba
    "dinner_includes": "juha, glavna jed, sladica",
    "child_discounts": {
        "0-4": 100,  # brezplačno
        "4-12": 50,  # 50% popust
    },
    "breakfast_included": True,
    "check_in": "14:00",
    "check_out": "10:00",
    "breakfast_time": "8:00-9:00",
    "dinner_time": "18:00",
    "closed_days": ["ponedeljek", "torek"],  # ni večerij
}


# kulinarična doživetja (sreda–petek, skupine 6+)
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

def _blank_reservation_state() -> dict[str, Optional[str | int]]:
    return {
        "step": None,
        "type": None,
        "date": None,
        "time": None,
        "nights": None,
        "rooms": None,
        "people": None,
        "adults": None,
        "kids": None,  # število otrok
        "kids_ages": None,  # starosti otrok
        "name": None,
        "phone": None,
        "email": None,
        "location": None,
        "available_locations": None,
        "language": None,
        "dinner_people": None,
        "note": None,
        "availability": None,
    }


def _blank_inquiry_state() -> dict[str, Optional[str]]:
    return {
        "step": None,
        "details": "",
        "deadline": "",
        "contact_name": "",
        "contact_email": "",
        "contact_phone": "",
        "contact_raw": "",
    }


reservation_states: dict[str, dict[str, Optional[str | int]]] = {}
inquiry_states: dict[str, dict[str, Optional[str]]] = {}


def get_reservation_state(session_id: str) -> dict[str, Optional[str | int]]:
    if session_id not in reservation_states:
        reservation_states[session_id] = _blank_reservation_state()
    return reservation_states[session_id]


def get_inquiry_state(session_id: str) -> dict[str, Optional[str]]:
    if session_id not in inquiry_states:
        inquiry_states[session_id] = _blank_inquiry_state()
    return inquiry_states[session_id]


def reset_inquiry_state(state: dict[str, Optional[str]]) -> None:
    state.update(_blank_inquiry_state())


def _sync_unified_state(
    unified_state: dict[str, Any],
    reservation_state: dict[str, Optional[str | int]],
    inquiry_state: dict[str, Optional[str]],
) -> None:
    if inquiry_state.get("step"):
        set_flow(unified_state, "inquiry", inquiry_state.get("step"))
        return
    if reservation_state.get("step"):
        res_type = reservation_state.get("type")
        flow = "reservation_room" if res_type == "room" else "reservation_table"
        set_flow(unified_state, flow, reservation_state.get("step"))
        return
    set_flow(unified_state, "idle", None)


last_product_query: Optional[str] = None
last_info_query: Optional[str] = None
last_menu_query: bool = False
conversation_history: list[dict[str, str]] = []
last_interaction: Optional[datetime] = None
unknown_question_state: dict[str, dict[str, Any]] = {}
chat_session_id: str = str(uuid.uuid4())[:8]

def handle_info_during_booking(message: str, session_state: dict) -> Optional[str]:
    """
    Če je booking aktiven in uporabnik vpraša info ali produkt, odgovorimo + nadaljujemo flow.
    """
    if not session_state or session_state.get("step") is None:
        return None
    step = session_state.get("step")
    msg = (message or "").strip()
    if step and str(step).startswith("awaiting_"):
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", msg):
            return None
        if len(re.sub(r"\D+", "", msg)) >= 7 and "?" not in msg:
            return None
    # Med vnosom kontaktnih podatkov ne smemo preusmeriti v info reply.
    if step == "awaiting_email" and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", msg):
        return None
    if step == "awaiting_phone" and len(re.sub(r"\D+", "", msg)) >= 7:
        return None
    if step == "awaiting_name" and "?" not in msg and len(msg.split()) >= 2:
        return None

    info_key = detect_info_intent(message)
    if info_key:
        info_response = get_info_response(info_key)
        if STRICT_POLICY:
            return info_response
        continuation = get_booking_continuation(session_state.get("step"), session_state)
        return f"{info_response}\n\n---\n\n📝 **Nadaljujemo z rezervacijo:**\n{continuation}"

    product_key = detect_product_intent(message)
    if product_key:
        if STRICT_POLICY and is_bulk_order_request(message):
            product_response = f"Tega izdelka ni v spletni trgovini. Pišite na {INFO_EMAIL}."
        else:
            product_response = get_product_response(product_key)
        if STRICT_POLICY:
            return product_response
        continuation = get_booking_continuation(session_state.get("step"), session_state)
        return f"{product_response}\n\n---\n\n📝 **Nadaljujemo z rezervacijo:**\n{continuation}"

    return None










def strip_product_followup(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return text
    drop_starts = (
        "želite",
        "zelite",
        "če želite",
        "ce zelite",
        "bi radi",
        "bi želeli",
        "bi želela",
        "bi hotel",
        "bi hotela",
        "lahko vam",
        "lahko ti",
        "želiš",
        "zelis",
    )
    while lines and (lines[-1].lower().startswith(drop_starts) or lines[-1].endswith("?")):
        lines.pop()
    return "\n".join(lines) if lines else text


def extract_email(text: str) -> str:
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    return digits if len(digits) >= 7 else ""





def is_escape_command(message: str) -> bool:
    lowered = message.lower()
    escape_words = {"prekliči", "preklici", "reset", "stop", "prekini"}
    return any(word in lowered for word in escape_words)


def is_switch_topic_command(message: str) -> bool:
    lowered = message.lower()
    switch_words = {
        "zamenjaj temo",
        "menjaj temo",
        "nova tema",
        "spremeni temo",
        "gremo drugam",
        "druga tema",
    }
    return any(phrase in lowered for phrase in switch_words)






def is_contact_request(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in ["kontakt", "telefon", "email", "e-po", "klic", "pokli", "številk"])


def has_wine_context(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["vinska klet", "vinograd", "klet", "degustacij", "vino", "vinar"])


def is_confirmation_question(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in [
            "želite",
            "zelite",
            "potrdite",
            "potrdim",
            "potrdi",
            "potrditi",
            "confirm",
            "would you like",
            "can i",
        ]
    )


def llm_is_affirmative(message: str, last_bot: str, detected_lang: str) -> bool:
    try:
        prompt = (
            "Answer with YES or NO only.\n"
            f"Assistant: {last_bot}\n"
            f"User: {message}\n"
        )
        if detected_lang == "en":
            prompt += "\nThe user is writing in English."
        elif detected_lang == "de":
            prompt += "\nThe user is writing in German."
        verdict = generate_llm_answer(prompt, history=[]).strip().lower()
        return verdict.startswith("yes") or verdict.startswith("da")
    except Exception:
        return False


def get_last_assistant_message() -> str:
    for msg in reversed(conversation_history):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return ""

def get_last_user_message() -> str:
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def get_last_reservation_user_message() -> str:
    for msg in reversed(conversation_history):
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if (
            is_reservation_related(content)
            or extract_date(content)
            or extract_date_range(content)
            or parse_people_count(content).get("total")
        ):
            return content
    return ""


def set_reservation_type_from_text(state: dict, text: str) -> None:
    lowered = text.lower()
    if any(token in lowered for token in ["mizo", "miza", "table", "kosilo", "kosila", "lunch"]):
        set_state_field(state, "type", "table")
    elif any(token in lowered for token in ["sobo", "soba", "preno", "room", "zimmer"]):
        set_state_field(state, "type", "room")


def last_bot_mentions_reservation(last_bot: str) -> bool:
    text = last_bot.lower()
    return any(token in text for token in ["rezerv", "reserve", "booking", "zimmer", "room", "mizo", "table"])


def last_bot_mentions_product_order(last_bot: str) -> bool:
    text = last_bot.lower()
    if "naroč" in text or "naroc" in text:
        return True
    if "trgovin" in text or "izdelek" in text or "katalog" in text:
        return True
    if any(stem in text for stem in PRODUCT_STEMS):
        return True
    return False


def get_greeting_response() -> str:
    base = random.choice(GREETINGS)
    if "pozdrav" in base.lower():
        return base
    return f"Pozdravljeni! {base}"


def get_goodbye_response() -> str:
    base = random.choice(THANKS_RESPONSES)
    if "adijo" in base.lower():
        return base
    return f"Adijo! {base}"



def detect_language(message: str) -> str:
    """Zazna jezik sporočila. Vrne 'si', 'en' ali 'de'."""
    lowered = message.lower()
    
    # Slovenske besede, ki vsebujejo angleške nize (izjeme), odstranimo pred detekcijo
    slovak_exceptions = ["liker", "likerj", " like ", "slike"]
    for exc in slovak_exceptions:
        lowered = lowered.replace(exc, "")

    german_words = [
        "ich",
        "sie",
        "wir",
        "haben",
        "möchte",
        "möchten",
        "können",
        "bitte",
        "zimmer",
        "tisch",
        "reservierung",
        "reservieren",
        "buchen",
        "wann",
        "wie",
        "was",
        "wo",
        "gibt",
        "guten tag",
        "hallo",
        "danke",
        "preis",
        "kosten",
        "essen",
        "trinken",
        "wein",
        "frühstück",
        "abendessen",
        "mittag",
        "nacht",
        "übernachtung",
    ]
    german_count = sum(1 for word in german_words if word in lowered)

    # posebna obravnava angleškega zaimka "I" kot samostojne besede
    english_pronoun = 1 if re.search(r"\bi\b", lowered) else 0

    english_words = [
        " we ",
        "you",
        "have",
        "would",
        " like ",
        "want",
        "can",
        "room",
        "table",
        "reservation",
        "reserve",
        "book",
        "booking",
        "when",
        "how",
        "what",
        "where",
        "there",
        "hello",
        "hi ",
        "thank",
        "price",
        "cost",
        "food",
        "drink",
        "wine",
        "menu",
        "breakfast",
        "dinner",
        "lunch",
        "night",
        "stay",
        "please",
    ]
    english_count = english_pronoun + sum(1 for word in english_words if word in lowered)

    if german_count >= 2:
        return "de"
    if english_count >= 2:
        return "en"
    if german_count == 1 and english_count == 0:
        return "de"
    if english_count == 1 and german_count == 0:
        return "en"

    return "si"


def translate_reply(reply: str, lang: str) -> str:
    """Prevede odgovor v angleščino ali nemščino, če je potrebno."""
    if not reply or lang not in {"en", "de"}:
        return reply
    try:
        prompt = (
            f"Translate this to English, keep it natural and friendly:\n{reply}"
            if lang == "en"
            else f"Translate this to German/Deutsch, keep it natural and friendly:\n{reply}"
        )
        return generate_llm_answer(prompt, history=[])
    except Exception:
        return reply


def maybe_translate(text: str, target_lang: str) -> str:
    """Po potrebi prevede besedilo v angleščino ali nemščino."""
    if target_lang not in {"en", "de"} or not text:
        return text
    try:
        prompt = (
            f"Translate this to English, keep it natural and friendly:\n{text}"
            if target_lang == "en"
            else f"Translate this to German/Deutsch, keep it natural and friendly:\n{text}"
        )
        return generate_llm_answer(prompt, history=[])
    except Exception:
        return text


def translate_response(text: str, target_lang: str) -> str:
    """Prevede besedilo glede na zaznan jezik rezervacije."""
    if target_lang == "si" or target_lang is None:
        return text
    try:
        if target_lang == "en":
            prompt = f"Translate to English, natural and friendly, only translation:\\n{text}"
        elif target_lang == "de":
            prompt = f"Translate to German, natural and friendly, only translation:\\n{text}"
        else:
            return text
        return generate_llm_answer(prompt, history=[])
    except Exception:
        return text


def is_unknown_response(response: str) -> bool:
    """Preveri, ali odgovor nakazuje neznano informacijo."""
    unknown_indicators = [
        "žal ne morem",
        "nimam informacij",
        "ne vem",
        "nisem prepričan",
        "ni na voljo",
        "podatka nimam",
    ]
    response_lower = response.lower()
    return any(ind in response_lower for ind in unknown_indicators)


def get_unknown_response(language: str = "si") -> str:
    """Vrne prijazen odgovor, ko podatkov ni."""
    if language == "si":
        return random.choice(UNKNOWN_RESPONSES)
    responses = {
        "en": "Unfortunately, I cannot answer this question. 😊\n\nIf you share your email address, I will inquire and get back to you.",
        "de": "Leider kann ich diese Frage nicht beantworten. 😊\n\nWenn Sie mir Ihre E-Mail-Adresse mitteilen, werde ich mich erkundigen und Ihnen antworten.",
    }
    return responses.get(language, "Na to vprašanje žal ne morem odgovoriti. 😊")


def is_email(text: str) -> bool:
    """Preveri, ali je besedilo e-poštni naslov."""
    import re as _re

    return bool(_re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", text.strip()))


def reset_reservation_state(state: dict[str, Optional[str | int]]) -> None:
    state.clear()
    state.update(_blank_reservation_state())


def start_inquiry_consent(state: dict[str, Optional[str]]) -> str:
    set_state_field(state, "step", "awaiting_consent")
    return (
        "Žal nimam dovolj informacij. "
        "Lahko zabeležim povpraševanje in ga posredujem ekipi. "
        "Želite to? (da/ne)"
    )


def handle_inquiry_flow(message: str, state: dict[str, Optional[str]], session_id: str) -> Optional[str]:
    text = message.strip()
    lowered = text.lower()
    step = state.get("step")
    if is_escape_command(message) or is_switch_topic_command(message):
        reset_inquiry_state(state)
        return "V redu, prekinil sem povpraševanje. Kako vam lahko še pomagam?"

    if step == "awaiting_consent":
        if lowered in {"da", "ja", "seveda", "lahko", "ok"}:
            set_state_field(state, "step", "awaiting_details")
            return "Odlično. Prosim opišite, kaj točno želite (količina, izdelek, storitev)."
        if lowered in {"ne", "ne hvala", "ni treba"}:
            reset_inquiry_state(state)
            return "V redu. Če želite, lahko vprašate še kaj drugega."
        return "Želite, da zabeležim povpraševanje? Odgovorite z 'da' ali 'ne'."

    if step == "awaiting_details":
        if text:
            current_details = state.get("details") or ""
            new_details = f"{current_details}\n{text}" if current_details else text
            set_state_field(state, "details", new_details)
        set_state_field(state, "step", "awaiting_deadline")
        return "Hvala! Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"

    if step == "awaiting_deadline":
        if any(word in lowered for word in ["ni", "ne vem", "kadar koli", "vseeno", "ni pomembno"]):
            set_state_field(state, "deadline", "")
        else:
            set_state_field(state, "deadline", text)
        set_state_field(state, "step", "awaiting_contact")
        return "Super. Prosim še kontakt (ime, telefon, email)."

    if step == "awaiting_contact":
        set_state_field(state, "contact_raw", text)
        email = extract_email(text)
        phone = extract_phone(text)
        set_state_field(state, "contact_email", email or state.get("contact_email") or "")
        set_state_field(state, "contact_phone", phone or state.get("contact_phone") or "")
        set_state_field(state, "contact_name", state.get("contact_name") or "")
        if not state["contact_email"]:
            return "Za povratni kontakt prosim dodajte email."

        details = state.get("details") or text
        deadline = state.get("deadline") or ""
        contact_summary = state.get("contact_raw") or ""
        summary = "\n".join(
            [
                "Novo povpraševanje:",
                f"- Podrobnosti: {details}",
                f"- Rok: {deadline or 'ni naveden'}",
                f"- Kontakt: {contact_summary}",
                f"- Session: {session_id}",
            ]
        )
        reservation_service.create_inquiry(
            session_id=session_id,
            details=details,
            deadline=deadline,
            contact_name=state.get("contact_name") or "",
            contact_email=state.get("contact_email") or "",
            contact_phone=state.get("contact_phone") or "",
            contact_raw=contact_summary,
            source="chat",
            status="new",
        )
        send_custom_message(
            INQUIRY_RECIPIENT,
            f"Novo povpraševanje – {BRAND_SHORT}",
            summary,
        )
        reset_inquiry_state(state)
        return "Hvala! Povpraševanje sem zabeležil in ga posredoval. Odgovorimo vam v najkrajšem možnem času."

    return None


def reset_conversation_context(session_id: Optional[str] = None) -> None:
    """Počisti začasne pogovorne podatke in ponastavi sejo."""
    global conversation_history, last_product_query, last_wine_query, last_info_query, last_menu_query
    global chat_session_id, unknown_question_state, last_interaction
    if session_id:
        state = reservation_states.get(session_id)
        if state is not None:
            reset_reservation_state(state)
            reservation_states.pop(session_id, None)
        unknown_question_state.pop(session_id, None)
    else:
        for state in reservation_states.values():
            reset_reservation_state(state)
        reservation_states.clear()
        unknown_question_state = {}
    conversation_history = []
    last_product_query = None
    last_wine_query = None
    last_info_query = None
    last_menu_query = False
    reset_info_state()
    chat_session_id = str(uuid.uuid4())[:8]
    last_interaction = None


def generate_confirmation_email(state: dict[str, Optional[str | int]]) -> str:
    subject = f"Zadeva: Rezervacija – {BRAND_NAME}"
    name = state.get("name") or "spoštovani"
    lines = [f"Pozdravljeni {name}!"]

    if state.get("type") == "room":
        try:
            adults = int(state.get("people") or 0)
        except (TypeError, ValueError):
            adults = 0
        try:
            nights_val = int(state.get("nights") or 0)
        except (TypeError, ValueError):
            nights_val = 0
        estimated_price = adults * nights_val * ROOM_PRICING["base_price"] if adults and nights_val else 0
        lines.append(
            f"Prejeli smo povpraševanje za sobo od {state.get('date')} za {state.get('nights')} nočitev "
            f"za {state.get('people')} gostov."
        )
        if estimated_price:
            lines.append(
                f"Okvirna cena bivanja: {estimated_price}€ ({adults} oseb × {state.get('nights')} noči × {ROOM_PRICING['base_price']}€). "
                "Popusti za otroke in večerje se dodajo ob potrditvi."
            )
        lines.append(
            "Zajtrk je vključen v ceno. Prijava od 14:00, odjava do 10:00, zajtrk 8:00–9:00, večerja 18:00 (pon/torki brez večerij)."
        )
        lines.append("Naše sobe so klimatizirane, na voljo je brezplačen Wi‑Fi.")
    else:
        lines.append(
            f"Prejeli smo rezervacijo mize za {state.get('people')} oseb na datum {state.get('date')} ob {state.get('time')}."
        )
        lines.append("Kuhinja ob sobotah in nedeljah deluje med 12:00 in 20:00, zadnji prihod na kosilo je ob 15:00.")

    lines.append("Rezervacijo bomo potrdili po preverjanju razpoložljivosti.")
    lines.append(f"Kontakt domačije: {CONTACT['phone']} | {CONTACT['email']}")
    body = "\n".join(lines)
    return f"{subject}\n\n{body}"


def room_intro_text() -> str:
    return (
        "Sobe: ALJAŽ (2+2), JULIJA (2+2), ANA (2+2). "
        "Minimalno 3 nočitve v juniju/juliju/avgustu, 2 nočitvi v ostalih mesecih. "
        "Prijava 14:00, odjava 10:00, zajtrk 8:00–9:00, večerja 18:00 (pon/torki brez večerij). "
        "Sobe so klimatizirane, Wi‑Fi je brezplačen, zajtrk je vključen."
    )


def table_intro_text() -> str:
    return (
        "Kosila ob sobotah in nedeljah med 12:00 in 20:00, zadnji prihod na kosilo ob 15:00. "
        "Jedilnici: 'Pri peči' (15 oseb) in 'Pri vrtu' (35 oseb)."
    )



def _validate_reservation_rules_bound(arrival_date_str: str, nights: int) -> Tuple[bool, str, str]:
    return reservation_validate_reservation_rules(arrival_date_str, nights, reservation_service)


def _advance_after_room_people_bound(
    reservation_state: dict[str, Optional[str | int]],
    _reservation_service: Any = None,
) -> str:
    return reservation_advance_after_room_people(reservation_state, reservation_service)


def handle_reservation_flow(message: str, state: dict[str, Optional[str | int]]) -> str:
    return reservation_flow_handle_reservation_flow(
        message,
        state,
        detect_language,
        translate_response,
        parse_reservation_type,
        room_intro_text,
        table_intro_text,
        reset_reservation_state,
        is_affirmative,
        reservation_service,
        _validate_reservation_rules_bound,
        _advance_after_room_people_bound,
        reservation_flow_handle_room_reservation,
        reservation_flow_handle_table_reservation,
        EXIT_KEYWORDS,
        detect_reset_request,
        _send_reservation_emails_async,
        RESERVATION_PENDING_MESSAGE,
    )


def is_greeting(message: str) -> bool:
    lowered = message.lower()
    return any(greeting in lowered for greeting in GREETING_KEYWORDS)


def append_today_hint(message: str, reply: str) -> str:
    lowered = message.lower()
    if "danes" in lowered:
        today = datetime.now().strftime("%A, %d.%m.%Y")
        reply = f"{reply}\n\nZa orientacijo: danes je {today}."
    return reply


def ensure_single_greeting(message: str, reply: str) -> str:
    greetings = ("pozdrav", "živjo", "zdravo", "hej", "hello")
    if reply.lstrip().lower().startswith(greetings):
        return reply
    return f"Pozdravljeni! {reply}"


def build_effective_query(message: str) -> str:
    global last_info_query
    normalized = message.strip().lower()
    # Če ima trenutno sporočilo že jasen intent, ga ne lepimo na prejšnjo temo.
    if detect_info_intent(message) or detect_product_intent(message):
        return message
    short_follow = (
        len(normalized) < 12
        or normalized in INFO_FOLLOWUP_PHRASES
        or normalized.rstrip("?") in INFO_FOLLOWUP_PHRASES
    )
    if short_follow:
        if last_product_query:
            return f"{last_product_query} {message}"
        if last_info_query:
            return f"{last_info_query} {message}"
    return message


@router.post("", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequestWithSession) -> ChatResponse:
    global last_product_query, last_wine_query, last_info_query, last_menu_query, conversation_history, last_interaction, chat_session_id
    now = datetime.now()
    session_id = payload.session_id or "default"
    if last_interaction and now - last_interaction > timedelta(hours=SESSION_TIMEOUT_HOURS):
        reset_conversation_context(session_id)
    last_interaction = now
    unified_state = None
    if USE_UNIFIED_ROUTER:
        unified_state = get_unified_state(session_id)
        state = ensure_flow_data(unified_state, "reservation", _blank_reservation_state())
        inquiry_state = ensure_flow_data(unified_state, "inquiry", _blank_inquiry_state())
    else:
        state = get_reservation_state(session_id)
        inquiry_state = get_inquiry_state(session_id)
    needs_followup = False
    detected_lang = detect_language(payload.message)
    # vedno osveži jezik seje, da se lahko sproti preklaplja
    set_state_field(state, "language", detected_lang)
    set_state_field(state, "session_id", session_id)

    def _yes_no_buttons() -> list[dict]:
        return [
            {"label": "Da ✅", "payload": "YES"},
            {"label": "Ne ❌", "payload": "NO"},
        ]

    def _sanitize_policy_response(text: str) -> str:
        def _finish(sentence_text: str) -> str:
            trimmed = sentence_text.strip()
            if not trimmed:
                return "Kako vam lahko pomagam."
            if trimmed[-1] in ".!?":
                return trimmed
            return trimmed + "."

        # Remove shop/catalog lines and unsolicited prompts/questions
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        filtered_lines = []
        for ln in lines:
            low = ln.lower()
            if low.startswith("trgovina:"):
                continue
            if any(tok in low for tok in ["ali želite", "če želite", "vas zanima", "če potrebujete", "kar povejte", "povejte,"]):
                continue
            if ln.endswith("?"):
                continue
            filtered_lines.append(ln)
        if not filtered_lines:
            merged_orig = " ".join(lines).strip()
            if not merged_orig:
                return "Kako vam lahko pomagam."
            parts_orig = [p.strip() for p in re.split(r"(?<=[.!?])\s+", merged_orig) if p.strip()]
            parts_orig = [p for p in parts_orig if not p.endswith("?")]
            if not parts_orig:
                return _finish(merged_orig)
            return _finish(" ".join(parts_orig[:4]))
        merged = " ".join(filtered_lines)
        # Limit to 4 sentences
        parts = re.split(r"(?<=[.!?])\s+", merged)
        parts = [p.strip() for p in parts if p.strip() and not p.strip().endswith("?")]
        if len(parts) > 4:
            parts = parts[:4]
        return _finish(" ".join(parts))

    def finalize(
        reply_text: str,
        intent_value: str,
        followup_flag: bool = False,
        buttons: list[dict] | None = None,
    ) -> ChatResponse:
        nonlocal needs_followup
        global conversation_history
        if USE_UNIFIED_ROUTER and unified_state is not None:
            _sync_unified_state(unified_state, state, inquiry_state)
        final_reply = reply_text
        # Apply strict policy for info/product responses (no offers, no questions, short)
        is_structured = (
            "\n" in final_reply
            or "•" in final_reply
            or "***" in final_reply
            or "📅" in final_reply
            or "👥" in final_reply
        )
        if STRICT_POLICY and any(k in intent_value for k in ["product", "info", "menu", "wine", "farm", "food"]) and not is_structured:
            # Pozdrava ne saniramo, sicer lahko pade na napačen fallback.
            if "pozdrav" not in intent_value and "greeting" not in intent_value:
                final_reply = _sanitize_policy_response(final_reply)
        flag = followup_flag or needs_followup or is_unknown_response(final_reply)
        if flag:
            final_reply = get_unknown_response(detected_lang)
        conv_id = reservation_service.log_conversation(
            session_id=session_id,
            user_message=payload.message,
            bot_response=final_reply,
            intent=intent_value,
            needs_followup=flag,
        )
        if flag:
            unknown_question_state[session_id] = {"question": payload.message, "conv_id": conv_id}
        conversation_history.append({"role": "assistant", "content": final_reply})
        if len(conversation_history) > 12:
            conversation_history = conversation_history[-12:]
        blocks: list[UIBlock] = [UIBlock(type="text", content=final_reply)]
        btns = list(buttons) if buttons else []
        if state.get("step") is not None and any(k in intent_value for k in ["reservation", "booking"]):
            if not any(str(b.get("payload")).lower() == "cancel_reservation" for b in btns):
                btns.append({"label": "Prekliči ❌", "payload": "CANCEL_RESERVATION"})
        if btns:
            button_models = [ActionButton(**btn) for btn in btns]
            blocks.append(UIBlock(type="buttons", content=button_models))
        return ChatResponse(
            reply=final_reply,
            blocks=blocks,
            intent=intent_value,
            session_id=session_id,
        )

    # Tourist override (allow outside booking flow when appropriate)
    tourist_reply = tourist_answer(payload.message)
    if (
        tourist_reply
        and not is_menu_query(payload.message)
        and not detect_info_intent(payload.message)
        and not detect_product_intent(payload.message)
        and not is_product_query(payload.message)
        and (state.get("step") is None or should_switch_from_reservation(payload.message, state))
    ):
        tourist_reply = maybe_translate(tourist_reply, detected_lang)
        return finalize(tourist_reply, "tourist_info", followup_flag=False)

    if is_switch_topic_command(payload.message):
        reset_reservation_state(state)
        reset_inquiry_state(inquiry_state)
        reset_availability_state(state)
        reply = "Seveda — zamenjamo temo. Kako vam lahko pomagam?"
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "switch_topic", followup_flag=False)

    # Pozdrav obravnavaj takoj, preden info policy začne rezati vprašalne dele.
    if is_greeting(payload.message):
        reply = get_greeting_response()
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "greeting", followup_flag=False)

    if USE_UNIFIED_ROUTER:
        lowered = payload.message.lower().strip()
        wine_followup_hint = (
            re.search(r"\bkater[aeio]\b", lowered)
            or "katera pa" in lowered
            or "katere pa" in lowered
            or "so to" in lowered
            or "ta vina" in lowered
        )
        if last_wine_query and wine_followup_hint:
            combined = f"{last_wine_query} {payload.message}"
            reply = answer_wine_question(combined)
            last_wine_query = combined
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "wine_followup_unified", followup_flag=False)

        if is_event_inquiry_request(payload.message) or (DISABLE_INQUIRY and is_inquiry_trigger(payload.message)):
            reply = f"Za tovrstna povpraševanja pišite na {INFO_EMAIL}."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_disabled_unified", followup_flag=False)

        if is_bulk_order_request(payload.message) and (is_product_query(payload.message) or detect_product_intent(payload.message)):
            reply = f"Za večja naročila pišite na {INFO_EMAIL}."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "bulk_order_email_unified", followup_flag=False)

        if is_explicit_cancel_command(payload.message) or is_escape_command(payload.message):
            reset_reservation_state(state)
            reset_inquiry_state(inquiry_state)
            reply = "V redu, postopek sem prekinil (preklical). Kako vam lahko pomagam?"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "flow_cancel_unified", followup_flag=False)

        # Active booking flow: only this branch can advance/update booking state.
        if state.get("step") is not None:
            step = state.get("step")
            msg = (payload.message or "").strip()
            slot_input = False
            if step == "awaiting_email" and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", msg):
                slot_input = True
            elif step == "awaiting_phone" and len(re.sub(r"\\D+", "", msg)) >= 7 and "?" not in msg:
                slot_input = True
            elif step == "awaiting_name" and "?" not in msg and len(msg.split()) >= 2:
                slot_input = True
            if slot_input:
                reply = handle_reservation_flow(payload.message, state)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "booking_continue_unified", followup_flag=False)

            switch_type = parse_reservation_type(payload.message)
            if switch_type in {"room", "table"} and switch_type != state.get("type"):
                reset_reservation_state(state)
                set_state_field(state, "type", switch_type)
                reply = handle_reservation_flow(payload.message, state)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "booking_switch_unified", followup_flag=False)

            # Soft interrupt inside booking: answer info/product and continue same step.
            info_key = detect_info_intent(payload.message)
            product_key = detect_product_intent(payload.message)
            if (
                info_key
                or product_key
                or is_menu_query(payload.message)
                or is_product_query(payload.message)
                or is_info_query(payload.message)
            ):
                if info_key == "vina":
                    answer = answer_wine_question(payload.message)
                    last_wine_query = payload.message
                elif info_key:
                    answer = get_info_response(info_key)
                    last_info_query = payload.message
                elif is_menu_query(payload.message):
                    answer = format_current_menu(
                        month_override=parse_month_from_text(payload.message) or parse_relative_month(payload.message),
                        force_full=is_full_menu_request(payload.message),

                        short_mode=SHORT_MODE,
                    )
                    last_menu_query = True
                elif product_key or is_product_query(payload.message):
                    answer = get_product_response(product_key) if product_key else answer_product_question(payload.message)
                    last_product_query = payload.message
                else:
                    answer = "Trenutno nimam podatkov o tem."

                cont = reservation_prompt_for_state(state, room_intro_text, table_intro_text)
                reply = f"{answer}\n\n---\n\n{cont}"
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "booking_interrupt_unified", followup_flag=False)

            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "booking_continue_unified", followup_flag=False)

        # No active booking: deterministic entry routing.
        reservation_type = parse_reservation_type(payload.message)
        if reservation_type in {"room", "table"} or is_reservation_related(payload.message):
            if reservation_type is None and not any(
                tok in lowered for tok in ["soba", "sobe", "noč", "noc", "miza", "mizo", "table", "kosilo"]
            ):
                reply = "Želite rezervirati **sobo** ali **mizo**?"
                reply = maybe_translate(reply, detected_lang)
                buttons = [
                    {"label": "Rezerviraj sobo 🛏️", "payload": "BOOK_ROOM"},
                    {"label": "Rezerviraj mizo 🍽️", "payload": "BOOK_TABLE"},
                ]
                return finalize(reply, "clarify_reservation", followup_flag=False, buttons=buttons)
            reset_reservation_state(state)
            set_state_field(state, "type", reservation_type or ("room" if "soba" in lowered or "noč" in lowered else "table"))
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "booking_start_unified", followup_flag=False)

        # Follow-up context for tourist questions (e.g. "kako pridem tja?" after ski answer).
        if last_info_query and any(tok in last_info_query.lower() for tok in ["smuči", "smuci", "areh", "pohorje"]) and any(
            tok in lowered for tok in ["kako pridem", "kako do", "tja", "na areh", "do areh", "do pohorja"]
        ):
            reply = "Do Areha in Mariborskega Pohorja najlažje pridete z avtom; vožnja traja približno 25–35 minut."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "tourist_followup_unified", followup_flag=False)

        info_key = detect_info_intent(payload.message)
        if info_key == "vina":
            reply = answer_wine_question(payload.message)
            last_wine_query = payload.message
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "wine_unified", followup_flag=False)
        if info_key:
            reply = get_info_response(info_key)
            last_info_query = payload.message
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "info_unified", followup_flag=False)

        if is_menu_query(payload.message):
            reply = format_current_menu(
                month_override=parse_month_from_text(payload.message) or parse_relative_month(payload.message),
                force_full=is_full_menu_request(payload.message),

                short_mode=SHORT_MODE,
            )
            last_menu_query = True
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "menu_unified", followup_flag=False)

        product_key = detect_product_intent(payload.message)
        if product_key or is_product_query(payload.message):
            reply = get_product_response(product_key) if product_key else answer_product_question(payload.message)
            last_product_query = payload.message
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_unified", followup_flag=False)

        # Safety net: keep high-value intents deterministic even if parser misses.
        if re.search(r"\b(vino|vina|vinska|vinsko|wine|wein)\b", lowered):
            reply = get_info_response("vina")
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "wine_keyword_unified", followup_flag=False)
        if re.search(r"\b(jahamo|jahati|jahanje|jaha|jah)\b", lowered):
            reply = get_info_response("jahanje")
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "riding_keyword_unified", followup_flag=False)
        if re.search(r"\b(zajc|zajcek|zajce|kunec)\b", lowered) or any(tok in lowered for tok in ["zajčk", "božam", "bozamo", "božat", "bozat"]):
            reply = get_info_response("zivali")
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "animals_keyword_unified", followup_flag=False)

        reply = "Trenutno nimam podatkov o tem."
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "fallback_unified", followup_flag=False)

    # Hard safety gate: with unified router enabled we must never execute legacy paths below.
    if USE_UNIFIED_ROUTER:
        reply = "Trenutno nimam podatkov o tem."
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "unified_hard_gate", followup_flag=False)

    # Strict policy: route special-event inquiries directly to email
    if STRICT_POLICY:
        lowered = payload.message.lower()
        if is_event_inquiry_request(payload.message):
            reply = f"Za tovrstna povpraševanja pišite na {INFO_EMAIL}."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_disabled", followup_flag=False)
        if detect_product_intent(payload.message) == "gibanica_narocilo" and not any(
            tok in lowered for tok in ["kaj je", "kaj pomeni"]
        ):
            reply = f"Tega izdelka ni v spletni trgovini. Pišite na {INFO_EMAIL}."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_unavailable", followup_flag=False)
        if is_bulk_order_request(payload.message) and (is_product_query(payload.message) or detect_product_intent(payload.message)):
            reply = f"Za večja naročila pišite na {INFO_EMAIL}."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "bulk_order_email", followup_flag=False)
        if DISABLE_INQUIRY and (
            is_inquiry_trigger(payload.message)
            or is_event_inquiry_request(payload.message)
        ):
            reply = f"Za tovrstna povpraševanja pišite na {INFO_EMAIL}."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_disabled", followup_flag=False)
        if state.get("step") is None and not state.get("type"):
            wine_followup_hint = (
                re.search(r"\bkater[aeio]\b", lowered)
                or "katera pa" in lowered
                or "katere pa" in lowered
                or "so to" in lowered
                or "ta vina" in lowered
            )
            wine_context = any(tok in lowered for tok in ["vino", "vina", "vin", "penina", "frankinja", "pinot", "rizling"])
            info_key = detect_info_intent(payload.message)
            if info_key == "vina" or (last_wine_query and wine_followup_hint and wine_context):
                combined = f"{last_wine_query} {payload.message}" if last_wine_query else payload.message
                wine_reply = answer_wine_question(combined)
                last_wine_query = combined
                last_product_query = None
                last_info_query = None
                last_menu_query = False
                wine_reply = maybe_translate(wine_reply, detected_lang)
                return finalize(wine_reply, "wine_strict", followup_flag=False)
            if info_key:
                if info_key == "pozdrav":
                    greeting_reply = get_greeting_response()
                    greeting_reply = maybe_translate(greeting_reply, detected_lang)
                    return finalize(greeting_reply, "greeting_strict", followup_flag=False)
                info_reply = get_info_response(info_key)
                info_reply = maybe_translate(info_reply, detected_lang)
                return finalize(info_reply, "info_strict", followup_flag=False)

            product_key = detect_product_intent(payload.message)
            if product_key:
                product_reply = get_product_response(product_key)
                product_reply = maybe_translate(product_reply, detected_lang)
                return finalize(product_reply, "product_strict", followup_flag=False)

    if state.get("awaiting_continue"):
        if is_negative(payload.message):
            reset_reservation_state(state)
            set_state_field(state, "awaiting_continue", False)
            reply = "V redu. Kako vam lahko pomagam?"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_interrupted", followup_flag=False)
        if is_affirmative(payload.message):
            set_state_field(state, "awaiting_continue", False)
            continuation = get_booking_continuation(state.get("step"), state)
            reply = f"Nadaljujmo z rezervacijo:\n{continuation}"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_continue", followup_flag=False)
        # če ni jasnega da/ne, spusti skozi in očisti flag
        set_state_field(state, "awaiting_continue", False)

    availability_followup = handle_availability_followup(
        payload.message,
        state,
        reservation_service,
        is_affirmative,
        is_negative,
        EXIT_KEYWORDS,
    )
    if availability_followup:
        availability_followup = maybe_translate(availability_followup, detected_lang)
        return finalize(availability_followup, "availability_followup", followup_flag=False)

    if USE_UNIFIED_ROUTER and state.get("step") is None and not inquiry_state.get("step"):
        if is_inquiry_trigger(payload.message):
            set_state_field(inquiry_state, "details", payload.message)
            set_state_field(inquiry_state, "step", "awaiting_deadline")
            reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_start", followup_flag=False)
        info_key = detect_info_intent(payload.message)
        if info_key:
            if info_key == "vina":
                reply = answer_wine_question(payload.message)
                last_wine_query = payload.message
                last_product_query = None
                last_info_query = None
                last_menu_query = False
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "wine", followup_flag=False)
            reply = get_info_response(info_key)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "info", followup_flag=False)
        if detect_product_intent(payload.message) or is_product_query(payload.message):
            key = detect_product_intent(payload.message)
            reply = get_product_response(key) if key else answer_product_question(payload.message)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_info", followup_flag=False)
        detected_type = parse_reservation_type(payload.message)
        if detected_type or is_reservation_related(payload.message):
            set_state_field(state, "type", detected_type or state.get("type") or ("room" if "soba" in payload.message.lower() else "table"))
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_start", followup_flag=False)

    availability_state = get_availability_state(state)
    if availability_state.get("active") and availability_state.get("can_reserve") and is_negative(payload.message):
        reset_availability_state(state)
        reply = "V redu. Kako vam lahko pomagam?"
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "availability_declined", followup_flag=False)

    last_bot_for_affirm = get_last_assistant_message()
    llm_affirm = (
        last_bot_mentions_reservation(last_bot_for_affirm)
        and is_confirmation_question(last_bot_for_affirm)
        and llm_is_affirmative(payload.message, last_bot_for_affirm, detected_lang)
    )
    if state.get("step") is None and (is_affirmative(payload.message) or llm_affirm):
        # Če smo govorili o izdelkih, "ja" pomeni naročilo -> daj povezavo do trgovine.
        last_user_msg = get_last_user_message()
        if last_bot_mentions_product_order(last_bot_for_affirm) or last_product_query or is_product_query(last_user_msg):
            reply = f"Super! Naročilo lahko oddate tukaj: {SHOP_URL}"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_order_link", followup_flag=False)
        # Če smo govorili o povpraševanju (teambuilding/poroka/catering), "ja" pomeni začetek inquiry.
        if inquiry_state.get("step") is None:
            last_bot_lower = last_bot_for_affirm.lower()
            inquiry_ctx = (
                is_inquiry_trigger(last_user_msg)
                or any(tok in last_bot_lower for tok in ["povpraš", "ponudb", "teambuilding", "porok", "catering", "pogostitev"])
            )
            if inquiry_ctx:
                set_state_field(inquiry_state, "details", last_user_msg or payload.message)
                set_state_field(inquiry_state, "step", "awaiting_deadline")
                reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "inquiry_start", followup_flag=False)
        availability_state = get_availability_state(state)
        if availability_state.get("active") and availability_state.get("can_reserve"):
            reply = start_reservation_from_availability(
                state,
                reservation_service,
                reset_reservation_state,
                handle_reservation_flow,
                reset_availability_state,
            )
            if reply:
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "availability_to_reservation", followup_flag=False)
        last_bot = last_bot_for_affirm.lower()
        if last_bot_mentions_reservation(last_bot):
            last_user = get_last_reservation_user_message()
            if last_bot:
                set_reservation_type_from_text(state, last_bot)
            if last_user:
                set_reservation_type_from_text(state, last_user)
            reply = handle_reservation_flow(last_user or payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_confirmed", followup_flag=False)

    if state.get("step") is None:
        last_bot = get_last_assistant_message().lower()
        has_room_context = any(token in last_bot for token in ["sobo", "soba", "preno", "room", "zimmer"])
        has_table_context = any(token in last_bot for token in ["mizo", "miza", "table"])
        date_hit = extract_date(payload.message) or extract_date_range(payload.message)
        people_hit = parse_people_count(payload.message).get("total")
        if date_hit and people_hit and (has_room_context or has_table_context):
            set_state_field(state, "type", "room" if has_room_context else "table")
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_context_start", followup_flag=False)

    if state.get("step") is not None:
        slot_input = False
        msg = (payload.message or "").strip()
        step = state.get("step")
        if step == "awaiting_email" and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", msg):
            slot_input = True
        elif step == "awaiting_phone" and len(re.sub(r"\D+", "", msg)) >= 7 and "?" not in msg:
            slot_input = True
        elif step == "awaiting_name" and "?" not in msg and len(msg.split()) >= 2:
            slot_input = True

        if is_explicit_cancel_command(payload.message):
            reset_reservation_state(state)
            reply = "V redu, rezervacijo sem preklical. Kako vam lahko pomagam?"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_cancelled", followup_flag=False)

        if USE_UNIFIED_ROUTER:
            decision = decide_route(payload.message)
            if decision.primary_intent == "GREETING":
                reply = handle_interrupt(get_greeting_response(), state.get("step"))
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "greeting_interrupt", followup_flag=False)
            if decision.primary_intent == "GOODBYE":
                reply = handle_interrupt(get_goodbye_response(), state.get("step"))
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "goodbye_interrupt", followup_flag=False)
            if decision.primary_intent == "BOOKING_TABLE" and state.get("type") != "table":
                reset_reservation_state(state)
                set_state_field(state, "type", "table")
                reply = handle_reservation_flow(payload.message, state)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "reservation_table_switch", followup_flag=False)
            if decision.primary_intent == "BOOKING_ROOM" and state.get("type") != "room":
                reset_reservation_state(state)
                set_state_field(state, "type", "room")
                reply = handle_reservation_flow(payload.message, state)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "reservation_room_switch", followup_flag=False)
            if decision.primary_intent == "INQUIRY" and decision.action == SwitchAction.HARD_SWITCH:
                reset_reservation_state(state)
                if DISABLE_INQUIRY:
                    reply = f"Za tovrstna povpraševanja pišite na {INFO_EMAIL}."
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "inquiry_disabled", followup_flag=False)
                set_state_field(inquiry_state, "details", payload.message)
                set_state_field(inquiry_state, "step", "awaiting_deadline")
                reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "inquiry_start", followup_flag=False)
            if decision.primary_intent == "WINE":
                wine_reply = answer_wine_question(payload.message)
                reply = handle_interrupt(wine_reply, state.get("step"))
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "wine_interrupt", followup_flag=False)
            if decision.primary_intent == "MENU":
                month_hint = parse_month_from_text(payload.message)
                menu_reply = format_current_menu(month_override=month_hint, force_full=is_full_menu_request(payload.message), short_mode=SHORT_MODE)
                reply = handle_interrupt(menu_reply, state.get("step"))
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "menu_interrupt", followup_flag=False)
        info_key = detect_info_intent(payload.message)
        if info_key and not slot_input:
            if info_key == "vina":
                reply = answer_wine_question(payload.message)
                last_wine_query = payload.message
                last_product_query = None
                last_info_query = None
                last_menu_query = False
            else:
                reply = get_info_response(info_key)
            reply = handle_interrupt(reply, state.get("step"))
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "info_interrupt", followup_flag=False)
        if (detect_product_intent(payload.message) or is_product_query(payload.message)) and not slot_input:
            key = detect_product_intent(payload.message)
            reply = get_product_response(key) if key else answer_product_question(payload.message)
            reply = handle_interrupt(reply, state.get("step"))
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_interrupt", followup_flag=False)
        if USE_UNIFIED_ROUTER:
            decision = decide_route(payload.message)
            if decision.action == SwitchAction.SOFT_INTERRUPT and decision.secondary_intent in {"INFO", "PRODUCT"}:
                if decision.secondary_intent == "INFO":
                    key = detect_info_intent(payload.message)
                    info_reply = get_info_response(key) if key else "Kako vam lahko pomagam?"
                    reply = handle_interrupt(info_reply, state.get("step"))
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "info_interrupt", followup_flag=False)
                if decision.secondary_intent == "PRODUCT":
                    key = detect_product_intent(payload.message)
                    product_reply = get_product_response(key) if key else answer_product_question(payload.message)
                    reply = handle_interrupt(product_reply, state.get("step"))
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "product_interrupt", followup_flag=False)
        generic_info_question = (
            ("?" in payload.message or is_info_only_question(payload.message) or is_info_query(payload.message))
            and not is_reservation_related(payload.message)
        )
        if generic_info_question and not slot_input:
            key = detect_info_intent(payload.message)
            if key == "vina":
                info_reply = answer_wine_question(payload.message)
                last_wine_query = payload.message
                last_product_query = None
                last_info_query = None
                last_menu_query = False
            else:
                info_reply = get_info_response(key) if key else answer_farm_info(payload.message)
            reply = handle_interrupt(info_reply, state.get("step"))
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "info_interrupt", followup_flag=False)
        reply = handle_reservation_flow(payload.message, state)
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "reservation_flow", followup_flag=False)

    wine_followup_message = payload.message.strip().lower()
    wine_followup_hint = (
        re.search(r"\bkater[aeio]\b", wine_followup_message)
        or "katera pa" in wine_followup_message
        or "katere pa" in wine_followup_message
        or "so to" in wine_followup_message
        or "ta vina" in wine_followup_message
    )
    wine_context_now = any(
        tok in wine_followup_message
        for tok in ["vino", "vina", "vin", "penina", "frankinja", "pinot", "rizling"]
    )
    info_key_now = detect_info_intent(payload.message)
    # Wine questions/followups have priority over generic info routing.
    if info_key_now == "vina" or (last_wine_query and wine_followup_hint and wine_context_now):
        combined = f"{last_wine_query} {payload.message}" if last_wine_query else payload.message
        reply = answer_wine_question(combined)
        last_wine_query = combined
        last_product_query = None
        last_info_query = None
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "wine_followup", followup_flag=False)

    if USE_UNIFIED_ROUTER:

        decision = decide_route(payload.message)
        if unified_state is not None:
            set_last_intent(unified_state, decision.primary_intent)

        in_active_flow = (
            state.get("step") is not None
            or inquiry_state.get("step") is not None
            or get_availability_state(state).get("active")
        )

        if decision.action == SwitchAction.SOFT_INTERRUPT and in_active_flow and decision.secondary_intent in {"INFO", "PRODUCT"}:
            if decision.secondary_intent == "INFO":
                key = detect_info_intent(payload.message)
                info_reply = get_info_response(key) if key else "Kako vam lahko pomagam?"
                reply = handle_interrupt(info_reply, state.get("step"))
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "info_interrupt", followup_flag=False)
            if decision.secondary_intent == "PRODUCT":
                key = detect_product_intent(payload.message)
                product_reply = get_product_response(key) if key else answer_product_question(payload.message)
                reply = handle_interrupt(product_reply, state.get("step"))
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "product_interrupt", followup_flag=False)

        if decision.action == SwitchAction.HARD_SWITCH:
            reset_reservation_state(state)
            reset_inquiry_state(inquiry_state)
            reset_availability_state(state)
            if unified_state is not None:
                reset_unified_state(unified_state)

            if decision.primary_intent == "BOOKING_TABLE":
                set_state_field(state, "type", "table")
                reply = handle_reservation_flow(payload.message, state)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "reservation_table_start", followup_flag=False)
            if decision.primary_intent == "BOOKING_ROOM":
                set_state_field(state, "type", "room")
                reply = handle_reservation_flow(payload.message, state)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "reservation_room_start", followup_flag=False)
            if decision.primary_intent == "INQUIRY":
                set_state_field(inquiry_state, "details", payload.message)
                set_state_field(inquiry_state, "step", "awaiting_deadline")
                reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "inquiry_start", followup_flag=False)
            if decision.primary_intent == "PRODUCT":
                key = detect_product_intent(payload.message)
                reply = get_product_response(key) if key else answer_product_question(payload.message)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "product_info", followup_flag=False)
            if decision.primary_intent == "INFO":
                key = detect_info_intent(payload.message)
                reply = get_info_response(key) if key else "Kako vam lahko pomagam?"
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "info", followup_flag=False)
            if decision.primary_intent == "GREETING":
                reply = get_greeting_response()
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "greeting", followup_flag=False)
            if decision.primary_intent == "GOODBYE":
                reply = get_goodbye_response()
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "goodbye", followup_flag=False)

        # Unified-only fallback path: do not continue into legacy router stack.
        if decision.primary_intent == "BOOKING_TABLE":
            set_state_field(state, "type", "table")
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_table_start", followup_flag=False)
        if decision.primary_intent == "BOOKING_ROOM":
            set_state_field(state, "type", "room")
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_room_start", followup_flag=False)
        if decision.primary_intent == "INQUIRY":
            if DISABLE_INQUIRY:
                reply = f"Za tovrstna povpraševanja pišite na {INFO_EMAIL}."
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "inquiry_disabled", followup_flag=False)
            set_state_field(inquiry_state, "details", payload.message)
            set_state_field(inquiry_state, "step", "awaiting_deadline")
            reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_start", followup_flag=False)
        if decision.primary_intent == "PRODUCT":
            key = detect_product_intent(payload.message)
            reply = get_product_response(key) if key else answer_product_question(payload.message)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_info", followup_flag=False)
        if decision.primary_intent == "INFO":
            key = detect_info_intent(payload.message)
            reply = get_info_response(key) if key else answer_farm_info(payload.message)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "info", followup_flag=False)
        if decision.primary_intent == "WINE":
            last_wine_query = payload.message
            last_product_query = None
            last_info_query = None
            last_menu_query = False
            reply = answer_wine_question(payload.message)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "wine", followup_flag=False)
        if decision.primary_intent == "MENU":
            month_hint = parse_month_from_text(payload.message)
            reply = format_current_menu(month_override=month_hint, force_full=is_full_menu_request(payload.message), short_mode=SHORT_MODE)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "menu", followup_flag=False)
        if decision.primary_intent == "GREETING":
            reply = get_greeting_response()
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "greeting", followup_flag=False)
        if decision.primary_intent == "GOODBYE":
            reply = get_goodbye_response()
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "goodbye", followup_flag=False)

        # conservative fallback in unified mode
        fallback_reply = "Trenutno nimam podatkov o tem."
        fallback_reply = maybe_translate(fallback_reply, detected_lang)
        return finalize(fallback_reply, "unified_fallback", followup_flag=False)

    # zabeležimo user vprašanje v zgodovino (omejimo na zadnjih 6 parov)
    conversation_history.append({"role": "user", "content": payload.message})
    if len(conversation_history) > 12:
        conversation_history = conversation_history[-12:]

    # inquiry flow
    if state.get("step") is None and inquiry_state.get("step"):
        inquiry_reply = handle_inquiry_flow(payload.message, inquiry_state, session_id)
        if inquiry_reply:
            inquiry_reply = maybe_translate(inquiry_reply, detected_lang)
            return finalize(inquiry_reply, "inquiry", followup_flag=False)

    if state.get("step") is None and is_inquiry_trigger(payload.message):
        if is_strong_inquiry_request(payload.message):
            set_state_field(inquiry_state, "details", payload.message.strip())
            set_state_field(inquiry_state, "step", "awaiting_deadline")
            reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_start", followup_flag=False)
        info_key = detect_info_intent(payload.message)
        if info_key:
            info_reply = get_info_response(info_key)
            consent = start_inquiry_consent(inquiry_state)
            reply = f"{info_reply}\n\n---\n\n{consent}"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_offer", followup_flag=False, buttons=_yes_no_buttons())
        inquiry_reply = start_inquiry_consent(inquiry_state)
        inquiry_reply = maybe_translate(inquiry_reply, detected_lang)
        return finalize(inquiry_reply, "inquiry_offer", followup_flag=False, buttons=_yes_no_buttons())

    # če je prejšnji odgovor bil "ne vem" in uporabnik pošlje email
    if session_id in unknown_question_state and is_email(payload.message):
        state = unknown_question_state.pop(session_id)
        email_value = payload.message.strip()
        conv_id = state.get("conv_id")
        if conv_id:
            reservation_service.update_followup_email(conv_id, email_value)
        reply = "Hvala! 📧 Vaš elektronski naslov sem si zabeležil. Odgovoril vam bom v najkrajšem možnem času."
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "followup_email", followup_flag=False)

    # V2 router/exec (opcijsko)
    if USE_FULL_KB_LLM:
        if is_availability_query(payload.message):
            availability_reply = handle_availability_query(payload.message, state, reservation_service)
            if availability_reply:
                availability_reply = maybe_translate(availability_reply, detected_lang)
                return finalize(availability_reply, "availability_check", followup_flag=False)
        if state.get("step") is None and is_booking_intent(payload.message):
            detected_type = parse_reservation_type(payload.message)
            if detected_type in {"room", "table"}:
                reset_reservation_state(state)
                set_state_field(state, "type", detected_type)
                reply = handle_reservation_flow(payload.message, state)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "booking_intent", followup_flag=False)
        if state.get("step") is not None:
            if should_switch_from_reservation(payload.message, state):
                reset_reservation_state(state)
                reply = _llm_answer_full_kb(payload.message, detected_lang)
                return finalize(reply, "switch_from_reservation", followup_flag=False)
            lowered_message = payload.message.lower()
            if is_inquiry_trigger(payload.message) and is_strong_inquiry_request(payload.message):
                reset_reservation_state(state)
                set_state_field(inquiry_state, "details", payload.message.strip())
                set_state_field(inquiry_state, "step", "awaiting_deadline")
                reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "inquiry_start", followup_flag=False)
            question_like = (
                "?" in payload.message
                or is_info_only_question(payload.message)
                or (is_info_query(payload.message) and not is_reservation_related(payload.message))
                or any(word in lowered_message for word in ["gospodar", "družin", "lastnik", "kmetij"])
            )
            if question_like:
                llm_reply = _llm_answer_full_kb(payload.message, detected_lang)
                continuation = get_booking_continuation(state.get("step"), state)
                llm_reply = f"{llm_reply}\n\n---\n\n📝 **Nadaljujemo z rezervacijo:**\n{continuation}"
                llm_reply = maybe_translate(llm_reply, detected_lang)
                return finalize(llm_reply, "info_during_reservation", followup_flag=False)
            reply = handle_reservation_flow(payload.message, state)
            return finalize(reply, "reservation", followup_flag=False)
        if is_ambiguous_reservation_request(payload.message):
            reply = "Želite rezervirati **sobo** ali **mizo**?"
            reply = maybe_translate(reply, detected_lang)
            buttons = [
                {"label": "Rezerviraj sobo 🛏️", "payload": "BOOK_ROOM"},
                {"label": "Rezerviraj mizo 🍽️", "payload": "BOOK_TABLE"},
            ]
            return finalize(reply, "clarify_reservation", followup_flag=False, buttons=buttons)
        if is_ambiguous_inquiry_request(payload.message):
            reply = (
                "Ali želite, da zabeležim **povpraševanje/naročilo**? "
                "Če da, prosim napišite **količino** in **rok**."
            )
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "clarify_inquiry", followup_flag=False)
        availability_reply = handle_availability_query(payload.message, state, reservation_service)
        if availability_reply:
            availability_reply = maybe_translate(availability_reply, detected_lang)
            return finalize(availability_reply, "availability_check", followup_flag=False)
        try:
            intent_result = _llm_route_reservation(payload.message)
        except Exception as exc:
            print(f"[LLM] routing failed: {exc}")
            intent_result = {"action": "NONE"}
        action = (intent_result or {}).get("action") or "NONE"
        if action in {"BOOKING_ROOM", "BOOKING_TABLE"}:
            reset_reservation_state(state)
            set_state_field(state, "type", "room" if action == "BOOKING_ROOM" else "table")
            reply = handle_reservation_flow(payload.message, state)
            return finalize(reply, action.lower(), followup_flag=False)
        info_key = detect_info_intent(payload.message)
        if info_key:
            info_reply = get_info_response(info_key)
            info_reply = maybe_translate(info_reply, detected_lang)
            return finalize(info_reply, "info_llm", followup_flag=False)
        # fallback: če LLM ne vrne action, uporabi osnovno heuristiko
        if any(token in payload.message.lower() for token in ["rezerv", "book", "booking", "reserve", "reservation", "zimmer"]) or is_reservation_typo(payload.message):
            if "mizo" in payload.message.lower() or "table" in payload.message.lower():
                reset_reservation_state(state)
                set_state_field(state, "type", "table")
                reply = handle_reservation_flow(payload.message, state)
                return finalize(reply, "booking_table_fallback", followup_flag=False)
            if "sobo" in payload.message.lower() or "room" in payload.message.lower() or "nočitev" in payload.message.lower():
                reset_reservation_state(state)
                set_state_field(state, "type", "room")
                reply = handle_reservation_flow(payload.message, state)
                return finalize(reply, "booking_room_fallback", followup_flag=False)
        llm_reply = _llm_answer_full_kb(payload.message, detected_lang)
        return finalize(llm_reply, "info_llm", followup_flag=False)

    if USE_ROUTER_V2:
        decision = route_message(
            payload.message,
            has_active_booking=state.get("step") is not None,
            booking_step=state.get("step"),
        )
        routing_info = decision.get("routing", {})
        print(f"[ROUTER_V2] intent={routing_info.get('intent')} conf={routing_info.get('confidence')} info={decision.get('context', {}).get('info_key')} product={decision.get('context', {}).get('product_category')} interrupt={routing_info.get('is_interrupt')}")
        info_key = decision.get("context", {}).get("info_key") or ""
        is_critical_info = info_key in CRITICAL_INFO_KEYS

        def _translate(txt: str) -> str:
            return maybe_translate(txt, detected_lang)

        def _info_resp(key: Optional[str], soft_sell: bool) -> str:
            reply_local = get_info_response(key or "")
            if (not STRICT_POLICY) and soft_sell and (key or "") in BOOKING_RELEVANT_KEYS:
                reply_local = f"{reply_local}\n\nŽelite, da pripravim **ponudbo**?"
            return reply_local

        def _product_resp(key: str) -> str:
            if STRICT_POLICY and is_bulk_order_request(payload.message):
                return f"Za večja naročila pišite na {INFO_EMAIL}."
            reply_local = strip_product_followup(get_product_response(key))
            return reply_local

        def _continuation(step_val: Optional[str], st: dict) -> str:
            return get_booking_continuation(step_val, st)

        # INFO brez kritičnih podatkov -> LLM/RAG odgovor (z možnostjo nadaljevanja rezervacije)
        if routing_info.get("intent") == "INFO" and not is_critical_info:
            llm_reply = _llm_answer(payload.message, conversation_history)
            if llm_reply:
                if routing_info.get("is_interrupt") and state.get("step"):
                    cont = _continuation(state.get("step"), state)
                    llm_reply = f"{llm_reply}\n\n---\n\n📝 **Nadaljujemo z rezervacijo:**\n{cont}"
                llm_reply = maybe_translate(llm_reply, detected_lang)
                if state.get("step") is None and is_unknown_response(llm_reply) and inquiry_state.get("step") is None:
                    inquiry_reply = start_inquiry_consent(inquiry_state)
                    inquiry_reply = maybe_translate(inquiry_reply, detected_lang)
                    return finalize(inquiry_reply, "inquiry_offer", followup_flag=False)
                return finalize(llm_reply, "info_llm", followup_flag=False)

        reply_v2 = execute_decision(
            decision=decision,
            message=payload.message,
            state=state,
            translate_fn=_translate,
            info_responder=_info_resp,
            product_responder=_product_resp,
            reservation_flow_fn=handle_reservation_flow,
            reset_fn=reset_reservation_state,
            continuation_fn=_continuation,
            general_handler=None,
        )
        if reply_v2:
            intent_v2 = decision.get("routing", {}).get("intent")
            if intent_v2 == "PRODUCT":
                last_product_query = payload.message
                last_wine_query = None
                last_info_query = None
                last_menu_query = False
            return finalize(reply_v2, decision.get("routing", {}).get("intent", "v2"), followup_flag=False)
        # Če nič ne ujame, poskusi LLM/RAG odgovor
        llm_reply = _llm_answer(payload.message, conversation_history)
        if llm_reply:
            llm_reply = maybe_translate(llm_reply, detected_lang)
            return finalize(llm_reply, "general_llm", followup_flag=False)
        # Če nič ne ujame, poskusi turistični RAG
        if state.get("step") is None:
            tourist_reply = tourist_answer(payload.message)
            if tourist_reply:
                tourist_reply = maybe_translate(tourist_reply, detected_lang)
                return finalize(tourist_reply, "tourist_info", followup_flag=False)
            # Nato semantični INFO odgovor iz knowledge baze
            semantic_reply = semantic_info_answer(payload.message)
            if semantic_reply:
                semantic_reply = maybe_translate(semantic_reply, detected_lang)
                return finalize(semantic_reply, "info_semantic", followup_flag=False)
            # Če še vedno nič, priznaj neznano in ponudi email
            if state.get("step") is None:
                if STRICT_POLICY:
                    reply = "Trenutno nimam podatkov o tem."
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "info_unknown", followup_flag=False)
                inquiry_reply = start_inquiry_consent(inquiry_state)
                inquiry_reply = maybe_translate(inquiry_reply, detected_lang)
                return finalize(inquiry_reply, "info_unknown", followup_flag=False)
            reply = random.choice(UNKNOWN_RESPONSES)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "info_unknown", followup_flag=False)
    if USE_UNIFIED_ROUTER:
        # Hard gate: pri vklopljenem unified routerju tukaj ustavimo vse legacy poti spodaj.
        # Če smo še v aktivnem flowu, vedno nadaljuj samo skozi reservation flow.
        if state.get("step") is not None:
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_unified_terminal", followup_flag=False)

        # V idle načinu daj prednost deterministicnim handlerjem.
        info_key = detect_info_intent(payload.message)
        if info_key:
            if info_key == "vina":
                reply = answer_wine_question(payload.message)
                reply = maybe_translate(reply, detected_lang)
                return finalize(reply, "wine_unified_terminal", followup_flag=False)
            reply = get_info_response(info_key)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "info_unified_terminal", followup_flag=False)

        if is_menu_query(payload.message):
            reply = format_current_menu(
                month_override=parse_month_from_text(payload.message) or parse_relative_month(payload.message),
                force_full=is_full_menu_request(payload.message),

                short_mode=SHORT_MODE,
            )
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "menu_unified_terminal", followup_flag=False)

        product_key = detect_product_intent(payload.message)
        if product_key or is_product_query(payload.message):
            reply = get_product_response(product_key) if product_key else answer_product_question(payload.message)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_unified_terminal", followup_flag=False)

        lowered = payload.message.lower().strip()
        if re.search(r"\b(vino|vina|vinska|vinsko|wine|wein)\b", lowered):
            reply = get_info_response("vina")
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "wine_keyword_unified_terminal", followup_flag=False)
        if re.search(r"\b(jahamo|jahati|jahanje|jaha|jah)\b", lowered):
            reply = get_info_response("jahanje")
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "riding_keyword_unified_terminal", followup_flag=False)
        if re.search(r"\b(zajc|zajcek|zajce|kunec)\b", lowered) or any(tok in lowered for tok in ["zajčk", "božam", "bozamo", "božat", "bozat"]):
            reply = get_info_response("zivali")
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "animals_keyword_unified_terminal", followup_flag=False)

        reply = "Trenutno nimam podatkov o tem."
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "unified_terminal_fallback", followup_flag=False)

    # Info ali produkt med aktivno rezervacijo: odgovor + nadaljevanje
    info_during = handle_info_during_booking(payload.message, state)
    if info_during:
        reply = maybe_translate(info_during, detected_lang)
        return finalize(reply, "info_during_reservation", followup_flag=False)

    # === ROUTER: Info intent detection ===
    info_key = detect_info_intent(payload.message)
    if info_key:
        reply = get_info_response(info_key)
        if (not STRICT_POLICY) and info_key in BOOKING_RELEVANT_KEYS:
            reply = f"{reply}\n\nŽelite, da pripravim **ponudbo**?"
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "info_static", followup_flag=False)
    # === KONEC ROUTER ===

    # Produktni intent brez LLM (samo če ni aktivne rezervacije)
    if state["step"] is None:
        product_key = detect_product_intent(payload.message)
        if product_key:
            if STRICT_POLICY and is_bulk_order_request(payload.message):
                reply = f"Za večja naročila pišite na {INFO_EMAIL}."
            else:
                reply = strip_product_followup(get_product_response(product_key))
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_static", followup_flag=False)

    # Guard: info-only vprašanja naj ne sprožijo rezervacije
    if state["step"] is None and is_info_only_question(payload.message):
        reply = random.choice(UNKNOWN_RESPONSES)
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "info_only", followup_flag=False)

    # Fuzzy router za rezervacije (robustno na tipkarske napake)
    router_intent = detect_router_intent(payload.message, state)

    # Zamenjava tipa rezervacije med aktivnim flowom (npr. "mizo bi" med room bookingom)
    if state["step"] is not None:
        current_type = state.get("type")
        lowered_msg = payload.message.lower()
        wants_table = any(tok in lowered_msg for tok in ["mizo", "miza", "mize", "table", "kosilo"])
        wants_room = any(tok in lowered_msg for tok in ["sobo", "soba", "sobe", "room", "nočitev"])
        # Če uporabnik želi drug tip kot trenutni, zamenjaj flow
        if wants_table and not wants_room and current_type != "table":
            reset_reservation_state(state)
            set_state_field(state, "type", "table")
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_switch_to_table", followup_flag=False)
        if wants_room and not wants_table and current_type != "room":
            reset_reservation_state(state)
            set_state_field(state, "type", "room")
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_switch_to_room", followup_flag=False)

    if router_intent == "booking_room" and state["step"] is None:
        reset_reservation_state(state)
        set_state_field(state, "type", "room")
        reply = handle_reservation_flow(payload.message, state)
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "reservation_router_room", followup_flag=False)
    if router_intent == "booking_table" and state["step"] is None:
        reset_reservation_state(state)
        set_state_field(state, "type", "table")
        reply = handle_reservation_flow(payload.message, state)
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "reservation_router_table", followup_flag=False)

    # Hrana/meni brez jasne rezervacijske namere
    if is_food_question_without_booking_intent(payload.message):
        reply = INFO_RESPONSES.get("menu_info", "Za informacije o meniju nas kontaktirajte.")
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "food_info", followup_flag=False)

    # aktivna rezervacija ima prednost, vendar omogoča izhod ali druga vprašanja
    if state["step"] is not None:
        if is_inquiry_trigger(payload.message) and is_strong_inquiry_request(payload.message):
            reset_reservation_state(state)
            set_state_field(inquiry_state, "details", payload.message.strip())
            set_state_field(inquiry_state, "step", "awaiting_deadline")
            reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_start", followup_flag=False)
        if is_escape_command(payload.message):
            reset_reservation_state(state)
            reply = "OK, prekinil sem rezervacijo."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_cancel", followup_flag=False)
        if payload.message.strip().lower() == "nadaljuj":
            prompt = reservation_prompt_for_state(state, room_intro_text, table_intro_text)
            reply = maybe_translate(prompt, detected_lang)
            return finalize(reply, "reservation_continue", followup_flag=False)
        lowered_message = payload.message.lower()
        question_like = (
            "?" in payload.message
            or is_info_only_question(payload.message)
            or is_info_query(payload.message)
            or any(word in lowered_message for word in ["gospodar", "družin", "lastnik", "kmetij"])
        )
        if question_like:
            if USE_FULL_KB_LLM:
                llm_reply = _llm_answer_full_kb(payload.message, detected_lang)
            else:
                llm_reply = _llm_answer(payload.message, conversation_history)
            if llm_reply:
                continuation = get_booking_continuation(state.get("step"), state)
                llm_reply = (
                    f"{llm_reply}\n\n---\n\n"
                    f"Želiš nadaljevati rezervacijo? (da/ne)\n"
                    f"📝 Trenutno čakamo:\n{continuation}"
                )
                set_state_field(state, "awaiting_continue", True)
                llm_reply = maybe_translate(llm_reply, detected_lang)
                return finalize(
                    llm_reply,
                    "info_during_reservation",
                    followup_flag=False,
                    buttons=_yes_no_buttons(),
                )
        if is_product_query(payload.message):
            reply = answer_product_question(payload.message)
            last_product_query = payload.message
            last_wine_query = None
            last_info_query = None
            last_menu_query = False
            reply = maybe_translate(reply, detected_lang)
            reply = f"{reply}\n\nŽeliš nadaljevati rezervacijo? (da/ne)"
            set_state_field(state, "awaiting_continue", True)
            return finalize(
                reply,
                "product_during_reservation",
                followup_flag=False,
                buttons=_yes_no_buttons(),
            )
        if is_info_query(payload.message):
            reply = answer_farm_info(payload.message)
            last_product_query = None
            last_wine_query = None
            last_info_query = payload.message
            last_menu_query = False
            reply = maybe_translate(reply, detected_lang)
            reply = f"{reply}\n\nŽeliš nadaljevati rezervacijo? (da/ne)"
            set_state_field(state, "awaiting_continue", True)
            return finalize(
                reply,
                "info_during_reservation",
                followup_flag=False,
                buttons=_yes_no_buttons(),
            )

        reply = handle_reservation_flow(payload.message, state)
        last_product_query = None
        last_wine_query = None
        last_info_query = None
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "reservation")

    intent = detect_intent(payload.message, state, last_product_query=last_product_query, last_wine_query=last_wine_query)

    if is_contact_request(payload.message) and last_info_query and has_wine_context(last_info_query):
        reply = (
            "Za vinske kleti nimam konkretnih kontaktov v bazi. "
            "Če želite, lahko priporočim nekaj kleti v okolici."
        )
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "wine_contact_fallback", followup_flag=False)

    if intent == "goodbye":
        reply = get_goodbye_response()
        last_product_query = None
        last_wine_query = None
        last_info_query = None
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "goodbye")

    if intent == "reservation":
        reply = handle_reservation_flow(payload.message, state)
        last_product_query = None
        last_wine_query = None
        last_info_query = None
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "reservation")

    # tedenska ponudba naj ima prednost pred vikend jedilnikom
    if intent == "weekly_menu":
        reply = answer_weekly_menu(payload.message)
        last_product_query = None
        last_wine_query = None
        last_info_query = payload.message
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "weekly_menu")

    if intent == "room_info":
        reply = """Seveda! 😊 Imamo tri prijetne družinske sobe:

🛏️ **Soba ALJAŽ** - soba z balkonom (2+2 osebi)
🛏️ **Soba JULIJA** - družinska soba z balkonom (2 odrasla + 2 otroka)  
🛏️ **Soba ANA** - družinska soba z dvema spalnicama (2 odrasla + 2 otroka)

**Cena**: 50€/osebo/noč z zajtrkom
**Večerja**: dodatnih 25€/osebo

Sobe so klimatizirane, Wi-Fi je brezplačen. Prijava ob 14:00, odjava ob 10:00.

Bi želeli rezervirati? Povejte mi datum in število oseb! 🗓️"""
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "room_info")

    if intent == "room_pricing":
        reply = answer_room_pricing(payload.message)
        last_product_query = None
        last_wine_query = None
        last_info_query = payload.message
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "room_pricing")

    if intent == "tourist_info":
        tourist_reply = tourist_answer(payload.message)
        if tourist_reply:
            detected_lang = detect_language(payload.message)
            if detected_lang == "en":
                reply = generate_llm_answer(
                    f"Translate this to English, keep it natural and friendly:\n{tourist_reply}",
                    history=[],
                )
            elif detected_lang == "de":
                reply = generate_llm_answer(
                    f"Translate this to German/Deutsch, keep it natural and friendly:\n{tourist_reply}",
                    history=[],
                )
            else:
                reply = tourist_reply
            last_product_query = None
            last_wine_query = None
            last_info_query = payload.message
            last_menu_query = False
            return finalize(reply, "tourist_info")

    month_hint = parse_month_from_text(payload.message) or parse_relative_month(payload.message)
    if is_menu_query(payload.message):
        reply = format_current_menu(month_override=month_hint, force_full=is_full_menu_request(payload.message), short_mode=SHORT_MODE)
        last_product_query = None
        last_wine_query = None
        last_info_query = None
        last_menu_query = True
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "menu")
    if month_hint is not None and intent == "default":
        reply = format_current_menu(month_override=month_hint, force_full=is_full_menu_request(payload.message), short_mode=SHORT_MODE)
        last_product_query = None
        last_wine_query = None
        last_info_query = None
        last_menu_query = True
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "menu")

    if intent == "product":
        reply = strip_product_followup(answer_product_question(payload.message))
        last_product_query = payload.message
        last_wine_query = None
        last_info_query = None
        last_menu_query = False
        reply = f"{reply}\n\nTrgovina: {SHOP_URL}"
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "product")

    if intent == "product_followup":
        reply = strip_product_followup(answer_product_question(payload.message))
        last_product_query = payload.message
        last_wine_query = None
        last_info_query = None
        last_menu_query = False
        reply = f"{reply}\n\nTrgovina: {SHOP_URL}"
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "product_followup")

    if intent == "farm_info":
        reply = answer_farm_info(payload.message)
        last_product_query = None
        last_wine_query = None
        last_info_query = payload.message
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "farm_info")

    if intent == "food_general":
        reply = answer_food_question(payload.message)
        last_product_query = None
        last_wine_query = None
        last_info_query = payload.message
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "food_general")

    if intent == "help":
        reply = get_help_response()
        last_product_query = None
        last_wine_query = None
        last_info_query = payload.message
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "help")

    if intent == "wine":
        reply = answer_wine_question(payload.message)
        last_product_query = None
        last_wine_query = payload.message
        last_info_query = None
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "wine")

    if intent == "wine_followup":
        combined = f"{last_wine_query} {payload.message}" if last_wine_query else payload.message
        reply = answer_wine_question(combined)
        last_wine_query = combined
        last_product_query = None
        last_info_query = None
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "wine_followup")

    try:
        effective_query = build_effective_query(payload.message)
        detected_lang = detect_language(payload.message)

        if detected_lang == "en":
            lang_hint = "\n\n[IMPORTANT: The user is writing in English. Respond in English.]"
            effective_query = effective_query + lang_hint
        elif detected_lang == "de":
            lang_hint = "\n\n[IMPORTANT: The user is writing in German. Respond in German/Deutsch.]"
            effective_query = effective_query + lang_hint

        scored = search_knowledge_scored(effective_query, top_k=1)
        top_score = scored[0][0] if scored else 0.0
        if top_score < GLOBAL_CONFIDENCE_THRESHOLD and not is_greeting(payload.message):
            reply = get_low_confidence_reply()
        else:
            reply = generate_llm_answer(effective_query, history=conversation_history)
        last_info_query = effective_query
    except Exception:
        reply = (
            "Trenutno imam tehnične težave pri dostopu do podatkov. "
            "Za natančne informacije prosim preverite www.kmetijapodgoro.si."
        )
        last_info_query = None
    last_product_query = None
    last_wine_query = None
    last_menu_query = False

    if intent == "default" and is_greeting(payload.message):
        reply = get_greeting_response()
    else:
        reply = append_today_hint(payload.message, reply)

    reply = maybe_translate(reply, detected_lang)
    return finalize(reply, intent)

@router.post("/stream")
def chat_stream(payload: ChatRequestWithSession):
    global conversation_history, last_interaction
    now = datetime.now()
    session_id = payload.session_id or "default"
    if last_interaction and now - last_interaction > timedelta(hours=SESSION_TIMEOUT_HOURS):
        reset_conversation_context(session_id)
    last_interaction = now
    state = get_reservation_state(session_id)
    inquiry_state = get_inquiry_state(session_id)
    availability_state = get_availability_state(state)
    detected_lang = detect_language(payload.message)
    try:
        info_key = detect_info_intent(payload.message)
        product_key = detect_product_intent(payload.message)
        _router_logger.info(
            json.dumps(
                {
                    "intent": "STREAM",
                    "confidence": 0.5,
                    "info_key": info_key,
                    "product_key": product_key,
                    "is_interrupt": bool(state.get("step") and (info_key or product_key)),
                    "booking_step": state.get("step"),
                    "message": payload.message[:200],
                    "metrics": {},
                },
                ensure_ascii=False,
            )
        )
    except Exception:
        pass

    if USE_UNIFIED_ROUTER:
        try:
            response = chat_endpoint(payload)
            reply_text = getattr(response, "reply", None) or "Seveda, z veseljem pomagam. Kaj vas zanima?"
        except Exception as exc:
            print(f"[STREAM] Failed to handle stream request: {exc}")
            reply_text = "Seveda, z veseljem pomagam. Kaj vas zanima?"
        return StreamingResponse(
            _stream_text_chunks(reply_text),
            media_type="text/plain",
        )

    def stream_and_log(reply_chunks):
        collected: list[str] = []
        for chunk in reply_chunks:
            collected.append(chunk)
            yield chunk
        final_reply = "".join(collected).strip() or "Seveda, z veseljem pomagam. Kaj vas zanima?"
        reservation_service.log_conversation(
            session_id=session_id,
            user_message=payload.message,
            bot_response=final_reply,
            intent="stream",
            needs_followup=False,
        )
        conversation_history.append({"role": "assistant", "content": final_reply})
        if len(conversation_history) > 12:
            conversation_history[:] = conversation_history[-12:]

    # Če uporabnik potrdi po rezervacijskem odgovoru, preusmeri v chat_endpoint
    if is_affirmative(payload.message) or (
        last_bot_mentions_reservation(get_last_assistant_message())
        and is_confirmation_question(get_last_assistant_message())
        and llm_is_affirmative(payload.message, get_last_assistant_message(), detected_lang)
    ):
        last_bot = get_last_assistant_message()
        if last_bot_mentions_reservation(last_bot) or get_last_reservation_user_message():
            response = chat_endpoint(payload)
            return StreamingResponse(
                _stream_text_chunks(response.reply),
                media_type="text/plain",
            )

    # Če je aktivna availability ali rezervacija, uporabimo obstoječo pot (brez pravega streama)
    if availability_state.get("active") or state.get("step") is not None or detect_intent(payload.message, state, last_product_query=last_product_query, last_wine_query=last_wine_query) == "reservation":
        response = chat_endpoint(payload)
        return StreamingResponse(
            _stream_text_chunks(response.reply),
            media_type="text/plain",
        )

    # inquiry flow mora prednostno delovati tudi v stream načinu
    if inquiry_state.get("step") or is_inquiry_trigger(payload.message):
        response = chat_endpoint(payload)
        return StreamingResponse(
            _stream_text_chunks(response.reply),
            media_type="text/plain",
        )

    if is_ambiguous_reservation_request(payload.message) or is_ambiguous_inquiry_request(payload.message):
        response = chat_endpoint(payload)
        return StreamingResponse(
            _stream_text_chunks(response.reply),
            media_type="text/plain",
        )
    if is_availability_query(payload.message):
        response = chat_endpoint(payload)
        return StreamingResponse(
            _stream_text_chunks(response.reply),
            media_type="text/plain",
        )

    if USE_FULL_KB_LLM:
        settings = Settings()
        conversation_history.append({"role": "user", "content": payload.message})
        if len(conversation_history) > 12:
            conversation_history = conversation_history[-12:]
        return StreamingResponse(
            stream_and_log(_llm_answer_full_kb_stream(payload.message, settings, detect_language(payload.message))),
            media_type="text/plain",
        )

    response = chat_endpoint(payload)
    return StreamingResponse(
        _stream_text_chunks(response.reply),
        media_type="text/plain",
    )
