"""
Handoff Service - Inteligenten prenos pogovora na recepcijo

FUNKCIONALNOST:
1. Summary generator - LLM povzetek pogovora
2. Sentiment analysis - ali je pacient frustriran
3. Suggested responses - pripravljeni odgovori za recepcijo
4. Priority queue - urgentni handoff-i najprej

UPORABA:
    from app.services.handoff_service import HandoffService

    handoff = HandoffService()
    summary = await handoff.create_handoff(session_id)
"""

import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Priority levels
class HandoffPriority(Enum):
    LOW = 1        # Splošno vprašanje
    MEDIUM = 2     # Standardna rezervacija
    HIGH = 3       # Frustriran pacient
    URGENT = 4     # Urgentno zdravstveno vprašanje


# Sentiment keywords (Slovenian)
FRUSTRATION_KEYWORDS = {
    "frustriran", "jezen", "jezna", "razočaran", "razočarana",
    "neprijetno", "slabo", "grozno", "nesprejemljivo", "skandal",
    "pritožba", "pritožujem", "čakam", "čakal", "dolgo", "počasi",
    "nikoli", "nič ne deluje", "ne razumem", "brez odgovora"
}

URGENCY_KEYWORDS = {
    "nujno", "urgentno", "takoj", "nemudoma", "nujna", "hudo",
    "zelo boli", "ne morem", "kri", "krvavi", "krvavitev",
    "nezavest", "omotica", "vročina", "visoka temperatura",
    "dihanje", "težko diham", "bolečina v prsih"
}

# Suggested response templates
RESPONSE_TEMPLATES = {
    "booking_issue": [
        "Opravičujem se za težave. Preveril/a bom razpoložljivost in vas takoj poklical/a nazaj.",
        "Razumem vašo frustracijo. Naj preverim, ali lahko najdem hitrejši termin.",
    ],
    "general_inquiry": [
        "Hvala za vaše vprašanje. Tukaj so informacije, ki jih potrebujete...",
        "Z veseljem vam pomagam. Naj pojasnim...",
    ],
    "frustrated_patient": [
        "Opravičujem se za neprijetnosti. Kako vam lahko pomagam rešiti to situacijo?",
        "Razumem, da ste razočarani. Naj vidim, kaj lahko storim, da vam pomagam.",
    ],
    "urgent_medical": [
        "URGENTNO: Prosim, pojdite na najbližjo urgentno ambulanto ali pokličite 112.",
        "Če imate resne simptome, prosim takoj poiščite medicinsko pomoč.",
    ]
}


def _get_db_connection():
    """Pridobi database connection."""
    DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

    if DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor), "postgres"
        except ImportError:
            raise

    import sqlite3
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    db_path = os.path.join(project_root, "data", "reservations.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


def _get_placeholder(db_type: str) -> str:
    return "%s" if db_type == "postgres" else "?"


class HandoffService:
    """Service za prenos pogovora na recepcijo."""

    def __init__(self):
        self.conn = None
        self.db_type = None
        self.pending_handoffs: Dict[str, Dict] = {}  # session_id -> handoff data

    def _ensure_connection(self):
        if self.conn is None:
            self.conn, self.db_type = _get_db_connection()

    def _close_connection(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    # ================================================================
    # CONVERSATION ANALYSIS
    # ================================================================

    def get_conversation_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """
        Pridobi zadnjih N sporočil iz pogovora.

        Args:
            session_id: ID seje
            limit: Maksimalno število sporočil

        Returns:
            Seznam sporočil [{role, content, created_at}]
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            query = f"""
                SELECT role, content, created_at, intent, service_mentioned
                FROM chat_history
                WHERE session_id = {ph}
                ORDER BY created_at DESC
                LIMIT {ph}
            """
            cur.execute(query, (session_id, limit))
            rows = cur.fetchall()

            # Reverse to chronological order
            messages = [dict(row) for row in reversed(rows)]
            return messages

        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
        finally:
            self._close_connection()

    def analyze_sentiment(self, messages: List[Dict]) -> Dict[str, Any]:
        """
        Analizira sentiment pogovora.

        Args:
            messages: Seznam sporočil

        Returns:
            {
                "overall": "positive" | "neutral" | "negative" | "frustrated",
                "frustration_level": 0-10,
                "urgency_level": 0-10,
                "trigger_messages": [...]
            }
        """
        frustration_score = 0
        urgency_score = 0
        trigger_messages = []

        for msg in messages:
            if msg.get('role') != 'user':
                continue

            content = (msg.get('content') or '').lower()

            # Check frustration
            frustration_hits = sum(1 for kw in FRUSTRATION_KEYWORDS if kw in content)
            if frustration_hits > 0:
                frustration_score += frustration_hits * 2
                trigger_messages.append({
                    "content": content[:100],
                    "type": "frustration",
                    "time": msg.get('created_at', '')
                })

            # Check urgency
            urgency_hits = sum(1 for kw in URGENCY_KEYWORDS if kw in content)
            if urgency_hits > 0:
                urgency_score += urgency_hits * 3  # Higher weight for urgency
                trigger_messages.append({
                    "content": content[:100],
                    "type": "urgency",
                    "time": msg.get('created_at', '')
                })

        # Normalize scores to 0-10
        frustration_level = min(10, frustration_score)
        urgency_level = min(10, urgency_score)

        # Determine overall sentiment
        if urgency_level >= 5:
            overall = "urgent"
        elif frustration_level >= 5:
            overall = "frustrated"
        elif frustration_level >= 2:
            overall = "negative"
        else:
            overall = "neutral"

        return {
            "overall": overall,
            "frustration_level": frustration_level,
            "urgency_level": urgency_level,
            "trigger_messages": trigger_messages[:5]  # Top 5
        }

    def extract_key_information(self, messages: List[Dict]) -> Dict[str, Any]:
        """
        Izvleče ključne informacije iz pogovora.

        Returns:
            {
                "patient_name": str or None,
                "phone": str or None,
                "email": str or None,
                "service_requested": str or None,
                "preferred_date": str or None,
                "main_concern": str or None,
                "intents": [str]
            }
        """
        info = {
            "patient_name": None,
            "phone": None,
            "email": None,
            "service_requested": None,
            "preferred_date": None,
            "main_concern": None,
            "intents": []
        }

        for msg in messages:
            content = msg.get('content', '')
            role = msg.get('role', '')

            if role == 'user':
                # Extract phone
                phone_match = re.search(r'(\+?386|0)\s*[0-9\s-]{8,}', content)
                if phone_match and not info["phone"]:
                    info["phone"] = re.sub(r'[\s-]', '', phone_match.group())

                # Extract email
                email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', content)
                if email_match and not info["email"]:
                    info["email"] = email_match.group()

                # Extract date
                date_match = re.search(r'\d{1,2}\.\d{1,2}\.(\d{4}|\d{2})', content)
                if date_match and not info["preferred_date"]:
                    info["preferred_date"] = date_match.group()

            # Extract service from metadata
            service = msg.get('service_mentioned')
            if service and not info["service_requested"]:
                info["service_requested"] = service

            # Collect intents
            intent = msg.get('intent')
            if intent and intent not in info["intents"]:
                info["intents"].append(intent)

        # Determine main concern from intents
        if info["intents"]:
            info["main_concern"] = info["intents"][-1]  # Most recent intent

        return info

    # ================================================================
    # SUMMARY GENERATION
    # ================================================================

    def generate_summary(self, messages: List[Dict], key_info: Dict) -> str:
        """
        Generira povzetek pogovora (brez LLM - rule-based).

        Args:
            messages: Seznam sporočil
            key_info: Izvlečene ključne informacije

        Returns:
            Povzetek pogovora (2-3 stavki)
        """
        parts = []

        # Patient info
        if key_info.get("patient_name"):
            parts.append(f"Pacient: {key_info['patient_name']}")
        if key_info.get("phone"):
            parts.append(f"Tel: {key_info['phone']}")

        # Main concern
        if key_info.get("service_requested"):
            parts.append(f"Išče: {key_info['service_requested']}")
        elif key_info.get("main_concern"):
            parts.append(f"Tema: {key_info['main_concern']}")

        # Preferred date
        if key_info.get("preferred_date"):
            parts.append(f"Želi termin: {key_info['preferred_date']}")

        # Message count
        user_messages = [m for m in messages if m.get('role') == 'user']
        parts.append(f"Sporočil: {len(user_messages)}")

        return " | ".join(parts)

    async def generate_llm_summary(self, messages: List[Dict]) -> str:
        """
        Generira LLM povzetek pogovora.

        Args:
            messages: Seznam sporočil

        Returns:
            LLM-generiran povzetek (2-3 stavki)
        """
        try:
            from app.core.llm_client import get_llm_client

            # Format messages for LLM
            conversation_text = "\n".join([
                f"{m['role'].upper()}: {m['content']}"
                for m in messages[-10:]  # Last 10 messages
                if m.get('content')
            ])

            prompt = f"""Povzemi naslednji pogovor med pacientom in zdravstvenim centrom v 2-3 KRATKIH stavkih.
Vključi: kaj pacient želi, ali je frustriran, in kakšen je trenutni status.

POGOVOR:
{conversation_text}

KRATEK POVZETEK (slovensko):"""

            client = get_llm_client()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.3
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating LLM summary: {e}")
            # Fallback to rule-based
            key_info = self.extract_key_information(messages)
            return self.generate_summary(messages, key_info)

    # ================================================================
    # SUGGESTED RESPONSES
    # ================================================================

    def get_suggested_responses(
        self,
        sentiment: Dict,
        key_info: Dict
    ) -> List[str]:
        """
        Generira predloge odgovorov za recepcijo.

        Args:
            sentiment: Rezultat sentiment analize
            key_info: Izvlečene informacije

        Returns:
            Seznam predlaganih odgovorov
        """
        suggestions = []

        # Based on sentiment
        if sentiment.get("urgency_level", 0) >= 5:
            suggestions.extend(RESPONSE_TEMPLATES["urgent_medical"])
        elif sentiment.get("frustration_level", 0) >= 5:
            suggestions.extend(RESPONSE_TEMPLATES["frustrated_patient"])
        elif key_info.get("service_requested"):
            suggestions.extend(RESPONSE_TEMPLATES["booking_issue"])
        else:
            suggestions.extend(RESPONSE_TEMPLATES["general_inquiry"])

        return suggestions[:3]  # Max 3 suggestions

    # ================================================================
    # PRIORITY CALCULATION
    # ================================================================

    def calculate_priority(self, sentiment: Dict, key_info: Dict) -> HandoffPriority:
        """
        Izračuna prioriteto handoff-a.

        Args:
            sentiment: Rezultat sentiment analize
            key_info: Izvlečene informacije

        Returns:
            HandoffPriority level
        """
        urgency = sentiment.get("urgency_level", 0)
        frustration = sentiment.get("frustration_level", 0)

        if urgency >= 5:
            return HandoffPriority.URGENT
        elif frustration >= 5:
            return HandoffPriority.HIGH
        elif key_info.get("service_requested") or frustration >= 2:
            return HandoffPriority.MEDIUM
        else:
            return HandoffPriority.LOW

    # ================================================================
    # HANDOFF CREATION
    # ================================================================

    async def create_handoff(
        self,
        session_id: str,
        use_llm_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Ustvari handoff paket za recepcijo.

        Args:
            session_id: ID seje
            use_llm_summary: Uporabi LLM za povzetek

        Returns:
            {
                "session_id": str,
                "created_at": str,
                "priority": str,
                "summary": str,
                "sentiment": {...},
                "key_info": {...},
                "suggested_responses": [...],
                "conversation_preview": [...]
            }
        """
        # 1. Get conversation history
        messages = self.get_conversation_history(session_id)

        if not messages:
            return {
                "error": "No conversation found",
                "session_id": session_id
            }

        # 2. Analyze sentiment
        sentiment = self.analyze_sentiment(messages)

        # 3. Extract key information
        key_info = self.extract_key_information(messages)

        # 4. Generate summary
        if use_llm_summary:
            summary = await self.generate_llm_summary(messages)
        else:
            summary = self.generate_summary(messages, key_info)

        # 5. Get suggested responses
        suggested_responses = self.get_suggested_responses(sentiment, key_info)

        # 6. Calculate priority
        priority = self.calculate_priority(sentiment, key_info)

        # 7. Create handoff package
        handoff = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "priority": priority.name,
            "priority_value": priority.value,
            "summary": summary,
            "sentiment": sentiment,
            "key_info": key_info,
            "suggested_responses": suggested_responses,
            "conversation_preview": [
                {
                    "role": m.get("role"),
                    "content": m.get("content", "")[:200],
                    "time": m.get("created_at", "")
                }
                for m in messages[-5:]  # Last 5 messages
            ],
            "message_count": len(messages)
        }

        # 8. Store in pending queue
        self.pending_handoffs[session_id] = handoff

        return handoff

    # ================================================================
    # HANDOFF QUEUE MANAGEMENT
    # ================================================================

    def get_pending_handoffs(self, sort_by_priority: bool = True) -> List[Dict]:
        """
        Vrne vse pending handoff-e.

        Args:
            sort_by_priority: Sortiraj po prioriteti (highest first)

        Returns:
            Seznam handoff paketov
        """
        handoffs = list(self.pending_handoffs.values())

        if sort_by_priority:
            handoffs.sort(key=lambda x: x.get("priority_value", 0), reverse=True)

        return handoffs

    def resolve_handoff(self, session_id: str, resolution_note: Optional[str] = None) -> bool:
        """
        Označi handoff kot rešen.

        Args:
            session_id: ID seje
            resolution_note: Opomba o rešitvi

        Returns:
            True če uspešno
        """
        if session_id in self.pending_handoffs:
            handoff = self.pending_handoffs.pop(session_id)
            handoff["resolved_at"] = datetime.now().isoformat()
            handoff["resolution_note"] = resolution_note
            logger.info(f"Handoff resolved: {session_id}")
            return True
        return False

    def get_handoff_stats(self) -> Dict[str, Any]:
        """
        Vrne statistiko handoff-ov.

        Returns:
            {
                "pending_count": int,
                "by_priority": {...},
                "avg_wait_time": float
            }
        """
        handoffs = self.get_pending_handoffs(sort_by_priority=False)

        by_priority = Counter(h.get("priority") for h in handoffs)

        # Calculate average wait time
        now = datetime.now()
        wait_times = []
        for h in handoffs:
            try:
                created = datetime.fromisoformat(h.get("created_at", ""))
                wait_times.append((now - created).total_seconds() / 60)
            except Exception:
                pass

        avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0

        return {
            "pending_count": len(handoffs),
            "by_priority": dict(by_priority),
            "avg_wait_time_minutes": round(avg_wait, 1),
            "oldest_handoff": min(wait_times) if wait_times else None
        }


# Singleton instance
_handoff_service = None


def get_handoff_service() -> HandoffService:
    """Vrne singleton instance."""
    global _handoff_service
    if _handoff_service is None:
        _handoff_service = HandoffService()
    return _handoff_service
