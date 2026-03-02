"""
Out-of-Domain (OOD) Policy Guard for Pod Goro AI

This module provides centralized OOD detection and response handling
for Kmetija Pod Goro chatbot.

Based on the spec:
- OOD_HARD: Clearly outside domain (traktor, avto, bitcoin, vreme, politika)
- OOD_MEDICAL: Medical questions outside farm domain
- OOD_SOFT: Borderline cases detected via RAG similarity threshold

Priority: ood_hard > ood_medical > ood_soft
"""
from __future__ import annotations

import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION (via environment variables)
# ─────────────────────────────────────────────────────────────────────────────

OOD_HARD_ENABLED = os.getenv("OOD_HARD_ENABLED", "false").lower() == "true"
OOD_MEDICAL_ENABLED = os.getenv("OOD_MEDICAL_ENABLED", "false").lower() == "true"
OOD_SOFT_ENABLED = os.getenv("OOD_SOFT_ENABLED", "false").lower() == "true"
OOD_SOFT_DRY_RUN = os.getenv("OOD_SOFT_DRY_RUN", "true").lower() == "true"
OOD_THRESHOLD = max(0.0, min(1.0, float(os.getenv("OOD_THRESHOLD", "0.45"))))
OOD_LOG_SAMPLES = os.getenv("OOD_LOG_SAMPLES", "true").lower() == "true"
OOD_LOG_SAMPLE_RATE = max(0.0, min(1.0, float(os.getenv("OOD_LOG_SAMPLE_RATE", "0.2"))))
OOD_MIXED_SPLIT_ENABLED = os.getenv("OOD_MIXED_SPLIT_ENABLED", "true").lower() == "true"

# Minimum input length for OOD classification (skip "ok", "ja", "hm")
MIN_OOD_INPUT_LENGTH = 4

# Log file path
OOD_LOG_PATH = Path("data/ood_samples.jsonl")


class OODLevel(str, Enum):
    """OOD classification levels."""
    HARD = "ood_hard"
    MEDICAL = "ood_medical"
    SOFT = "ood_soft"
    NONE = "none"


@dataclass
class OODResult:
    """Result of OOD classification."""
    is_ood: bool
    level: OODLevel
    confidence: float
    reason: str
    response: Optional[str] = None
    in_domain_parts: Optional[list[str]] = None  # For mixed-input handling


# ─────────────────────────────────────────────────────────────────────────────
# OOD HARD KEYWORDS (minimalen seznam)
# ─────────────────────────────────────────────────────────────────────────────

OOD_HARD_KEYWORDS = frozenset({
    # Transport / vehicles
    "traktor", "avto", "avtomobil", "motocikel", "motor",
    # Finance / crypto
    "bitcoin", "crypto", "kripto", "delnice", "investic", "banka", "kredit",
    # Politics / news
    "politika", "politik", "volit", "volitve", "vlada", "predsednik",
    "stranka", "trump", "biden",
    # Weather (general, not farm-related)
    "napoved vremena", "vremenska napoved",
    # Real estate
    "nepremičnin", "nepremicnin", "stanovanje",
    # Tech / IT
    "programir", "python", "javascript", "linux", "windows",
    "android", "iphone",
    # Sports results
    "nogomet rezultat", "košarka rezultat", "tenis rezultat",
    # Completely unrelated
    "letalo", "ladja", "vlak",
})

# ─────────────────────────────────────────────────────────────────────────────
# OOD MEDICAL KEYWORDS (za kmetijo - zdravstvene teme so OOD)
# ─────────────────────────────────────────────────────────────────────────────

OOD_MEDICAL_KEYWORDS = frozenset({
    "zdravnik", "doktor", "bolnišnic", "ambulant", "recept",
    "zdravilo", "tablete", "bolečin", "bolezen", "simptom",
    "diagnoz", "terapij", "operacij", "pregled",
    "covid", "korona", "cepiv", "gripa",
    "driska", "bruhanje", "vročin", "mrzlic",
})

# ─────────────────────────────────────────────────────────────────────────────
# IN-DOMAIN KEYWORDS (za Kmetijo Pod Goro)
# ─────────────────────────────────────────────────────────────────────────────

IN_DOMAIN_KEYWORDS = frozenset({
    # Accommodation
    "soba", "sobo", "sobi", "nastanit", "nočit", "nocit", "prenočit", "prenocit",
    "rezerv", "book", "termin",
    # Food / restaurant
    "miza", "mizo", "kosilo", "večerj", "zajtrk", "hrana", "jedilnik", "meni",
    "degustacij", "kulinarik", "jed", "krožnik",
    # Products
    "marmelad", "liker", "sirup", "čaj", "sok", "med",
    "vino", "cvicek", "šipon", "renski", "sauvignon",
    # Activities
    "jahanj", "kolesarj", "izlet", "sprehod", "pohor",
    # Animals
    "žival", "zival", "konj", "konji",
    # Farm / location
    "kmetij", "pod goro", "podgoro", "domačij", "pohorj", "fram",
    # People (staff)
    "marko", "sara", "jakob", "lana", "nika", "marija",
    # General inquiries
    "lokacij", "naslov", "kje ste", "kako pridem", "parkir",
    "wifi", "internet", "opremlj",
    "cen", "koliko stane", "koliko je",
    "odprto", "delovni čas", "ura",
    "kontakt", "telefon", "email", "mail",
    # Wine / drinks
    "vinska", "klet", "degustacij",
    # Events
    "poroka", "rojstni dan", "praznov", "teambuilding", "catering",
})

# ─────────────────────────────────────────────────────────────────────────────
# OOD RESPONSE TEMPLATES (3-5 variant na nivo)
# ─────────────────────────────────────────────────────────────────────────────

OOD_HARD_RESPONSES = [
    "O tem nimam informacij — sem specializiran za Domačijo Pod Goro.\n"
    "Lahko vam pomagam z rezervacijo, informacijami o naših izdelkih, jedilniku ali vinih.\n"
    "Kako vam lahko pomagam?",

    "To je izven mojega področja. Sem tu za pomoč z nastanitvijo, prehrano in aktivnostmi na Domačiji Pod Goro.\n"
    "Vas zanima kaj od tega?",

    "Žal o tem ne morem pomagati. Moje znanje zajema Domačijo Pod Goro — "
    "sobe, kulinariko, domače izdelke in vina.\n"
    "Pri čem vam lahko pomagam?",

    "To ni moje področje — sem asistent za Kmetijo Pod Goro.\n"
    "Lahko pa pomagam z rezervacijami, informacijami o sobah, jedilniku ali vinih.",
]

OOD_MEDICAL_RESPONSES = [
    "Za zdravstvena vprašanja se prosim obrnite na zdravnika ali ustrezno zdravstveno ustanovo.\n"
    "Jaz sem tu za pomoč pri Domačiji Pod Goro — rezervacije, nastanitve, kulinarika.\n"
    "Vam lahko pomagam s čim na tem področju?",

    "O zdravstvenih temah vam žal ne morem svetovati — to ni moje področje.\n"
    "Sem specializiran za Domačijo Pod Goro.\n"
    "Vas zanima rezervacija ali informacije o kmetiji?",

    "Zdravstvena vprašanja presegajo moje znanje — priporočam posvet z zdravnikom.\n"
    "Z veseljem pa pomagam z informacijami o Domačiji Pod Goro!",
]

OOD_SOFT_RESPONSES = [
    "Nisem povsem prepričan, da razumem vaše vprašanje.\n"
    "Sem specializiran za Domačijo Pod Goro — nastanitve, prehrano, domače izdelke, vina.\n"
    "Mi lahko pojasnite, kaj vas zanima?",

    "To vprašanje je morda izven mojega znanja.\n"
    "Lahko pomagam z rezervacijami, informacijami o sobah, jedilniku ali vinih.\n"
    "Kaj od tega vas zanima?",

    "Nisem prepričan, da imam te informacije.\n"
    "Moje področje je Domačija Pod Goro — povejte mi več, pa poskusim pomagati!",
]


def _get_random_response(responses: list[str]) -> str:
    """Return a random response from the list."""
    return random.choice(responses)


def _log_ood_sample(
    message: str,
    level: OODLevel,
    dry_run: bool = False,
    confidence: float = 0.0,
    reason: str = "",
) -> None:
    """Log OOD sample with sampling rate control."""
    if not OOD_LOG_SAMPLES:
        return
    if random.random() > OOD_LOG_SAMPLE_RATE:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message[:500],
        "level": level.value,
        "confidence": confidence,
        "reason": reason,
        "dry_run": dry_run,
    }

    try:
        OOD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OOD_LOG_PATH.open("a", encoding="utf-8") as f:
            import json
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log OOD sample: {e}")


def _has_keywords(text: str, keywords: frozenset[str]) -> tuple[bool, list[str]]:
    """Check if text contains any keywords. Returns (match, matched_keywords)."""
    text_lower = text.lower()
    matched = [kw for kw in keywords if kw in text_lower]
    return bool(matched), matched


def _detect_mixed_input(message: str) -> tuple[list[str], list[str]]:
    """
    Detect mixed input (OOD + in-domain parts).
    Returns (ood_parts, in_domain_parts).
    """
    sentences = re.split(r'[.?!]+', message)
    ood_parts = []
    in_domain_parts = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        has_ood, _ = _has_keywords(sentence, OOD_HARD_KEYWORDS)
        has_in_domain, _ = _has_keywords(sentence, IN_DOMAIN_KEYWORDS)

        if has_ood and not has_in_domain:
            ood_parts.append(sentence)
        elif has_in_domain:
            in_domain_parts.append(sentence)

    return ood_parts, in_domain_parts


def classify_ood(
    message: str,
    rag_similarity: Optional[float] = None,
    session_data: Optional[dict[str, Any]] = None,
) -> OODResult:
    """
    Classify message as OOD or in-domain.

    Args:
        message: User message to classify
        rag_similarity: Optional RAG similarity score (0-1)
        session_data: Optional session data for context

    Returns:
        OODResult with classification details
    """
    # Skip short inputs
    if len(message.strip()) < MIN_OOD_INPUT_LENGTH:
        return OODResult(
            is_ood=False,
            level=OODLevel.NONE,
            confidence=0.0,
            reason="Short input - skipped OOD check",
        )

    text_lower = message.lower()

    # Check if user is mid-booking - be more permissive
    is_booking = False
    if session_data:
        flow = session_data.get("flow")
        reservation = session_data.get("reservation", {})
        is_booking = flow in ("reservation_room", "reservation_table") or bool(reservation.get("step"))

    if is_booking:
        has_hard, matched_hard = _has_keywords(text_lower, OOD_HARD_KEYWORDS)
        if has_hard and OOD_HARD_ENABLED:
            return OODResult(
                is_ood=True,
                level=OODLevel.HARD,
                confidence=0.95,
                reason=f"OOD hard keyword during booking: {matched_hard}",
                response=_get_random_response(OOD_HARD_RESPONSES),
            )
        return OODResult(
            is_ood=False,
            level=OODLevel.NONE,
            confidence=0.0,
            reason="Mid-booking - OOD check relaxed",
        )

    # ── PRIORITY 1: OOD_HARD ────────────────────────────────────────────────
    if OOD_HARD_ENABLED:
        has_hard, matched_hard = _has_keywords(text_lower, OOD_HARD_KEYWORDS)
        if has_hard:
            if OOD_MIXED_SPLIT_ENABLED:
                ood_parts, in_domain_parts = _detect_mixed_input(message)
                if in_domain_parts:
                    _log_ood_sample(message, OODLevel.HARD, confidence=0.9, reason="mixed_input")
                    return OODResult(
                        is_ood=True,
                        level=OODLevel.HARD,
                        confidence=0.9,
                        reason=f"Mixed input: OOD={matched_hard}",
                        response=None,
                        in_domain_parts=in_domain_parts,
                    )

            _log_ood_sample(message, OODLevel.HARD, confidence=0.95, reason=str(matched_hard))
            return OODResult(
                is_ood=True,
                level=OODLevel.HARD,
                confidence=0.95,
                reason=f"OOD hard keywords: {matched_hard}",
                response=_get_random_response(OOD_HARD_RESPONSES),
            )

    # ── PRIORITY 2: OOD_MEDICAL ─────────────────────────────────────────────
    if OOD_MEDICAL_ENABLED:
        has_medical, matched_medical = _has_keywords(text_lower, OOD_MEDICAL_KEYWORDS)
        if has_medical:
            _log_ood_sample(message, OODLevel.MEDICAL, confidence=0.9, reason=str(matched_medical))
            return OODResult(
                is_ood=True,
                level=OODLevel.MEDICAL,
                confidence=0.9,
                reason=f"OOD medical keywords: {matched_medical}",
                response=_get_random_response(OOD_MEDICAL_RESPONSES),
            )

    # ── PRIORITY 3: OOD_SOFT (RAG similarity) ───────────────────────────────
    if OOD_SOFT_ENABLED and rag_similarity is not None:
        if rag_similarity < OOD_THRESHOLD:
            has_in_domain, _ = _has_keywords(text_lower, IN_DOMAIN_KEYWORDS)

            if not has_in_domain:
                if OOD_SOFT_DRY_RUN:
                    _log_ood_sample(
                        message, OODLevel.SOFT,
                        dry_run=True,
                        confidence=1.0 - rag_similarity,
                        reason=f"RAG similarity {rag_similarity:.2f} < {OOD_THRESHOLD}",
                    )
                    return OODResult(
                        is_ood=False,
                        level=OODLevel.SOFT,
                        confidence=1.0 - rag_similarity,
                        reason=f"OOD soft (dry run): RAG similarity {rag_similarity:.2f}",
                    )
                else:
                    _log_ood_sample(
                        message, OODLevel.SOFT,
                        confidence=1.0 - rag_similarity,
                        reason=f"RAG similarity {rag_similarity:.2f} < {OOD_THRESHOLD}",
                    )
                    return OODResult(
                        is_ood=True,
                        level=OODLevel.SOFT,
                        confidence=1.0 - rag_similarity,
                        reason=f"Low RAG similarity: {rag_similarity:.2f}",
                        response=_get_random_response(OOD_SOFT_RESPONSES),
                    )

    # ── NO OOD DETECTED ─────────────────────────────────────────────────────
    return OODResult(
        is_ood=False,
        level=OODLevel.NONE,
        confidence=0.0,
        reason="In-domain",
    )


def get_mixed_response(ood_result: OODResult, in_domain_response: str) -> str:
    """
    Generate response for mixed input.
    """
    if not ood_result.in_domain_parts:
        return ood_result.response or _get_random_response(OOD_HARD_RESPONSES)

    ood_acknowledgment = random.choice([
        "O prvem delu vašega vprašanja nimam informacij — to ni moje področje.",
        "Za del vašega vprašanja nimam podatkov.",
        "Žal ne morem pomagati z vsem, kar sprašujete.",
    ])

    return f"{ood_acknowledgment}\n\n{in_domain_response}"


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def check_ood(
    message: str,
    rag_similarity: Optional[float] = None,
    session_data: Optional[dict[str, Any]] = None,
) -> OODResult:
    """
    Main entry point for OOD checking.
    """
    return classify_ood(message, rag_similarity, session_data)
