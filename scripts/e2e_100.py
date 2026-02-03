#!/usr/bin/env python3
"""
100 E2E tests for Health Center chatbot (real chat flow via chat endpoint).
Runs full conversational steps and validates expected substrings.
"""
import os
import sys
import asyncio
from typing import List, Tuple

# Force unified router
os.environ["USE_UNIFIED_ROUTER"] = "true"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.chat import ChatRequest  # noqa: E402
from app.services.chat_router import chat  # noqa: E402

Step = Tuple[str, List[str]]
Scenario = Tuple[str, List[Step]]


async def run_step(message: str, session_id: str) -> str:
    resp = await chat(ChatRequest(message=message, session_id=session_id))
    return resp.reply or ""


def assert_contains(reply: str, expected: List[str]) -> bool:
    return all(token.lower() in reply.lower() for token in expected)


def build_scenarios() -> List[Scenario]:
    scenarios: List[Scenario] = []

    services = [
        ("dermatolog", "dermatolog"),
        ("ortoped", "ortoped"),
        ("okulist", "okulist"),
        ("kozmetika", "kozmet"),
        ("estetski poseg", "estetsk"),
        ("laserski poseg", "laser"),
    ]

    # 1) Basic booking flows (24 scenarios)
    for i, (svc, key) in enumerate(services * 4, start=1):
        scenarios.append((
            f"B{i:02d} booking {svc}",
            [
                (f"Rad bi termin pri {svc}", ["datum"]),
                ("16.3.2026", ["ura"]),
                ("09:00", ["ime"]),
            ],
        ))

    # 2) Symptom -> booking confirm (16 scenarios)
    symptoms = [
        ("boli me koleno", "ortoped"),
        ("imam čudno znamenje", "dermatolog"),
        ("slabše vidim", "okulist"),
        ("težave s hrbtom", "ortoped"),
    ]
    for i, (sym, svc) in enumerate(symptoms * 4, start=1):
        scenarios.append((
            f"S{i:02d} symptom {svc}",
            [
                (sym, ["termin", "datum"]),
                ("da", ["pregled", "datum"]),
                (svc, ["datum"]),
            ],
        ))

    # 3) Info flows (20 scenarios)
    info_q = [
        ("Kdaj ste odprti?", ["delovni", "pon" ]),
        ("Kje se nahajate?", ["naslov"]),
        ("Ali imate parking?", ["parking"]),
        ("Kako se naročim?", ["naroč" ]),
        ("Koliko stane dermatolog?", ["dermatolog", "€"]),
    ]
    for i, (q, exp) in enumerate(info_q * 4, start=1):
        scenarios.append((f"I{i:02d} info", [(q, exp)]))

    # 4) Booking with soft interrupts (20 scenarios)
    for i in range(1, 21):
        scenarios.append((
            f"M{i:02d} booking+interrupt",
            [
                ("Rad bi termin pri dermatologu", ["datum"]),
                ("Koliko stane?", ["cena", "€"]),
                ("17.3.2026", ["ura"]),
            ],
        ))

    # 5) Mixed language / typos (20 scenarios)
    mixed = [
        ("I need an eye check", ["okulist", "datum"]),
        ("rad bi termin pr dermatalogu", ["datum"]),
        ("cenik", ["cena", "€"]),
        ("kje ste", ["naslov"]),
        ("naročil bi se", ["pregled"]),
    ]
    for i, (q, exp) in enumerate(mixed * 4, start=1):
        scenarios.append((f"X{i:02d} mixed", [(q, exp)]))

    # ensure exactly 100
    return scenarios[:100]


async def main():
    scenarios = build_scenarios()
    passed = 0
    failed = 0

    print("=" * 70)
    print("🔥 100 E2E TESTS - Health Center")
    print("=" * 70)

    for idx, (name, steps) in enumerate(scenarios, start=1):
        session_id = f"e2e-{idx}"  # isolate sessions
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
            print(f"✅ {name}")
            passed += 1
        else:
            failed += 1

    print("=" * 70)
    print(f"REZULTAT: {passed}/{len(scenarios)} PASSED, {failed}/{len(scenarios)} FAILED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
