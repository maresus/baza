"""
Chat API router for Kmetija Pod Goro V2.
Hybrid: Direct LLM for info, State machine for bookings.
"""
from __future__ import annotations

import re as _re
import uuid
from datetime import datetime as _dt
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.chat.llm_chat import chat, chat_stream
from app.booking.state_machine import (
    BookingState,
    detect_booking_intent,
    start_booking,
    process_booking,
    is_booking_active,
)


router = APIRouter(prefix="/chat", tags=["chat"])

# Simple in-memory session storage
_sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    action: str | None = None
    booking_type_hint: str | None = None
    booking_prefill: dict | None = None


class QuickBookingRequest(BaseModel):
    session_id: str | None = None
    booking_type: str = "room"
    date: str
    nights: int | None = None
    time: str | None = None
    adults: int = 2
    children: int = 0
    children_ages: list[int] = []
    name: str
    phone: str
    email: str = ""
    dinner: bool = False
    note: str = ""
    gdpr: bool = False


def _get_session(session_id: str | None) -> tuple[str, dict]:
    """Get or create session."""
    if session_id:
        if session_id not in _sessions:
            _sessions[session_id] = {"history": [], "booking": None}
        return session_id, _sessions[session_id]

    new_id = str(uuid.uuid4())
    _sessions[new_id] = {"history": [], "booking": None}
    return new_id, _sessions[new_id]


def _try_extract_prefill(message: str) -> dict | None:
    """Izvleče datum, noči, odrasle, otroke iz sporočila. Vrne prefill dict ali None."""
    msg = message.lower()
    prefill: dict = {}

    # Datumski range: "6.-8.5." ali "od 6.5. do 8.5."
    range_match = _re.search(r'(\d{1,2})\.\s*[-–do]+\s*(\d{1,2})\.(\d{1,2})\.?(\d{4})?', msg)
    if range_match:
        day1, day2, month = int(range_match.group(1)), int(range_match.group(2)), int(range_match.group(3))
        year = int(range_match.group(4)) if range_match.group(4) else _dt.now().year
        try:
            d1 = _dt(year, month, day1)
            d2 = _dt(year, month, day2)
            prefill["date"] = d1.strftime("%Y-%m-%d")
            nights = (d2 - d1).days
            if 1 <= nights <= 30:
                prefill["nights"] = nights
        except ValueError:
            pass
    else:
        # Enojni datum: "6.5."
        single_match = _re.search(r'(\d{1,2})\.(\d{1,2})\.?(\d{4})?', msg)
        if single_match:
            day, month = int(single_match.group(1)), int(single_match.group(2))
            year = int(single_match.group(3)) if single_match.group(3) else _dt.now().year
            try:
                prefill["date"] = _dt(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                pass

    if not prefill.get("date"):
        return None

    # Odrasli
    adults_match = _re.search(r'(\d+)\s*(?:odrasl|oseb[^i]|gost)', msg)
    if adults_match:
        prefill["adults"] = int(adults_match.group(1))

    # Otroci
    kids_match = _re.search(r'(\d+)\s*(?:otro[kc]|malčk)', msg)
    if kids_match:
        prefill["children"] = int(kids_match.group(1))

    # Besedni zapis
    word_nums = {"en ": 1, "ena ": 1, "dva ": 2, "dve ": 2, "tri ": 3, "štiri ": 4, "pet ": 5}
    if not prefill.get("adults"):
        for w, n in word_nums.items():
            if w + "odrasl" in msg or w + "oseb" in msg:
                prefill["adults"] = n
                break
    if not prefill.get("children"):
        for w, n in word_nums.items():
            if w + "otro" in msg or w + "malč" in msg:
                prefill["children"] = n
                break

    return prefill


def _try_auto_save_inquiry(session_id: str, session: dict) -> None:
    """Po 4+ sporočilih LLM avtomatsko shrani povpraševanje iz pogovora."""
    history = session.get("history", [])
    if len(history) < 8:  # 4 user + 4 bot = 8 entries
        return
    if session.get("_inquiry_saved"):
        return

    session["_inquiry_saved"] = True  # označi takoj da ne teče dvakrat

    try:
        import os
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

        conversation_text = "\n".join(
            f"{'Gost' if m['role'] == 'user' else 'Bot'}: {m['content']}"
            for m in history[-12:]
        )

        prompt = f"""Iz spodnjega pogovora izvleci podatke o rezervaciji/povpraševanju.
Vrni JSON z polji (prazno polje = null):
{{
  "booking_type": "room" | "table" | "bike" | "animals" | null,
  "date": "YYYY-MM-DD" | null,
  "nights": number | null,
  "adults": number | null,
  "children": number | null,
  "name": "ime priimek" | null,
  "phone": "tel" | null,
  "note": "kratka opomba" | null
}}
Če ni jasnih podatkov za rezervacijo, vrni {{"booking_type": null}}.

Pogovor:
{conversation_text}

Vrni SAMO JSON brez razlage:"""

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=200,
        )
        raw = resp.choices[0].message.content if resp.choices else ""
        raw = raw.strip().strip("```json").strip("```").strip()

        import json
        data = json.loads(raw)

        if not data.get("booking_type") or not data.get("date"):
            return

        from app.services.reservation_service import ReservationService
        svc = ReservationService()
        svc.log_conversation(
            session_id,
            "[Auto-ekstrakcija] Povpraševanje zaznano v pogovoru",
            f"{data.get('booking_type')} | {data.get('date')} | {data.get('name') or 'ni imena'}",
        )

        # Shrani kot rezervacijo (pending) samo če je dovolj podatkov
        if data.get("name") and data.get("date"):
            svc.create_reservation(
                date=data["date"],
                people=(data.get("adults") or 1) + (data.get("children") or 0),
                reservation_type=data["booking_type"],
                nights=data.get("nights"),
                name=data["name"],
                phone=data.get("phone"),
                note=data.get("note"),
                source="chat_autoextract",
                status="pending",
            )
            print(f"[auto_save] Rezervacija shranjena iz pogovora {session_id}")
    except Exception as e:
        print(f"[auto_save] Napaka: {e}")


def _is_side_question(message: str, booking: BookingState) -> bool:
    """Check if message is a side question during booking."""
    msg_l = message.lower()

    question_words = (
        "koliko", "kdo", "kaj", "kje", "kdaj", "ali", "kako", "zakaj", "?",
        "kakšen", "kakšna", "kakšno", "kateri", "katera", "katero",
        "imate", "a imate", "ali imate", "je kje", "je kaj",
        "lahko", "se da", "a je", "ali je", "obstaja", "ponujate",
    )
    has_question = any(q in msg_l for q in question_words)

    if booking.step == "awaiting_date" and any(c.isdigit() for c in message):
        import re
        if re.search(r'\d{1,2}\.\d{1,2}', message):
            return False

    if booking.step == "awaiting_nights":
        if any(c.isdigit() for c in message):
            return False

    if booking.step == "awaiting_adults":
        if any(c.isdigit() for c in message) or any(w in msg_l for w in ("odrasl", "oseb")):
            return False

    if booking.step == "awaiting_children_count":
        if any(c.isdigit() for c in message) or any(w in msg_l for w in ("otrok", "brez", "ne", "nimamo")):
            return False

    if booking.step == "awaiting_children_ages":
        if any(c.isdigit() for c in message) or any(w in msg_l for w in ("let", "star")):
            return False

    if booking.step == "awaiting_contact":
        words = message.strip().split()
        if len(words) >= 1 and not any(c.isdigit() for c in message) and not has_question:
            return False

    if booking.step == "awaiting_phone":
        if sum(c.isdigit() for c in message) >= 6:
            return False

    if booking.step in ("awaiting_confirm",):
        simple = msg_l.strip()
        if simple in ("da", "ne", "ja", "no", "ok", "yes", "prosim", "hvala"):
            return False

    return has_question


def _handle_side_question(message: str, booking: BookingState, session: dict) -> str | None:
    """Handle side question during booking."""
    if not _is_side_question(message, booking):
        return None

    context_msg = f"[Uporabnik je SREDI rezervacije ({booking.type}) za {booking.date or 'TBD'}. Odgovori KRATKO (1-2 stavka).]"
    augmented_message = f"{context_msg}\n\nVprašanje: {message}"

    result = chat(message=augmented_message, history=session.get("history"))
    return result["reply"]


def _get_booking_continuation(booking: BookingState) -> str:
    """Get the continuation prompt for current booking step."""
    prompts = {
        "awaiting_type": "Kaj želite rezervirati? (sobo, mizo, kolesa, hranjenje živali)",
        "awaiting_animal_type": "Hranjenje srn, kmečkih živali ali oboje?",
        "awaiting_date": "Za kateri datum? (npr. 15.7.2026)",
        "awaiting_time": "Katero uro?",
        "awaiting_bike_type": "Gorska kolesa ali e-kolesa?",
        "awaiting_bike_count": "Koliko koles potrebujete?",
        "awaiting_nights": "Koliko nočitev?",
        "awaiting_adults": "Koliko odraslih oseb?",
        "awaiting_children_count": "Ali boste imeli otroke?",
        "awaiting_children_ages": f"Koliko let {'ima otrok' if booking.children == 1 else 'imajo otroci'}?",
        "awaiting_contact": "Vaše ime in priimek?",
        "awaiting_phone": "Vaša telefonska številka?",
        "awaiting_email": "Vaš email (ali 'preskoči')?",
        "awaiting_confirm": "Ali potrjujete rezervacijo? (da/ne)",
    }
    return prompts.get(booking.step, "Kako nadaljujemo?")


def _log(session_id: str, user_msg: str, bot_reply: str) -> None:
    try:
        from app.services.reservation_service import ReservationService
        ReservationService().log_conversation(session_id, user_msg, bot_reply)
    except Exception:
        pass


@router.post("", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest, background_tasks: BackgroundTasks) -> ChatResponse:
    """Main chat endpoint - hybrid approach."""
    session_id, session = _get_session(payload.session_id)
    message = payload.message.strip()

    booking: BookingState | None = session.get("booking")

    if is_booking_active(booking):
        side_answer = _handle_side_question(message, booking, session)
        if side_answer:
            continuation = _get_booking_continuation(booking)
            reply = f"{side_answer}\n\n—\nNadaljujemo z rezervacijo?\n{continuation}"
            return ChatResponse(reply=reply, session_id=session_id)

        booking, reply = process_booking(booking, message)
        session["booking"] = booking

        if booking.step in ("confirmed", "cancelled"):
            session["booking"] = None

        _log(session_id, message, reply)
        return ChatResponse(reply=reply, session_id=session_id)

    # Booking intent + prefill detekcija
    booking_type = detect_booking_intent(message)
    prefill = _try_extract_prefill(message)
    if not booking_type and prefill:
        booking_type = "room"

    if booking_type:
        result = chat(message=message, history=session["history"], booking_type_hint=booking_type)
        reply = result["reply"]
        session["history"].append({"role": "user", "content": message})
        session["history"].append({"role": "assistant", "content": reply})
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]
        _log(session_id, message, reply)
        return ChatResponse(
            reply=reply,
            session_id=session_id,
            action="open_booking_form",
            booking_type_hint=booking_type,
            booking_prefill=prefill,
        )

    # Regular chat - direct LLM
    result = chat(message=message, history=session["history"])

    session["history"].append({"role": "user", "content": message})
    session["history"].append({"role": "assistant", "content": result["reply"]})

    if len(session["history"]) > 20:
        session["history"] = session["history"][-20:]

    _log(session_id, message, result["reply"])
    background_tasks.add_task(_try_auto_save_inquiry, session_id, session)

    return ChatResponse(reply=result["reply"], session_id=session_id)


@router.post("/stream")
async def chat_stream_endpoint(payload: ChatRequest, background_tasks: BackgroundTasks):
    """Streaming chat endpoint — SSE, besedo po besedo."""
    session_id, session = _get_session(payload.session_id)
    message = payload.message.strip()

    booking: BookingState | None = session.get("booking")

    # Med aktivno rezervacijo ne streamamo — vrni navaden odgovor
    if is_booking_active(booking):
        side_answer = _handle_side_question(message, booking, session)
        if side_answer:
            continuation = _get_booking_continuation(booking)
            reply = f"{side_answer}\n\n—\nNadaljujemo z rezervacijo?\n{continuation}"
        else:
            booking, reply = process_booking(booking, message)
            session["booking"] = booking
            if booking.step in ("confirmed", "cancelled"):
                session["booking"] = None
        _log(session_id, message, reply)

        async def _single():
            yield f"data: {reply}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_single(), media_type="text/event-stream",
                                 headers={"X-Session-Id": session_id})

    async def _generate():
        full_reply = []
        for chunk in chat_stream(message=message, history=session["history"]):
            if chunk == "[DONE]":
                session["history"].append({"role": "user", "content": message})
                session["history"].append({"role": "assistant", "content": "".join(full_reply)})
                if len(session["history"]) > 20:
                    session["history"] = session["history"][-20:]
                _log(session_id, message, "".join(full_reply))
                background_tasks.add_task(_try_auto_save_inquiry, session_id, session)
                yield "data: [DONE]\n\n"
            else:
                full_reply.append(chunk)
                yield f"data: {chunk}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream",
                             headers={"X-Session-Id": session_id})


@router.post("/quick-booking")
async def quick_booking(payload: QuickBookingRequest):
    """Sprejme celo rezervacijo naenkrat iz vizualne forme v widgetu."""
    if not payload.gdpr:
        return {"ok": False, "error": "GDPR soglasje je obvezno."}

    try:
        from app.services.reservation_service import ReservationService
        from app.services.email_service import send_guest_confirmation, send_admin_notification
    except ImportError:
        return {"ok": False, "error": "Servis ni dosegljiv."}

    service = ReservationService()
    total_people = payload.adults + payload.children

    kids_str = ""
    if payload.children > 0:
        ages_str = ", ".join(str(a) for a in payload.children_ages) if payload.children_ages else ""
        kids_str = f"{payload.children} ({ages_str} let)" if ages_str else str(payload.children)

    note_parts = []
    if payload.booking_type == "room" and payload.dinner:
        note_parts.append("Večerja: Da")
    if payload.note:
        note_parts.append(payload.note)
    note = "; ".join(note_parts) if note_parts else None

    try:
        reservation_id = service.create_reservation(
            date=payload.date,
            people=total_people,
            reservation_type=payload.booking_type,
            nights=payload.nights if payload.booking_type == "room" else None,
            time=payload.time if payload.booking_type == "table" else None,
            name=payload.name,
            phone=payload.phone,
            email=payload.email if payload.email else None,
            note=note,
            kids=kids_str if kids_str else None,
            source="widget_form",
            status="pending",
            gdpr_consent="da" if payload.gdpr else None,
        )

        email_data = {
            "id": reservation_id,
            "date": payload.date,
            "people": total_people,
            "reservation_type": payload.booking_type,
            "name": payload.name,
            "phone": payload.phone,
            "email": payload.email if payload.email else None,
            "nights": payload.nights if payload.booking_type == "room" else None,
            "time": payload.time if payload.booking_type == "table" else None,
            "kids": kids_str if kids_str else None,
            "note": note,
            "source": "widget_form",
        }
        if payload.email:
            try:
                send_guest_confirmation(email_data)
            except Exception:
                pass
        try:
            send_admin_notification(email_data)
        except Exception:
            pass

        sid = payload.session_id or str(uuid.uuid4())
        _log(sid, f"[Widget forma] {payload.booking_type}: {payload.date}, {payload.name}", f"Rezervacija #{reservation_id} shranjena.")

        return {"ok": True, "reservation_id": reservation_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}
