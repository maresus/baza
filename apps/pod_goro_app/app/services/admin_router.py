"""
Admin Router za Kmetija Pod Goro V2
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from app.services.email_service import (
    send_custom_message,
    send_reservation_confirmed,
    send_reservation_rejected,
)
from app.services.reservation_service import ROOMS, TOTAL_TABLE_CAPACITY, ReservationService

router = APIRouter(tags=["admin"])
service = ReservationService()

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ROOM_IDS = {r["id"] for r in ROOMS}


def verify_admin(token: str = Header(None, alias="X-Admin-Token"), t: str = Query(None)):
    if not ADMIN_TOKEN:
        return
    provided = token or t
    if provided != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Neveljaven admin token")


def _log(event: str, **kwargs) -> None:
    try:
        ts = datetime.now().isoformat(timespec="seconds")
        extras = " ".join([f"{k}={v}" for k, v in kwargs.items() if v is not None])
        print(f"[ADMIN API] {ts} {event} {extras}")
    except Exception:
        pass


def _ensure_subject_tag(reservation_id: Optional[int], subject: str) -> str:
    if not reservation_id:
        return subject or ""
    tag = f"Rezervacija #{reservation_id}"
    if tag.lower() in (subject or "").lower():
        return subject
    return f"{tag} - {subject}" if subject else tag


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
    try:
        nights_int = int(nights or 1)
    except Exception:
        nights_int = 1
    if nights_int <= 0:
        nights_int = 1
    start = _parse_ddmmyyyy(date_str)
    if not start:
        return []
    return [start + timedelta(days=i) for i in range(nights_int)]


def _room_conflicts(reservation_id: int, room_id: str, date_str: str, nights: Optional[int]) -> list[str]:
    occupied: list[str] = []
    days = _reservation_days(date_str, nights)
    if not days:
        return occupied
    other_reservations = service.read_reservations(limit=1000, reservation_type="room")
    for r in other_reservations:
        if r.get("id") == reservation_id:
            continue
        if r.get("status") not in {"confirmed", "processing"}:
            continue
        other_room = _normalize_room_id(r.get("location"))
        if other_room != room_id:
            continue
        other_days = _reservation_days(r.get("date", ""), r.get("nights"))
        overlaps = {d.date() for d in days} & {d.date() for d in other_days}
        if overlaps:
            occupied.extend(sorted({d.strftime("%d.%m.%Y") for d in overlaps}))
    return occupied


# ============================================================
# PYDANTIC MODELS
# ============================================================

class ReservationUpdate(BaseModel):
    status: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    people: Optional[int] = None
    nights: Optional[int] = None
    location: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    event_type: Optional[str] = None
    special_needs: Optional[str] = None
    admin_notes: Optional[str] = None
    kids: Optional[str] = None
    kids_small: Optional[str] = None


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
    status: Optional[str] = None
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


class KnowledgeFeedbackRequest(BaseModel):
    question: str
    suggestion: str


# ============================================================
# STATIC FILE ROUTES
# ============================================================

@router.get("/test", response_class=HTMLResponse)
def barbara_page() -> HTMLResponse:
    html_path = Path("static/barbara.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Barbara UI manjka (static/barbara.html)</h1>", status_code=500)
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@router.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    html_path = Path("static/admin.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Admin UI manjka (static/admin.html)</h1>", status_code=500)
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@router.get("/admin/conversations", response_class=HTMLResponse)
def admin_conversations_page() -> HTMLResponse:
    html_path = Path("static/conversations.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Conversations UI manjka</h1>", status_code=500)
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ============================================================
# CONVERSATIONS API
# ============================================================

@router.get("/api/admin/conversations")
def get_conversations(limit: int = 200, needs_followup_only: bool = False):
    _log("conversations", limit=limit)
    conversations = service.get_conversations(limit=limit)
    return {"conversations": conversations, "stats": {"total": len(conversations)}}


@router.get("/api/admin/conversations/session/{session_id}")
def get_conversations_by_session(session_id: str, limit: int = 200):
    conversations = service.get_conversations_by_session(session_id=session_id, limit=limit)
    return {"session_id": session_id, "conversations": conversations, "total": len(conversations)}


@router.get("/api/admin/usage_stats")
def get_usage_stats():
    return service.get_usage_stats()


# ============================================================
# RESERVATIONS API
# ============================================================

@router.get("/api/admin/reservations")
def get_reservations(
    limit: int = 100,
    status: Optional[str] = None,
    type: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    _log("reservations", limit=limit, status=status, type=type)
    reservations = service.read_reservations(limit=limit, status=status, reservation_type=type, source=source)

    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
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
                filtered.append(r)
                continue
            for d in days:
                if start and d < start:
                    continue
                if end and d > end:
                    continue
                filtered.append(r)
                break
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


@router.put("/api/admin/reservations/{reservation_id}")
def update_reservation(reservation_id: int, data: ReservationUpdate):
    existing = service.get_reservation(reservation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    ok = service.update_reservation(
        reservation_id,
        **{k: v for k, v in data.model_dump().items() if v is not None},
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    return {"ok": True}


@router.patch("/api/admin/reservations/{reservation_id}")
def patch_reservation(reservation_id: int, data: ReservationUpdate):
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if data.status == "confirmed":
        fields["confirmed_at"] = datetime.now().isoformat()
    ok = service.update_reservation(reservation_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    return {"ok": True}


@router.post("/api/admin/reservations/{reservation_id}/confirm")
def confirm_reservation(reservation_id: int, data: Optional[ConfirmReservationRequest] = None):
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

    service.update_reservation(
        reservation_id,
        status="confirmed",
        confirmed_at=datetime.now().isoformat(),
        confirmed_by=os.getenv("ADMIN_EMAIL", "info@podgoro.si"),
        location=requested_room or requested_location,
    )
    res = service.get_reservation(reservation_id) or res
    send_reservation_confirmed(res)
    service.add_reservation_message(
        reservation_id=reservation_id,
        direction="outbound",
        subject=_ensure_subject_tag(reservation_id, "Potrditev rezervacije"),
        body="Rezervacija potrjena.",
        from_email=os.getenv("ADMIN_EMAIL", "info@podgoro.si"),
        to_email=res.get("email") or "",
        message_id=None,
    )
    return {"success": True, "email_sent": True, "room": requested_room or requested_location}


@router.post("/api/admin/reservations/{reservation_id}/reject")
def reject_reservation(reservation_id: int):
    res = service.get_reservation(reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    service.update_reservation(reservation_id, status="rejected")
    res = service.get_reservation(reservation_id) or res
    send_reservation_rejected(res)
    service.add_reservation_message(
        reservation_id=reservation_id,
        direction="outbound",
        subject=_ensure_subject_tag(reservation_id, "Zavrnjena rezervacija"),
        body="Rezervacija zavrnjena.",
        from_email=os.getenv("ADMIN_EMAIL", "info@podgoro.si"),
        to_email=res.get("email") or "",
        message_id=None,
    )
    return {"success": True, "email_sent": True}


def _email_action_html(title: str, message: str, success: bool = True) -> str:
    color = "#22c55e" if success else "#ef4444"
    return f"""
    <!DOCTYPE html><html lang="sl"><head><meta charset="UTF-8"><title>{title}</title>
    <style>body{{font-family:-apple-system,sans-serif;background:#f4f9f3;margin:0;padding:40px 20px}}
    .c{{max-width:500px;margin:0 auto;background:#fff;border-radius:16px;padding:40px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.1)}}
    h1{{color:#3a6b35;margin:0 0 16px;font-size:24px}}p{{color:#666;line-height:1.6;margin:0 0 24px}}
    a{{display:inline-block;margin-top:24px;color:#3a6b35;text-decoration:none}}</style></head>
    <body><div class="c"><h1 style="color:{color}">{title}</h1><p>{message}</p>
    <a href="/admin">Nazaj na admin panel</a></div></body></html>"""


@router.get("/api/admin/reservations/{reservation_id}/confirm")
def confirm_reservation_get(reservation_id: int):
    res = service.get_reservation(reservation_id)
    if not res:
        return HTMLResponse(_email_action_html("Ni najdena", f"Rezervacija #{reservation_id} ne obstaja.", False), status_code=404)
    if res.get("status") == "confirmed":
        return HTMLResponse(_email_action_html("Ze potrjeno", f"Rezervacija #{reservation_id} je bila ze potrjena."))
    service.update_reservation(reservation_id, status="confirmed", confirmed_at=datetime.now().isoformat())
    res = service.get_reservation(reservation_id) or res
    send_reservation_confirmed(res)
    return HTMLResponse(_email_action_html("Rezervacija potrjena", f"Rezervacija #{reservation_id} za {res.get('name', 'gosta')} je uspesno potrjena."))


@router.get("/api/admin/reservations/{reservation_id}/reject")
def reject_reservation_get(reservation_id: int):
    res = service.get_reservation(reservation_id)
    if not res:
        return HTMLResponse(_email_action_html("Ni najdena", f"Rezervacija #{reservation_id} ne obstaja.", False), status_code=404)
    if res.get("status") == "rejected":
        return HTMLResponse(_email_action_html("Ze zavrnjeno", f"Rezervacija #{reservation_id} je bila ze zavrnjena.", False))
    service.update_reservation(reservation_id, status="rejected")
    res = service.get_reservation(reservation_id) or res
    send_reservation_rejected(res)
    return HTMLResponse(_email_action_html("Rezervacija zavrnjena", f"Rezervacija #{reservation_id} zavrnjena.", False))


@router.post("/api/admin/send-message")
def send_message(data: SendMessageRequest):
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
            from_email=os.getenv("ADMIN_EMAIL", "info@podgoro.si"),
            to_email=data.email,
            message_id=None,
        )
    if data.set_processing:
        service.update_reservation(data.reservation_id, status="processing", guest_message=data.body)
    return {"ok": True}


@router.get("/api/admin/messages/pending")
def get_pending_messages():
    """Rezervacije z neprebranimi odgovori gostov."""
    items = service.get_pending_replies()
    return {"items": items, "count": len(items)}


@router.post("/api/admin/reservations/{reservation_id}/mark-read")
def mark_reservation_read(reservation_id: int):
    """Označi pogovor kot prebran."""
    res = service.get_reservation(reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    service.add_reservation_message(
        reservation_id=reservation_id,
        direction="outbound",
        subject="[PREBRANO]",
        body="",
        from_email=os.getenv("ADMIN_EMAIL", "info@podgoro.si"),
        to_email=res.get("email") or "",
        message_id=None,
    )
    return {"ok": True}


@router.delete("/api/admin/reservations/{reservation_id}")
def delete_reservation(reservation_id: int):
    """Izbriše posamezno rezervacijo."""
    ok = service.delete_reservation(reservation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rezervacija ni najdena")
    return {"success": True, "deleted": reservation_id}


@router.get("/api/admin/reservations/{reservation_id}/messages")
def get_reservation_messages(reservation_id: int):
    messages = service.list_reservation_messages(reservation_id)
    return {"messages": messages}


@router.get("/api/admin/stats")
def get_stats():
    _log("stats")
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    week_ago = datetime.now() - timedelta(days=7)
    month_ago = datetime.now().replace(day=1)
    res_list = service.read_reservations(limit=1000)

    counts = {
        "danes": 0,
        "ta_teden": 0,
        "ta_mesec": 0,
        "po_statusu": {"pending": 0, "processing": 0, "confirmed": 0, "rejected": 0},
        "po_tipu": {"room": 0, "table": 0, "bike": 0, "animals": 0},
    }
    for r in res_list:
        try:
            created = datetime.fromisoformat(str(r.get("created_at", "")))
        except Exception:
            created = None
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


@router.get("/api/admin/export")
def export_reservations(
    status: Optional[str] = None,
    type: Optional[str] = None,
    source: Optional[str] = None,
):
    data = get_reservations(limit=1000, status=status, type=type, source=source)
    reservations = data.get("reservations", [])
    headers = ["id", "date", "time", "nights", "people", "kids", "reservation_type", "name", "email", "phone", "location", "note", "status", "source", "created_at"]
    lines = [",".join(headers)]
    for r in reservations:
        row = []
        for h in headers:
            val = r.get(h, "") or ""
            cell = str(val).replace('"', '""')
            if any(c in cell for c in [",", "\n", '"']):
                cell = f'"{cell}"'
            row.append(cell)
        lines.append(",".join(row))
    return Response(
        content="\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pod_goro_reservations.csv"},
    )


@router.get("/api/admin/calendar/rooms")
def calendar_rooms(month: int, year: int):
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Neveljaven mesec")
    days: dict = {}
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
            entry["reservations"].append({
                "id": r.get("id"),
                "reservation_type": "room",
                "name": r.get("name"),
                "people": r.get("people"),
                "location": room_id,
                "status": status,
                "date": r.get("date"),
                "nights": r.get("nights"),
            })
    return {"days": days}


@router.get("/api/admin/calendar/tables")
def calendar_tables(month: int, year: int):
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Neveljaven mesec")
    days: dict = {}
    reservations = service.read_reservations(limit=1000, reservation_type="table")
    for r in reservations:
        status = r.get("status")
        if status not in {"pending", "processing", "confirmed"}:
            continue
        date_str = r.get("date", "")
        day = None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
            try:
                day = datetime.strptime(date_str.strip(), fmt)
                break
            except Exception:
                continue
        if not day:
            continue
        if day.month != month or day.year != year:
            continue
        key = day.strftime("%Y-%m-%d")
        entry = days.setdefault(key, {"reservations": [], "total_people": 0, "capacity": 40})
        entry["reservations"].append({
            "id": r.get("id"),
            "reservation_type": "table",
            "name": r.get("name"),
            "people": r.get("people") or 0,
            "location": r.get("location") or "Jedilnica",
            "status": status,
            "date": date_str,
            "time": r.get("time"),
            "email": r.get("email"),
            "phone": r.get("phone"),
        })
        entry["total_people"] += r.get("people") or 0
    return days


@router.post("/api/admin/reservations")
def create_admin_reservation(data: AdminCreateReservation):
    location = _normalize_room_id(data.location) if data.reservation_type == "room" else data.location
    final_status = data.status or ("pending" if data.source == "chatbot" else "confirmed")
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
        status=final_status,
        admin_notes=data.admin_notes,
        kids=data.kids,
        kids_small=data.kids_small,
        source=data.source,
        event_type=data.event_type,
        special_needs=data.special_needs,
    )
    return {"success": True, "id": new_id}


@router.delete("/api/admin/reservations/all")
def delete_all_reservations(token: str = Header(None, alias="X-Admin-Token"), t: str = Query(None)):
    verify_admin(token, t)
    count = service.delete_all_reservations()
    return {"success": True, "deleted": count}


@router.post("/api/admin/knowledge_feedback")
def create_knowledge_feedback(payload: KnowledgeFeedbackRequest):
    return {"ok": True, "id": None}
