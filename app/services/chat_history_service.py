import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

DATABASE_URL = os.environ.get("DATABASE_URL")


class ChatHistoryService:
    """Service for storing and retrieving chat message history"""

    def __init__(self) -> None:
        db_url = (DATABASE_URL or "").strip()
        self.use_postgres = bool(
            HAS_POSTGRES and (db_url.startswith("postgres://") or db_url.startswith("postgresql://"))
        )

        if not self.use_postgres:
            # SQLite fallback for local development
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.data_dir = os.path.join(project_root, "data")
            os.makedirs(self.data_dir, exist_ok=True)
            self.db_path = os.path.join(self.data_dir, "chat_history.db")

        self._ensure_table()

    def _conn(self):
        """Get database connection"""
        if self.use_postgres:
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _placeholder(self) -> str:
        """Get SQL placeholder for current database"""
        return "%s" if self.use_postgres else "?"

    def _ensure_table(self) -> None:
        """Create chat_messages table if it doesn't exist"""
        conn = self._conn()
        cursor = conn.cursor()

        # Create table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id {"SERIAL PRIMARY KEY" if self.use_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"},
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                intent TEXT,
                service_mentioned TEXT,
                timestamp TEXT NOT NULL,
                booking_step TEXT,
                response_cached BOOLEAN DEFAULT FALSE,
                metadata {"JSONB" if self.use_postgres else "TEXT"}
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_id ON chat_messages(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON chat_messages(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_intent ON chat_messages(intent)
        """)

        conn.commit()
        conn.close()

        print(f"[CHAT_HISTORY] Table ready (using {'PostgreSQL' if self.use_postgres else 'SQLite'})")

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: Optional[str] = None,
        service_mentioned: Optional[str] = None,
        booking_step: Optional[str] = None,
        response_cached: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Save a chat message to history

        Args:
            session_id: Unique session identifier
            role: "user" or "assistant"
            content: Message content
            intent: Classified intent (if available)
            service_mentioned: Service mentioned in message
            booking_step: Current booking step (if in booking flow)
            response_cached: Whether response was served from cache
            metadata: Additional metadata as dict

        Returns:
            Message ID
        """
        conn = self._conn()
        cursor = conn.cursor()
        ph = self._placeholder()

        timestamp = datetime.now().isoformat()
        metadata_str = json.dumps(metadata or {}) if metadata else None

        cursor.execute(f"""
            INSERT INTO chat_messages
            (session_id, role, content, intent, service_mentioned, timestamp,
             booking_step, response_cached, metadata)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            {"RETURNING id" if self.use_postgres else ""}
        """, (
            session_id, role, content, intent, service_mentioned, timestamp,
            booking_step, response_cached, metadata_str
        ))

        if self.use_postgres:
            message_id = cursor.fetchone()["id"]
        else:
            message_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return message_id

    def get_session_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get chat history for a specific session

        Args:
            session_id: Session to retrieve
            limit: Maximum number of messages (None for all)

        Returns:
            List of message dictionaries
        """
        conn = self._conn()
        cursor = conn.cursor()
        ph = self._placeholder()

        query = f"""
            SELECT * FROM chat_messages
            WHERE session_id = {ph}
            ORDER BY timestamp ASC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (session_id,))
        rows = cursor.fetchall()
        conn.close()

        messages = []
        for row in rows:
            msg = dict(row)
            # Parse metadata if exists
            if msg.get("metadata"):
                try:
                    msg["metadata"] = json.loads(msg["metadata"])
                except:
                    pass
            messages.append(msg)

        return messages

    def get_all_sessions(
        self,
        since: Optional[str] = None,
        limit: int = 100
    ) -> List[str]:
        """
        Get list of all session IDs

        Args:
            since: ISO timestamp to filter sessions after this time
            limit: Maximum sessions to return

        Returns:
            List of session IDs
        """
        conn = self._conn()
        cursor = conn.cursor()
        ph = self._placeholder()

        if since:
            cursor.execute(f"""
                SELECT DISTINCT session_id FROM chat_messages
                WHERE timestamp >= {ph}
                ORDER BY timestamp DESC
                LIMIT {limit}
            """, (since,))
        else:
            cursor.execute(f"""
                SELECT DISTINCT session_id FROM chat_messages
                ORDER BY timestamp DESC
                LIMIT {limit}
            """)

        rows = cursor.fetchall()
        conn.close()

        return [row["session_id"] if self.use_postgres else row[0] for row in rows]

    def get_conversation_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get conversation statistics for last N days

        Args:
            days: Number of days to analyze

        Returns:
            Statistics dictionary
        """
        conn = self._conn()
        cursor = conn.cursor()

        since = (datetime.now() - timedelta(days=days)).isoformat()
        ph = self._placeholder()

        # Total sessions
        cursor.execute(f"""
            SELECT COUNT(DISTINCT session_id) as total_sessions
            FROM chat_messages
            WHERE timestamp >= {ph}
        """, (since,))
        total_sessions = cursor.fetchone()[0] if not self.use_postgres else cursor.fetchone()["total_sessions"]

        # Total messages
        cursor.execute(f"""
            SELECT COUNT(*) as total_messages
            FROM chat_messages
            WHERE timestamp >= {ph}
        """, (since,))
        total_messages = cursor.fetchone()[0] if not self.use_postgres else cursor.fetchone()["total_messages"]

        # Most common intents
        cursor.execute(f"""
            SELECT intent, COUNT(*) as count
            FROM chat_messages
            WHERE timestamp >= {ph} AND intent IS NOT NULL
            GROUP BY intent
            ORDER BY count DESC
            LIMIT 10
        """, (since,))
        top_intents = [dict(row) for row in cursor.fetchall()]

        # Sessions with booking
        cursor.execute(f"""
            SELECT COUNT(DISTINCT session_id) as booking_sessions
            FROM chat_messages
            WHERE timestamp >= {ph} AND booking_step IS NOT NULL
        """, (since,))
        booking_sessions = cursor.fetchone()[0] if not self.use_postgres else cursor.fetchone()["booking_sessions"]

        conn.close()

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "messages_per_session": round(total_messages / total_sessions, 1) if total_sessions > 0 else 0,
            "booking_sessions": booking_sessions,
            "conversion_rate": round(booking_sessions / total_sessions * 100, 1) if total_sessions > 0 else 0,
            "top_intents": top_intents,
            "period_days": days
        }

    def search_messages(
        self,
        query: str,
        role: Optional[str] = None,
        intent: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search messages by content

        Args:
            query: Text to search for
            role: Filter by role (user/assistant)
            intent: Filter by intent
            limit: Maximum results

        Returns:
            List of matching messages
        """
        conn = self._conn()
        cursor = conn.cursor()
        ph = self._placeholder()

        conditions = [f"content LIKE {ph}"]
        params = [f"%{query}%"]

        if role:
            conditions.append(f"role = {ph}")
            params.append(role)

        if intent:
            conditions.append(f"intent = {ph}")
            params.append(intent)

        where_clause = " AND ".join(conditions)

        cursor.execute(f"""
            SELECT * FROM chat_messages
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT {limit}
        """, tuple(params))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]


# Singleton instance
_chat_history_service = None

def get_chat_history_service() -> ChatHistoryService:
    """Get or create singleton ChatHistoryService instance"""
    global _chat_history_service
    if _chat_history_service is None:
        _chat_history_service = ChatHistoryService()
    return _chat_history_service
