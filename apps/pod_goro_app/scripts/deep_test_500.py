#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

os.environ.setdefault("USE_UNIFIED_ROUTER", "true")
os.environ.setdefault("STRICT_POLICY", "true")
os.environ.setdefault("DISABLE_INQUIRY", "true")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


@dataclass
class Turn:
    msg: str
    any_of: List[str]
    none_of: List[str]


@dataclass
class Scenario:
    name: str
    turns: List[Turn]


client = TestClient(app)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def run_scenario(idx: int, sc: Scenario) -> tuple[bool, str]:
    sid = f"deep500_{idx}_{re.sub(r'[^a-z0-9_]+', '_', sc.name.lower())}"
    last_reply = ""
    for t_i, turn in enumerate(sc.turns, start=1):
        res = client.post("/chat/", json={"message": turn.msg, "session_id": sid})
        if res.status_code != 200:
            return False, f"HTTP {res.status_code} at turn {t_i}"
        reply = (res.json().get("reply") or "").strip()
        last_reply = reply
        n = _norm(reply)
        if turn.any_of and not any(_norm(x) in n for x in turn.any_of):
            return False, (
                f"turn {t_i}: missing expected token(s) {turn.any_of}\n"
                f"  msg={turn.msg}\n"
                f"  reply={reply[:320]}"
            )
        if turn.none_of and any(_norm(x) in n for x in turn.none_of):
            return False, (
                f"turn {t_i}: contained forbidden token(s) {turn.none_of}\n"
                f"  msg={turn.msg}\n"
                f"  reply={reply[:320]}"
            )
    return True, last_reply


def base_one_turn_cases() -> List[Scenario]:
    cases: List[Scenario] = []

    greetings = ["zdravo", "živjo", "dober dan", "hej", "pozdrav"]
    for g in greetings:
        cases.append(Scenario(f"greet_{g}", [Turn(g, ["pomagam", "kaj vas zanima", "pozdrav"], [])]))

    info_cases = [
        ("kdaj ste odprti", ["odprti", "12:00", "15:00"]),
        ("ali imate parking", ["parkiri", "brezpla"]),
        ("imate wifi", ["wifi", "brezpla"]),
        ("kje se nahajate", ["planica", "fram"]),
        ("kakšna je telefonska", ["kontakt", "031", "02"]),
        ("koliko stane večerja", ["25", "večerj"]),
        ("koliko stane nočitev", ["nočitev", "50"]),
        ("kdo je gospodar kmetije", ["gospodar", "marko"]),
        ("lahko božamo zajčke", ["žival", "zaj"]),
        ("lahko jahamo konja", ["jahanje", "ponij"]),
        ("imate traktor", ["traktor"]),
        ("kje je smučišče", ["pohor", "areh", "smuči"]),
        ("kaj pa terme", ["terme", "zreče", "ptuj"]),
        ("kaj če dežuje", ["dež", "terme", "notranje"]),
    ]
    for q, exp in info_cases:
        cases.append(Scenario(f"info_{q[:18]}", [Turn(q, exp, [])]))

    product_cases = [
        "imate kako marmelado",
        "čemažev pesto",
        "imate bunko",
        "imate salamo",
        "imate liker",
        "katalog izdelkov",
        "kje kupim sirup",
    ]
    for q in product_cases:
        cases.append(Scenario(f"product_{q[:16]}", [Turn(q, ["/izdelek/", "€", "trgovin"], [])]))

    menu_cases = [
        "kaj imate za vikend kosilo",
        "pokaži jedilnik",
        "kakšna je vikend ponudba",
    ]
    for q in menu_cases:
        cases.append(Scenario(f"menu_{q[:16]}", [Turn(q, ["meni", "gibanica", "36"], [])]))

    table_booking = [
        "rad bi rezerviral mizo",
        "rezervacija mize",
        "mizo za 5",
        "bi se dalo rezervirat mizo",
        "book a table",
    ]
    for q in table_booking:
        cases.append(Scenario(f"book_table_{q[:12]}", [Turn(q, ["datum", "sobota", "nedelja", "mizo", "date", "saturday", "sunday", "table"], [])]))

    room_booking = [
        "rad bi rezerviral sobo",
        "rezervacija sobe",
        "bi prespali 2 noči",
        "book a room",
        "prenočitev za vikend",
        "sobe za družino",
    ]
    for q in room_booking:
        cases.append(Scenario(f"book_room_{q[:12]}", [Turn(q, ["datum", "sobo", "nočit", "date", "arriv", "room"], [])]))

    typo_cases = [
        "rezrviral bi sobo",
        "rezervriu bi mizo",
        "kje stee",
        "imatte wifi",
        "kaj pp terme",
        "lahko bozamo zajcke",
        "lahko jahamoo",
        "pokazi jedilnk",
        "cemazev pestoo",
        "kolko stane nocitev",
    ]
    typo_expect = [
        ["datum", "sobo", "nočit"],
        ["datum", "mizo", "sobota"],
        ["planica", "fram"],
        ["wifi", "brezpla"],
        ["terme", "zreče", "ptuj"],
        ["žival", "zaj"],
        ["jahan", "ponij"],
        ["meni", "gibanica"],
        ["/izdelek/", "€"],
        ["nočitev", "50"],
    ]
    for i, q in enumerate(typo_cases):
        cases.append(Scenario(f"typo_{i+1}", [Turn(q, typo_expect[i], [])]))

    emotions = [
        ("ful sem jezen ker nič ne dela", ["pomagam", "zanima", "podatk", "rezerv"]),
        ("super ste, hvala", ["hvala", "ni za kaj", "pomagam"]),
        ("zmeden sem", ["pomagam", "zanima", "rezerv"]),
    ]
    for q, exp in emotions:
        cases.append(Scenario(f"emotion_{q[:10]}", [Turn(q, exp, [])]))

    return cases


def multi_turn_cases() -> List[Scenario]:
    cases: List[Scenario] = []

    # Room full flow
    for i in range(70):
        cases.append(
            Scenario(
                f"room_flow_{i+1}",
                [
                    Turn("rad bi rezerviral sobo", ["datum", "sobo"], []),
                    Turn("24.05.2026", ["nočitev", "koliko"], []),
                    Turn("2", ["oseb"], []),
                    Turn("2 odrasla in 2 otroka", ["stari", "otroci", "ime"], []),
                    Turn("6 in 9", ["ime", "priimek"], []),
                ],
            )
        )

    # Table flow with interrupts
    for i in range(70):
        cases.append(
            Scenario(
                f"table_interrupt_{i+1}",
                [
                    Turn("rezerviral bi mizo", ["datum", "sobota"], []),
                    Turn("ali imate parking", ["parkir"], []),
                    Turn("12.04.2026", ["ura"], []),
                    Turn("15:00", ["oseb"], []),
                    Turn("5", ["otrok", "lokacija", "jedilnica"], []),
                ],
            )
        )

    # Topic switching while in flow
    switches = [
        "kakšna vina imate",
        "imate čemažev pesto",
        "kje je smučišče",
        "kaj pa terme",
        "lahko božamo zajčke",
    ]
    for i in range(80):
        q = switches[i % len(switches)]
        cases.append(
            Scenario(
                f"switch_flow_{i+1}",
                [
                    Turn("rad bi rezerviral sobo", ["datum", "sobo"], []),
                    Turn("24.05.2026", ["nočitev", "koliko"], []),
                    Turn("2", ["oseb"], []),
                    Turn(q, ["---", "datum", "oseb", "podatk", "vina", "/izdelek/", "pohor", "terme", "žival"], []),
                ],
            )
        )

    # Hard switches room<->table
    for i in range(60):
        cases.append(
            Scenario(
                f"hard_switch_{i+1}",
                [
                    Turn("rad bi rezerviral sobo", ["datum", "sobo"], []),
                    Turn("raje bi mizo", ["mizo", "sobota", "datum"], []),
                ],
            )
        )

    # Cancel / reset scenarios
    for i in range(50):
        cases.append(
            Scenario(
                f"cancel_reset_{i+1}",
                [
                    Turn("rad bi rezerviral mizo", ["datum", "mizo"], []),
                    Turn("konec", ["prekin", "preklical"], []),
                    Turn("rad bi rezerviral sobo", ["datum", "sobo"], []),
                ],
            )
        )

    return cases


def build_500() -> List[Scenario]:
    scenarios = base_one_turn_cases() + multi_turn_cases()
    # deterministically expand with typo + mood variants to exactly 500
    extras: List[Scenario] = []
    seeds = [
        ("rad bi rezerviral sobo za 3 noči", ["datum", "sobo", "nočit"]),
        ("lahko rezerviram mizo za soboto", ["datum", "sobota", "mizo"]),
        ("kaka vina ponujate", ["vina", "rde", "bela"]),
        ("prodajate bunko", ["/izdelek/", "bunka", "€"]),
        ("kaj lahko delamo če dežuje", ["dež", "terme", "aktiv"]),
    ]
    idx = 0
    while len(scenarios) + len(extras) < 500:
        q, exp = seeds[idx % len(seeds)]
        mood = ["", " prosim", " NUJNO", " :)", " ker sem jezen"][(idx // len(seeds)) % 5]
        extras.append(Scenario(f"extra_{idx+1}", [Turn(q + mood, exp, [])]))
        idx += 1
    scenarios.extend(extras)
    return scenarios[:500]


def main() -> int:
    scenarios = build_500()
    print(f"Running deep test with {len(scenarios)} scenarios...")

    passed = 0
    failed = 0
    failures: list[tuple[str, str]] = []

    for i, sc in enumerate(scenarios, start=1):
        ok, info = run_scenario(i, sc)
        if ok:
            passed += 1
        else:
            failed += 1
            failures.append((sc.name, info))

    print("\n=== SUMMARY ===")
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")

    if failures:
        print("\n=== FAILURES (first 40) ===")
        for name, msg in failures[:40]:
            print(f"- {name}: {msg}")
        return 1

    print("All deep scenarios passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
