#!/usr/bin/env python3
"""
E2E variations test runner for Health Center chatbot.
Generates many dialog variants (typos, slang, mixed intents, confirmations) and runs them.

Usage:
  python scripts/e2e_variations.py            # default 300 scenarios
  COUNT=1000 python scripts/e2e_variations.py
"""
import os
import sys
import asyncio
import random
from typing import List, Tuple

os.environ["USE_UNIFIED_ROUTER"] = "true"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.chat import ChatRequest  # noqa: E402
from app.services.chat_router import chat  # noqa: E402

Step = Tuple[str, List[str]]
Scenario = Tuple[str, List[Step]]

RANDOM = random.Random(42)


def assert_contains(reply: str, expected: List[str]) -> bool:
    return all(token.lower() in reply.lower() for token in expected)


async def run_step(message: str, session_id: str) -> str:
    resp = await chat(ChatRequest(message=message, session_id=session_id))
    return resp.reply or ""


def _variants(base: List[str], typos: List[str]) -> List[str]:
    return list(dict.fromkeys(base + typos))


def build_variation_scenarios(count: int) -> List[Scenario]:
    scenarios: List[Scenario] = []

    service_variants = {
        "dermatolog": _variants(
            ["dermatolog", "dermatološki", "koža", "kožne težave", "znamnje"],
            ["dermatalog", "dermatalogu", "dermatlog", "kozna"],
        ),
        "ortoped": _variants(
            ["ortoped", "ortopedski", "koleno", "hrbet", "bolečine v hrbtu"],
            ["ortopet", "ortopd", "hrbtom"],
        ),
        "okulist": _variants(
            ["okulist", "očesni", "slabo vidim", "ocena vida", "eye check"],
            ["okulsit", "ocmi", "vision", "eye exam"],
        ),
    }

    booking_intros = _variants(
        ["rad bi termin pri", "želim termin pri", "naročil bi se k", "bi se naročil na"],
        ["rad bi termin pr", "naročil bi se", "bi narocil"],
    )

    confirm_words = ["da", "ja", "dada", "okej", "ok"]

    info_questions = [
        ("Kdaj ste odprti?", ["delovni"]),
        ("Kje se nahajate?", ["naslov"]),
        ("Ali imate parking?", ["parking"]),
        ("Kako se naročim?", ["naročanje"]),
        ("Koliko stane dermatolog?", ["dermatolog", "€"]),
    ]

    price_interrupts = [
        ("Koliko stane?", ["cena", "€"]),
        ("A je drago?", ["cena", "€"]),
        ("cenik", ["cena", "€"]),
    ]

    # 1) Booking flows with variations
    for svc, variants in service_variants.items():
        for v in variants:
            intro = RANDOM.choice(booking_intros)
            scenarios.append((
                f"booking-{svc}-{v}",
                [
                    (f"{intro} {v}", ["datum"]),
                    ("16.3.2026", ["ura"]),
                    ("09:00", ["ime"]),
                ],
            ))

    # 2) Symptom -> booking confirm (affirmative)
    symptoms = [
        ("boli me koleno", "ortoped"),
        ("imam čudno znamenje", "dermatolog"),
        ("slabše vidim", "okulist"),
        ("težave s hrbtom", "ortoped"),
    ]
    for msg, svc in symptoms:
        scenarios.append((
            f"symptom-{svc}",
            [
                (msg, ["termin", "datum"]),
                (RANDOM.choice(confirm_words), ["datum"]),
            ],
        ))

    # 3) Info questions
    for q, exp in info_questions:
        scenarios.append((f"info-{q}", [(q, exp)]))

    # 4) Booking + soft interrupt (price)
    for _ in range(40):
        scenarios.append((
            "booking-interrupt-price",
            [
                ("Rad bi termin pri dermatologu", ["datum"]),
                (RANDOM.choice([p[0] for p in price_interrupts]), ["cena", "€"]),
                ("17.3.2026", ["ura"]),
            ],
        ))

    # 5) Mixed language / vague booking
    mixed = [
        ("I need an eye check", ["okulist", "datum"]),
        ("rad bi termin pr dermatalogu", ["datum"]),
        ("naročil bi se", ["pregled"]),
        ("kje ste", ["naslov"]),
    ]
    for q, exp in mixed:
        scenarios.append((f"mixed-{q}", [(q, exp)]))

    # Trim or expand to requested count
    if len(scenarios) >= count:
        return scenarios[:count]

    # If not enough, repeat with random shuffle
    while len(scenarios) < count:
        scenarios.extend(RANDOM.sample(scenarios, min(50, len(scenarios))))
    return scenarios[:count]


async def main():
    count = int(os.environ.get("COUNT", "300"))
    scenarios = build_variation_scenarios(count)

    passed = 0
    failed = 0

    print("=" * 70)
    print(f"🔥 E2E VARIATIONS - {len(scenarios)} scenarios")
    print("=" * 70)

    for idx, (name, steps) in enumerate(scenarios, start=1):
        session_id = f"e2e-var-{idx}"
        ok = True
        for step_idx, (msg, expected) in enumerate(steps, start=1):
            reply = await run_step(msg, session_id)
            if not assert_contains(reply, expected):
                print(f"❌ {name} (step {step_idx})")
                print(f"   msg: {msg}")
                print(f"   expected: {expected}")
                print(f"   reply: {reply[:200]}...")
                ok = False
                break
        if ok:
            passed += 1
        else:
            failed += 1

    print("=" * 70)
    print(f"REZULTAT: {passed}/{len(scenarios)} PASSED, {failed}/{len(scenarios)} FAILED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
