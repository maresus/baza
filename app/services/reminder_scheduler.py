"""
Reminder Scheduler - Avtomatsko pošiljanje opomnikov za termine

UPORABA:
1. Zaženi v main.py kot background task pri startu aplikacije
2. Preverja termine vsakih 60 minut
3. Pošlje opomnik 24 ur pred terminom
4. Sledi reminder_sent stanju, da ne pošlje dvakrat

AKTIVACIJA:
- V main.py dodaj: await start_reminder_scheduler()
- Scheduler se bo zagnal v ozadju in deloval dokler FastAPI teče
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

# Import email service
from app.services.email_service import send_appointment_reminder

# Logger
logger = logging.getLogger(__name__)

# Konfiguracija
REMINDER_CHECK_INTERVAL_MINUTES = int(os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "60"))  # Preveri vsako uro
REMINDER_HOURS_BEFORE = int(os.getenv("REMINDER_HOURS_BEFORE", "24"))  # Pošlji 24 ur pred terminom

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


def _ensure_reminder_sent_column():
    """Doda reminder_sent stolpec v bazo, če še ne obstaja."""
    conn, db_type = _get_db_connection()
    try:
        cur = conn.cursor()

        # Preveri če stolpec že obstaja
        if db_type == "postgres":
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='reservations' AND column_name='reminder_sent'
            """)
            exists = cur.fetchone()
        else:  # SQLite
            cur.execute("PRAGMA table_info(reservations)")
            columns = [row[1] for row in cur.fetchall()]
            exists = 'reminder_sent' in columns

        # Dodaj stolpec, če ne obstaja
        if not exists:
            logger.info("Adding reminder_sent column to reservations table")
            cur.execute("ALTER TABLE reservations ADD COLUMN reminder_sent INTEGER DEFAULT 0")
            conn.commit()
            logger.info("reminder_sent column added successfully")
    except Exception as e:
        logger.error(f"Error ensuring reminder_sent column: {e}")
    finally:
        cur.close()
        conn.close()


def get_appointments_needing_reminder() -> List[Dict[str, Any]]:
    """
    Poišče vse potrjene termine, ki potrebujejo opomnik.

    Kriteriji:
    - status = 'confirmed'
    - reminder_sent = 0 (ali NULL)
    - datum+čas je med 24-26 urami od zdaj (buffer 2 uri)

    Returns:
        Seznam terminov, ki potrebujejo opomnik
    """
    conn, db_type = _get_db_connection()
    ph = _get_placeholder(db_type)

    try:
        cur = conn.cursor()

        # Poišči potrjene termine brez poslanega opomnika
        query = f"""
            SELECT * FROM reservations
            WHERE status = {ph}
            AND (reminder_sent IS NULL OR reminder_sent = 0)
            AND date IS NOT NULL
            AND time IS NOT NULL
            AND email IS NOT NULL
        """
        cur.execute(query, ('confirmed',))
        rows = cur.fetchall()

        # Filtriraj termine, ki so v naslednjih 24-26 urah
        now = datetime.now()
        target_start = now + timedelta(hours=REMINDER_HOURS_BEFORE)
        target_end = now + timedelta(hours=REMINDER_HOURS_BEFORE + 2)  # 2-urni buffer

        appointments_to_remind = []
        for row in rows:
            try:
                appointment_dt = _parse_datetime(row['date'], row['time'])

                # Če je termin v ciljnem časovnem oknu
                if target_start <= appointment_dt <= target_end:
                    appointments_to_remind.append(dict(row))
            except ValueError as e:
                logger.warning(f"Skipping appointment {row['id']}: {e}")
                continue

        return appointments_to_remind

    except Exception as e:
        logger.error(f"Error fetching appointments needing reminder: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def mark_reminder_sent(appointment_id: int) -> bool:
    """
    Označi termin kot 'reminder_sent = 1'.

    Args:
        appointment_id: ID termina

    Returns:
        True če uspešno posodobljeno
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


async def check_and_send_reminders():
    """
    Glavna funkcija - preveri termine in pošlje opomnike.
    Kliče se periodično vsako uro.
    """
    logger.info("🔔 Checking for appointments needing reminders...")

    try:
        # 1. Pridobi termine, ki potrebujejo opomnik
        appointments = get_appointments_needing_reminder()

        if not appointments:
            logger.info("No appointments need reminders at this time")
            return

        logger.info(f"Found {len(appointments)} appointment(s) needing reminder")

        # 2. Pošlji opomnik za vsak termin
        for apt in appointments:
            try:
                appointment_id = apt['id']
                logger.info(f"Sending reminder for appointment #{appointment_id} - {apt.get('name')} on {apt.get('date')} at {apt.get('time')}")

                # Pošlji opomnik
                success = send_appointment_reminder(apt)

                if success:
                    # Označi kot poslano
                    mark_reminder_sent(appointment_id)
                    logger.info(f"✅ Reminder sent successfully for appointment #{appointment_id}")
                else:
                    logger.warning(f"⚠️ Failed to send reminder for appointment #{appointment_id}")

            except Exception as e:
                logger.error(f"Error processing reminder for appointment #{apt.get('id')}: {e}")
                continue

        logger.info(f"✅ Reminder check completed. Sent {len(appointments)} reminder(s)")

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
# MANUAL TEST
# ============================================================

async def test_reminder_scheduler():
    """
    Testna funkcija - ročno preveri in pošlje opomnike.

    Uporaba:
        python -c "import asyncio; from app.services.reminder_scheduler import test_reminder_scheduler; asyncio.run(test_reminder_scheduler())"
    """
    print("=" * 60)
    print("REMINDER SCHEDULER TEST")
    print("=" * 60)

    # Preveri reminder_sent stolpec
    _ensure_reminder_sent_column()
    print("✅ Database reminder_sent column ready")

    # Preveri termine
    appointments = get_appointments_needing_reminder()
    print(f"\nFound {len(appointments)} appointment(s) needing reminder:")
    for apt in appointments:
        print(f"  - #{apt['id']}: {apt.get('name')} on {apt.get('date')} at {apt.get('time')}")

    # Pošlji opomnike
    if appointments:
        print("\nSending reminders...")
        await check_and_send_reminders()
        print("\n✅ Test completed")
    else:
        print("\nNo appointments need reminders at this time")
        print("ℹ️ Create a confirmed appointment 24 hours from now to test")


if __name__ == "__main__":
    # Zaženi test
    asyncio.run(test_reminder_scheduler())
