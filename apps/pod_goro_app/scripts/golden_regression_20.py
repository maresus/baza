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
class Step:
    message: str
    any_of: List[str]
    none_of: List[str]


@dataclass
class Case:
    name: str
    steps: List[Step]


def _n(txt: str) -> str:
    return re.sub(r"\s+", " ", txt.lower().strip())


def _contains_any(reply: str, keywords: List[str]) -> bool:
    n = _n(reply)
    return any(_n(k) in n for k in keywords)


def build_cases() -> List[Case]:
    return [
        Case(
            "marmelada_format",
            [
                Step(
                    "rad bi kupil marmelado",
                    any_of=["Seveda, tukaj je nekaj izdelkov", "Povezava:", "Celotna trgovina"],
                    none_of=["Trenutno nimam podatkov"],
                )
            ],
        ),
        Case(
            "room_info_not_booking",
            [
                Step(
                    "koliko sob imate?",
                    any_of=["Imamo **3 sobe**", "ALJAŽ", "JULIJA", "ANA"],
                    none_of=["Za kateri datum prihoda", "z veseljem uredim rezervacijo"],
                )
            ],
        ),
        Case(
            "sir_not_random_package",
            [
                Step(
                    "sir?",
                    any_of=["Tega izdelka ni v spletni trgovini", "Pišite na"],
                    none_of=["Jakobev paket", "Anin paket"],
                )
            ],
        ),
        Case(
            "snops_maps_to_liker",
            [
                Step(
                    "lahko pri vas kupim snops?",
                    any_of=["liker", "Tepkovec", "Povezava:"],
                    none_of=["Trenutno nimam podatkov"],
                )
            ],
        ),
        Case(
            "animals_krave",
            [Step("imate krave?", any_of=["goveji", "čredi", "živali"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "animals_koze",
            [Step("imate koze?", any_of=["živali", "čredi", "kmetiji"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "rain_with_kids",
            [Step("kaj ce dezuje pa smo z otroki", any_of=["Če dežuje", "terme", "aktivnosti"], none_of=[])],
        ),
        Case(
            "theme_switch_inside_booking",
            [
                Step("rad bi rezerviral sobo", any_of=["Za kateri datum prihoda"], none_of=[]),
                Step("kaka vina ponujate", any_of=["---", "vino", "Prosim"], none_of=["Trenutno nimam podatkov"]),
            ],
        ),
        Case(
            "theme_switch_inside_booking_2",
            [
                Step("rad bi rezerviral sobo", any_of=["Za kateri datum prihoda"], none_of=[]),
                Step("lahko božamo zajčke", any_of=["---", "živali", "Prosim"], none_of=["Trenutno nimam podatkov"]),
            ],
        ),
        Case(
            "table_flow_keeps_state",
            [
                Step("lahko rezerviram mizo za soboto", any_of=["Za kateri datum"], none_of=[]),
                Step("12.4.2026", any_of=["Katera **ura**", "Katera ura"], none_of=[]),
                Step("15:00", any_of=["koliko oseb", "Za koliko oseb"], none_of=[]),
                Step("8 oseb", any_of=["Imate otroke", "Lokacija", "ime in priimek"], none_of=["Za kateri datum"]),
            ],
        ),
        Case(
            "greeting",
            [Step("/start", any_of=["Pozdravljeni", "Lahko pomagam"], none_of=[])],
        ),
        Case(
            "owner",
            [Step("kdo je gospodar kmetije", any_of=["Gospodar kmetije je Marko"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "wifi",
            [Step("imate wifi", any_of=["Wi-Fi", "brezplačen"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "parking",
            [Step("imate parkirišče", any_of=["Parkirišče", "brezplačno"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "weekend_lunch",
            [Step("kaj imate za vikend kosilo", any_of=["AKTUALNI SEZONSKI MENI", "Kosila ob sobotah", "CENA po ODRASLI osebi"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "menu_view",
            [Step("pokaži jedilnik za ta vikend", any_of=["AKTUALNI SEZONSKI MENI", "CENA po ODRASLI osebi"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "tractor",
            [Step("kaki traktor imate?", any_of=["traktor", "mehanizacijo"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "riding",
            [Step("lahko jahamo konja", any_of=["Jahanje", "po dogovoru"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "family",
            [Step("imate kake otroke", any_of=["družinska", "domačija", "otroke"], none_of=["Trenutno nimam podatkov"])],
        ),
        Case(
            "no_hard_fallback_basic",
            [Step("lahko igramo nogomet?", any_of=["Trenutno nimam podatkov", "okolici", "izlete"], none_of=["Traceback"])],
        ),
    ]


def main() -> int:
    client = TestClient(app)
    cases = build_cases()
    passed = 0
    failed = 0

    for i, case in enumerate(cases, start=1):
        sid = f"golden20_{i}"
        ok = True
        reason = ""
        for j, step in enumerate(case.steps, start=1):
            resp = client.post("/chat/", json={"message": step.message, "session_id": sid})
            if resp.status_code != 200:
                ok = False
                reason = f"HTTP {resp.status_code} step {j}"
                break
            reply = (resp.json().get("reply") or "").strip()
            if step.any_of and not _contains_any(reply, step.any_of):
                ok = False
                reason = f"missing expected step {j} reply={reply[:200]}"
                break
            if step.none_of and _contains_any(reply, step.none_of):
                ok = False
                reason = f"contains forbidden step {j} reply={reply[:200]}"
                break
        if ok:
            passed += 1
            print(f"[PASS] {case.name}")
        else:
            failed += 1
            print(f"[FAIL] {case.name}: {reason}")

    print(f"\nSUMMARY: {passed}/{len(cases)} PASS, {failed} FAIL")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
