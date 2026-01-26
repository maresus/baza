import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from app.services.email_service import (
    send_custom_message,
    send_reservation_confirmed,
    send_reservation_rejected,
)
from app.services.reservation_service import SERVICES, ReservationService
from app.services.chat_history_service import get_chat_history_service

# Compatibility aliases za admin panel
ROOMS = SERVICES  # Storitve namesto sob
TOTAL_TABLE_CAPACITY = 0  # Ni miz

# Veljavne vrste pregledov/posegov za zdravstveni center (za validacijo)
VALID_TABLE_LOCATIONS = {
    "Ortopedski pregled",
    "Dermatološki pregled",
    "Laserski poseg",
    "Estetski poseg",
    "Fizioterapija",
    "Okulistični pregled",
    "Predpis očal/leč",
    "Kozmetični salon",
}
from app.services.imap_poll_service import load_state, preview_last_messages, resync_last_messages

router = APIRouter(tags=["admin"])
service = ReservationService()

ROOM_IDS = {r["id"] for r in ROOMS}


def _log(event: str, **kwargs) -> None:
    """Preprost log za admin API klice."""
    try:
        ts = datetime.now().isoformat(timespec="seconds")
        extras = " ".join([f"{k}={v}" for k, v in kwargs.items() if v is not None])
        print(f"[ADMIN API] {ts} {event} {extras}")
    except Exception:
        # Logging nesme prekiniti requesta
        pass


def _ensure_subject_tag(reservation_id: Optional[int], subject: str) -> str:
    if not reservation_id:
        return subject or ""
    tag = f"Rezervacija #{reservation_id}"
    if tag.lower() in (subject or "").lower():
        return subject
    if subject:
        return f"{tag} - {subject}"
    return tag


def _normalize_room_id(room: Optional[str]) -> Optional[str]:
    if not room:
        return None
    upper = room.strip().upper()
    for rid in ROOM_IDS:
        if rid in upper or upper in rid:
            return rid
    return None


def _parse_ddmmyyyy(date_str: str) -> Optional[datetime]:
    try:
        return datetime.strptime(date_str.strip(), "%d.%m.%Y")
    except Exception:
        return None


def _reservation_days(date_str: str, nights: Optional[int]) -> list[datetime]:
    nights_int = 1
    try:
        nights_int = int(nights or 1)
    except Exception:
        # poskusi izvleči prvo število iz niza (npr. "5 noči")
        import re

        m = re.search(r"\d+", str(nights or ""))
        if m:
            try:
                nights_int = int(m.group(0))
            except Exception:
                nights_int = 1
    if nights_int <= 0:
        nights_int = 1
    start = _parse_ddmmyyyy(date_str)
    if not start:
        return []
    return [start + timedelta(days=i) for i in range(nights_int)]


def _room_conflicts(reservation_id: int, room_id: str, date_str: str, nights: Optional[int]) -> list[str]:
    """Vrne seznam datumov (dd.mm.yyyy) kjer je soba že zasedena."""
    occupied: list[str] = []
    days = _reservation_days(date_str, nights)
    if not days:
        return occupied
    other_reservations = service.read_reservations(limit=1000, reservation_type="room")
    for r in other_reservations:
        if r.get("id") == reservation_id:
            continue
        status = r.get("status")
        if status not in {"confirmed", "processing"}:
            continue
        other_room = _normalize_room_id(r.get("location"))
        if other_room != room_id:
            continue
        other_days = _reservation_days(r.get("date", ""), r.get("nights"))
        overlaps = {d.date() for d in days} & {d.date() for d in other_days}
        if overlaps:
            occupied.extend(sorted({d.strftime("%d.%m.%Y") for d in overlaps}))
    return occupied


class ReservationUpdate(BaseModel):
    status: Optional[str] = None
    date: Optional[str] = None
    people: Optional[int] = None
    nights: Optional[int] = None
    time: Optional[str] = None
    time_window: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    admin_notes: Optional[str] = None
    note: Optional[str] = None
    kids_small: Optional[str] = None
    kids: Optional[str] = None
    event_type: Optional[str] = None
    special_needs: Optional[str] = None
    birth_date: Optional[str] = None


class SendMessageRequest(BaseModel):
    reservation_id: int
    email: str
    subject: str
    body: str
    set_processing: bool = True


class ConfirmReservationRequest(BaseModel):
    room: Optional[str] = None
    location: Optional[str] = None


class AdminCreateReservation(BaseModel):
    date: str
    people: int
    reservation_type: str
    source: str = "admin"
    nights: Optional[int] = None
    rooms: Optional[int] = None
    time: Optional[str] = None
    location: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None
    admin_notes: Optional[str] = None
    kids: Optional[str] = None
    kids_small: Optional[str] = None
    event_type: Optional[str] = None
    special_needs: Optional[str] = None
    birth_date: Optional[str] = None
    time_window: Optional[str] = None


class KnowledgeFeedbackRequest(BaseModel):
    question: str
    suggestion: str


@router.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    """Postreže statično datoteko admin UI (static/admin.html)."""
    html_path = Path("static/admin.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Admin UI manjka (static/admin.html)</h1>", status_code=500)
    html = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@router.get("/admin/new", response_class=HTMLResponse)
def admin_new_page() -> HTMLResponse:
    """Nov admin UI s koledarskim pogledom (static/admin_new.html)."""
    html_path = Path("static/admin_new.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Nov admin UI manjka (static/admin_new.html)</h1>", status_code=500)
    html = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@router.get("/admin/conversations", response_class=HTMLResponse)
def admin_conversations_page() -> HTMLResponse:
    """Postreže statično datoteko za pogovore (static/conversations.html)."""
    html_path = Path("static/conversations.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Conversations UI manjka (static/conversations.html)</h1>", status_code=500)
    html = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@router.get("/admin/inquiries", response_class=HTMLResponse)
def admin_inquiries_page() -> HTMLResponse:
    """Postreže statično datoteko za povpraševanja (static/inquiries.html)."""
    html_path = Path("static/inquiries.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Inquiries UI manjka (static/inquiries.html)</h1>", status_code=500)
    html = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@router.get("/conversations")
def get_conversations(limit: int = 200, needs_followup_only: bool = False):
    """Vrne zadnje pogovore za admin pregled."""
    _log("conversations", limit=limit, needs_followup_only=needs_followup_only)
    conversations = service.get_conversations(limit=limit, needs_followup_only=needs_followup_only)
    stats = {
        "total": len(conversations),
        "followup": len([c for c in conversations if c.get("needs_followup")]),
    }
    return {"conversations": conversations, "stats": stats}


@router.get("/conversations/session/{session_id}")
def get_conversations_by_session(session_id: str, limit: int = 200):
    """Vrne pogovor za posamezen session_id."""
    _log("conversations_session", session_id=session_id, limit=limit)
    conversations = service.get_conversations_by_session(session_id=session_id, limit=limit)
    return {"session_id": session_id, "conversations": conversations, "total": len(conversations)}


@router.get("/inquiries")
def get_inquiries(limit: int = 200, status: Optional[str] = None):
    _log("inquiries", limit=limit, status=status)
    inquiries = service.get_inquiries(limit=limit, status=status)
    return {"inquiries": inquiries}


@router.get("/usage_stats")
def get_usage_stats():
    _log("usage_stats")
    return service.get_usage_stats()


@router.get("/question_stats")
def get_question_stats(limit: int = 10):
    _log("question_stats", limit=limit)
    return {"questions": service.get_top_questions(limit=limit)}


@router.get("/lost_intents")
def get_lost_intents(limit: int = 10):
    _log("lost_intents", limit=limit)
    return {"items": service.get_lost_intents(limit=limit)}


@router.get("/funnel_stats")
def get_funnel_stats(days: int = 30):
    _log("funnel_stats", days=days)
    return service.get_funnel_stats(days=days)


@router.get("/missed_questions")
def get_missed_questions(limit: int = 5):
    _log("missed_questions", limit=limit)
    return {"items": service.get_lost_intents(limit=limit)}


@router.post("/knowledge_feedback")
def create_knowledge_feedback(payload: KnowledgeFeedbackRequest):
    _log("knowledge_feedback", question=payload.question[:60] if payload.question else "")
    feedback_id = service.create_knowledge_feedback(payload.question.strip(), payload.suggestion.strip())
    if not feedback_id:
        raise HTTPException(status_code=400, detail="Neveljaven predlog.")
    return {"ok": True, "id": feedback_id}


@router.get("/reservations")
def get_reservations(
    limit: int = 100,
    status: Optional[str] = None,
    type: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Vrne seznam rezervacij s filtri ter osnovno statistiko."""
    _log("reservations", limit=limit, status=status, type=type, source=source, date_from=date_from, date_to=date_to)
    reservations = service.read_reservations(limit=limit, status=status, reservation_type=type, source=source)

    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        date_str = date_str.replace(" ", "")
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue
        return None

    if date_from or date_to:
        start = _parse_date(date_from) if date_from else None
        end = _parse_date(date_to) if date_to else None
        filtered = []
        for r in reservations:
            days = _reservation_days(r.get("date", ""), r.get("nights"))
            if not days:
                # če ni datuma, ga obdržimo (ne izločimo)
                filtered.append(r)
                continue
            overlaps = False
            for d in days:
                if start and d < start:
                    continue
                if end and d > end:
                    continue
                overlaps = True
                break
            if overlaps:
                filtered.append(r)
        reservations = filtered

    all_res = service.read_reservations(limit=1000)
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    stats = {
        "pending": len([r for r in all_res if r.get("status") == "pending"]),
        "processing": len([r for r in all_res if r.get("status") == "processing"]),
        "confirmed": len([r for r in all_res if r.get("status") == "confirmed"]),
        "today": len([r for r in all_res if str(r.get("created_at", "")).startswith(today_prefix)]),
    }

    return {"reservations": reservations, "stats": stats}


@router.put("/reservations/{reservation_id}")
def update_reservation(reservation_id: int, data: ReservationUpdate):
    """Posodobi rezervacijo."""
    existing = service.get_reservation(reservation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    res_type = existing.get("reservation_type")
    location = data.location
    valid_rooms = {"", None, "ALJAZ", "JULIJA", "ANA"}
    if res_type == "room" and location is not None and location not in valid_rooms:
        raise HTTPException(status_code=400, detail="Neveljavna soba")
    if res_type == "table" and location is not None and location not in VALID_TABLE_LOCATIONS:
        raise HTTPException(status_code=400, detail="Neveljavna vrsta pregleda/posega")
    ok = service.update_reservation(
        reservation_id,
        status=data.status,
        date=data.date,
        people=data.people,
        nights=data.nights,
        location=data.location,
        admin_notes=data.admin_notes,
        kids=data.kids,
        kids_small=data.kids_small,
        time=data.time,
        time_window=data.time_window,
        name=data.name,
        phone=data.phone,
        email=data.email,
        note=data.note,
        event_type=data.event_type,
        special_needs=data.special_needs,
        birth_date=data.birth_date,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    return {"ok": True}


@router.patch("/api/admin/reservations/{reservation_id}")
def patch_reservation(reservation_id: int, data: ReservationUpdate):
    """Partial update rezervacije (status, admin_notes, kids)."""
    fields = {
        "status": data.status,
        "admin_notes": data.admin_notes,
        "kids": data.kids,
        "kids_small": data.kids_small,
        "time": data.time,
        "time_window": data.time_window,
        "location": data.location,
        "name": data.name,
        "phone": data.phone,
        "email": data.email,
        "note": data.note,
        "event_type": data.event_type,
        "special_needs": data.special_needs,
        "birth_date": data.birth_date,
    }
    if data.status == "confirmed":
        fields["confirmed_at"] = datetime.now().isoformat()
    ok = service.update_reservation(reservation_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    return {"ok": True}


@router.delete("/reservations/{reservation_id}")
def delete_reservation(reservation_id: int):
    """Izbriši rezervacijo."""
    _log("delete_reservation", reservation_id=reservation_id)
    res = service.get_reservation(reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    ok = service.delete_reservation(reservation_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Napaka pri brisanju")
    return {"ok": True, "deleted_id": reservation_id}


@router.post("/reservations/{reservation_id}/confirm")
def confirm_reservation(reservation_id: int, data: Optional[ConfirmReservationRequest] = None):
    """Potrdi rezervacijo, preveri zasedenost sobe in pošlje email gostu."""
    res = service.get_reservation(reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    requested_room = _normalize_room_id((data.room if data else None) or res.get("location"))
    requested_location = (data.location if data else None) or res.get("location")
    if res.get("reservation_type") == "room":
        if not requested_room:
            raise HTTPException(status_code=400, detail="Soba mora biti izbrana.")
        conflicts = _room_conflicts(reservation_id, requested_room, res.get("date", ""), res.get("nights"))
        if conflicts:
            return {"success": False, "warning": f"Soba {requested_room} je zasedena: {', '.join(conflicts)}"}
    else:
        requested_room = None

    if res.get("reservation_type") == "table" and not res.get("time"):
        auto_time = service.pick_time_slot(
            res.get("date", ""),
            requested_location,
            res.get("time_window"),
        )
        if auto_time:
            res["time"] = auto_time

    service.update_reservation(
        reservation_id,
        status="confirmed",
        confirmed_at=datetime.now().isoformat(),
        confirmed_by=os.getenv("ADMIN_EMAIL", "info@kovacnik.com"),
        location=requested_room or requested_location,
        time=res.get("time"),
    )
    res = service.get_reservation(reservation_id) or res
    send_reservation_confirmed(res)
    subject = _ensure_subject_tag(reservation_id, "Potrditev rezervacije")
    service.add_reservation_message(
        reservation_id=reservation_id,
        direction="outbound",
        subject=subject,
        body="Rezervacija potrjena.",
        from_email=os.getenv("ADMIN_EMAIL", "info@kovacnik.com"),
        to_email=res.get("email") or "",
        message_id=None,
    )
    return {"success": True, "email_sent": True, "room": requested_room or requested_location}


@router.post("/reservations/{reservation_id}/reject")
def reject_reservation(reservation_id: int):
    """Zavrne rezervacijo in pošlje email gostu."""
    res = service.get_reservation(reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    service.update_reservation(reservation_id, status="rejected")
    res = service.get_reservation(reservation_id) or res
    send_reservation_rejected(res)
    subject = _ensure_subject_tag(reservation_id, "Zavrnjena rezervacija")
    service.add_reservation_message(
        reservation_id=reservation_id,
        direction="outbound",
        subject=subject,
        body="Rezervacija zavrnjena.",
        from_email=os.getenv("ADMIN_EMAIL", "info@kovacnik.com"),
        to_email=res.get("email") or "",
        message_id=None,
    )
    return {"success": True, "email_sent": True}


@router.post("/send-message")
def send_message(data: SendMessageRequest):
    """Pošlje sporočilo gostu in opcijsko status nastavi na 'processing'."""
    if not data.email:
        raise HTTPException(status_code=400, detail="Email manjka")
    subject = _ensure_subject_tag(data.reservation_id, data.subject or "")
    send_custom_message(data.email, subject, data.body)
    if data.reservation_id:
        service.add_reservation_message(
            reservation_id=data.reservation_id,
            direction="outbound",
            subject=subject,
            body=data.body,
            from_email=os.getenv("ADMIN_EMAIL", "info@kovacnik.com"),
            to_email=data.email,
            message_id=None,
        )
    if data.set_processing:
        service.update_reservation(
            data.reservation_id,
            status="processing",
            guest_message=data.body,
        )
    return {"ok": True}


@router.get("/reservations/{reservation_id}/messages")
def get_reservation_messages(reservation_id: int):
    """Vrne sporočila za izbrano rezervacijo."""
    messages = service.list_reservation_messages(reservation_id)
    return {"messages": messages}


@router.get("/imap_status")
def get_imap_status():
    """Vrne stanje IMAP pollinga."""
    return load_state()


@router.post("/imap_resync")
def imap_resync(limit: int = 50):
    """Ročno prebere zadnjih N sporočil iz IMAP."""
    return resync_last_messages(limit=limit)


@router.get("/imap_preview")
def imap_preview(limit: int = 10):
    """Vrne osnovne podatke zadnjih N sporočil (subject/from/date)."""
    return preview_last_messages(limit=limit)


@router.get("/stats")
def get_stats():
    """Agregirani podatki za dashboard."""
    _log("stats")
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    week_ago = datetime.now() - timedelta(days=7)
    month_ago = datetime.now().replace(day=1)
    res_list = service.read_reservations(limit=1000)

    def parse_created(r) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(str(r.get("created_at", "")))
        except Exception:
            return None

    counts = {
        "danes": 0,
        "ta_teden": 0,
        "ta_mesec": 0,
        "po_statusu": {"pending": 0, "processing": 0, "confirmed": 0, "rejected": 0},
        "po_tipu": {"room": 0, "table": 0},
    }
    for r in res_list:
        created = parse_created(r)
        if created:
            if str(r.get("created_at", "")).startswith(today_prefix):
                counts["danes"] += 1
            if created >= week_ago:
                counts["ta_teden"] += 1
            if created >= month_ago:
                counts["ta_mesec"] += 1
        status = r.get("status")
        if status in counts["po_statusu"]:
            counts["po_statusu"][status] += 1
        rtype = r.get("reservation_type")
        if rtype in counts["po_tipu"]:
            counts["po_tipu"][rtype] += 1
    return counts


@router.get("/export")
def export_reservations(
    status: Optional[str] = None,
    type: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Izvoz rezervacij v CSV (uporabi iste filtre kot /reservations)."""
    data = get_reservations(limit=1000, status=status, type=type, source=source, date_from=date_from, date_to=date_to)
    reservations = data.get("reservations", [])
    headers = [
        "id",
        "date",
        "time",
        "nights",
        "rooms",
        "people",
        "kids",
        "kids_small",
        "reservation_type",
        "name",
        "email",
        "phone",
        "location",
        "note",
        "status",
        "source",
        "created_at",
    ]
    lines = [",".join(headers)]
    for r in reservations:
        row = []
        for h in headers:
            val = r.get(h, "")
            if val is None:
                val = ""
            cell = str(val).replace('"', '""')
            if any(c in cell for c in [",", "\n", '"']):
                cell = f'"{cell}"'
            row.append(cell)
        lines.append(",".join(row))
    csv_content = "\n".join(lines)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reservations.csv"},
    )


@router.get("/calendar/rooms")
def calendar_rooms(month: int, year: int):
    """Vrne zasedenost sob po dnevih z ločenimi pending/confirmed."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Neveljaven mesec")
    days: dict[str, dict[str, Any]] = {}
    reservations = service.read_reservations(limit=1000, reservation_type="room")
    for r in reservations:
        status = r.get("status")
        if status not in {"pending", "processing", "confirmed"}:
            continue
        room_id = _normalize_room_id(r.get("location"))
        if not room_id:
            continue
        for day in _reservation_days(r.get("date", ""), r.get("nights")):
            if day.month != month or day.year != year:
                continue
            key = day.strftime("%Y-%m-%d")
            bucket = "confirmed" if status == "confirmed" else "pending"
            entry = days.setdefault(key, {"confirmed": [], "pending": [], "reservations": []})
            if room_id not in entry[bucket]:
                entry[bucket].append(room_id)
            entry["reservations"].append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "people": r.get("people"),
                    "kids": r.get("kids"),
                    "location": room_id,
                    "email": r.get("email"),
                    "phone": r.get("phone"),
                    "status": status,
                    "date": r.get("date"),
                    "nights": r.get("nights"),
                }
            )
    return {"days": days}


@router.get("/calendar/tables")
def calendar_tables(month: int, year: int, location: Optional[str] = None):
    """Zasedenost miz po dnevih in urah."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Neveljaven mesec")
    calendar: dict[str, dict[str, Any]] = {}
    reservations = service.read_reservations(limit=1000, reservation_type="table")
    for r in reservations:
        status = r.get("status")
        if status in {"rejected", "cancelled"}:
            continue
        if location and r.get("location") and r.get("location") != location:
            continue
        day = _parse_ddmmyyyy(r.get("date", ""))
        if not day or day.month != month or day.year != year:
            continue
        iso = day.strftime("%Y-%m-%d")
        people = 0
        try:
            people = int(r.get("people") or 0)
        except Exception:
            people = 0
        entry = calendar.setdefault(
            iso, {"total_people": 0, "capacity": TOTAL_TABLE_CAPACITY, "reservations": []}
        )
        entry["total_people"] += people
        entry["reservations"].append(
            {
                "time": r.get("time"),
                "time_window": r.get("time_window"),
                "people": people,
                "name": r.get("name"),
                "status": status,
                "location": r.get("location"),
                "email": r.get("email"),
                "phone": r.get("phone"),
                "date": r.get("date"),
                "id": r.get("id"),
                "birth_date": r.get("birth_date"),
                "reservation_type": "table",
            }
        )
    return calendar


@router.post("/reservations")
def create_admin_reservation(data: AdminCreateReservation):
    """Ročno dodajanje rezervacije (admin)."""
    warning: Optional[str] = None
    valid_rooms = {"", None, "ALJAZ", "JULIJA", "ANA"}
    location = _normalize_room_id(data.location) if data.reservation_type == "room" else data.location

    if data.reservation_type == "room":
        if location not in valid_rooms:
            raise HTTPException(status_code=400, detail="Neveljavna soba")
    if data.reservation_type == "table":
        if location and location not in VALID_TABLE_LOCATIONS:
            raise HTTPException(status_code=400, detail="Neveljavna vrsta pregleda/posega")

    if data.reservation_type == "room" and location:
        conflicts = _room_conflicts(0, location, data.date, data.nights)
        if conflicts:
            warning = f"Soba {location} je zasedena: {', '.join(conflicts)}"
    if data.reservation_type == "table" and data.time:
        ok, suggested_location, suggestions = service.check_table_availability(data.date, data.time, data.people)
        if not ok:
            warning = "Kapaciteta je polna za izbrano uro."
            if suggestions:
                warning += f" Predlogi: {', '.join(suggestions)}"
        if suggested_location and not data.location:
            location = suggested_location

    try:
        new_id = service.create_reservation(
            date=data.date,
            nights=data.nights,
            rooms=data.rooms,
            people=data.people,
            reservation_type=data.reservation_type,
            time=data.time,
            location=location,
            name=data.name,
            phone=data.phone,
            email=data.email,
            note=data.note,
            status="confirmed",
            admin_notes=data.admin_notes,
            kids=data.kids,
            kids_small=data.kids_small,
            source="admin",
            event_type=data.event_type,
            special_needs=data.special_needs,
            birth_date=data.birth_date,
            time_window=data.time_window,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Napaka pri shranjevanju: {exc}")
    return {"success": True, "id": new_id, "warning": warning}


# ==================== CHAT HISTORY ENDPOINTS ====================

@router.get("/chat_sessions")
def get_chat_sessions(days: int = 7, limit: int = 100):
    """
    Get list of recent chat sessions

    Args:
        days: Number of days back to look
        limit: Maximum number of sessions to return
    """
    _log("GET /chat_sessions", days=days, limit=limit)
    try:
        history_service = get_chat_history_service()
        since = (datetime.now() - timedelta(days=days)).isoformat()
        sessions = history_service.get_all_sessions(since=since, limit=limit)

        return {
            "sessions": sessions,
            "total": len(sessions),
            "days": days
        }
    except Exception as e:
        print(f"[ADMIN] Error fetching chat sessions: {e}")
        return {"sessions": [], "total": 0, "error": str(e)}


@router.get("/chat_history/{session_id}")
def get_session_history(session_id: str, limit: Optional[int] = None):
    """
    Get chat history for a specific session

    Args:
        session_id: Session ID to retrieve
        limit: Optional limit on number of messages
    """
    _log("GET /chat_history", session_id=session_id, limit=limit)
    try:
        history_service = get_chat_history_service()
        messages = history_service.get_session_history(session_id=session_id, limit=limit)

        return {
            "session_id": session_id,
            "messages": messages,
            "total": len(messages)
        }
    except Exception as e:
        print(f"[ADMIN] Error fetching session history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat_stats")
def get_chat_stats(days: int = 7):
    """
    Get conversation statistics

    Args:
        days: Number of days to analyze
    """
    _log("GET /chat_stats", days=days)
    try:
        history_service = get_chat_history_service()
        stats = history_service.get_conversation_stats(days=days)

        return stats
    except Exception as e:
        print(f"[ADMIN] Error fetching chat stats: {e}")
        return {
            "error": str(e),
            "total_sessions": 0,
            "total_messages": 0
        }


@router.get("/search_messages")
def search_chat_messages(
    query: str,
    role: Optional[str] = None,
    intent: Optional[str] = None,
    limit: int = 50
):
    """
    Search chat messages by content

    Args:
        query: Text to search for
        role: Filter by role (user/assistant)
        intent: Filter by intent
        limit: Maximum results
    """
    _log("GET /search_messages", query=query, role=role, intent=intent)
    try:
        history_service = get_chat_history_service()
        results = history_service.search_messages(
            query=query,
            role=role,
            intent=intent,
            limit=limit
        )

        return {
            "results": results,
            "total": len(results),
            "query": query
        }
    except Exception as e:
        print(f"[ADMIN] Error searching messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))
