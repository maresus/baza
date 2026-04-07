"""
Chat API router for Kmetija Pod Goro V2.
Hybrid: Direct LLM for info, State machine for bookings.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter
from pydantic import BaseModel

from app.chat.llm_chat import chat
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


@router.post("", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
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

        # Log conversation
        try:
            from app.services.reservation_service import ReservationService
            service = ReservationService()
            service.log_conversation(session_id, message, reply)
        except Exception:
            pass

        return ChatResponse(reply=reply, session_id=session_id)

    # Check for new booking intent → open visual form
    booking_type = detect_booking_intent(message)
    if booking_type:
        if booking_type == "room":
            reply = "Odpiramo rezervacijsko formo za sobo. Izpolnite podatke in pošljite! 🛏️"
        elif booking_type == "table":
            reply = "Odpiramo rezervacijsko formo za mizo. Izpolnite podatke in pošljite! 🍽️"
        else:
            reply = "Odpiramo rezervacijsko formo. Izpolnite podatke in pošljite! 📅"

        try:
            from app.services.reservation_service import ReservationService
            service = ReservationService()
            service.log_conversation(session_id, message, reply)
        except Exception:
            pass

        return ChatResponse(
            reply=reply,
            session_id=session_id,
            action="open_booking_form",
            booking_type_hint=booking_type,
        )

    # Regular chat - direct LLM
    result = chat(
        message=message,
        history=session["history"],
    )

    # Update history
    session["history"].append({"role": "user", "content": message})
    session["history"].append({"role": "assistant", "content": result["reply"]})

    if len(session["history"]) > 20:
        session["history"] = session["history"][-20:]

    # Log conversation
    try:
        from app.services.reservation_service import ReservationService
        service = ReservationService()
        service.log_conversation(session_id, message, result["reply"])
    except Exception:
        pass

    return ChatResponse(reply=result["reply"], session_id=session_id)


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
        try:
            service.log_conversation(sid, f"[Widget forma] {payload.booking_type}: {payload.date}, {payload.name}", f"Rezervacija #{reservation_id} shranjena.")
        except Exception:
            pass

        return {"ok": True, "reservation_id": reservation_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}
