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

    # Check for new booking intent
    booking_type = detect_booking_intent(message)
    if booking_type:
        booking, reply = start_booking(booking_type)
        session["booking"] = booking

        try:
            from app.services.reservation_service import ReservationService
            service = ReservationService()
            service.log_conversation(session_id, message, reply)
        except Exception:
            pass

        return ChatResponse(reply=reply, session_id=session_id)

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
