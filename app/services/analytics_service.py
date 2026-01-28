"""
Analytics Service za Zdravstveni Center

FUNKCIONALNOST:
1. Trending topics/symptoms - kaj pacienti najpogosteje sprašujejo
2. Bottleneck analysis - kje uporabniki odpadejo v booking flow
3. Sentiment tracking - ton pogovorov (pozitiven/negativen/nevtralen)
4. Peak hours - kdaj je največ pogovorov
5. Conversion funnel - uspešnost booking procesa

UPORABA:
    from app.services.analytics_service import AnalyticsService

    analytics = AnalyticsService()
    stats = analytics.get_dashboard_stats(days=7)
"""

import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter, defaultdict
import logging

logger = logging.getLogger(__name__)

# Sentiment keywords (Slovenian)
POSITIVE_KEYWORDS = {
    "hvala", "super", "odlično", "dobro", "perfektno", "krasno", "lepo",
    "zadovoljen", "zadovoljna", "pomaga", "pomagalo", "uspelo", "v redu",
    "prijazni", "hitro", "učinkovito", "priporočam", "všeč"
}

NEGATIVE_KEYWORDS = {
    "slabo", "grozno", "neprijetno", "počasi", "dolgo", "čakam", "čakanje",
    "napaka", "problem", "težava", "ne dela", "ne razumem", "frustriran",
    "jezen", "jezna", "razočaran", "razočarana", "nikoli", "nič"
}

# Medical/symptom keywords for topic detection
SYMPTOM_KEYWORDS = {
    "bolečina": ["bolečina", "boli", "bolečine", "peče", "zbada"],
    "koža": ["koža", "kožne", "izpuščaj", "akne", "dermatolog", "rdečica"],
    "oči": ["oči", "vid", "očala", "slab vid", "okulist", "očesni"],
    "sklepi": ["sklep", "sklepi", "koleno", "rama", "hrbtenica", "ortoped"],
    "estetika": ["botox", "filer", "gube", "estetski", "pomlajevanje"],
    "laser": ["laser", "laserski", "žile", "žilice", "bradavice"],
    "splošno": ["pregled", "zdravnik", "termin", "naročiti", "cena"]
}

# Booking flow stages for funnel analysis
BOOKING_STAGES = [
    "service_inquiry",      # Vprašanje o storitvi
    "date_selection",       # Izbira datuma
    "time_selection",       # Izbira časa
    "info_collection",      # Zbiranje podatkov (ime, tel)
    "confirmation",         # Potrditev
    "completed"             # Uspešna rezervacija
]


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


class AnalyticsService:
    """Service za analitiko pogovorov in rezervacij."""

    def __init__(self):
        self.conn = None
        self.db_type = None

    def _ensure_connection(self):
        """Zagotovi aktivno povezavo."""
        if self.conn is None:
            self.conn, self.db_type = _get_db_connection()

    def _close_connection(self):
        """Zapri povezavo."""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ================================================================
    # TRENDING TOPICS / SYMPTOMS
    # ================================================================

    def get_trending_topics(self, days: int = 7) -> Dict[str, Any]:
        """
        Analizira najpogostejše teme/simptome v pogovorih.

        Args:
            days: Število dni za analizo

        Returns:
            {
                "topics": [{"name": str, "count": int, "trend": float}],
                "keywords": [{"word": str, "count": int}],
                "period_days": int
            }
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            # Pridobi chat history iz zadnjih N dni
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            query = f"""
                SELECT content, created_at FROM chat_history
                WHERE role = 'user' AND created_at >= {ph}
                ORDER BY created_at DESC
            """

            try:
                cur.execute(query, (cutoff_date,))
                messages = cur.fetchall()
            except Exception:
                # Če tabela ne obstaja, vrni prazne rezultate
                return {"topics": [], "keywords": [], "period_days": days}

            # Štej teme
            topic_counts = Counter()
            keyword_counts = Counter()

            for msg in messages:
                content = msg['content'].lower() if msg['content'] else ""

                # Najdi teme
                for topic, keywords in SYMPTOM_KEYWORDS.items():
                    for kw in keywords:
                        if kw in content:
                            topic_counts[topic] += 1
                            keyword_counts[kw] += 1
                            break

            # Top teme
            topics = [
                {"name": name, "count": count, "trend": 0.0}
                for name, count in topic_counts.most_common(10)
            ]

            # Top ključne besede
            keywords = [
                {"word": word, "count": count}
                for word, count in keyword_counts.most_common(20)
            ]

            return {
                "topics": topics,
                "keywords": keywords,
                "period_days": days,
                "total_messages": len(messages)
            }

        except Exception as e:
            logger.error(f"Error getting trending topics: {e}")
            return {"topics": [], "keywords": [], "period_days": days, "error": str(e)}
        finally:
            self._close_connection()

    # ================================================================
    # BOTTLENECK ANALYSIS / CONVERSION FUNNEL
    # ================================================================

    def get_booking_funnel(self, days: int = 30) -> Dict[str, Any]:
        """
        Analizira booking funnel - kje uporabniki odpadejo.

        Returns:
            {
                "stages": [
                    {"name": str, "count": int, "drop_rate": float}
                ],
                "conversion_rate": float,
                "avg_steps_before_drop": float
            }
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            # Pridobi chat history z booking_step
            query = f"""
                SELECT session_id, booking_step, created_at
                FROM chat_history
                WHERE created_at >= {ph}
                ORDER BY session_id, created_at
            """

            try:
                cur.execute(query, (cutoff_date,))
                rows = cur.fetchall()
            except Exception:
                return {"stages": [], "conversion_rate": 0.0, "period_days": days}

            # Grupiraj po session_id
            sessions = defaultdict(list)
            for row in rows:
                if row['booking_step']:
                    sessions[row['session_id']].append(row['booking_step'])

            # Štej faze
            stage_counts = Counter()
            completed_count = 0
            total_sessions = len(sessions)

            for session_id, steps in sessions.items():
                if steps:
                    # Najdi najvišjo doseženo fazo
                    max_stage_idx = -1
                    for step in steps:
                        if step in BOOKING_STAGES:
                            idx = BOOKING_STAGES.index(step)
                            max_stage_idx = max(max_stage_idx, idx)

                    if max_stage_idx >= 0:
                        stage_counts[BOOKING_STAGES[max_stage_idx]] += 1

                    if "completed" in steps or max_stage_idx == len(BOOKING_STAGES) - 1:
                        completed_count += 1

            # Izračunaj funnel
            stages = []
            prev_count = total_sessions if total_sessions > 0 else 1

            for stage in BOOKING_STAGES:
                count = stage_counts.get(stage, 0)
                drop_rate = (prev_count - count) / prev_count * 100 if prev_count > 0 else 0
                stages.append({
                    "name": stage,
                    "count": count,
                    "drop_rate": round(drop_rate, 1)
                })
                if count > 0:
                    prev_count = count

            conversion_rate = completed_count / total_sessions * 100 if total_sessions > 0 else 0

            return {
                "stages": stages,
                "conversion_rate": round(conversion_rate, 1),
                "total_sessions": total_sessions,
                "completed_bookings": completed_count,
                "period_days": days
            }

        except Exception as e:
            logger.error(f"Error getting booking funnel: {e}")
            return {"stages": [], "conversion_rate": 0.0, "error": str(e)}
        finally:
            self._close_connection()

    # ================================================================
    # SENTIMENT ANALYSIS
    # ================================================================

    def get_sentiment_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Analizira sentiment pogovorov.

        Returns:
            {
                "overall": "positive" | "neutral" | "negative",
                "scores": {"positive": float, "neutral": float, "negative": float},
                "trend": [{"date": str, "sentiment": float}],
                "flagged_conversations": [...]
            }
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            query = f"""
                SELECT session_id, content, created_at
                FROM chat_history
                WHERE role = 'user' AND created_at >= {ph}
                ORDER BY created_at
            """

            try:
                cur.execute(query, (cutoff_date,))
                messages = cur.fetchall()
            except Exception:
                return {"overall": "neutral", "scores": {}, "period_days": days}

            # Analiziraj sentiment
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            daily_sentiment = defaultdict(list)
            flagged = []

            for msg in messages:
                content = (msg['content'] or "").lower()
                date_str = msg['created_at'][:10] if msg['created_at'] else ""

                # Štej ključne besede
                pos_hits = sum(1 for kw in POSITIVE_KEYWORDS if kw in content)
                neg_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in content)

                # Določi sentiment
                if neg_hits > pos_hits:
                    sentiment = -1
                    negative_count += 1
                    if neg_hits >= 2:  # Flagged če ima več negativnih besed
                        flagged.append({
                            "session_id": msg['session_id'],
                            "content": content[:100] + "..." if len(content) > 100 else content,
                            "date": date_str
                        })
                elif pos_hits > neg_hits:
                    sentiment = 1
                    positive_count += 1
                else:
                    sentiment = 0
                    neutral_count += 1

                if date_str:
                    daily_sentiment[date_str].append(sentiment)

            # Izračunaj povprečja
            total = positive_count + negative_count + neutral_count
            if total == 0:
                total = 1

            scores = {
                "positive": round(positive_count / total * 100, 1),
                "neutral": round(neutral_count / total * 100, 1),
                "negative": round(negative_count / total * 100, 1)
            }

            # Določi overall sentiment
            if scores["positive"] > scores["negative"] + 10:
                overall = "positive"
            elif scores["negative"] > scores["positive"] + 10:
                overall = "negative"
            else:
                overall = "neutral"

            # Trend po dnevih
            trend = []
            for date, sentiments in sorted(daily_sentiment.items()):
                avg = sum(sentiments) / len(sentiments) if sentiments else 0
                trend.append({
                    "date": date,
                    "sentiment": round(avg, 2),
                    "message_count": len(sentiments)
                })

            return {
                "overall": overall,
                "scores": scores,
                "trend": trend[-14:],  # Zadnjih 14 dni
                "flagged_conversations": flagged[:10],  # Top 10
                "total_messages": total,
                "period_days": days
            }

        except Exception as e:
            logger.error(f"Error getting sentiment stats: {e}")
            return {"overall": "neutral", "scores": {}, "error": str(e)}
        finally:
            self._close_connection()

    # ================================================================
    # PEAK HOURS ANALYSIS
    # ================================================================

    def get_peak_hours(self, days: int = 30) -> Dict[str, Any]:
        """
        Analizira kdaj je največ pogovorov.

        Returns:
            {
                "hourly": [{"hour": int, "count": int, "percentage": float}],
                "daily": [{"day": str, "count": int}],
                "peak_hour": int,
                "peak_day": str,
                "recommendations": [str]
            }
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            query = f"""
                SELECT created_at FROM chat_history
                WHERE role = 'user' AND created_at >= {ph}
            """

            try:
                cur.execute(query, (cutoff_date,))
                messages = cur.fetchall()
            except Exception:
                return {"hourly": [], "daily": [], "period_days": days}

            # Štej po urah in dnevih
            hourly_counts = Counter()
            daily_counts = Counter()
            day_names = ["Ponedeljek", "Torek", "Sreda", "Četrtek", "Petek", "Sobota", "Nedelja"]

            for msg in messages:
                try:
                    created_at = msg['created_at']
                    if created_at:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00').split('+')[0])
                        hourly_counts[dt.hour] += 1
                        daily_counts[dt.weekday()] += 1
                except Exception:
                    continue

            total = sum(hourly_counts.values()) or 1

            # Hourly distribution
            hourly = [
                {
                    "hour": h,
                    "count": hourly_counts.get(h, 0),
                    "percentage": round(hourly_counts.get(h, 0) / total * 100, 1)
                }
                for h in range(24)
            ]

            # Daily distribution
            daily = [
                {
                    "day": day_names[d],
                    "day_num": d,
                    "count": daily_counts.get(d, 0)
                }
                for d in range(7)
            ]

            # Peak hour & day
            peak_hour = max(hourly_counts.items(), key=lambda x: x[1])[0] if hourly_counts else 10
            peak_day_num = max(daily_counts.items(), key=lambda x: x[1])[0] if daily_counts else 1
            peak_day = day_names[peak_day_num]

            # Recommendations
            recommendations = []
            if peak_hour >= 9 and peak_hour <= 11:
                recommendations.append("Najvišja aktivnost dopoldne - priporočamo več terminalov v tem času")
            if peak_hour >= 14 and peak_hour <= 16:
                recommendations.append("Visoka aktivnost popoldan - razmislite o podaljšanju delovnega časa")
            if daily_counts.get(0, 0) > daily_counts.get(4, 0) * 1.5:
                recommendations.append("Ponedeljek je izjemno zaseden - priporočamo dodatno osebje")

            return {
                "hourly": hourly,
                "daily": daily,
                "peak_hour": peak_hour,
                "peak_day": peak_day,
                "recommendations": recommendations,
                "total_messages": sum(hourly_counts.values()),
                "period_days": days
            }

        except Exception as e:
            logger.error(f"Error getting peak hours: {e}")
            return {"hourly": [], "daily": [], "error": str(e)}
        finally:
            self._close_connection()

    # ================================================================
    # RESERVATION STATISTICS
    # ================================================================

    def get_reservation_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Statistika rezervacij.

        Returns:
            {
                "total": int,
                "by_status": {...},
                "by_service": {...},
                "avg_per_day": float,
                "no_show_rate": float
            }
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%d.%m.%Y")

            # Vse rezervacije
            query = "SELECT * FROM reservations"
            cur.execute(query)
            all_reservations = cur.fetchall()

            # Štej po statusu
            status_counts = Counter()
            service_counts = Counter()
            recent_count = 0

            for res in all_reservations:
                status = res['status'] or 'unknown'
                status_counts[status] += 1

                service = res.get('service_type') or res.get('location') or 'unknown'
                service_counts[service] += 1

                # Preveri če je recent
                date_str = res.get('date', '')
                if date_str:
                    try:
                        parts = date_str.split('.')
                        if len(parts) == 3:
                            res_date = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                            if res_date >= datetime.now() - timedelta(days=days):
                                recent_count += 1
                    except Exception:
                        pass

            total = len(all_reservations)
            completed = status_counts.get('completed', 0)
            no_shows = status_counts.get('no_show', 0)
            finished = completed + no_shows

            return {
                "total": total,
                "recent_count": recent_count,
                "by_status": dict(status_counts),
                "by_service": dict(service_counts.most_common(10)),
                "avg_per_day": round(recent_count / days, 1) if days > 0 else 0,
                "no_show_rate": round(no_shows / finished * 100, 1) if finished > 0 else 0,
                "completion_rate": round(completed / finished * 100, 1) if finished > 0 else 0,
                "period_days": days
            }

        except Exception as e:
            logger.error(f"Error getting reservation stats: {e}")
            return {"total": 0, "by_status": {}, "error": str(e)}
        finally:
            self._close_connection()

    # ================================================================
    # FULL DASHBOARD
    # ================================================================

    def get_dashboard_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Vrne vse statistike za dashboard.

        Args:
            days: Število dni za analizo

        Returns:
            Kompletna statistika za dashboard
        """
        return {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "trending_topics": self.get_trending_topics(days),
            "booking_funnel": self.get_booking_funnel(days * 4),  # Funnel za daljše obdobje
            "sentiment": self.get_sentiment_stats(days),
            "peak_hours": self.get_peak_hours(days * 4),
            "reservations": self.get_reservation_stats(days * 4)
        }


# Singleton instance
_analytics_service = None


def get_analytics_service() -> AnalyticsService:
    """Vrne singleton instance."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
