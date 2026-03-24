import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

DATABASE_URL = os.environ.get("DATABASE_URL")

ROOMS = [
    {"id": "GOZD", "name": "Soba GOZD - Soba z balkonom in pogledom na gozd (do 4 osebe)", "capacity": 4},
    {"id": "RAZGLED", "name": "Soba RAZGLED - Družinska soba z panoramskim razgledom (do 4 osebe)", "capacity": 4},
    {"id": "SONCE", "name": "Soba SONCE - Prostorna soba z dvema spalnicama (do 4 osebe)", "capacity": 4},
]
ROOM_NAME_MAP = {
    "gozd": "GOZD",
    "razgled": "RAZGLED",
    "sonce": "SONCE",
}
ROOM_IDS = {r["id"] for r in ROOMS}

DINING_ROOMS = [
    {"id": "JEDILNICA", "name": "Jedilnica", "capacity": 40},
]
TOTAL_TABLE_CAPACITY = sum(r["capacity"] for r in DINING_ROOMS)
MAX_NIGHTS = 30


class ReservationService:
    def __init__(self) -> None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.use_postgres = bool(DATABASE_URL)
        if not self.use_postgres:
            self.data_dir = os.path.join(project_root, "data")
            os.makedirs(self.data_dir, exist_ok=True)
            self.db_path = os.path.join(self.data_dir, "reservations.db")

        self._ensure_db()

    def _conn(self):
        if self.use_postgres:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _placeholder(self) -> str:
        return "%s" if self.use_postgres else "?"

    def _ensure_db(self) -> None:
        if self.use_postgres:
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reservations (
                    id SERIAL PRIMARY KEY,
                    date TEXT NOT NULL,
                    people INTEGER NOT NULL,
                    reservation_type TEXT NOT NULL,
                    nights INTEGER,
                    time TEXT,
                    location TEXT,
                    name TEXT,
                    phone TEXT,
                    email TEXT,
                    note TEXT,
                    kids TEXT,
                    kids_small TEXT,
                    rooms INTEGER,
                    status TEXT DEFAULT 'pending',
                    source TEXT DEFAULT 'chatbot',
                    admin_notes TEXT,
                    confirmed_at TEXT,
                    confirmed_by TEXT,
                    guest_message TEXT,
                    event_type TEXT,
                    special_needs TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT,
                    user_message TEXT,
                    bot_reply TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reservation_messages (
                    id SERIAL PRIMARY KEY,
                    reservation_id INTEGER,
                    direction TEXT,
                    subject TEXT,
                    body TEXT,
                    from_email TEXT,
                    to_email TEXT,
                    message_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    people INTEGER NOT NULL,
                    reservation_type TEXT NOT NULL,
                    nights INTEGER,
                    time TEXT,
                    location TEXT,
                    name TEXT,
                    phone TEXT,
                    email TEXT,
                    note TEXT,
                    kids TEXT,
                    kids_small TEXT,
                    rooms INTEGER,
                    status TEXT DEFAULT 'pending',
                    source TEXT DEFAULT 'chatbot',
                    admin_notes TEXT,
                    confirmed_at TEXT,
                    confirmed_by TEXT,
                    guest_message TEXT,
                    event_type TEXT,
                    special_needs TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_message TEXT,
                    bot_reply TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reservation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reservation_id INTEGER,
                    direction TEXT,
                    subject TEXT,
                    body TEXT,
                    from_email TEXT,
                    to_email TEXT,
                    message_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()

    def create_reservation(
        self,
        date: str,
        people: int,
        reservation_type: str,
        nights: Optional[int] = None,
        time: Optional[str] = None,
        location: Optional[str] = None,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        note: Optional[str] = None,
        kids: Optional[str] = None,
        kids_small: Optional[str] = None,
        rooms: Optional[int] = None,
        status: str = "pending",
        source: str = "chatbot",
        admin_notes: Optional[str] = None,
        event_type: Optional[str] = None,
        special_needs: Optional[str] = None,
    ) -> int:
        p = self._placeholder()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO reservations
            (date, people, reservation_type, nights, time, location, name, phone, email,
             note, kids, kids_small, rooms, status, source, admin_notes, event_type, special_needs)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
        """, (date, people, reservation_type, nights, time, location, name, phone, email,
              note, kids, kids_small, rooms, status, source, admin_notes, event_type, special_needs))
        conn.commit()
        if self.use_postgres:
            cur.execute("SELECT lastval()")
            row = cur.fetchone()
            new_id = row[0] if row else 0
        else:
            new_id = cur.lastrowid
        cur.close()
        conn.close()
        return new_id

    def read_reservations(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        reservation_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> list[dict]:
        p = self._placeholder()
        conn = self._conn()
        cur = conn.cursor()
        query = "SELECT * FROM reservations WHERE 1=1"
        params = []
        if status:
            query += f" AND status = {p}"
            params.append(status)
        if reservation_type:
            query += f" AND reservation_type = {p}"
            params.append(reservation_type)
        if source:
            query += f" AND source = {p}"
            params.append(source)
        query += " ORDER BY id DESC LIMIT " + str(limit)
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def get_reservation(self, reservation_id: int) -> Optional[dict]:
        p = self._placeholder()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM reservations WHERE id = {p}", (reservation_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def update_reservation(self, reservation_id: int, **fields) -> bool:
        if not fields:
            return False
        p = self._placeholder()
        conn = self._conn()
        cur = conn.cursor()
        set_parts = [f"{k} = {p}" for k in fields]
        values = list(fields.values()) + [reservation_id]
        cur.execute(
            f"UPDATE reservations SET {', '.join(set_parts)} WHERE id = {p}",
            values,
        )
        updated = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return updated

    def delete_all_reservations(self) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM reservations")
        count = cur.fetchone()[0]
        cur.execute("DELETE FROM reservations")
        conn.commit()
        cur.close()
        conn.close()
        return count

    def log_conversation(self, session_id: str, user_message: str, bot_reply: str) -> None:
        try:
            p = self._placeholder()
            conn = self._conn()
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO conversations (session_id, user_message, bot_reply) VALUES ({p},{p},{p})",
                (session_id, user_message, bot_reply),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"[DB] log_conversation error: {e}")

    def get_conversations(self, limit: int = 200, needs_followup_only: bool = False) -> list[dict]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def get_conversations_by_session(self, session_id: str, limit: int = 200) -> list[dict]:
        p = self._placeholder()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM conversations WHERE session_id = {p} ORDER BY id ASC LIMIT {limit}",
            (session_id,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def add_reservation_message(
        self,
        reservation_id: int,
        direction: str,
        subject: str,
        body: str,
        from_email: str,
        to_email: str,
        message_id: Optional[str],
    ) -> None:
        try:
            p = self._placeholder()
            conn = self._conn()
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO reservation_messages (reservation_id, direction, subject, body, from_email, to_email, message_id) VALUES ({p},{p},{p},{p},{p},{p},{p})",
                (reservation_id, direction, subject, body, from_email, to_email, message_id),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"[DB] add_reservation_message error: {e}")

    def list_reservation_messages(self, reservation_id: int) -> list[dict]:
        p = self._placeholder()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM reservation_messages WHERE reservation_id = {p} ORDER BY id ASC",
            (reservation_id,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def get_usage_stats(self) -> dict:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM conversations")
        total_convs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM reservations")
        total_res = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {"total_conversations": total_convs, "total_reservations": total_res}

    def get_top_questions(self, limit: int = 10) -> list[dict]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT user_message, COUNT(*) as cnt FROM conversations GROUP BY user_message ORDER BY cnt DESC LIMIT {limit}"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def get_lost_intents(self, limit: int = 10) -> list[dict]:
        return []

    def get_funnel_stats(self, days: int = 30) -> dict:
        return {}

    def get_inquiries(self, limit: int = 200, status: Optional[str] = None) -> list[dict]:
        return []

    def create_knowledge_feedback(self, question: str, suggestion: str) -> Optional[int]:
        return None

    def check_table_availability(self, date: str, time: str, people: int) -> tuple:
        return True, "JEDILNICA", []
