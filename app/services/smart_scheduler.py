"""
Smart Scheduler - Inteligentni sistem za predlaganje terminov

FUNKCIONALNOST:
1. User preference learning - analiza preteklih rezervacij
2. Clinic optimization - load balancing, slot optimization
3. Smart suggestions - personalizirani predlogi terminov

UPORABA:
    from app.services.smart_scheduler import SmartScheduler

    scheduler = SmartScheduler()
    suggestions = scheduler.get_smart_suggestions(
        phone="+38640123456",
        service_type="dermatolog",
        preferred_date="15.02.2026"
    )
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter, defaultdict
import logging

from app.services.health_center_extensions import (
    get_available_time_slots,
    SERVICES,
    WORKING_HOURS,
    WORKING_DAYS,
)

logger = logging.getLogger(__name__)


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


class SmartScheduler:
    """Inteligentni scheduler za predlaganje optimalnih terminov."""

    def __init__(self):
        self.conn = None
        self.db_type = None

    def _ensure_connection(self):
        if self.conn is None:
            self.conn, self.db_type = _get_db_connection()

    def _close_connection(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    # ================================================================
    # USER PREFERENCE LEARNING
    # ================================================================

    def get_user_preferences(self, phone: str) -> Dict[str, Any]:
        """
        Analizira pretekle rezervacije uporabnika za ugotovitev preferenc.

        Args:
            phone: Telefonska številka (normalizirana)

        Returns:
            {
                "preferred_hour": int,
                "preferred_day": int (0=pon, 4=pet),
                "preferred_service": str,
                "booking_count": int,
                "avg_days_ahead": float,
                "no_show_count": int
            }
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            # Normaliziraj telefon za iskanje (zadnjih 9 števk)
            phone_pattern = f"%{phone[-9:]}%" if len(phone) >= 9 else f"%{phone}%"

            query = f"""
                SELECT * FROM reservations
                WHERE phone LIKE {ph}
                ORDER BY date DESC
            """
            cur.execute(query, (phone_pattern,))
            reservations = cur.fetchall()

            if not reservations:
                return {
                    "has_history": False,
                    "booking_count": 0
                }

            # Analiziraj preference
            hours = []
            days = []
            services = []
            days_ahead = []
            no_shows = 0

            for res in reservations:
                # Čas termina
                time_str = res.get('time', '')
                if time_str and ':' in time_str:
                    hours.append(int(time_str.split(':')[0]))

                # Dan v tednu
                date_str = res.get('date', '')
                if date_str:
                    try:
                        parts = date_str.split('.')
                        if len(parts) == 3:
                            dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                            days.append(dt.weekday())
                    except Exception:
                        pass

                # Storitev
                service = res.get('service_type') or res.get('location', '')
                if service:
                    services.append(service.lower())

                # No-show
                if res.get('status') == 'no_show':
                    no_shows += 1

            # Izračunaj povprečja/mode
            preferred_hour = max(set(hours), key=hours.count) if hours else 10
            preferred_day = max(set(days), key=days.count) if days else 1
            preferred_service = max(set(services), key=services.count) if services else None

            return {
                "has_history": True,
                "booking_count": len(reservations),
                "preferred_hour": preferred_hour,
                "preferred_day": preferred_day,
                "preferred_service": preferred_service,
                "no_show_count": no_shows,
                "no_show_rate": round(no_shows / len(reservations) * 100, 1) if reservations else 0,
                "recent_services": list(set(services))[:5]
            }

        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {"has_history": False, "error": str(e)}
        finally:
            self._close_connection()

    # ================================================================
    # CLINIC LOAD ANALYSIS
    # ================================================================

    def get_slot_occupancy(self, date_str: str) -> Dict[str, Any]:
        """
        Analizira zasedenost terminov za določen dan.

        Args:
            date_str: Datum v formatu DD.MM.YYYY

        Returns:
            {
                "total_slots": int,
                "booked_slots": int,
                "occupancy_rate": float,
                "busiest_hour": int,
                "quietest_hour": int,
                "by_hour": {hour: {"booked": int, "available": int}}
            }
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            # Pridobi rezervacije za ta dan
            query = f"""
                SELECT time, service_type FROM reservations
                WHERE date = {ph}
                AND status IN ('pending', 'confirmed', 'completed')
            """
            cur.execute(query, (date_str,))
            reservations = cur.fetchall()

            # Štej po urah
            hourly_bookings = Counter()
            for res in reservations:
                time_str = res.get('time', '')
                if time_str and ':' in time_str:
                    hour = int(time_str.split(':')[0])
                    hourly_bookings[hour] += 1

            # Izračunaj za vsako uro
            total_slots = 0
            booked_total = 0
            by_hour = {}

            for hour in range(WORKING_HOURS["start"], WORKING_HOURS["end"]):
                # 2 slota na uro (ob :00 in :30)
                slots_this_hour = 2
                booked_this_hour = hourly_bookings.get(hour, 0)
                available = max(0, slots_this_hour - booked_this_hour)

                by_hour[hour] = {
                    "booked": booked_this_hour,
                    "available": available,
                    "slots": slots_this_hour
                }

                total_slots += slots_this_hour
                booked_total += booked_this_hour

            # Najdi peak in quiet ure
            busiest = max(hourly_bookings.items(), key=lambda x: x[1])[0] if hourly_bookings else 10
            quietest = min(by_hour.items(), key=lambda x: x[1]["booked"])[0] if by_hour else 14

            return {
                "date": date_str,
                "total_slots": total_slots,
                "booked_slots": booked_total,
                "available_slots": total_slots - booked_total,
                "occupancy_rate": round(booked_total / total_slots * 100, 1) if total_slots > 0 else 0,
                "busiest_hour": busiest,
                "quietest_hour": quietest,
                "by_hour": by_hour
            }

        except Exception as e:
            logger.error(f"Error getting slot occupancy: {e}")
            return {"error": str(e)}
        finally:
            self._close_connection()

    def get_weekly_load(self, start_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Vrne load za cel teden.

        Args:
            start_date: Začetni datum (default: danes)

        Returns:
            {
                "days": [{"date": str, "occupancy": float, "available": int}],
                "busiest_day": str,
                "recommended_day": str
            }
        """
        try:
            if start_date:
                parts = start_date.split('.')
                start = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            else:
                start = datetime.now()

            days = []
            occupancies = []

            for i in range(7):
                current = start + timedelta(days=i)

                # Skip vikende
                if current.weekday() not in WORKING_DAYS:
                    continue

                date_str = current.strftime("%d.%m.%Y")
                occupancy = self.get_slot_occupancy(date_str)

                days.append({
                    "date": date_str,
                    "day_name": ["Pon", "Tor", "Sre", "Čet", "Pet", "Sob", "Ned"][current.weekday()],
                    "occupancy_rate": occupancy.get("occupancy_rate", 0),
                    "available_slots": occupancy.get("available_slots", 0)
                })

                occupancies.append((date_str, occupancy.get("occupancy_rate", 0)))

            # Najdi busiest in recommended
            if occupancies:
                busiest = max(occupancies, key=lambda x: x[1])[0]
                recommended = min(occupancies, key=lambda x: x[1])[0]
            else:
                busiest = recommended = None

            return {
                "days": days,
                "busiest_day": busiest,
                "recommended_day": recommended,
                "week_start": start.strftime("%d.%m.%Y")
            }

        except Exception as e:
            logger.error(f"Error getting weekly load: {e}")
            return {"error": str(e)}

    # ================================================================
    # SMART SUGGESTIONS
    # ================================================================

    def get_smart_suggestions(
        self,
        service_type: str,
        preferred_date: Optional[str] = None,
        phone: Optional[str] = None,
        max_suggestions: int = 5
    ) -> Dict[str, Any]:
        """
        Vrne pametne predloge terminov na podlagi:
        - Uporabnikovih preferenc (če je znan)
        - Zasedenosti klinike
        - Tipa storitve

        Args:
            service_type: Tip storitve (dermatolog, ortoped, ...)
            preferred_date: Želeni datum (DD.MM.YYYY)
            phone: Telefon za lookup preferenc
            max_suggestions: Maksimalno število predlogov

        Returns:
            {
                "suggestions": [
                    {
                        "date": str,
                        "time": str,
                        "reason": str,
                        "score": float
                    }
                ],
                "user_preferences": {...} or None,
                "clinic_status": str
            }
        """
        try:
            suggestions = []

            # 1. Pridobi user preferences (če je phone)
            user_prefs = None
            if phone:
                user_prefs = self.get_user_preferences(phone)

            # 2. Določi datumsko območje
            if preferred_date:
                try:
                    parts = preferred_date.split('.')
                    start_date = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                except Exception:
                    start_date = datetime.now()
            else:
                start_date = datetime.now()

            # 3. Generiraj kandidate za naslednje 2 tedne
            candidates = []

            for days_ahead in range(14):
                current_date = start_date + timedelta(days=days_ahead)

                # Skip vikende
                if current_date.weekday() not in WORKING_DAYS:
                    continue

                # Skip preteklost
                if current_date.date() < datetime.now().date():
                    continue

                date_str = current_date.strftime("%d.%m.%Y")

                # Pridobi proste slote
                available_slots = get_available_time_slots(date_str, service_type)

                for time_slot in available_slots:
                    hour = int(time_slot.split(':')[0])

                    # Izračunaj score
                    score = 50.0  # Base score

                    # Bonus za user preference
                    if user_prefs and user_prefs.get("has_history"):
                        pref_hour = user_prefs.get("preferred_hour", 10)
                        pref_day = user_prefs.get("preferred_day", 1)

                        # Hour match
                        hour_diff = abs(hour - pref_hour)
                        if hour_diff == 0:
                            score += 20
                        elif hour_diff <= 1:
                            score += 10

                        # Day match
                        if current_date.weekday() == pref_day:
                            score += 15

                    # Bonus za preferred date
                    if days_ahead == 0:
                        score += 10
                    elif days_ahead <= 2:
                        score += 5

                    # Penalty za zelo zgodnje/pozne ure
                    if hour < 9 or hour >= 17:
                        score -= 5

                    # Bonus za "prime time" (10-14)
                    if 10 <= hour <= 14:
                        score += 5

                    candidates.append({
                        "date": date_str,
                        "time": time_slot,
                        "score": score,
                        "day_name": ["Ponedeljek", "Torek", "Sreda", "Četrtek", "Petek"][current_date.weekday()],
                        "days_ahead": days_ahead
                    })

            # 4. Sortiraj po score in izberi top N
            candidates.sort(key=lambda x: x["score"], reverse=True)
            top_candidates = candidates[:max_suggestions]

            # 5. Dodaj razloge
            for candidate in top_candidates:
                reasons = []

                if candidate["days_ahead"] == 0:
                    reasons.append("danes")
                elif candidate["days_ahead"] == 1:
                    reasons.append("jutri")

                hour = int(candidate["time"].split(':')[0])
                if 10 <= hour <= 14:
                    reasons.append("ugoden čas")

                if user_prefs and user_prefs.get("has_history"):
                    pref_hour = user_prefs.get("preferred_hour")
                    if pref_hour and abs(hour - pref_hour) <= 1:
                        reasons.append("vaš običajen čas")

                candidate["reason"] = ", ".join(reasons) if reasons else "prost termin"
                suggestions.append(candidate)

            # 6. Generiraj clinic status
            if not suggestions:
                clinic_status = "Ni prostih terminov v naslednjih 2 tednih"
            elif suggestions[0]["days_ahead"] > 7:
                clinic_status = "Zasedeno - prvi prosti termin čez teden dni"
            else:
                clinic_status = "Dobra razpoložljivost"

            return {
                "suggestions": suggestions,
                "user_preferences": user_prefs if user_prefs and user_prefs.get("has_history") else None,
                "clinic_status": clinic_status,
                "service_type": service_type,
                "total_candidates": len(candidates)
            }

        except Exception as e:
            logger.error(f"Error getting smart suggestions: {e}")
            return {"suggestions": [], "error": str(e)}

    def format_suggestion_message(
        self,
        suggestions: List[Dict],
        user_prefs: Optional[Dict] = None
    ) -> str:
        """
        Formatira predloge v prijazno sporočilo za uporabnika.

        Args:
            suggestions: Seznam predlogov iz get_smart_suggestions()
            user_prefs: User preferences (opcijsko)

        Returns:
            Formatirano sporočilo za chatbot
        """
        if not suggestions:
            return "Trenutno ni prostih terminov. Prosimo, pokličite recepcijo."

        lines = []

        # Personaliziran uvod
        if user_prefs and user_prefs.get("has_history"):
            lines.append(f"Na podlagi vaših {user_prefs['booking_count']} preteklih obiskov predlagam:")
        else:
            lines.append("Predlagam naslednje termine:")

        lines.append("")

        # Seznam terminov
        for i, sug in enumerate(suggestions[:3], 1):
            time_str = sug["time"]
            date_str = sug["date"]
            day_name = sug.get("day_name", "")
            reason = sug.get("reason", "")

            line = f"{i}. **{day_name}, {date_str}** ob {time_str}"
            if reason:
                line += f" ({reason})"
            lines.append(line)

        lines.append("")
        lines.append("Kateri termin vam ustreza?")

        return "\n".join(lines)


# Singleton instance
_smart_scheduler = None


def get_smart_scheduler() -> SmartScheduler:
    """Vrne singleton instance."""
    global _smart_scheduler
    if _smart_scheduler is None:
        _smart_scheduler = SmartScheduler()
    return _smart_scheduler
