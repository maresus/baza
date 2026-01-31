import re
import random
import json
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple
import uuid
import threading

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ChatResponse
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
from app.rag.chroma_service import answer_tourist_question, is_tourist_query
from app.services.router_agent import route_message
from app.services.executor_v2 import execute_decision
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
from app.utils.session_store import SessionStore, blank_chat_context
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
from brand_config import (
    BRAND_NAME,
    BRAND_SHORT,
    FAMILY,
    get_system_prompt_intro,
)
from app.services.interrupt_layer import (
    check_for_interrupt,
    build_interrupt_response,
)
from app.services.smart_router import classify_intent as smart_classify_intent
from app.services.language import (
    detect_language,
    maybe_translate,
    translate_reply,
    translate_response,
)
from app.services.validators import (
    is_affirmative,
    is_negative,
    is_escape_command,
    is_switch_topic_command,
    is_confirmation_question,
    is_email,
    extract_email,
    extract_phone,
    is_contact_request,
    is_greeting,
    is_goodbye,
    is_hours_question,
    is_menu_query,
    is_full_menu_request,
    is_unknown_response,
)
from app.services.responses import (
    GREETINGS,
    THANKS_RESPONSES,
    UNKNOWN_RESPONSES,
    get_greeting_response,
    get_goodbye_response,
    get_unknown_response,
)
from app.services.session import (
    blank_reservation_state,
    get_reservation_state,
    reset_reservation_state,
    reservation_states,
    blank_inquiry_state,
    get_inquiry_state,
    reset_inquiry_state,
    inquiry_states,
)
from app.services.menu import (
    SEASONAL_MENUS,
    WEEKLY_EXPERIENCES,
    MENU_INTROS,
    parse_month_from_text,
    parse_relative_month,
    format_current_menu,
    next_menu_intro,
)
from app.services.farm_info import (
    FARM_INFO,
    LOCATION_KEYWORDS,
    FARM_INFO_KEYWORDS,
    answer_farm_info,
)
from app.services.wine import WINE_LIST, WINE_KEYWORDS

router = APIRouter(prefix="/chat", tags=["chat"])
USE_ROUTER_V2 = True
USE_FULL_KB_LLM = False  # False = RAG (hitro), True = full KB (počasno)
INQUIRY_RECIPIENT = os.getenv("INQUIRY_RECIPIENT", "satlermarko@gmail.com")
SHORT_MODE = os.getenv("SHORT_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
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
    # Intro iz brand_config (družina, gospodar, živali)
    intro = get_system_prompt_intro(language)

    menu_and_rules = (
        "Preverjeni meniji (uporabi dobesedno, brez dodajanja novih jedi):\n"
        "Zimska srajčka (dec–feb):\n"
        "- Pohorska bunka in zorjen Frešerjev sir, hišna salama, paštetka iz domačih jetrc, zaseka, bučni namaz, hišni kruhek\n"
        "- Goveja župca z rezanci in jetrnimi rolicami ali koprivna juhica s čemažem in sirne lizike\n"
        "- Meso na plošči: pujskov hrbet, hrustljavi piščanec Pesek, piščančje kroglice z zelišči, mlado goveje meso z jabolki in rdečim vinom\n"
        "- Priloge: štukelj s skuto, ričota s pirino kašo in jurčki, pražen krompir iz šporheta na drva, mini pita s porom, ocvrte hruške \"Debeluške\", pomladna/zimska solata\n"
        f"- Sladica: Pohorska gibanica babice {FAMILY['grandmother']}\n\n"
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
        "Odgovarjaj prijazno, naravno in slovensko.\n"
    )
    return intro + menu_and_rules

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
GOODBYE_KEYWORDS = {
    "hvala",
    "najlepša hvala",
    "hvala lepa",
    "adijo",
    "nasvidenje",
    "na svidenje",
    "čao",
    "ciao",
    "bye",
    "goodbye",
    "lp",
    "lep pozdrav",
    "se vidimo",
    "vidimo se",
    "srečno",
    "vse dobro",
    "lahko noč",
}
# GREETINGS, THANKS_RESPONSES, UNKNOWN_RESPONSES moved to app.services.responses

reservation_service = ReservationService()

# Spletna trgovina (fallback za "ja" pri izdelkih)
SHOP_URL = os.getenv("SHOP_URL", "https://kovacnik.com/katalog")

# FARM_INFO, LOCATION_KEYWORDS, FARM_INFO_KEYWORDS moved to app.services.farm_info

FOOD_GENERAL_KEYWORDS = {"hrana", "jest", "jesti", "ponujate", "kuhate", "jedilnik?"}

HELP_KEYWORDS = {"pomoč", "help", "kaj znaš", "kaj znate", "kaj lahko", "možnosti"}
WEEKLY_KEYWORDS = {
    "teden",
    "tedensk",
    "čez teden",
    "med tednom",
    "sreda",
    "četrtek",
    "petek",
    "degustacij",
    "kulinarično",
    "doživetje",
    "4-hodn",
    "5-hodn",
    "6-hodn",
    "7-hodn",
    "4 hodn",
    "5 hodn",
    "6 hodn",
    "7 hodn",
    "štiri hod",
    "stiri hod",
    "pet hod",
    "šest hod",
    "sest hod",
    "sedem hod",
    "4-hodni meni",
    "5-hodni meni",
    "6-hodni meni",
    "7-hodni meni",
}

PRICE_KEYWORDS = {
    "cena",
    "cene",
    "cenika",
    "cenik",
    "koliko stane",
    "koliko stal",
    "koliko košta",
    "koliko kosta",
    "ceno",
    "cenah",
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

# WINE_LIST, WINE_KEYWORDS moved to app.services.wine

# SEASONAL_MENUS, WEEKLY_EXPERIENCES moved to app.services.menu

# Session state management moved to app.services.session
# (_blank_reservation_state, _blank_inquiry_state, reservation_states, inquiry_states,
#  get_reservation_state, get_inquiry_state, reset_inquiry_state)

# Alias for backwards compatibility with internal code
_blank_reservation_state = blank_reservation_state

last_product_query: Optional[str] = None
last_info_query: Optional[str] = None
last_menu_query: bool = False
conversation_history: list[dict[str, str]] = []
last_shown_products: list[str] = []
last_interaction: Optional[datetime] = None
unknown_question_state: dict[str, dict[str, Any]] = {}
chat_session_id: str = str(uuid.uuid4())[:8]
session_store = SessionStore(os.getenv("REDIS_URL"))


def _load_session_context(session_id: str) -> dict[str, Any]:
    """Naloži per-session kontekst in nastavi module globals (legacy code)."""
    ctx = session_store.get(session_id)
    global conversation_history, last_product_query, last_wine_query, last_info_query, last_menu_query
    global last_shown_products, last_interaction, chat_session_id
    conversation_history = ctx.get("conversation_history", [])
    last_product_query = ctx.get("last_product_query")
    last_wine_query = ctx.get("last_wine_query")
    last_info_query = ctx.get("last_info_query")
    last_menu_query = ctx.get("last_menu_query", False)
    last_shown_products = ctx.get("last_shown_products", [])
    last_interaction = ctx.get("last_interaction")
    chat_session_id = ctx.get("chat_session_id") or str(uuid.uuid4())[:8]
    ctx["chat_session_id"] = chat_session_id
    return ctx


def _save_session_context(session_id: str, ctx: dict[str, Any]) -> None:
    """Shrani trenutne globals v per-session kontekst."""
    ctx.update(
        {
            "conversation_history": conversation_history,
            "last_product_query": last_product_query,
            "last_wine_query": last_wine_query,
            "last_info_query": last_info_query,
            "last_menu_query": last_menu_query,
            "last_shown_products": last_shown_products,
            "last_interaction": last_interaction,
            "chat_session_id": chat_session_id,
        }
    )
    session_store.set(session_id, ctx)

# MENU_INTROS, menu_intro_index moved to app.services.menu


def answer_wine_question(message: str) -> str:
    """Odgovarja na vprašanja o vinih SAMO iz WINE_LIST, z upoštevanjem followupov."""
    global last_shown_products

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


def answer_weekly_menu(message: str) -> str:
    """Odgovarja na vprašanja o tedenski ponudbi (sreda-petek)."""
    lowered = message.lower()

    requested_courses = None
    if "4" in message or "štiri" in lowered or "stiri" in lowered:
        requested_courses = 4
    elif "5" in message or "pet" in lowered:
        requested_courses = 5
    elif "6" in message or "šest" in lowered or "sest" in lowered:
        requested_courses = 6
    elif "7" in message or "sedem" in lowered:
        requested_courses = 7

    if requested_courses is None:
        lines = [
            "**KULINARIČNA DOŽIVETJA** (sreda–petek, od 13:00, min. 6 oseb)\n",
            "Na voljo imamo degustacijske menije:",
            "",
            f"🍽️ **4-hodni meni**: {WEEKLY_MENUS[4]['price']}€/oseba (vinska spremljava +{WEEKLY_MENUS[4]['wine_pairing']}€ za {WEEKLY_MENUS[4]['wine_glasses']} kozarce)",
            f"🍽️ **5-hodni meni**: {WEEKLY_MENUS[5]['price']}€/oseba (vinska spremljava +{WEEKLY_MENUS[5]['wine_pairing']}€ za {WEEKLY_MENUS[5]['wine_glasses']} kozarcev)",
            f"🍽️ **6-hodni meni**: {WEEKLY_MENUS[6]['price']}€/oseba (vinska spremljava +{WEEKLY_MENUS[6]['wine_pairing']}€ za {WEEKLY_MENUS[6]['wine_glasses']} kozarcev)",
            f"🍽️ **7-hodni meni**: {WEEKLY_MENUS[7]['price']}€/oseba (vinska spremljava +{WEEKLY_MENUS[7]['wine_pairing']}€ za {WEEKLY_MENUS[7]['wine_glasses']} kozarcev)",
            "",
            f"🥗 Posebne zahteve (vege, brez glutena): +{WEEKLY_INFO['special_diet_extra']}€/hod",
            "",
            f"📞 Rezervacije: {WEEKLY_INFO['contact']['phone']} ali {WEEKLY_INFO['contact']['email']}",
            "",
            "Povejte kateri meni vas zanima (4, 5, 6 ali 7-hodni) za podrobnosti!",
        ]
        return "\n".join(lines)

    menu = WEEKLY_MENUS[requested_courses]
    lines = [
        f"**{menu['name']}**",
        f"📅 {WEEKLY_INFO['days'].upper()}, {WEEKLY_INFO['time']}",
        f"👥 Minimum {WEEKLY_INFO['min_people']} oseb",
        "",
    ]

    for i, course in enumerate(menu["courses"], 1):
        wine_text = f" 🍷 _{course['wine']}_" if course["wine"] else ""
        lines.append(f"**{i}.** {course['dish']}{wine_text}")

    lines.extend(
        [
            "",
            f"💰 **Cena: {menu['price']}€/oseba**",
            f"🍷 Vinska spremljava: +{menu['wine_pairing']}€ ({menu['wine_glasses']} kozarcev)",
            f"🥗 Vege/brez glutena: +{WEEKLY_INFO['special_diet_extra']}€/hod",
            "",
            f"📞 Rezervacije: {WEEKLY_INFO['contact']['phone']} ali {WEEKLY_INFO['contact']['email']}",
        ]
    )

    return "\n".join(lines)


def detect_intent(message: str, state: dict[str, Optional[str | int]]) -> str:
    global last_product_query, last_wine_query
    lower_message = message.lower()

    # 1) nadaljevanje rezervacije ima vedno prednost
    if state["step"] is not None:
        if is_menu_query(message):
            return "menu"
        if is_hours_question(message):
            return "farm_info"
        return "reservation"

    # vprašanja o odpiralnem času / zajtrk/večerja
    if is_hours_question(message):
        return "farm_info"

    # koliko sob imate -> info, ne rezervacija
    if re.search(r"koliko\s+soba", lower_message) or re.search(r"koliko\s+sob", lower_message):
        return "room_info"

    # Rezervacija - fuzzy match (tudi s tipkarskimi napakami)
    rezerv_patterns = ["rezerv", "rezev", "rezer", "book", "buking", "bokking", "reserve", "reservation"]
    soba_patterns = ["sobo", "sobe", "soba", "room"]
    miza_patterns = ["mizo", "mize", "miza", "table"]
    has_rezerv = any(p in lower_message for p in rezerv_patterns)
    has_soba = any(p in lower_message for p in soba_patterns)
    has_miza = any(p in lower_message for p in miza_patterns)
    if has_rezerv and (has_soba or has_miza or "nočitev" in lower_message or "nocitev" in lower_message):
        return "reservation"
    if is_reservation_typo(message) and (has_soba or has_miza):
        return "reservation"
    if any(phrase in lower_message for phrase in RESERVATION_START_PHRASES):
        return "reservation"

    # goodbye/hvala
    if is_goodbye(message):
        return "goodbye"

    # jedilnik / meni naj ne sproži rezervacije
    if is_menu_query(message):
        return "menu"

    # SOBE - posebej pred rezervacijo
    sobe_keywords = ["sobe", "soba", "sobo", "nastanitev", "prenočitev", "nočitev nočitve", "rooms", "room", "accommodation"]
    if any(kw in lower_message for kw in sobe_keywords) and "rezerv" not in lower_message and "book" not in lower_message:
        return "room_info"

    # vino intent
    if any(keyword in lower_message for keyword in WINE_KEYWORDS):
        return "wine"

    # vino followup (če je bila prejšnja interakcija o vinih)
    if last_wine_query and any(
        phrase in lower_message for phrase in ["še", "še kakšn", "še kater", "kaj pa", "drug"]
    ):
        return "wine_followup"

    # cene sob
    if any(word in lower_message for word in PRICE_KEYWORDS):
        if any(word in lower_message for word in ["sob", "nočitev", "nocitev", "noč", "spanje", "bivanje"]):
            return "room_pricing"

    # tedenska ponudba (degustacijski meniji) – pred jedilnikom
    if any(word in lower_message for word in WEEKLY_KEYWORDS):
        return "weekly_menu"
    if re.search(r"\b[4-7]\s*-?\s*hodn", lower_message):
        return "weekly_menu"

    # 3) info o kmetiji / kontakt
    if any(keyword in lower_message for keyword in FARM_INFO_KEYWORDS):
        return "farm_info"

    if is_tourist_query(message):
        return "tourist_info"

    # 3) produktna vprašanja (salama, bunka, marmelada, paket, vino …)
    if any(stem in lower_message for stem in PRODUCT_STEMS):
        return "product"

    # 4) kratko nadaljevanje produktnega vprašanja
    if last_product_query and any(
        phrase in lower_message for phrase in PRODUCT_FOLLOWUP_PHRASES
    ):
        return "product_followup"

    # 5) info vprašanja (kje, soba, nočitve …)
    if any(keyword in lower_message for keyword in INFO_KEYWORDS):
        return "info"
    # 6) splošna hrana (ne jedilnik)
    if any(word in lower_message for word in FOOD_GENERAL_KEYWORDS) and not is_menu_query(message):
        return "food_general"
    # 7) pomoč
    if any(word in lower_message for word in HELP_KEYWORDS):
        return "help"
    # 9) tedenska ponudba
    if any(word in lower_message for word in WEEKLY_KEYWORDS):
        return "weekly_menu"
    return "default"


def handle_info_during_booking(message: str, session_state: dict) -> Optional[str]:
    """
    Če je booking aktiven in uporabnik vpraša info ali produkt, odgovorimo + nadaljujemo flow.
    """
    if not session_state or session_state.get("step") is None:
        return None

    info_key = detect_info_intent(message)
    if info_key:
        info_response = get_info_response(info_key)
        continuation = get_booking_continuation(session_state.get("step"), session_state)
        return f"{info_response}\n\n---\n\n📝 **Nadaljujemo z rezervacijo:**\n{continuation}"

    product_key = detect_product_intent(message)
    if product_key:
        product_response = get_product_response(product_key)
        if is_bulk_order_request(message):
            product_response = f"{product_response}\n\nZa večja naročila nam pišite na info@kovacnik.com."
        continuation = get_booking_continuation(session_state.get("step"), session_state)
        return f"{product_response}\n\n---\n\n📝 **Nadaljujemo z rezervacijo:**\n{continuation}"

    return None


def is_booking_intent(message: str) -> bool:
    lowered = message.lower()
    if any(phrase in lowered for phrase in RESERVATION_START_PHRASES):
        return True
    intent_tokens = ["rad bi", "rada bi", "želim", "zelim", "hočem", "hocem", "imel bi", "imela bi"]
    has_intent = any(tok in lowered for tok in intent_tokens)
    has_type = parse_reservation_type(message) in {"room", "table"}
    return has_intent and has_type


def should_switch_from_reservation(message: str, state: dict[str, Optional[str | int]]) -> bool:
    lowered = message.lower()
    if is_reservation_related(message):
        return False
    if is_affirmative(message) or lowered in {"ne", "no"}:
        return False
    if extract_date(message) or extract_date_range(message) or extract_time(message):
        return False
    if parse_people_count(message).get("total"):
        return False
    if state.get("step") in {"awaiting_phone", "awaiting_email"}:
        return False
    if detect_info_intent(message) or detect_product_intent(message) or is_menu_query(message) or is_hours_question(message):
        return True
    if is_tourist_query(message):
        return True
    return False

def is_product_followup(message: str) -> bool:
    lowered = message.lower()
    if not last_product_query:
        return False
    if any(phrase in lowered for phrase in PRODUCT_FOLLOWUP_PHRASES):
        return True
    return False

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


# extract_email, extract_phone, is_hours_question, is_menu_query
# moved to app.services.validators


# parse_month_from_text, parse_relative_month, next_menu_intro
# moved to app.services.menu


# answer_farm_info moved to app.services.farm_info


def answer_food_question(message: str) -> str:
    lowered = message.lower()
    if "alerg" in lowered or "gob" in lowered or "glive" in lowered:
        return (
          "Alergije uredimo brez težav. Ob rezervaciji zapiši alergije (npr. brez gob) ali povej osebju ob prihodu, da lahko prilagodimo jedi. "
          "Želiš, da označim alergije v tvoji rezervaciji?"
        )
    return (
        "Pripravljamo tradicionalne pohorske jedi iz lokalnih sestavin.\n"
        "Vikend kosila (sob/ned): 36€ odrasli, otroci 4–12 let -50%, vključuje predjed, juho, glavno jed, priloge in sladico.\n"
        "Če želite videti aktualni sezonski jedilnik, recite 'jedilnik'. Posebne zahteve (vege, brez glutena) uredimo ob rezervaciji."
    )


def answer_room_pricing(message: str) -> str:
    """Odgovori na vprašanja o cenah sob."""
    lowered = message.lower()

    if "večerj" in lowered or "penzion" in lowered:
        return (
            f"**Penzionska večerja**: {ROOM_PRICING['dinner_price']}€/oseba\n"
            f"Vključuje: {ROOM_PRICING['dinner_includes']}\n\n"
            "⚠️ Ob ponedeljkih in torkih večerij ni.\n"
            f"Večerja je ob {ROOM_PRICING['dinner_time']}."
        )

    if "otro" in lowered or "popust" in lowered or "otrok" in lowered:
        return (
            "**Popusti za otroke:**\n"
            "• Otroci do 4 let: **brezplačno**\n"
            "• Otroci 4-12 let: **50% popust**\n"
            "• Otroci nad 12 let: polna cena"
        )

    return (
        f"**Cena sobe**: {ROOM_PRICING['base_price']}€/nočitev na odraslo osebo (min. {ROOM_PRICING['min_adults']} odrasli)\n\n"
        f"**Zajtrk**: vključen ({ROOM_PRICING['breakfast_time']})\n"
        f"**Večerja**: {ROOM_PRICING['dinner_price']}€/oseba ({ROOM_PRICING['dinner_includes']})\n\n"
        "**Popusti za otroke:**\n"
        "• Do 4 let: brezplačno\n"
        "• 4-12 let: 50% popust\n\n"
        f"**Minimalno bivanje**: {ROOM_PRICING['min_nights_other']} nočitvi (poleti {ROOM_PRICING['min_nights_summer']})\n"
        f"**Prijava**: {ROOM_PRICING['check_in']}, **Odjava**: {ROOM_PRICING['check_out']}\n\n"
        "Za rezervacijo povejte datum in število oseb!"
    )


def get_help_response() -> str:
    return (
        "Pomagam vam lahko z:\n"
        "📅 Rezervacije – sobe ali mize za vikend kosilo\n"
        "🍽️ Jedilnik – aktualni sezonski meni\n"
        "🏠 Info o kmetiji – lokacija, kontakt, delovni čas\n"
        "🛒 Izdelki – salame, marmelade, vina, likerji\n"
        "❓ Vprašanja – karkoli o naši ponudbi\n"
        "Kar vprašajte!"
    )


# is_full_menu_request moved to app.services.validators


# format_current_menu moved to app.services.menu


def detect_reset_request(message: str) -> bool:
    lowered = message.lower()
    reset_words = [
        "reset",
        "začni znova",
        "zacni znova",
        "od začetka",
        "od zacetka",
        "zmota",
        "zmoto",
        "zmotu",
        "zmotil",
        "zmotila",
        "zgresil",
        "zgrešil",
        "zgrešila",
        "zgresila",
        "napačno",
        "narobe",
        "popravi",
        "nova rezervacija",
    ]
    exit_words = [
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
    ]
    return any(word in lowered for word in reset_words + exit_words)


# is_escape_command, is_switch_topic_command, is_affirmative, is_negative, is_contact_request
# moved to app.services.validators


def has_wine_context(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["vinska klet", "vinograd", "klet", "degustacij", "vino", "vinar"])


# is_confirmation_question moved to app.services.validators


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
        state["type"] = "table"
    elif any(token in lowered for token in ["sobo", "soba", "preno", "room", "zimmer"]):
        state["type"] = "room"


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


# get_greeting_response, get_goodbye_response, get_unknown_response
# moved to app.services.responses


def normalize_loop_text(text: str) -> str:
    """Normalizira besedilo za primerjavo ponavljanja."""
    lowered = text.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^a-z0-9čćšžđáàäéèëíìïóòöúùüščž ]", "", lowered)
    return lowered


def append_shop_link_if_needed(reply: str) -> str:
    if "Trgovina:" in reply or SHOP_URL in reply:
        return reply
    return f"{reply}\n\nTrgovina: {SHOP_URL}"


# is_email moved to app.services.validators


# reset_reservation_state moved to app.services.session


def start_inquiry_consent(state: dict[str, Optional[str]]) -> str:
    state["step"] = "awaiting_consent"
    return (
        "Žal nimam dovolj informacij. "
        "Lahko zabeležim povpraševanje in ga posredujem ekipi. "
        "Želite to? (da/ne)"
    )


def handle_inquiry_flow(message: str, state: dict[str, Optional[str]], session_id: str) -> Optional[str]:
    text = message.strip()
    lowered = text.lower()
    step = state.get("step")
    if is_info_query(message) or detect_info_intent(message):
        info_reply = answer_farm_info(message)
        return f"{info_reply}\n\n---\n\nŽelite nadaljevati povpraševanje? (da/ne)"
    if is_product_query(message):
        product_reply = answer_product_question(message)
        product_reply = strip_product_followup(product_reply)
        product_reply = append_shop_link_if_needed(product_reply)
        return f"{product_reply}\n\n---\n\nŽelite nadaljevati povpraševanje? (da/ne)"
    if is_negative(message):
        reset_inquiry_state(state)
        return "V redu, prekinil sem povpraševanje. Kako vam lahko še pomagam?"
    if is_escape_command(message) or is_switch_topic_command(message):
        reset_inquiry_state(state)
        return "V redu, prekinil sem povpraševanje. Kako vam lahko še pomagam?"

    if step == "awaiting_consent":
        if lowered in {"da", "ja", "seveda", "lahko", "ok"}:
            state["step"] = "awaiting_details"
            return "Odlično. Prosim opišite, kaj točno želite (količina, izdelek, storitev)."
        if lowered in {"ne", "ne hvala", "ni treba"}:
            reset_inquiry_state(state)
            return "V redu. Če želite, lahko vprašate še kaj drugega."
        return "Želite, da zabeležim povpraševanje? Odgovorite z 'da' ali 'ne'."

    if step == "awaiting_details":
        if text:
            state["details"] = (state.get("details") or "")
            if state["details"]:
                state["details"] += "\n" + text
            else:
                state["details"] = text
        state["step"] = "awaiting_deadline"
        return "Hvala! Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"

    if step == "awaiting_deadline":
        if any(word in lowered for word in ["ni", "ne vem", "kadar koli", "vseeno", "ni pomembno"]):
            state["deadline"] = ""
        else:
            state["deadline"] = text
        state["step"] = "awaiting_contact"
        return "Super. Prosim še kontakt (ime, telefon, email)."

    if step == "awaiting_contact":
        state["contact_raw"] = text
        email = extract_email(text)
        phone = extract_phone(text)
        state["contact_email"] = email or state.get("contact_email") or ""
        state["contact_phone"] = phone or state.get("contact_phone") or ""
        state["contact_name"] = state.get("contact_name") or ""
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
            "Novo povpraševanje – Kovačnik",
            summary,
        )
        reset_inquiry_state(state)
        return "Hvala! Povpraševanje sem zabeležil in ga posredoval. Odgovorimo vam v najkrajšem možnem času."

    return None


def reset_conversation_context(session_id: Optional[str] = None) -> None:
    """Počisti začasne pogovorne podatke in ponastavi sejo."""
    global conversation_history, last_product_query, last_wine_query, last_info_query, last_menu_query
    global last_shown_products, chat_session_id, unknown_question_state, last_interaction
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
    last_shown_products = []
    chat_session_id = str(uuid.uuid4())[:8]
    last_interaction = None
    if session_id:
        session_store.set(session_id, blank_chat_context())


def generate_confirmation_email(state: dict[str, Optional[str | int]]) -> str:
    subject = "Zadeva: Rezervacija – Domačija Kovačnik"
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


def parse_reservation_type(message: str) -> Optional[str]:
    lowered = message.lower()

    def _has_term(term: str) -> bool:
        if " " in term:
            return term in lowered
        return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered) is not None

    # soba - slovensko, angleško, nemško
    room_keywords = [
        # slovensko
        "soba",
        "sobe",
        "sobo",
        "sob",
        "nočitev",
        "prenocitev",
        "noč",
        "prenočiti",
        "prespati",
        # angleško
        "room",
        "rooms",
        "stay",
        "overnight",
        "night",
        "accommodation",
        "sleep",
        # nemško
        "zimmer",
        "übernachtung",
        "übernachten",
        "nacht",
        "schlafen",
        "unterkunft",
    ]
    if any(_has_term(word) for word in room_keywords):
        return "room"

    # miza - slovensko, angleško, nemško
    table_keywords = [
        # slovensko
        "miza",
        "mizo",
        "mize",
        "rezervacija mize",
        "kosilo",
        "večerja",
        "kosilu",
        "mizico",
        "jest",
        "jesti",
        # angleško
        "table",
        "lunch",
        "dinner",
        "meal",
        "eat",
        "dining",
        "restaurant",
        # nemško
        "tisch",
        "mittagessen",
        "abendessen",
        "essen",
        "speisen",
        "restaurant",
    ]
    if any(_has_term(word) for word in table_keywords):
        return "table"
    return None


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


# is_greeting moved to app.services.validators


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
    ctx = _load_session_context(session_id)
    if last_interaction and now - last_interaction > timedelta(hours=SESSION_TIMEOUT_HOURS):
        reset_conversation_context(session_id)
        ctx = _load_session_context(session_id)
    last_interaction = now
    state = get_reservation_state(session_id)
    inquiry_state = get_inquiry_state(session_id)
    needs_followup = False
    detected_lang = detect_language(payload.message)
    # vedno osveži jezik seje, da se lahko sproti preklaplja
    state["language"] = detected_lang
    state["session_id"] = session_id

    # Guard: če uporabnik jasno spremeni namen, prekinemo aktivni flow
    if USE_ROUTER_V2 and (state.get("step") is not None or inquiry_state.get("step")):
        decision_guard = route_message(
            payload.message,
            has_active_booking=state.get("step") is not None,
            booking_step=state.get("step"),
        )
        routing_guard = decision_guard.get("routing", {})
        intent_guard = routing_guard.get("intent")
        conf_guard = routing_guard.get("confidence", 0)
        if intent_guard in {"INFO", "PRODUCT"} and conf_guard >= 0.8 and state.get("step") is not None:
            reset_reservation_state(state)
        if intent_guard in {"BOOKING_ROOM", "BOOKING_TABLE"} and conf_guard >= 0.8 and inquiry_state.get("step"):
            reset_inquiry_state(inquiry_state)

    def finalize(reply_text: str, intent_value: str, followup_flag: bool = False) -> ChatResponse:
        nonlocal needs_followup
        global conversation_history
        final_reply = reply_text
        last_bot = get_last_assistant_message()
        if last_bot and normalize_loop_text(last_bot) == normalize_loop_text(final_reply):
            final_reply = "Oprostite, da se ponavljam. Napišite prosim bolj konkretno (npr. izdelek, datum ali storitev)."
        if is_product_query(payload.message) or intent_value in {"product", "product_followup", "product_static", "product_order_link"}:
            final_reply = append_shop_link_if_needed(final_reply)
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
        _save_session_context(session_id, ctx)
        return ChatResponse(reply=final_reply)

    # === SMART ROUTER (LLM-based) ===
    # Uporabi samo za nejasne ali mešane primere (hibridni routing)

    if is_switch_topic_command(payload.message):
        reset_reservation_state(state)
        reset_inquiry_state(inquiry_state)
        reset_availability_state(state)
        reply = "Seveda — zamenjamo temo. Kako vam lahko pomagam?"
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "switch_topic", followup_flag=False)

    if state.get("awaiting_continue"):
        if is_negative(payload.message):
            reset_reservation_state(state)
            state["awaiting_continue"] = False
            reply = "V redu. Kako vam lahko pomagam?"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_interrupted", followup_flag=False)
        if is_affirmative(payload.message):
            state["awaiting_continue"] = False
            continuation = get_booking_continuation(state.get("step"), state)
            reply = f"Nadaljujmo z rezervacijo:\n{continuation}"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_continue", followup_flag=False)
        # če ni jasnega da/ne, spusti skozi in očisti flag
        state["awaiting_continue"] = False

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
            reply = f"Trgovina: {SHOP_URL}"
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
                inquiry_state["details"] = last_user_msg or payload.message
                inquiry_state["step"] = "awaiting_deadline"
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
            state["type"] = "room" if has_room_context else "table"
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_context_start", followup_flag=False)

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
        if is_reservation_related(payload.message):
            pass
        elif is_product_query(payload.message):
            pass
        elif is_strong_inquiry_request(payload.message):
            inquiry_state["details"] = payload.message.strip()
            inquiry_state["step"] = "awaiting_deadline"
            reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_start", followup_flag=False)
        info_key = detect_info_intent(payload.message)
        if info_key:
            info_reply = get_info_response(info_key)
            consent = start_inquiry_consent(inquiry_state)
            reply = f"{info_reply}\n\n---\n\n{consent}"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_offer", followup_flag=False)
        inquiry_reply = start_inquiry_consent(inquiry_state)
        inquiry_reply = maybe_translate(inquiry_reply, detected_lang)
        return finalize(inquiry_reply, "inquiry_offer", followup_flag=False)

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
                state["type"] = detected_type
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
                inquiry_state["details"] = payload.message.strip()
                inquiry_state["step"] = "awaiting_deadline"
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
            return finalize(reply, "clarify_reservation", followup_flag=False)
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
            state["type"] = "room" if action == "BOOKING_ROOM" else "table"
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
                state["type"] = "table"
                reply = handle_reservation_flow(payload.message, state)
                return finalize(reply, "booking_table_fallback", followup_flag=False)
            if "sobo" in payload.message.lower() or "room" in payload.message.lower() or "nočitev" in payload.message.lower():
                reset_reservation_state(state)
                state["type"] = "room"
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
            if soft_sell and (key or "") in BOOKING_RELEVANT_KEYS:
                reply_local = f"{reply_local}\n\nŽelite, da pripravim **ponudbo**?"
            return reply_local

        def _product_resp(key: str) -> str:
            reply_local = strip_product_followup(get_product_response(key))
            if is_bulk_order_request(payload.message):
                reply_local = f"{reply_local}\n\nZa večja naročila nam pišite na info@kovacnik.com, da uskladimo količine in prevzem."
            reply_local = f"{reply_local}\n\nTrgovina: {SHOP_URL}"
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
            tourist_reply = answer_tourist_question(payload.message)
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
                inquiry_reply = start_inquiry_consent(inquiry_state)
                inquiry_reply = maybe_translate(inquiry_reply, detected_lang)
                return finalize(inquiry_reply, "info_unknown", followup_flag=False)
            reply = random.choice(UNKNOWN_RESPONSES)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "info_unknown", followup_flag=False)
    # Info ali produkt med aktivno rezervacijo: odgovor + nadaljevanje
    info_during = handle_info_during_booking(payload.message, state)
    if info_during:
        reply = maybe_translate(info_during, detected_lang)
        return finalize(reply, "info_during_reservation", followup_flag=False)

    # === ROUTER: Info intent detection ===
    info_key = detect_info_intent(payload.message)
    if info_key:
        reply = get_info_response(info_key)
        if info_key in BOOKING_RELEVANT_KEYS:
            reply = f"{reply}\n\nŽelite, da pripravim **ponudbo**?"
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "info_static", followup_flag=False)
    # === KONEC ROUTER ===

    # Produktni intent brez LLM (samo če ni aktivne rezervacije)
    if state["step"] is None:
        product_key = detect_product_intent(payload.message)
        if product_key:
            reply = strip_product_followup(get_product_response(product_key))
            if is_bulk_order_request(payload.message):
                reply = f"{reply}\n\nZa večja naročila nam pišite na info@kovacnik.com, da uskladimo količine in prevzem."
            reply = f"{reply}\n\nTrgovina: {SHOP_URL}"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "product_static", followup_flag=False)

    # Guard: info-only vprašanja naj ne sprožijo rezervacije
    if state["step"] is None and is_info_only_question(payload.message):
        reply = random.choice(UNKNOWN_RESPONSES)
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "info_only", followup_flag=False)

    # Fuzzy router za rezervacije (robustno na tipkarske napake)
    router_intent = detect_router_intent(payload.message, state)

    # === INTERRUPT LAYER ===
    # Če je aktiven booking flow in uporabnik vpraša INFO/PRODUCT vprašanje,
    # odgovori na vprašanje IN nadaljuj z bookingom (brez "Želiš nadaljevati? da/ne")
    if state["step"] is not None:
        interrupt_type = check_for_interrupt(payload.message, state)
        if interrupt_type:
            # Odgovori na vprašanje
            if interrupt_type == "PRODUCT":
                interrupt_answer = answer_product_question(payload.message)
            else:  # INFO
                interrupt_answer = answer_farm_info(payload.message)

            # Kombiniraj odgovor z resume promptom
            reply = build_interrupt_response(interrupt_answer, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, f"interrupt_{interrupt_type.lower()}", followup_flag=False)

    # Zamenjava tipa rezervacije med aktivnim flowom (npr. "mizo bi" med room bookingom)
    if state["step"] is not None:
        current_type = state.get("type")
        lowered_msg = payload.message.lower()
        wants_table = any(tok in lowered_msg for tok in ["mizo", "miza", "mize", "table", "kosilo"])
        wants_room = any(tok in lowered_msg for tok in ["sobo", "soba", "sobe", "room", "nočitev"])
        # Če uporabnik želi drug tip kot trenutni, zamenjaj flow
        if wants_table and not wants_room and current_type != "table":
            reset_reservation_state(state)
            state["type"] = "table"
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_switch_to_table", followup_flag=False)
        if wants_room and not wants_table and current_type != "room":
            reset_reservation_state(state)
            state["type"] = "room"
            reply = handle_reservation_flow(payload.message, state)
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_switch_to_room", followup_flag=False)

    if router_intent == "booking_room" and state["step"] is None:
        reset_reservation_state(state)
        state["type"] = "room"
        reply = handle_reservation_flow(payload.message, state)
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "reservation_router_room", followup_flag=False)
    if router_intent == "booking_table" and state["step"] is None:
        reset_reservation_state(state)
        state["type"] = "table"
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
            inquiry_state["details"] = payload.message.strip()
            inquiry_state["step"] = "awaiting_deadline"
            reply = "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "inquiry_start", followup_flag=False)
        if is_escape_command(payload.message):
            reset_reservation_state(state)
            reply = "OK, prekinil sem rezervacijo."
            reply = maybe_translate(reply, detected_lang)
            return finalize(reply, "reservation_cancel", followup_flag=False)
        if payload.message.strip().lower() == "nadaljuj":
            prompt = reservation_prompt_for_state(state)
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
                state["awaiting_continue"] = True
                llm_reply = maybe_translate(llm_reply, detected_lang)
                return finalize(llm_reply, "info_during_reservation", followup_flag=False)
        if is_product_query(payload.message):
            reply = answer_product_question(payload.message)
            last_product_query = payload.message
            last_wine_query = None
            last_info_query = None
            last_menu_query = False
            reply = maybe_translate(reply, detected_lang)
            reply = f"{reply}\n\nŽeliš nadaljevati rezervacijo? (da/ne)"
            state["awaiting_continue"] = True
            return finalize(reply, "product_during_reservation", followup_flag=False)
        if is_info_query(payload.message):
            reply = answer_farm_info(payload.message)
            last_product_query = None
            last_wine_query = None
            last_info_query = payload.message
            last_menu_query = False
            reply = maybe_translate(reply, detected_lang)
            reply = f"{reply}\n\nŽeliš nadaljevati rezervacijo? (da/ne)"
            state["awaiting_continue"] = True
            return finalize(reply, "info_during_reservation", followup_flag=False)

        reply = handle_reservation_flow(payload.message, state)
        last_product_query = None
        last_wine_query = None
        last_info_query = None
        last_menu_query = False
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "reservation")

    intent = detect_intent(payload.message, state)

    # === HYBRID ROUTING (Rule-based + LLM fallback) ===
    composite = is_reservation_related(payload.message) and is_product_query(payload.message)
    if intent == "default" or composite:
        try:
            smart = smart_classify_intent(payload.message, state, conversation_history)
            smart_intent = smart.get("intent")
            conf = smart.get("confidence", 0.0)
            booking_data = smart.get("booking_data", {}) or {}
            if conf >= 0.75 and smart_intent in {"INFO", "PRODUCT", "BOOKING", "GREETING", "GOODBYE", "COMPOSITE"}:
                if smart_intent == "GREETING":
                    reply = get_greeting_response()
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "greeting", followup_flag=False)
                if smart_intent == "GOODBYE":
                    reply = get_goodbye_response()
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "goodbye", followup_flag=False)
                if smart_intent == "INFO":
                    reply = answer_farm_info(payload.message)
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "info", followup_flag=False)
                if smart_intent == "PRODUCT":
                    reply = strip_product_followup(answer_product_question(payload.message))
                    reply = maybe_translate(reply, detected_lang)
                    reply = strip_product_followup(reply)
                    return finalize(reply, "product", followup_flag=False)
                if smart_intent == "BOOKING":
                    booking_type = booking_data.get("type")
                    if not booking_type:
                        if "mizo" in payload.message.lower() or "table" in payload.message.lower():
                            booking_type = "table"
                        elif "sobo" in payload.message.lower() or "room" in payload.message.lower():
                            booking_type = "room"
                    if booking_type:
                        reset_reservation_state(state)
                        state["type"] = booking_type
                    reply = handle_reservation_flow(payload.message, state)
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "reservation", followup_flag=False)
                if smart_intent == "COMPOSITE":
                    product_reply = strip_product_followup(answer_product_question(payload.message))
                    booking_type = booking_data.get("type")
                    if not booking_type:
                        if "mizo" in payload.message.lower() or "table" in payload.message.lower():
                            booking_type = "table"
                        elif "sobo" in payload.message.lower() or "room" in payload.message.lower():
                            booking_type = "room"
                    if booking_type:
                        reset_reservation_state(state)
                        state["type"] = booking_type
                        booking_reply = handle_reservation_flow(payload.message, state)
                        reply = f"{product_reply}\n\n---\n\n{booking_reply}"
                    else:
                        reply = product_reply
                    reply = maybe_translate(reply, detected_lang)
                    return finalize(reply, "composite", followup_flag=False)
        except Exception as e:
            _router_logger.warning(f"Smart routing fallback error: {e}")

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
        tourist_reply = answer_tourist_question(payload.message)
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
        reply = format_current_menu(month_override=month_hint, force_full=is_full_menu_request(payload.message))
        last_product_query = None
        last_wine_query = None
        last_info_query = None
        last_menu_query = True
        reply = maybe_translate(reply, detected_lang)
        return finalize(reply, "menu")
    if month_hint is not None and intent == "default":
        reply = format_current_menu(month_override=month_hint, force_full=is_full_menu_request(payload.message))
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
            "Za natančne informacije prosim preverite www.kovacnik.com."
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
WEEKLY_MENUS = {
    4: {
        "name": "4-HODNI DEGUSTACIJSKI MENI",
        "price": 36,
        "wine_pairing": 15,
        "wine_glasses": 4,
        "courses": [
            {"wine": "Penina Doppler Diona 2017 (zelo suho, 100% chardonnay)", "dish": "Pozdrav iz kuhinje"},
            {"wine": "Frešer Sauvignon 2024 (suho)", "dish": "Kiblflajš s prelivom, zelenjava s Kovačnikovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi"},
            {"wine": None, "dish": "Juha s kislim zeljem in krvavico"},
            {"wine": "Šumenjak Alter 2021 (suho)", "dish": "Krompir iz naše njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka iz vrta gospodinje Barbare"},
            {"wine": "Greif Rumeni muškat 2024 (polsladko)", "dish": "Pohorska gibanica babice Angelce ali domač jabolčni štrudl ali pita sezone, hišni sladoled"},
        ],
    },
    5: {
        "name": "5-HODNI DEGUSTACIJSKI MENI",
        "price": 43,
        "wine_pairing": 20,
        "wine_glasses": 5,
        "courses": [
            {"wine": "Penina Doppler Diona 2017 (zelo suho, 100% chardonnay)", "dish": "Pozdrav iz kuhinje"},
            {"wine": "Frešer Sauvignon 2024 (suho)", "dish": "Kiblflajš s prelivom, zelenjava s Kovačnikovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi"},
            {"wine": None, "dish": "Juha s kislim zeljem in krvavico"},
            {"wine": "Frešer Renski rizling 2019 (suho)", "dish": "Ričotka pirine kaše z jurčki in zelenjavo"},
            {"wine": "Šumenjak Alter 2021 (suho)", "dish": "Krompir iz naše njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka iz vrta gospodinje Barbare"},
            {"wine": "Greif Rumeni muškat 2024 (polsladko)", "dish": "Pohorska gibanica babice Angelce ali domač jabolčni štrudl ali pita sezone, hišni sladoled"},
        ],
    },
    6: {
        "name": "6-HODNI DEGUSTACIJSKI MENI",
        "price": 53,
        "wine_pairing": 25,
        "wine_glasses": 6,
        "courses": [
            {"wine": "Penina Doppler Diona 2017 (zelo suho, 100% chardonnay)", "dish": "Pozdrav iz kuhinje"},
            {"wine": "Frešer Sauvignon 2024 (suho)", "dish": "Kiblflajš s prelivom, zelenjava s Kovačnikovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi"},
            {"wine": None, "dish": "Juha s kislim zeljem in krvavico"},
            {"wine": "Frešer Renski rizling 2019 (suho)", "dish": "Ričotka pirine kaše z jurčki in zelenjavo"},
            {"wine": "Šumenjak Alter 2021 (suho)", "dish": "Krompir iz naše njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka iz vrta gospodinje Barbare"},
            {"wine": "Greif Modra frankinja 2020 (suho)", "dish": "Štrukelj s skuto naše krave Miške, goveje meso iz Kovačnikove proste reje, rdeča pesa, rabarbara, naravna omaka"},
            {"wine": "Greif Rumeni muškat 2024 (polsladko)", "dish": "Pohorska gibanica babice Angelce ali domač jabolčni štrudl ali pita sezone, hišni sladoled"},
        ],
    },
    7: {
        "name": "7-HODNI DEGUSTACIJSKI MENI",
        "price": 62,
        "wine_pairing": 29,
        "wine_glasses": 7,
        "courses": [
            {"wine": "Penina Doppler Diona 2017 (zelo suho, 100% chardonnay)", "dish": "Pozdrav iz kuhinje"},
            {"wine": "Frešer Sauvignon 2024 (suho)", "dish": "Kiblflajš s prelivom, zelenjava s Kovačnikovega vrta, zorjen Frešerjev sir, hišni kruh z drožmi"},
            {"wine": None, "dish": "Juha s kislim zeljem in krvavico"},
            {"wine": "Greif Laški rizling Terase 2020 (suho)", "dish": "An ban en goban – Jurčki, ajda, ocvirki, korenček, peteršilj"},
            {"wine": "Frešer Renski rizling 2019 (suho)", "dish": "Ričotka pirine kaše z jurčki in zelenjavo"},
            {"wine": "Šumenjak Alter 2021 (suho)", "dish": "Krompir iz naše njive, zelenjavni pire, pohan pišek s kmetije Pesek, solatka iz vrta gospodinje Barbare"},
            {"wine": "Greif Modra frankinja 2020 (suho)", "dish": "Štrukelj s skuto naše krave Miške, goveje meso iz Kovačnikove proste reje, rdeča pesa, rabarbara, naravna omaka"},
            {"wine": "Greif Rumeni muškat 2024 (polsladko)", "dish": "Pohorska gibanica babice Angelce ali domač jabolčni štrudl ali pita sezone, hišni sladoled"},
        ],
    },
}

WEEKLY_INFO = {
    "days": "sreda, četrtek, petek",
    "time": "od 13:00 naprej",
    "min_people": 6,
    "contact": {"phone": "031 330 113", "email": "info@kovacnik.com"},
    "special_diet_extra": 8,
}


@router.post("/stream")
def chat_stream(payload: ChatRequestWithSession):
    global conversation_history, last_interaction
    now = datetime.now()
    session_id = payload.session_id or "default"
    ctx = _load_session_context(session_id)
    if last_interaction and now - last_interaction > timedelta(hours=SESSION_TIMEOUT_HOURS):
        reset_conversation_context(session_id)
        ctx = _load_session_context(session_id)
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
        _save_session_context(session_id, ctx)

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
    if availability_state.get("active") or state.get("step") is not None or detect_intent(payload.message, state) == "reservation":
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
    if is_product_query(payload.message):
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
