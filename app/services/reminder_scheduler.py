"""
Reminder Scheduler - SMART REMINDERS za zdravstveni center

FUNKCIONALNOST:
1. 3 dni pred terminom: Email + SMS z navodili
2. 2 uri pred terminom: SMS z quick actions (DA/PRESTAVI/ODPOVEJ)
3. 1 dan po obisku: Follow-up SMS "Kako ste?"
4. No-show tracking in analytics

UPORABA:
- V main.py dodaj: await start_reminder_scheduler()
- Scheduler se bo zagnal v ozadju in deloval dokler FastAPI teče

KONFIGURACIJA (.env):
- REMINDER_CHECK_INTERVAL_MINUTES=30
- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER (za SMS)
- SMS_MOCK_MODE=true (za testiranje brez Twilio)
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from enum import Enum

# Import email service
from app.services.email_service import send_appointment_reminder as send_email_reminder

# Import SMS service
try:
    from app.services.sms_service import (
        send_3_day_reminder as send_sms_3_day,
        send_2_hour_reminder as send_sms_2_hour,
        send_post_visit_followup as send_sms_followup,
        send_confirmation_sms,
    )
    HAS_SMS = True
except ImportError:
    HAS_SMS = False
    print("[REMINDER] SMS service not available")

# Logger
logger = logging.getLogger(__name__)

# Konfiguracija
REMINDER_CHECK_INTERVAL_MINUTES = int(os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "30"))  # Preveri vsakih 30 min
ENABLE_SMS_REMINDERS = os.getenv("ENABLE_SMS_REMINDERS", "true").lower() in ("true", "1", "yes")
ENABLE_EMAIL_REMINDERS = os.getenv("ENABLE_EMAIL_REMINDERS", "true").lower() in ("true", "1", "yes")


class ReminderStage(Enum):
    """Različne stopnje opomnikov"""
    NONE = 0                    # Noben opomnik še poslan
    SENT_3_DAY = 1              # Poslan 3 dni prej
    SENT_2_HOUR = 2             # Poslan 2 uri prej
    COMPLETED = 3               # Termin opravljen
    NO_SHOW = 4                 # Pacient ni prišel
    FOLLOWUP_SENT = 5           # Follow-up poslan po obisku

# Globalna referenca na running task (za graceful shutdown)
_scheduler_task = None


def _parse_datetime(date_str: str, time_str: str) -> datetime:
    """
    Pretvori datum (DD.MM.YYYY) in čas (HH:MM) v datetime objekt.

    Args:
        date_str: Format DD.MM.YYYY (npr. "25.01.2026")
        time_str: Format HH:MM (npr. "14:30")

    Returns:
        datetime objekt

    Raises:
        ValueError: če format ni pravilen
    """
    try:
        parts = date_str.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid date format: {date_str}")

        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        hour, minute = map(int, time_str.split(':'))

        return datetime(year, month, day, hour, minute)
    except Exception as e:
        raise ValueError(f"Error parsing date/time {date_str} {time_str}: {e}")


def _get_db_connection():
    """Pridobi database connection (SQLite ali Postgres)."""
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

    # Postgres
    if DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor), "postgres"
        except ImportError:
            logger.error("psycopg2 not installed but DATABASE_URL is set")
            raise

    # SQLite (default za lokalni razvoj)
    import sqlite3
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    db_path = os.path.join(project_root, "data", "reservations.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


def _get_placeholder(db_type: str) -> str:
    """Vrne placeholder za SQL query (? za SQLite, %s za Postgres)."""
    return "%s" if db_type == "postgres" else "?"


def _ensure_reminder_columns():
    """
    Doda potrebne stolpce za smart reminders v bazo.

    Stolpci:
    - reminder_stage: 0=none, 1=3-day sent, 2=2-hour sent, 3=completed, 4=no-show, 5=followup sent
    - reminder_sent: Legacy (za backwards compatibility)
    - last_reminder_at: Timestamp zadnjega opomnika
    - patient_confirmed: Ali je pacient potrdil prihod (via SMS quick action)
    """
    conn, db_type = _get_db_connection()
    try:
        cur = conn.cursor()

        columns_to_add = [
            ("reminder_sent", "INTEGER DEFAULT 0"),
            ("reminder_stage", "INTEGER DEFAULT 0"),
            ("last_reminder_at", "TEXT"),
            ("patient_confirmed", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_type in columns_to_add:
            try:
                # Preveri če stolpec že obstaja
                if db_type == "postgres":
                    cur.execute(f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name='reservations' AND column_name='{col_name}'
                    """)
                    exists = cur.fetchone()
                else:  # SQLite
                    cur.execute("PRAGMA table_info(reservations)")
                    columns = [row[1] for row in cur.fetchall()]
                    exists = col_name in columns

                # Dodaj stolpec, če ne obstaja
                if not exists:
                    logger.info(f"Adding {col_name} column to reservations table")
                    cur.execute(f"ALTER TABLE reservations ADD COLUMN {col_name} {col_type}")
                    conn.commit()
                    logger.info(f"{col_name} column added successfully")

            except Exception as e:
                logger.warning(f"Could not add column {col_name}: {e}")

    except Exception as e:
        logger.error(f"Error ensuring reminder columns: {e}")
    finally:
        cur.close()
        conn.close()


def _ensure_reminder_sent_column():
    """Legacy wrapper za backwards compatibility."""
    _ensure_reminder_columns()


def get_appointments_by_stage(target_stage: ReminderStage) -> List[Dict[str, Any]]:
    """
    Poišče termine, ki potrebujejo določeno stopnjo opomnika.

    Args:
        target_stage: Katera stopnja opomnika se išče

    Returns:
        Seznam terminov, ki potrebujejo to stopnjo opomnika
    """
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()

        # Določi current stage in time window glede na target
        if target_stage == ReminderStage.SENT_3_DAY:
            # 3 dni pred - stage mora biti NONE (0)
            current_stage = ReminderStage.NONE.value
            hours_before_min = 70  # ~3 dni (72h) - 2h buffer
            hours_before_max = 74  # ~3 dni + 2h buffer
        elif target_stage == ReminderStage.SENT_2_HOUR:
            # 2 uri pred - stage mora biti SENT_3_DAY (1)
            current_stage = ReminderStage.SENT_3_DAY.value
            hours_before_min = 1.5  # 1.5h
            hours_before_max = 2.5  # 2.5h
        elif target_stage == ReminderStage.FOLLOWUP_SENT:
            # 1 dan po - stage mora biti COMPLETED (3)
            current_stage = ReminderStage.COMPLETED.value
            hours_before_min = -26  # 26h po (negativno = v preteklosti)
            hours_before_max = -22  # 22h po
        else:
            return []

        # Poišči termine z ustreznim stage
        query = f"""
            SELECT * FROM reservations
            WHERE status = {ph}
            AND (reminder_stage IS NULL OR reminder_stage = {ph})
            AND date IS NOT NULL
            AND time IS NOT NULL
        """
        cur.execute(query, ('confirmed', current_stage))
        rows = cur.fetchall()

        # Filtriraj termine v časovnem oknu
        now = datetime.now()
        appointments = []

        for row in rows:
            try:
                appointment_dt = _parse_datetime(row['date'], row['time'])
                hours_until = (appointment_dt - now).total_seconds() / 3600

                # Preveri časovno okno
                if hours_before_min <= hours_until <= hours_before_max:
                    appointments.append(dict(row))

            except ValueError as e:
                logger.warning(f"Skipping appointment {row['id']}: {e}")
                continue

        return appointments

    except Exception as e:
        logger.error(f"Error fetching appointments for stage {target_stage}: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_completed_appointments_for_followup() -> List[Dict[str, Any]]:
    """
    Poišče opravljene termine, ki potrebujejo follow-up.

    Kriteriji:
    - status = 'completed'
    - reminder_stage = COMPLETED (3)
    - 22-26 ur po terminu
    """
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()

        query = f"""
            SELECT * FROM reservations
            WHERE status = {ph}
            AND reminder_stage = {ph}
            AND date IS NOT NULL
            AND time IS NOT NULL
            AND phone IS NOT NULL
        """
        cur.execute(query, ('completed', ReminderStage.COMPLETED.value))
        rows = cur.fetchall()

        now = datetime.now()
        appointments = []

        for row in rows:
            try:
                appointment_dt = _parse_datetime(row['date'], row['time'])
                hours_since = (now - appointment_dt).total_seconds() / 3600

                # 22-26 ur po terminu (približno 1 dan)
                if 22 <= hours_since <= 26:
                    appointments.append(dict(row))

            except ValueError as e:
                logger.warning(f"Skipping appointment {row['id']}: {e}")
                continue

        return appointments

    except Exception as e:
        logger.error(f"Error fetching appointments for followup: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_appointments_needing_reminder() -> List[Dict[str, Any]]:
    """
    LEGACY: Poišče termine za 24h opomnik.
    Ohrani za backwards compatibility.
    """
    return get_appointments_by_stage(ReminderStage.SENT_3_DAY)


def update_reminder_stage(appointment_id: int, new_stage: ReminderStage) -> bool:
    """
    Posodobi reminder_stage za termin.

    Args:
        appointment_id: ID termina
        new_stage: Nova stopnja opomnika

    Returns:
        True če uspešno posodobljeno
    """
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()
        now_str = datetime.now().isoformat()
        cur.execute(
            f"UPDATE reservations SET reminder_stage = {ph}, last_reminder_at = {ph} WHERE id = {ph}",
            (new_stage.value, now_str, appointment_id)
        )
        conn.commit()
        logger.info(f"Updated appointment {appointment_id} to stage {new_stage.name}")
        return True
    except Exception as e:
        logger.error(f"Error updating reminder stage for appointment {appointment_id}: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def mark_patient_confirmed(appointment_id: int, confirmed: bool = True) -> bool:
    """
    Označi, da je pacient potrdil prihod (via SMS quick action).

    Args:
        appointment_id: ID termina
        confirmed: True = potrjeno, False = odpovedano/prestavljeno

    Returns:
        True če uspešno posodobljeno
    """
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE reservations SET patient_confirmed = {ph} WHERE id = {ph}",
            (1 if confirmed else 0, appointment_id)
        )
        conn.commit()
        logger.info(f"Marked appointment {appointment_id} patient_confirmed={confirmed}")
        return True
    except Exception as e:
        logger.error(f"Error marking patient confirmed for appointment {appointment_id}: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def mark_reminder_sent(appointment_id: int) -> bool:
    """
    LEGACY: Označi termin kot 'reminder_sent = 1'.
    Ohrani za backwards compatibility.
    """
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE reservations SET reminder_sent = 1 WHERE id = {ph}", (appointment_id,))
        conn.commit()
        logger.info(f"Marked appointment {appointment_id} as reminder_sent")
        return True
    except Exception as e:
        logger.error(f"Error marking reminder sent for appointment {appointment_id}: {e}")
        return False
    finally:
        cur.close()
        conn.close()


async def send_3_day_reminders():
    """
    Pošlje 3-dnevne opomnike (Email + SMS z navodili).
    """
    if not ENABLE_EMAIL_REMINDERS and not ENABLE_SMS_REMINDERS:
        return 0

    appointments = get_appointments_by_stage(ReminderStage.SENT_3_DAY)
    sent_count = 0

    for apt in appointments:
        try:
            appointment_id = apt['id']
            logger.info(f"[3-DAY] Sending reminder for #{appointment_id} - {apt.get('name')}")

            email_sent = False
            sms_sent = False

            # Pošlji Email
            if ENABLE_EMAIL_REMINDERS and apt.get('email'):
                try:
                    email_sent = send_email_reminder(apt)
                    if email_sent:
                        logger.info(f"[3-DAY] Email sent for #{appointment_id}")
                except Exception as e:
                    logger.warning(f"[3-DAY] Email failed for #{appointment_id}: {e}")

            # Pošlji SMS
            if ENABLE_SMS_REMINDERS and HAS_SMS and apt.get('phone'):
                try:
                    result = send_sms_3_day(apt)
                    sms_sent = result.get('success', False)
                    if sms_sent:
                        logger.info(f"[3-DAY] SMS sent for #{appointment_id}")
                except Exception as e:
                    logger.warning(f"[3-DAY] SMS failed for #{appointment_id}: {e}")

            # Če vsaj en kanal uspešen, posodobi stage
            if email_sent or sms_sent:
                update_reminder_stage(appointment_id, ReminderStage.SENT_3_DAY)
                sent_count += 1

        except Exception as e:
            logger.error(f"[3-DAY] Error for #{apt.get('id')}: {e}")

    return sent_count


async def send_2_hour_reminders():
    """
    Pošlje 2-urne opomnike (SMS z quick actions).
    """
    if not ENABLE_SMS_REMINDERS or not HAS_SMS:
        return 0

    appointments = get_appointments_by_stage(ReminderStage.SENT_2_HOUR)
    sent_count = 0

    for apt in appointments:
        try:
            appointment_id = apt['id']

            if not apt.get('phone'):
                logger.warning(f"[2-HOUR] No phone for #{appointment_id}, skipping")
                continue

            logger.info(f"[2-HOUR] Sending reminder for #{appointment_id} - {apt.get('name')}")

            result = send_sms_2_hour(apt)

            if result.get('success'):
                update_reminder_stage(appointment_id, ReminderStage.SENT_2_HOUR)
                sent_count += 1
                logger.info(f"[2-HOUR] SMS sent for #{appointment_id}")
            else:
                logger.warning(f"[2-HOUR] SMS failed for #{appointment_id}: {result.get('error')}")

        except Exception as e:
            logger.error(f"[2-HOUR] Error for #{apt.get('id')}: {e}")

    return sent_count


async def send_post_visit_followups():
    """
    Pošlje follow-up sporočila 1 dan po obisku.
    """
    if not ENABLE_SMS_REMINDERS or not HAS_SMS:
        return 0

    appointments = get_completed_appointments_for_followup()
    sent_count = 0

    for apt in appointments:
        try:
            appointment_id = apt['id']

            if not apt.get('phone'):
                logger.warning(f"[FOLLOWUP] No phone for #{appointment_id}, skipping")
                continue

            logger.info(f"[FOLLOWUP] Sending follow-up for #{appointment_id} - {apt.get('name')}")

            result = send_sms_followup(apt)

            if result.get('success'):
                update_reminder_stage(appointment_id, ReminderStage.FOLLOWUP_SENT)
                sent_count += 1
                logger.info(f"[FOLLOWUP] SMS sent for #{appointment_id}")
            else:
                logger.warning(f"[FOLLOWUP] SMS failed for #{appointment_id}: {result.get('error')}")

        except Exception as e:
            logger.error(f"[FOLLOWUP] Error for #{apt.get('id')}: {e}")

    return sent_count


async def check_and_send_reminders():
    """
    Glavna funkcija - preveri vse stopnje opomnikov.
    Kliče se periodično (vsakih 30 min).

    Stopnje:
    1. 3 dni prej: Email + SMS z navodili
    2. 2 uri prej: SMS z quick actions (DA/PRESTAVI/ODPOVEJ)
    3. 1 dan po: Follow-up SMS "Kako ste?"
    """
    logger.info("🔔 Checking for appointments needing reminders...")

    try:
        total_sent = 0

        # 1. 3-dnevni opomniki
        count_3day = await send_3_day_reminders()
        total_sent += count_3day

        # 2. 2-urni opomniki
        count_2hour = await send_2_hour_reminders()
        total_sent += count_2hour

        # 3. Post-visit follow-up
        count_followup = await send_post_visit_followups()
        total_sent += count_followup

        if total_sent > 0:
            logger.info(f"✅ Reminder check completed: {count_3day} 3-day, {count_2hour} 2-hour, {count_followup} follow-up")
        else:
            logger.info("No reminders needed at this time")

    except Exception as e:
        logger.error(f"Error in check_and_send_reminders: {e}")


async def reminder_scheduler_loop():
    """
    Neskončna zanka, ki periodično preverja termine.
    Teče v ozadju kot asyncio task.
    """
    logger.info(f"🚀 Reminder scheduler started (checking every {REMINDER_CHECK_INTERVAL_MINUTES} minutes)")

    # Najprej dodaj reminder_sent stolpec, če ne obstaja
    _ensure_reminder_sent_column()

    while True:
        try:
            await check_and_send_reminders()
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")

        # Počakaj do naslednjega preverjanja
        await asyncio.sleep(REMINDER_CHECK_INTERVAL_MINUTES * 60)


async def start_reminder_scheduler():
    """
    Zaženi scheduler v ozadju.
    Uporabi v main.py kot startup event:

    @app.on_event("startup")
    async def startup_event():
        await start_reminder_scheduler()
    """
    global _scheduler_task

    # Če je scheduler že zagnan, ne zaganjaj ponovno
    if _scheduler_task and not _scheduler_task.done():
        logger.warning("Reminder scheduler is already running")
        return

    logger.info("Starting reminder scheduler...")
    _scheduler_task = asyncio.create_task(reminder_scheduler_loop())
    logger.info("✅ Reminder scheduler started successfully")


async def stop_reminder_scheduler():
    """
    Ustavi scheduler (uporabi pri shutdown).

    @app.on_event("shutdown")
    async def shutdown_event():
        await stop_reminder_scheduler()
    """
    global _scheduler_task

    if _scheduler_task and not _scheduler_task.done():
        logger.info("Stopping reminder scheduler...")
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            logger.info("✅ Reminder scheduler stopped")
    else:
        logger.info("Reminder scheduler was not running")


# ============================================================
# NO-SHOW DETECTION & SMS RESPONSE HANDLING
# ============================================================

def detect_no_shows() -> List[Dict[str, Any]]:
    """
    Zazna termine kjer pacient ni prišel (no-show).

    Kriteriji:
    - Termin je bil v preteklosti
    - Status je še vedno 'confirmed' (ni bil označen kot completed)
    - Minila je več kot 1 ura od termina
    """
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()

        query = f"""
            SELECT * FROM reservations
            WHERE status = {ph}
            AND reminder_stage < {ph}
            AND date IS NOT NULL
            AND time IS NOT NULL
        """
        cur.execute(query, ('confirmed', ReminderStage.NO_SHOW.value))
        rows = cur.fetchall()

        now = datetime.now()
        no_shows = []

        for row in rows:
            try:
                appointment_dt = _parse_datetime(row['date'], row['time'])

                # Če je termin več kot 1 uro v preteklosti
                if appointment_dt < now - timedelta(hours=1):
                    no_shows.append(dict(row))

            except ValueError:
                continue

        return no_shows

    except Exception as e:
        logger.error(f"Error detecting no-shows: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def mark_appointment_no_show(appointment_id: int) -> bool:
    """Označi termin kot no-show."""
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE reservations SET reminder_stage = {ph}, status = {ph} WHERE id = {ph}",
            (ReminderStage.NO_SHOW.value, 'no_show', appointment_id)
        )
        conn.commit()
        logger.info(f"Marked appointment {appointment_id} as NO_SHOW")
        return True
    except Exception as e:
        logger.error(f"Error marking no-show for {appointment_id}: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def mark_appointment_completed(appointment_id: int) -> bool:
    """Označi termin kot opravljen."""
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE reservations SET reminder_stage = {ph}, status = {ph} WHERE id = {ph}",
            (ReminderStage.COMPLETED.value, 'completed', appointment_id)
        )
        conn.commit()
        logger.info(f"Marked appointment {appointment_id} as COMPLETED")
        return True
    except Exception as e:
        logger.error(f"Error marking completed for {appointment_id}: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def handle_sms_response(from_phone: str, message_body: str) -> Dict[str, Any]:
    """
    Procesira odgovor na SMS quick action.

    Args:
        from_phone: Telefonska številka pošiljatelja
        message_body: Besedilo SMS-a (DA, PRESTAVI, ODPOVEJ)

    Returns:
        {
            "success": bool,
            "action": str,
            "appointment_id": int or None,
            "response_message": str
        }
    """
    from app.services.sms_service import process_sms_response

    # Normaliziraj telefon
    phone = from_phone.replace(" ", "").replace("-", "")
    if phone.startswith("00386"):
        phone = "+386" + phone[5:]
    elif not phone.startswith("+"):
        phone = "+386" + phone.lstrip("0")

    # Poišči termin za to telefonsko
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()

        # Išči aktiven termin za to številko
        query = f"""
            SELECT * FROM reservations
            WHERE phone LIKE {ph}
            AND status = {ph}
            AND reminder_stage = {ph}
            ORDER BY date DESC, time DESC
            LIMIT 1
        """
        # Handle phone variations
        phone_pattern = f"%{phone[-9:]}%"  # Last 9 digits
        cur.execute(query, (phone_pattern, 'confirmed', ReminderStage.SENT_2_HOUR.value))
        row = cur.fetchone()

        if not row:
            return {
                "success": False,
                "action": "unknown",
                "appointment_id": None,
                "response_message": "Nismo našli aktivnega termina za vašo številko."
            }

        appointment = dict(row)
        appointment_id = appointment['id']

        # Procesiraj odgovor
        result = process_sms_response(from_phone, message_body, appointment_id)
        action = result.get('action')

        # Posodobi bazo glede na akcijo
        if action == "confirm":
            mark_patient_confirmed(appointment_id, True)
            logger.info(f"Patient confirmed appointment #{appointment_id}")

        elif action == "cancel":
            conn2, db_type2 = _get_db_connection()
            cur2 = conn2.cursor()
            cur2.execute(
                f"UPDATE reservations SET status = {_get_placeholder(db_type2)} WHERE id = {_get_placeholder(db_type2)}",
                ('cancelled', appointment_id)
            )
            conn2.commit()
            cur2.close()
            conn2.close()
            logger.info(f"Patient cancelled appointment #{appointment_id}")

        elif action == "reschedule":
            logger.info(f"Patient wants to reschedule #{appointment_id} - requires manual handling")

        return {
            "success": True,
            "action": action,
            "appointment_id": appointment_id,
            "response_message": result.get('message', '')
        }

    except Exception as e:
        logger.error(f"Error handling SMS response: {e}")
        return {
            "success": False,
            "action": "error",
            "appointment_id": None,
            "response_message": "Prišlo je do napake. Prosimo pokličite nas."
        }
    finally:
        cur.close()
        conn.close()


def get_reminder_stats() -> Dict[str, Any]:
    """
    Vrne statistiko opomnikov za dashboard.

    Returns:
        {
            "total_appointments": int,
            "by_stage": {stage_name: count},
            "no_show_rate": float,
            "confirmation_rate": float
        }
    """
    conn, db_type = _get_db_connection()

    try:
        cur = conn.cursor()

        stats = {
            "total_appointments": 0,
            "by_stage": {},
            "no_show_rate": 0.0,
            "confirmation_rate": 0.0
        }

        # Count by stage
        cur.execute("SELECT reminder_stage, COUNT(*) FROM reservations GROUP BY reminder_stage")
        rows = cur.fetchall()

        total = 0
        no_shows = 0
        completed = 0

        for row in rows:
            stage_val = row[0] if row[0] is not None else 0
            count = row[1]
            total += count

            try:
                stage = ReminderStage(stage_val)
                stats["by_stage"][stage.name] = count

                if stage == ReminderStage.NO_SHOW:
                    no_shows = count
                elif stage == ReminderStage.COMPLETED or stage == ReminderStage.FOLLOWUP_SENT:
                    completed += count
            except ValueError:
                stats["by_stage"][f"UNKNOWN_{stage_val}"] = count

        stats["total_appointments"] = total

        # Calculate rates
        finished = no_shows + completed
        if finished > 0:
            stats["no_show_rate"] = round(no_shows / finished * 100, 1)
            stats["confirmation_rate"] = round(completed / finished * 100, 1)

        # Confirmed patients
        cur.execute("SELECT COUNT(*) FROM reservations WHERE patient_confirmed = 1")
        confirmed_row = cur.fetchone()
        stats["patient_confirmations"] = confirmed_row[0] if confirmed_row else 0

        return stats

    except Exception as e:
        logger.error(f"Error getting reminder stats: {e}")
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()


# ============================================================
# MANUAL TEST
# ============================================================

async def test_reminder_scheduler():
    """
    Testna funkcija - preveri vse stopnje opomnikov.

    Uporaba:
        python -c "import asyncio; from app.services.reminder_scheduler import test_reminder_scheduler; asyncio.run(test_reminder_scheduler())"
    """
    print("=" * 60)
    print("SMART REMINDER SCHEDULER TEST")
    print("=" * 60)

    # Inicializacija
    _ensure_reminder_columns()
    print("✅ Database columns ready")

    # Statistika
    print("\n📊 Current Statistics:")
    stats = get_reminder_stats()
    print(f"   Total appointments: {stats.get('total_appointments', 0)}")
    print(f"   By stage: {stats.get('by_stage', {})}")
    print(f"   No-show rate: {stats.get('no_show_rate', 0)}%")
    print(f"   Confirmation rate: {stats.get('confirmation_rate', 0)}%")
    print(f"   Patient confirmations: {stats.get('patient_confirmations', 0)}")

    # 3-dnevni opomniki
    print("\n📅 3-Day Reminders:")
    apt_3day = get_appointments_by_stage(ReminderStage.SENT_3_DAY)
    print(f"   Found {len(apt_3day)} appointment(s) needing 3-day reminder")
    for apt in apt_3day[:3]:  # Max 3
        print(f"   - #{apt['id']}: {apt.get('name')} on {apt.get('date')} at {apt.get('time')}")

    # 2-urni opomniki
    print("\n⏰ 2-Hour Reminders:")
    apt_2hour = get_appointments_by_stage(ReminderStage.SENT_2_HOUR)
    print(f"   Found {len(apt_2hour)} appointment(s) needing 2-hour reminder")
    for apt in apt_2hour[:3]:
        print(f"   - #{apt['id']}: {apt.get('name')} on {apt.get('date')} at {apt.get('time')}")

    # Follow-up
    print("\n💬 Post-Visit Follow-ups:")
    apt_followup = get_completed_appointments_for_followup()
    print(f"   Found {len(apt_followup)} appointment(s) needing follow-up")
    for apt in apt_followup[:3]:
        print(f"   - #{apt['id']}: {apt.get('name')} on {apt.get('date')}")

    # No-shows
    print("\n❌ No-Show Detection:")
    no_shows = detect_no_shows()
    print(f"   Found {len(no_shows)} potential no-show(s)")
    for apt in no_shows[:3]:
        print(f"   - #{apt['id']}: {apt.get('name')} on {apt.get('date')} at {apt.get('time')}")

    # Run reminders
    total_appointments = len(apt_3day) + len(apt_2hour) + len(apt_followup)
    if total_appointments > 0:
        print("\n🚀 Sending reminders...")
        await check_and_send_reminders()
        print("\n✅ Reminder check completed")
    else:
        print("\n✅ No reminders needed at this time")

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


def test_sms_response_handler():
    """
    Test SMS response handling.

    Uporaba:
        python -c "from app.services.reminder_scheduler import test_sms_response_handler; test_sms_response_handler()"
    """
    print("Testing SMS Response Handler...")

    # Test responses
    test_cases = [
        ("+38640123456", "DA"),
        ("+38640123456", "prestavi"),
        ("+38640123456", "ODPOVEJ"),
        ("+38640123456", "kaj?"),
    ]

    for phone, message in test_cases:
        result = handle_sms_response(phone, message)
        print(f"  {phone} -> '{message}': action={result['action']}")


if __name__ == "__main__":
    # Zaženi test
    asyncio.run(test_reminder_scheduler())
