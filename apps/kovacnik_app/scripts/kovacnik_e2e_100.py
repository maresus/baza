#!/usr/bin/env python3
"""
End-to-end dialog tests (100 scenarios) against /chat endpoint.
Run:
  python scripts/kovacnik_e2e_100.py --start-server
or
  python scripts/kovacnik_e2e_100.py --base-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def expect_contains(reply: str, expected: list[str]) -> bool:
    reply_l = reply.lower()
    return all(e.lower() in reply_l for e in expected)


def run_scenarios(base_url: str) -> int:
    scenarios = [
        # existing 50
        ("s1", [("Rad bi rezerviral mizo.", ["datum"]), ("Ali imate parking?", ["parkiri"]), ("15.2.2026", ["ura"]) ]),
        ("s2", [("Rad bi rezerviral sobo.", ["datum"]), ("Lahko organiziramo teambuilding?", ["povpraševanje", "do kdaj"]) ]),
        ("s3", [("Rad bi rezerviral mizo.", ["datum"]), ("Raje sobo.", ["datum"]) ]),
        ("s4", [("Rad bi rezerviral sobo.", ["datum"]), ("Imate čemažev pesto?", ["pesto"]) ]),
        ("s5", [("Rad bi rezerviral sobo.", ["datum"]), ("Katera rdeča vina imate?", ["vina"]) ]),
        ("s6", [("Rad bi rezerviral mizo.", ["datum"]), ("Kaj ponujate za kosilo?", ["jedilnik"]) ]),
        ("s7", [("Kdaj ste odprti?", ["odprti"]), ("Rad bi rezerviral mizo.", ["datum"]) ]),
        ("s8", [("Kje se nahajate?", ["planica"]), ("Imate namaze?", ["namaz"]) ]),
        ("s9", [("Imate marmelade?", ["marmelad"]), ("Rad bi mizo.", ["datum"]) ]),
        ("s10", [("Mizo bi rezerviral.", ["datum"]), ("Ne, pustimo.", ["preklical"]) ]),
        ("s11", [("Sobo bi rezerviral.", ["datum"]), ("Ne bom.", ["preklical"]) ]),
        ("s12", [("Rad bi sobo.", ["datum"]), ("Kakšne sobe imate?", ["sobe"]) ]),
        ("s13", [("Rezervacija sobe.", ["datum"]), ("Kdaj lahko pridemo?", ["prijava", "odjava"]) ]),
        ("s14", [("Soba.", ["datum"]), ("Kako pridem do vas?", ["planica"]) ]),
        ("s15", [("Miza.", ["datum"]), ("21.3.2026", ["ura"]), ("14:00", ["oseb"]) ]),
        ("s16", [("Soba.", ["datum"]), ("10.5.2026", ["nočitv"]), ("2", ["oseb"]) ]),
        ("s17", [("Soba.", ["datum"]), ("Ali je zajtrk vključen?", ["zajtrk"]) ]),
        ("s18", [("Miza.", ["datum"]), ("Rad bi kupil sirup.", ["sirup"]) ]),
        ("s19", [("Ali organizirate poroke?", ["povpraševanje", "do kdaj"]) ]),
        ("s20", [("Poroka.", ["povpraševanje"]), ("Ne, nič.", ["prekinil", "preklical"]) ]),
        ("s21", [("Teambuilding.", ["povpraševanje"]), ("Kdaj ste odprti?", ["odprti"]) ]),
        ("s22", [("Miza.", ["datum"]), ("Kaj ponujate?", ["jedilnik"]), ("Ok.", ["datum"]) ]),
        ("s23", [("Soba.", ["datum"]), ("Imate wifi?", ["wi-fi", "wifi"]), ("12.6.2026", ["nočitv"]) ]),
        ("s24", [("Miza.", ["datum"]), ("Je kje smučišče?", ["pohorje"]) ]),
        ("s25", [("Kako deluje rezervacija?", ["datum", "rezerv"]) ]),
        ("s26", [("Da.", ["kaj", "točno"]) ]),
        ("s27", [("Imate pesto?", ["pesto", "namaz"]), ("Ja.", ["katalog", "trgovina"]) ]),
        ("s28", [("Miza.", ["datum"]), ("Ja.", ["datum"]) ]),
        ("s29", [("Miza.", ["datum"]), ("Ne.", ["preklical", "prekinil"]) ]),
        ("s30", [("Rad bi rezerviral mizo za 4 in kupil marmelado.", ["marmelad", "datum"]) ]),
        ("s31", [("Kakšne sobe imate?", ["sobe"]) ]),
        ("s32", [("Kako pridem do vas?", ["fram", "izvoz"]) ]),
        ("s33", [("Koliko stane soba?", ["cenik", "soba"]) ]),
        ("s34", [("Koliko stane kosilo?", ["kosilo"]) ]),
        ("s35", [("Delovni čas?", ["odprti"]) ]),
        ("s36", [("Ali ste odprti ob ponedeljkih?", ["ponedeljk"]) ]),
        ("s37", [("Je kje smučišče?", ["pohorje"]), ("Areh", ["areh"]) ]),
        ("s38", [("Katere terme so blizu?", ["terme"]) ]),
        ("s39", [("Teambuilding.", ["povpraševanje"]), ("Rad bi mizo.", ["datum"]) ]),
        ("s40", [("Poroka.", ["povpraševanje"]), ("Sobo bi.", ["datum"]) ]),
        ("s41", [("Miza.", ["datum"]), ("Stop.", ["preklical", "prekinil"]) ]),
        ("s42", [("Miza.", ["datum"]), ("Konec.", ["preklical", "prekinil"]) ]),
        ("s43", [("Soba.", ["datum"]), ("12.2.2024", ["nočitv"]) ]),
        ("s44", [("Miza.", ["datum"]), ("12.2.2024", ["prihodnosti"]) ]),
        ("s45", [("Soba.", ["datum"]), ("13.4.2026", ["nočitv"]) ]),
        ("s46", [("Miza.", ["datum"]), ("22.2.2026", ["ura"]), ("21:30", ["zadnji prihod"]) ]),
        ("s47", [("Miza 21.2.2026 ob 13:00 za 4.", ["kontakt", "ime"]) ]),
        ("s48", [("Soba 12.6.2026, 3 nočitve, 4 osebe.", ["kontakt", "ime"]) ]),
        ("s49", [("Kje ste?", ["planica"]), ("Imate pesto?", ["pesto"]), ("Miza.", ["datum"]) ]),
        ("s50", [("Kdaj ste odprti?", ["odprti"]), ("Miza.", ["datum"]), ("Ali imate parking?", ["parkiri"]), ("15.2.2026", ["ura"]) ]),
        # +50 additional
        ("s51", [("Imate konje?", ["konj"]) ]),
        ("s52", [("Kdo je gospodar kmetije?", ["gospodar"]) ]),
        ("s53", [("Ali imate traktor?", ["traktor"]) ]),
        ("s54", [("Zadnja ura za prihod?", ["zadnji", "15:00"]) ]),
        ("s55", [("Rezerviral bi mizo.", ["datum"]), ("Imate čemažev pesto?", ["pesto"]), ("15.2.2026", ["ura"]) ]),
        ("s56", [("Rad bi sobo.", ["datum"]), ("Imate živali?", ["živali"]) ]),
        ("s57", [("Soba.", ["datum"]), ("13.5.2026", ["nočitv"]), ("3", ["oseb"]), ("Ne.", ["preklical", "prekinil"]) ]),
        ("s58", [("Miza.", ["datum"]), ("10.5.2026", ["ura"]), ("12:00", ["oseb"]), ("4", ["otrok"]) ]),
        ("s59", [("Ali imate peneča vina?", ["vina"]) ]),
        ("s60", [("Kaj je za vikend kosila?", ["jedilnik"]) ]),
        ("s61", [("Kje kupim izdelke?", ["trgovina"]) ]),
        ("s62", [("Ali pošiljate po pošti?", ["trgovina"]) ]),
        ("s63", [("Miza.", ["datum"]), ("A imate parking?", ["parkiri"]), ("21.2.2026", ["ura"]) ]),
        ("s64", [("Soba.", ["datum"]), ("15.4.2026", ["nočitv"]), ("2", ["oseb"]) ]),
        ("s65", [("Soba.", ["datum"]), ("15.4.2026", ["nočitv"]), ("2 nočitvi", ["oseb"]) ]),
        ("s66", [("Soba.", ["datum"]), ("15.4.2026", ["nočitv"]), ("2", ["oseb"]), ("2 osebi", ["ime"]) ]),
        ("s67", [("Miza 15.2.2026 ob 13:00 za 2.", ["kontakt"]) ]),
        ("s68", [("Je blizu smučišče?", ["pohorje"]) ]),
        ("s69", [("Areh", ["areh"]) ]),
        ("s70", [("Kje so terme?", ["terme"]) ]),
        ("s71", [("Koliko sob imate?", ["sobe"]) ]),
        ("s72", [("Ali imate wifi?", ["wifi"]) ]),
        ("s73", [("Ali imate klimo?", ["klim"]) ]),
        ("s74", [("Kako do vas?", ["fram"]) ]),
        ("s75", [("Delovni čas", ["odprti"]) ]),
        ("s76", [("Ali lahko rezerviram mizo za 10?", ["datum"]) ]),
        ("s77", [("Rad bi rezerviral sobo za 4 nočitve.", ["datum"]) ]),
        ("s78", [("Rad bi mizo za nedeljo.", ["datum"]) ]),
        ("s79", [("Imate marmelade?", ["marmelad"]) ]),
        ("s80", [("Imate namaze?", ["namaz"]) ]),
        ("s81", [("Imate sirupe?", ["sirup"]) ]),
        ("s82", [("Imate bučni namaz?", ["namaz"]) ]),
        ("s83", [("Miza.", ["datum"]), ("15.2.2026", ["ura"]), ("13:00", ["oseb"]), ("4", ["otrok"]) ]),
        ("s84", [("Soba.", ["datum"]), ("15.4.2026", ["nočitv"]), ("2", ["oseb"]), ("2 osebi", ["ime"]) ]),
        ("s85", [("Kakšna je cena večerje?", ["večerj"]) ]),
        ("s86", [("Kakšna je cena kosila?", ["kosilo"]) ]),
        ("s87", [("Kdaj je check-in?", ["prijava"]) ]),
        ("s88", [("Kdaj je check-out?", ["odjava"]) ]),
        ("s89", [("Imate darilne bone?", ["bon"]) ]),
        ("s90", [("Ali lahko pridem s psom?", ["ljubljenčki", "dog", "hišni", "živali"]) ]),
        ("s91", [("Rad bi rezerviral sobo.", ["datum"]), ("Imate smučišče?", ["pohorje"]) ]),
        ("s92", [("Rad bi rezerviral mizo.", ["datum"]), ("Imate pesto?", ["pesto"]), ("Ja.", ["trgovina"]) ]),
        ("s93", [("Miza.", ["datum"]), ("12.2.2024", ["prihodnosti"]), ("15.2.2026", ["ura"]) ]),
        ("s94", [("Soba.", ["datum"]), ("12.2.2024", ["nočitv"]), ("15.4.2026", ["nočitv"]) ]),
        ("s95", [("Kakšna je lokacija?", ["planica"]) ]),
        ("s96", [("Kontakt?", ["kontakt"]) ]),
        ("s97", [("Miza.", ["datum"]), ("15.2.2026", ["ura"]), ("14:00", ["oseb"]), ("4", ["otrok"]), ("ne", ["ime"]) ]),
        ("s98", [("Soba.", ["datum"]), ("15.4.2026", ["nočitv"]), ("2", ["oseb"]), ("2", ["ime"]) ]),
        ("s99", [("Ali ste odprti ob torkih?", ["tork"]) ]),
        ("s100", [("Ali imate parkirišče?", ["parkiri"]) ]),
    ]

    failures = 0
    for scenario_id, steps in scenarios:
        session_id = f"e2e-{scenario_id}"
        for msg, expected in steps:
            payload = {"session_id": session_id, "message": msg}
            resp = post_json(f"{base_url}/chat", payload)
            reply = resp.get("reply") or resp.get("message") or resp.get("raw", "")
            if not expect_contains(reply, expected):
                failures += 1
                print(f"FAIL {scenario_id} | {msg}")
                print(f"  reply: {reply}")
                print(f"  expected contains: {expected}")
                break
    print(f"\nFailures: {failures}")
    return 0 if failures == 0 else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--start-server", action="store_true")
    args = parser.parse_args()

    proc = None
    if args.start_server:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        for _ in range(30):
            try:
                urllib.request.urlopen(f"{args.base_url}/", timeout=1)
                break
            except Exception:
                time.sleep(0.5)

    try:
        return run_scenarios(args.base_url)
    finally:
        if proc:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
