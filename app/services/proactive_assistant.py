"""
Proaktivni Health Assistant - Predvidevanje potreb pacientov

FUNKCIONALNOST:
1. Seasonal pattern detection - "Vsako pomlad iščete alergologa..."
2. Preventive reminders - "Minilo je leto od zadnjega pregleda..."
3. Follow-up care - Po določenih posegih: kontrolni pregled
4. Health campaigns - Preventivni pregledi, akcije

UPORABA:
    from app.services.proactive_assistant import ProactiveAssistant

    assistant = ProactiveAssistant()
    alerts = assistant.get_patient_alerts(phone="+38640123456")
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import Counter, defaultdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Tipi proaktivnih opozoril"""
    SEASONAL_PATTERN = "seasonal_pattern"       # Sezonski vzorec
    ANNUAL_CHECKUP = "annual_checkup"           # Letni pregled
    FOLLOWUP_NEEDED = "followup_needed"         # Potreben kontrolni pregled
    HEALTH_CAMPAIGN = "health_campaign"         # Preventivna akcija
    APPOINTMENT_GAP = "appointment_gap"         # Dolgo ni bilo pregleda


# Sezonski vzorci (mesec -> storitve)
SEASONAL_PATTERNS = {
    # Pomlad (marec-maj)
    3: ["alergolog", "dermatolog"],
    4: ["alergolog", "dermatolog"],
    5: ["alergolog", "dermatolog", "okulist"],
    # Poletje (junij-avgust)
    6: ["dermatolog", "estetski_poseg"],
    7: ["dermatolog", "estetski_poseg"],
    8: ["dermatolog", "okulist"],
    # Jesen (september-november)
    9: ["okulist", "ortoped"],
    10: ["ortoped", "dermatolog"],
    11: ["ortoped", "dermatolog"],
    # Zima (december-februar)
    12: ["ortoped", "kozmetika"],
    1: ["kozmetika", "estetski_poseg"],
    2: ["kozmetika", "estetski_poseg", "dermatolog"],
}

# Storitve, ki potrebujejo follow-up
FOLLOWUP_REQUIRED = {
    "laserski_poseg": {
        "days_after": 14,
        "message": "Kontrolni pregled po laserskem posegu"
    },
    "estetski_poseg": {
        "days_after": 14,
        "message": "Kontrolni pregled po estetskem posegu"
    },
    "ortoped": {
        "days_after": 30,
        "message": "Kontrolni ortopedski pregled"
    }
}

# Letni pregledi (storitev -> interval v dnevih)
ANNUAL_CHECKUP_INTERVALS = {
    "okulist": 365,         # 1x letno
    "dermatolog": 365,      # 1x letno (pregled kože)
    "ortoped": 365,         # 1x letno za kronične težave
}

# Health campaigns (mesec -> kampanja)
HEALTH_CAMPAIGNS = {
    1: {
        "title": "Novoletna akcija - Estetski posegi",
        "services": ["estetski_poseg", "kozmetika"],
        "discount": "20%"
    },
    3: {
        "title": "Mesec zdravja kože",
        "services": ["dermatolog"],
        "discount": "Brezplačen pregled znamenj"
    },
    5: {
        "title": "Alergijska sezona",
        "services": ["alergolog", "dermatolog"],
        "message": "Preventivni pregled pred sezono"
    },
    9: {
        "title": "Nazaj v šolo - Očesni pregled",
        "services": ["okulist"],
        "discount": "15%"
    },
    10: {
        "title": "Mesec rožnate pentlje",
        "services": ["dermatolog"],
        "message": "Preventivni pregled dojk"
    }
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


class ProactiveAssistant:
    """Proaktivni asistent za predvidevanje potreb pacientov."""

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
    # PATIENT HISTORY ANALYSIS
    # ================================================================

    def get_patient_history(self, phone: str) -> List[Dict]:
        """
        Pridobi zgodovino rezervacij za pacienta.

        Args:
            phone: Telefonska številka

        Returns:
            Seznam rezervacij
        """
        try:
            self._ensure_connection()
            cur = self.conn.cursor()
            ph = _get_placeholder(self.db_type)

            # Normaliziraj telefon
            phone_pattern = f"%{phone[-9:]}%" if len(phone) >= 9 else f"%{phone}%"

            query = f"""
                SELECT * FROM reservations
                WHERE phone LIKE {ph}
                AND status IN ('completed', 'confirmed')
                ORDER BY date DESC
            """
            cur.execute(query, (phone_pattern,))
            rows = cur.fetchall()

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting patient history: {e}")
            return []
        finally:
            self._close_connection()

    def analyze_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """
        Analizira vzorce v zgodovini pacienta.

        Returns:
            {
                "seasonal_services": {month: [services]},
                "service_frequency": {service: count},
                "last_visits": {service: date},
                "avg_interval_days": float
            }
        """
        if not history:
            return {
                "has_history": False,
                "service_frequency": {},
                "last_visits": {},
                "seasonal_services": {}
            }

        seasonal_services = defaultdict(list)
        service_frequency = Counter()
        last_visits = {}
        visit_dates = []

        for res in history:
            date_str = res.get('date', '')
            service = (res.get('service_type') or res.get('location', '')).lower()

            if date_str and service:
                try:
                    parts = date_str.split('.')
                    if len(parts) == 3:
                        dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                        month = dt.month

                        # Seasonal pattern
                        if service not in seasonal_services[month]:
                            seasonal_services[month].append(service)

                        # Service frequency
                        service_frequency[service] += 1

                        # Last visit per service
                        if service not in last_visits:
                            last_visits[service] = date_str

                        # All visit dates
                        visit_dates.append(dt)

                except Exception:
                    pass

        # Calculate average interval
        avg_interval = 0
        if len(visit_dates) >= 2:
            visit_dates.sort(reverse=True)
            intervals = []
            for i in range(len(visit_dates) - 1):
                delta = (visit_dates[i] - visit_dates[i + 1]).days
                intervals.append(delta)
            avg_interval = sum(intervals) / len(intervals) if intervals else 0

        return {
            "has_history": True,
            "total_visits": len(history),
            "service_frequency": dict(service_frequency),
            "last_visits": dict(last_visits),
            "seasonal_services": dict(seasonal_services),
            "avg_interval_days": round(avg_interval, 1)
        }

    # ================================================================
    # SEASONAL PATTERN DETECTION
    # ================================================================

    def detect_seasonal_needs(
        self,
        patterns: Dict,
        current_month: Optional[int] = None
    ) -> List[Dict]:
        """
        Zazna sezonske potrebe na podlagi preteklih vzorcev.

        Args:
            patterns: Rezultat analyze_patterns()
            current_month: Trenutni mesec (default: danes)

        Returns:
            Seznam sezonskih priporočil
        """
        if not patterns.get("has_history"):
            return []

        month = current_month or datetime.now().month
        recommendations = []

        seasonal_services = patterns.get("seasonal_services", {})

        # Preveri če je pacient v preteklosti ta mesec uporabljal storitve
        if month in seasonal_services:
            for service in seasonal_services[month]:
                # Preveri kdaj je bil zadnji obisk
                last_visit = patterns.get("last_visits", {}).get(service)

                if last_visit:
                    try:
                        parts = last_visit.split('.')
                        last_dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                        days_since = (datetime.now() - last_dt).days

                        # Če je minilo več kot 10 mesecev, priporoči
                        if days_since > 300:
                            recommendations.append({
                                "type": AlertType.SEASONAL_PATTERN.value,
                                "service": service,
                                "message": f"Vsako leto v tem času uporabljate storitev {service}. Želite rezervirati termin?",
                                "last_visit": last_visit,
                                "days_since": days_since,
                                "priority": 2
                            })
                    except Exception:
                        pass

        return recommendations

    # ================================================================
    # PREVENTIVE REMINDERS
    # ================================================================

    def check_annual_checkups(self, patterns: Dict) -> List[Dict]:
        """
        Preveri potrebo po letnih pregledih.

        Returns:
            Seznam priporočil za letne preglede
        """
        if not patterns.get("has_history"):
            return []

        recommendations = []
        last_visits = patterns.get("last_visits", {})
        service_frequency = patterns.get("service_frequency", {})

        for service, interval_days in ANNUAL_CHECKUP_INTERVALS.items():
            # Preveri samo storitve, ki jih je pacient že uporabil
            if service not in service_frequency:
                continue

            last_visit = last_visits.get(service)
            if not last_visit:
                continue

            try:
                parts = last_visit.split('.')
                last_dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                days_since = (datetime.now() - last_dt).days

                # Če je minilo več kot interval, priporoči
                if days_since >= interval_days:
                    recommendations.append({
                        "type": AlertType.ANNUAL_CHECKUP.value,
                        "service": service,
                        "message": f"Od zadnjega pregleda ({service}) je minilo {days_since} dni. Priporočamo letni kontrolni pregled.",
                        "last_visit": last_visit,
                        "days_since": days_since,
                        "overdue_days": days_since - interval_days,
                        "priority": 3
                    })
            except Exception:
                pass

        return recommendations

    # ================================================================
    # FOLLOW-UP CARE
    # ================================================================

    def check_followup_needs(self, history: List[Dict]) -> List[Dict]:
        """
        Preveri potrebo po kontrolnih pregledih.

        Returns:
            Seznam potrebnih follow-up-ov
        """
        recommendations = []
        now = datetime.now()

        for res in history:
            service = (res.get('service_type') or res.get('location', '')).lower()
            date_str = res.get('date', '')
            status = res.get('status', '')

            # Samo dokončani obiski
            if status != 'completed':
                continue

            # Preveri če storitev potrebuje follow-up
            if service not in FOLLOWUP_REQUIRED:
                continue

            followup_config = FOLLOWUP_REQUIRED[service]

            try:
                parts = date_str.split('.')
                visit_dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                days_since = (now - visit_dt).days
                followup_days = followup_config["days_after"]

                # Če je čas za follow-up (v oknu 7 dni pred/po)
                if followup_days - 7 <= days_since <= followup_days + 7:
                    recommendations.append({
                        "type": AlertType.FOLLOWUP_NEEDED.value,
                        "service": service,
                        "message": followup_config["message"],
                        "original_visit": date_str,
                        "days_since": days_since,
                        "followup_due": followup_days,
                        "priority": 4
                    })
            except Exception:
                pass

        return recommendations

    # ================================================================
    # HEALTH CAMPAIGNS
    # ================================================================

    def get_active_campaigns(
        self,
        patterns: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Vrne aktivne zdravstvene kampanje.

        Args:
            patterns: Patient patterns za personalizacijo

        Returns:
            Seznam aktivnih kampanj
        """
        month = datetime.now().month
        campaigns = []

        if month in HEALTH_CAMPAIGNS:
            campaign = HEALTH_CAMPAIGNS[month]

            # Preveri relevantnost za pacienta
            relevance = "general"
            if patterns and patterns.get("has_history"):
                patient_services = set(patterns.get("service_frequency", {}).keys())
                campaign_services = set(campaign.get("services", []))

                if patient_services & campaign_services:
                    relevance = "personalized"

            campaigns.append({
                "type": AlertType.HEALTH_CAMPAIGN.value,
                "title": campaign.get("title"),
                "services": campaign.get("services", []),
                "discount": campaign.get("discount"),
                "message": campaign.get("message"),
                "relevance": relevance,
                "priority": 1
            })

        return campaigns

    # ================================================================
    # MAIN ALERT GENERATOR
    # ================================================================

    def get_patient_alerts(
        self,
        phone: str,
        include_campaigns: bool = True
    ) -> Dict[str, Any]:
        """
        Vrne vse proaktivne alerte za pacienta.

        Args:
            phone: Telefonska številka
            include_campaigns: Vključi kampanje

        Returns:
            {
                "alerts": [...],
                "patient_summary": {...},
                "total_alerts": int
            }
        """
        # Get patient history
        history = self.get_patient_history(phone)
        patterns = self.analyze_patterns(history)

        alerts = []

        # 1. Seasonal patterns
        seasonal = self.detect_seasonal_needs(patterns)
        alerts.extend(seasonal)

        # 2. Annual checkups
        annual = self.check_annual_checkups(patterns)
        alerts.extend(annual)

        # 3. Follow-up needs
        followup = self.check_followup_needs(history)
        alerts.extend(followup)

        # 4. Health campaigns
        if include_campaigns:
            campaigns = self.get_active_campaigns(patterns)
            alerts.extend(campaigns)

        # Sort by priority (highest first)
        alerts.sort(key=lambda x: x.get("priority", 0), reverse=True)

        return {
            "phone": phone,
            "generated_at": datetime.now().isoformat(),
            "alerts": alerts,
            "total_alerts": len(alerts),
            "patient_summary": {
                "total_visits": patterns.get("total_visits", 0),
                "services_used": list(patterns.get("service_frequency", {}).keys()),
                "avg_interval_days": patterns.get("avg_interval_days", 0)
            } if patterns.get("has_history") else None
        }

    def format_proactive_message(
        self,
        alerts: List[Dict],
        patient_name: Optional[str] = None
    ) -> str:
        """
        Formatira proaktivno sporočilo za pacienta.

        Args:
            alerts: Seznam alertov
            patient_name: Ime pacienta (opcijsko)

        Returns:
            Formatirano sporočilo
        """
        if not alerts:
            return ""

        lines = []

        greeting = f"Pozdravljeni{', ' + patient_name if patient_name else ''}!"
        lines.append(greeting)
        lines.append("")

        # Group by type
        for alert in alerts[:3]:  # Max 3 alerts
            alert_type = alert.get("type", "")
            message = alert.get("message", "")

            if alert_type == AlertType.FOLLOWUP_NEEDED.value:
                lines.append(f"📋 **Kontrolni pregled**: {message}")
            elif alert_type == AlertType.ANNUAL_CHECKUP.value:
                lines.append(f"📅 **Letni pregled**: {message}")
            elif alert_type == AlertType.SEASONAL_PATTERN.value:
                lines.append(f"🌸 {message}")
            elif alert_type == AlertType.HEALTH_CAMPAIGN.value:
                title = alert.get("title", "")
                discount = alert.get("discount", "")
                if discount:
                    lines.append(f"🎁 **{title}** - {discount}")
                else:
                    lines.append(f"ℹ️ **{title}**")

        lines.append("")
        lines.append("Želite rezervirati termin?")

        return "\n".join(lines)


# Singleton instance
_proactive_assistant = None


def get_proactive_assistant() -> ProactiveAssistant:
    """Vrne singleton instance."""
    global _proactive_assistant
    if _proactive_assistant is None:
        _proactive_assistant = ProactiveAssistant()
    return _proactive_assistant
