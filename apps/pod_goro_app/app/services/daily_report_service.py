"""
Daily Conversation Report Service - Kovačnik AI

Generates and sends daily email reports of all chatbot conversations
to marko@creative-media.si every morning at 7:00.

FEATURES:
- Aggregates conversations since last report
- Groups messages by session
- Shows full conversation transcripts
- Highlights potential bugs/issues
- Provides summary statistics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pathlib import Path

from app.services.email_service import _send_email, _email_wrapper, BRAND_COLOR, BORDER_COLOR, MUTED_COLOR

# Configuration
REPORT_EMAIL = os.getenv("DAILY_REPORT_EMAIL", "marko@creative-media.si")
REPORT_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "last_report.txt"


def get_last_report_time() -> datetime:
    """
    Prebere čas zadnjega poročila iz datoteke.
    Če datoteka ne obstaja, vrne čas pred 24 urami.
    """
    if REPORT_STATE_FILE.exists():
        try:
            timestamp_str = REPORT_STATE_FILE.read_text().strip()
            return datetime.fromisoformat(timestamp_str)
        except Exception:
            pass

    # Default: 24 ur nazaj
    return datetime.now() - timedelta(hours=24)


def save_report_time(timestamp: datetime) -> None:
    """Shrani čas zadnjega poročila."""
    REPORT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_STATE_FILE.write_text(timestamp.isoformat())


def get_new_conversations(service, since: datetime) -> List[Dict[str, Any]]:
    """
    Pridobi vse pogovore od določenega časa naprej.

    Args:
        service: ReservationService instance
        since: Datum/čas od katerega naprej iščemo

    Returns:
        List of conversation dicts with session grouping
    """
    # Get all conversations since timestamp
    conn = service._conn()
    cursor = conn.cursor()
    ph = service._placeholder()

    query = f"""
        SELECT session_id, user_message, bot_response, intent,
               needs_followup, followup_email, created_at
        FROM conversations
        WHERE created_at >= {ph}
        ORDER BY created_at ASC
    """

    # Convert datetime to SQLite-compatible format (YYYY-MM-DD HH:MM:SS)
    since_str = since.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(query, (since_str,))
    rows = cursor.fetchall()

    # Convert rows to dicts for compatibility with both SQLite and PostgreSQL
    rows_dicts = [dict(row) for row in rows]

    # Group by session
    sessions = {}
    for row in rows_dicts:
        session_id = row["session_id"]
        if session_id not in sessions:
            sessions[session_id] = {
                "session_id": session_id,
                "messages": [],
                "intents": set(),
                "needs_followup": False,
                "email": None,
                "first_message_time": row["created_at"],
            }

        sessions[session_id]["messages"].append({
            "user": row["user_message"],
            "bot": row["bot_response"],
            "intent": row["intent"],
            "time": row["created_at"],
        })

        if row["intent"]:
            sessions[session_id]["intents"].add(row["intent"])

        if row["needs_followup"]:
            sessions[session_id]["needs_followup"] = True

        if row["followup_email"]:
            sessions[session_id]["email"] = row["followup_email"]

    cursor.close()
    conn.close()

    return list(sessions.values())


def _format_session_html(session: Dict[str, Any], index: int) -> str:
    """Formatira en session pogovora v HTML."""
    session_id = session["session_id"]
    messages = session["messages"]
    intents = ", ".join(sorted(session["intents"])) if session["intents"] else "—"
    email = session.get("email") or "—"
    needs_followup = session.get("needs_followup", False)
    first_time = datetime.fromisoformat(session["first_message_time"]).strftime("%d.%m.%Y %H:%M")

    # Warning badge if needs followup
    warning = ""
    if needs_followup:
        warning = f"""
        <span style="display:inline-block; background:#ef4444; color:#fff; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:700; margin-left:8px;">
            ⚠️ POTREBUJE ODGOVOR
        </span>
        """

    # Message transcript
    transcript = ""
    for msg in messages:
        msg_time = datetime.fromisoformat(msg["time"]).strftime("%H:%M")
        user_msg = msg["user"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        bot_msg = msg["bot"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        intent_tag = f" <code style='font-size:11px; color:#888;'>[{msg['intent']}]</code>" if msg["intent"] else ""

        transcript += f"""
        <div style="margin:12px 0; padding:10px; background:#f9fafb; border-left:3px solid #e5e7eb; border-radius:6px;">
            <div style="color:#6b7280; font-size:12px; margin-bottom:6px;">
                <strong>Gost</strong> · {msg_time}
            </div>
            <div style="color:#111827; line-height:1.6;">
                {user_msg}
            </div>
        </div>

        <div style="margin:12px 0 12px 20px; padding:10px; background:#fef3c7; border-left:3px solid {BRAND_COLOR}; border-radius:6px;">
            <div style="color:#92400e; font-size:12px; margin-bottom:6px;">
                <strong>Bot</strong> · {msg_time}{intent_tag}
            </div>
            <div style="color:#451a03; line-height:1.6;">
                {bot_msg}
            </div>
        </div>
        """

    return f"""
    <div style="margin:24px 0; padding:20px; background:#fff; border:2px solid {BORDER_COLOR}; border-radius:12px;">
        <div style="margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid {BORDER_COLOR};">
            <h3 style="margin:0; color:{BRAND_COLOR}; font-size:16px;">
                Pogovor #{index} {warning}
            </h3>
            <div style="margin-top:8px; font-size:13px; color:{MUTED_COLOR};">
                <strong>Session ID:</strong> {session_id}<br>
                <strong>Prvi kontakt:</strong> {first_time}<br>
                <strong>Intenti:</strong> {intents}<br>
                <strong>Email:</strong> {email}
            </div>
        </div>

        {transcript}
    </div>
    """


def _generate_report_html(conversations: List[Dict[str, Any]], since: datetime, now: datetime) -> str:
    """Generira HTML report vseh pogovorov."""
    total_conversations = len(conversations)
    total_messages = sum(len(c["messages"]) for c in conversations)
    needs_followup = sum(1 for c in conversations if c.get("needs_followup"))

    # Intent statistics
    intent_counts = {}
    for conv in conversations:
        for intent in conv["intents"]:
            intent_counts[intent] = intent_counts.get(intent, 0) + 1

    top_intents = sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    intent_list = "<br>".join([f"• {intent}: {count}x" for intent, count in top_intents]) if top_intents else "—"

    # Period formatting
    since_str = since.strftime("%d.%m.%Y %H:%M")
    now_str = now.strftime("%d.%m.%Y %H:%M")

    # Summary box
    summary = f"""
    <div style="background:{BRAND_COLOR}; color:#fff; padding:20px; border-radius:10px; margin-bottom:24px;">
        <h2 style="margin:0 0 16px 0; font-size:20px;">📊 Dnevno poročilo - Kovačnik AI</h2>
        <div style="font-size:14px; line-height:1.8;">
            <strong>Obdobje:</strong> {since_str} → {now_str}<br>
            <strong>Skupaj pogovorov:</strong> {total_conversations}<br>
            <strong>Skupaj sporočil:</strong> {total_messages}<br>
            <strong>Potrebuje odgovor:</strong> {needs_followup}
        </div>
    </div>

    <div style="background:#fef3c7; border-left:4px solid #f59e0b; padding:16px; border-radius:8px; margin-bottom:24px;">
        <div style="font-size:14px; color:#92400e;">
            <strong>Najbolj pogosti intenti:</strong><br>
            <div style="margin-top:8px; line-height:1.8;">
                {intent_list}
            </div>
        </div>
    </div>
    """

    # No conversations
    if total_conversations == 0:
        content = summary + f"""
        <div style="padding:40px; text-align:center; background:#f9fafb; border-radius:10px; color:{MUTED_COLOR};">
            <p style="margin:0; font-size:16px;">Ni novih pogovorov v tem obdobju.</p>
        </div>
        """
        return _email_wrapper(content)

    # Conversations
    conversations_html = ""
    for i, conv in enumerate(conversations, start=1):
        conversations_html += _format_session_html(conv, i)

    content = f"""
    {summary}

    <h2 style="color:{BRAND_COLOR}; font-size:18px; margin:32px 0 16px 0; padding-bottom:8px; border-bottom:2px solid {BORDER_COLOR};">
        💬 Vsi pogovori
    </h2>

    {conversations_html}

    <div style="margin-top:32px; padding:16px; background:#f0fdf4; border:1px solid #86efac; border-radius:8px; font-size:13px; color:#166534;">
        <strong>Naslednje poročilo:</strong> Jutri ob 7:00<br>
        <strong>Admin panel:</strong> <a href="https://kovacnik-ai.up.railway.app/admin" style="color:{BRAND_COLOR};">Ogled vseh rezervacij</a>
    </div>
    """

    return _email_wrapper(content)


def generate_and_send_daily_report() -> bool:
    """
    Glavna funkcija za generiranje in pošiljanje dnevnega poročila.

    Returns:
        True če uspešno poslano
    """
    from app.services.reservation_service import ReservationService

    try:
        service = ReservationService()
        now = datetime.now()
        since = get_last_report_time()

        print(f"[DAILY REPORT] Generiram poročilo: {since.isoformat()} → {now.isoformat()}")

        # Get conversations
        conversations = get_new_conversations(service, since)

        print(f"[DAILY REPORT] Najdenih {len(conversations)} pogovorov")

        # Generate HTML
        html = _generate_report_html(conversations, since, now)

        # Send email
        subject = f"Kovačnik AI - Dnevno poročilo ({now.strftime('%d.%m.%Y')})"
        success = _send_email(REPORT_EMAIL, subject, html)

        if success:
            # Save report time
            save_report_time(now)
            print(f"[DAILY REPORT] Poročilo uspešno poslano na {REPORT_EMAIL}")
        else:
            print(f"[DAILY REPORT] Napaka pri pošiljanju poročila")

        return success

    except Exception as e:
        print(f"[DAILY REPORT] Napaka: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# WEEKLY TABLE RESERVATION REMINDER
# ============================================================

WEEKLY_REMINDER_EMAILS = os.getenv("WEEKLY_REMINDER_EMAILS", "satlermarko@gmail.com")


def get_upcoming_weekend_reservations(service) -> Dict[str, List[Dict[str, Any]]]:
    """
    Pridobi rezervacije miz za prihajajoči vikend (petek-nedelja).
    Vrne samo POTRJENE rezervacije.
    """
    from datetime import date, timedelta

    today = date.today()
    weekday = today.weekday()  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun

    # Če je danes petek, sobota ali nedelja -> prikaži TA vikend
    if weekday == 4:  # Petek
        friday = today
        saturday = today + timedelta(days=1)
        sunday = today + timedelta(days=2)
    elif weekday == 5:  # Sobota
        friday = today - timedelta(days=1)
        saturday = today
        sunday = today + timedelta(days=1)
    elif weekday == 6:  # Nedelja
        friday = today - timedelta(days=2)
        saturday = today - timedelta(days=1)
        sunday = today
    else:  # Pon-Čet -> prikaži PRIHAJAJOČI vikend
        days_until_friday = (4 - weekday) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        friday = today + timedelta(days=days_until_friday)
        saturday = friday + timedelta(days=1)
        sunday = friday + timedelta(days=2)

    # Get all table reservations for these 3 days
    conn = service._conn()
    cursor = conn.cursor()
    ph = service._placeholder()

    query = f"""
        SELECT id, date, time, people, name, email, phone, location, note, status
        FROM reservations
        WHERE reservation_type = 'table'
        AND status = 'confirmed'
        AND date IN ({ph}, {ph}, {ph})
        ORDER BY date ASC, time ASC
    """

    # Database stores dates in DD.MM.YYYY format
    cursor.execute(query, (
        friday.strftime("%d.%m.%Y"),
        saturday.strftime("%d.%m.%Y"),
        sunday.strftime("%d.%m.%Y"),
    ))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert rows to dicts for PostgreSQL compatibility
    rows_dicts = [dict(row) for row in rows]

    # Group by date
    by_date = {
        friday.strftime("%Y-%m-%d"): [],
        saturday.strftime("%Y-%m-%d"): [],
        sunday.strftime("%Y-%m-%d"): [],
    }

    for row in rows_dicts:
        reservation = {
            "id": row["id"],
            "date": row["date"],
            "time": row["time"],
            "people": row["people"],
            "name": row["name"],
            "email": row["email"],
            "phone": row["phone"],
            "location": row["location"],
            "note": row["note"],
            "status": row["status"],
        }
        # Convert date from DD.MM.YYYY to YYYY-MM-DD for dictionary key
        try:
            db_date = datetime.strptime(row["date"], "%d.%m.%Y")
            date_key = db_date.strftime("%Y-%m-%d")
        except Exception:
            date_key = row["date"]

        if date_key in by_date:
            by_date[date_key].append(reservation)

    return by_date


def _format_reservation_item(res: Dict[str, Any]) -> str:
    """Formatira eno rezervacijo v HTML."""
    special_notes = []
    if res.get("note"):
        note = res["note"].lower()
        if any(kw in note for kw in ("vegan", "vegetar", "gluten", "alergij", "lakto")):
            special_notes.append(f"⚠️ {res['note']}")

    special_html = ""
    if special_notes:
        special_html = f"""
        <div style="margin-top:4px; padding:6px 10px; background:#fef3c7; border-left:3px solid #f59e0b; border-radius:4px; font-size:13px; color:#92400e;">
            {'<br>'.join(special_notes)}
        </div>
        """

    phone_display = res.get('phone') or '—'
    location = res.get('location') or '—'

    return f"""
    <div style="margin:10px 0; padding:12px; background:#fff; border-left:4px solid {BRAND_COLOR}; border-radius:6px;">
        <div style="font-size:15px; color:#111;">
            <strong>{res['time']}</strong> | <strong>{res['people']} oseb</strong> | {res['name']}
        </div>
        <div style="margin-top:6px; font-size:13px; color:{MUTED_COLOR}; line-height:1.6;">
            Jedilnica: {location}<br>
            Telefon: {phone_display}
        </div>
        {special_html}
    </div>
    """


def _format_weekend_reminder_html(by_date: Dict[str, List[Dict[str, Any]]]) -> str:
    """Generira HTML za tedenski reminder rezervacij."""
    from datetime import datetime

    # Calculate totals
    total_reservations = sum(len(reservations) for reservations in by_date.values())
    total_guests = sum(
        sum(r.get('people', 0) for r in reservations)
        for reservations in by_date.values()
    )

    special_count = 0
    for reservations in by_date.values():
        for r in reservations:
            if r.get('note'):
                note = r['note'].lower()
                if any(kw in note for kw in ("vegan", "vegetar", "gluten", "alergij", "lakto")):
                    special_count += 1

    # Format date labels
    day_labels = {}
    day_names = ["Ponedeljek", "Torek", "Sreda", "Četrtek", "Petek", "Sobota", "Nedelja"]
    for date_str in by_date.keys():
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = day_names[dt.weekday()]
        day_labels[date_str] = f"{day_name.upper()} {dt.strftime('%d.%m.%Y')}"

    # Build days HTML
    days_html = ""
    for date_str, reservations in by_date.items():
        if not reservations:
            continue

        day_total = sum(r.get('people', 0) for r in reservations)

        reservations_html = "".join(_format_reservation_item(r) for r in reservations)

        days_html += f"""
        <div style="margin:24px 0;">
            <h3 style="margin:0 0 12px 0; padding:10px; background:{BRAND_COLOR}; color:#fff; border-radius:8px; font-size:16px;">
                {day_labels[date_str]} | Skupaj: {day_total} oseb
            </h3>
            {reservations_html}
        </div>
        """

    if not days_html:
        days_html = f"""
        <div style="padding:40px; text-align:center; background:#f9fafb; border-radius:10px; color:{MUTED_COLOR};">
            <p style="margin:0; font-size:16px;">Ni potrjenih rezervacij za prihajajoči vikend.</p>
        </div>
        """

    # Summary
    summary = f"""
    <div style="background:{BRAND_COLOR}; color:#fff; padding:20px; border-radius:10px; margin-bottom:24px;">
        <h2 style="margin:0 0 16px 0; font-size:20px;">🍽️ Tedenski pregled - Rezervacije miz</h2>
        <div style="font-size:14px; line-height:1.8;">
            <strong>Obdobje:</strong> Prihajajoči vikend (petek-nedelja)<br>
            <strong>Skupaj rezervacij:</strong> {total_reservations}<br>
            <strong>Skupaj gostov:</strong> {total_guests}<br>
            <strong>Posebne zahteve:</strong> {special_count}
        </div>
    </div>
    """

    content = f"""
    {summary}

    <h2 style="color:{BRAND_COLOR}; font-size:18px; margin:32px 0 16px 0; padding-bottom:8px; border-bottom:2px solid {BORDER_COLOR};">
        📅 Rezervacije po dnevih
    </h2>

    {days_html}

    <div style="margin-top:32px; padding:16px; background:#f0fdf4; border:1px solid #86efac; border-radius:8px; font-size:13px; color:#166534;">
        <strong>Naslednji reminder:</strong> Prihodnji četrtek ob 18:00<br>
        <strong>Admin panel:</strong> <a href="https://kovacnik-ai.up.railway.app/admin" style="color:{BRAND_COLOR};">Ogled vseh rezervacij</a>
    </div>
    """

    return _email_wrapper(content)


def generate_and_send_weekly_reminder() -> bool:
    """
    Glavna funkcija za generiranje in pošiljanje tedenskega reminderja rezervacij miz.
    Pošlje vsak četrtek ob 18:00.

    Returns:
        True če uspešno poslano
    """
    from app.services.reservation_service import ReservationService

    try:
        service = ReservationService()

        print("[WEEKLY REMINDER] Generiram tedenski reminder...")

        # Get weekend reservations
        by_date = get_upcoming_weekend_reservations(service)

        # Count total
        total = sum(len(reservations) for reservations in by_date.values())
        print(f"[WEEKLY REMINDER] Najdenih {total} potrjenih rezervacij")

        # Generate HTML
        html = _format_weekend_reminder_html(by_date)

        # Send to all recipients
        recipients = [email.strip() for email in WEEKLY_REMINDER_EMAILS.split(",")]

        today = datetime.now()
        subject = f"Kovačnik - Rezervacije za vikend ({today.strftime('%d.%m.%Y')})"

        success_count = 0
        for recipient in recipients:
            if recipient:
                success = _send_email(recipient, subject, html)
                if success:
                    success_count += 1
                    print(f"[WEEKLY REMINDER] Poslano na {recipient}")
                else:
                    print(f"[WEEKLY REMINDER] Napaka pri pošiljanju na {recipient}")

        print(f"[WEEKLY REMINDER] Poslano na {success_count}/{len(recipients)} naslovov")
        return success_count > 0

    except Exception as e:
        print(f"[WEEKLY REMINDER] Napaka: {e}")
        import traceback
        traceback.print_exc()
        return False
