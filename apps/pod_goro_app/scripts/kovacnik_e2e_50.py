#!/usr/bin/env python3
"""
End-to-end dialog tests (50 scenarios) against /chat endpoint.
Run:
  python scripts/kovacnik_e2e_50.py --start-server
or
  python scripts/kovacnik_e2e_50.py --base-url http://127.0.0.1:8000
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
        # 1) table -> info -> back
        ("s1", [
            ("Rad bi rezerviral mizo.", ["datum"]),
            ("Ali imate parking?", ["parkiri"]),
            ("15.2.2026", ["ura"]),
        ]),
        # 2) room -> teambuilding hard switch
        ("s2", [
            ("Rad bi rezerviral sobo.", ["datum"]),
            ("Lahko organiziramo teambuilding?", ["povpraševanje", "do kdaj"]),
        ]),
        # 3) table -> room hard switch
        ("s3", [
            ("Rad bi rezerviral mizo.", ["datum"]),
            ("Raje sobo.", ["datum"]),
        ]),
        # 4) room -> product soft interrupt
        ("s4", [
            ("Rad bi rezerviral sobo.", ["datum"]),
            ("Imate čemažev pesto?", ["pesto"]),
        ]),
        # 5) room -> wine soft interrupt
        ("s5", [
            ("Rad bi rezerviral sobo.", ["datum"]),
            ("Katera rdeča vina imate?", ["vina"]),
        ]),
        # 6) table -> menu soft interrupt
        ("s6", [
            ("Rad bi rezerviral mizo.", ["datum"]),
            ("Kaj ponujate za kosilo?", ["jedilnik"]),
        ]),
        # 7) info -> booking
        ("s7", [
            ("Kdaj ste odprti?", ["odprti"]),
            ("Rad bi rezerviral mizo.", ["datum"]),
        ]),
        # 8) info -> product
        ("s8", [
            ("Kje se nahajate?", ["planica"]),
            ("Imate namaze?", ["namaz"]),
        ]),
        # 9) product -> table
        ("s9", [
            ("Imate marmelade?", ["marmelad"]),
            ("Rad bi mizo.", ["datum"]),
        ]),
        # 10) table cancel
        ("s10", [
            ("Mizo bi rezerviral.", ["datum"]),
            ("Ne, pustimo.", ["preklical"]),
        ]),
        # 11) room cancel
        ("s11", [
            ("Sobo bi rezerviral.", ["datum"]),
            ("Ne bom.", ["preklical"]),
        ]),
        # 12) room -> info about rooms
        ("s12", [
            ("Rad bi sobo.", ["datum"]),
            ("Kakšne sobe imate?", ["sobe"]),
        ]),
        # 13) room -> check-in time
        ("s13", [
            ("Rezervacija sobe.", ["datum"]),
            ("Kdaj lahko pridemo?", ["prijava", "odjava"]),
        ]),
        # 14) room -> directions
        ("s14", [
            ("Soba.", ["datum"]),
            ("Kako pridem do vas?", ["planica"]),
        ]),
        # 15) table full flow partial
        ("s15", [
            ("Miza.", ["datum"]),
            ("21.3.2026", ["ura"]),
            ("14:00", ["oseb"]),
        ]),
        # 16) room flow partial
        ("s16", [
            ("Soba.", ["datum"]),
            ("10.5.2026", ["nočitev"]),
            ("2", ["oseb"]),
        ]),
        # 17) room -> breakfast
        ("s17", [
            ("Soba.", ["datum"]),
            ("Ali je zajtrk vključen?", ["zajtrk"]),
        ]),
        # 18) table -> buy
        ("s18", [
            ("Miza.", ["datum"]),
            ("Rad bi kupil sirup.", ["sirup"]),
        ]),
        # 19) inquiry wedding
        ("s19", [
            ("Ali organizirate poroke?", ["povpraševanje", "do kdaj"]),
        ]),
        # 20) inquiry cancel
        ("s20", [
            ("Poroka.", ["povpraševanje"]),
            ("Ne, nič.", ["prekinil", "preklical"]),
        ]),
        # 21) inquiry -> info
        ("s21", [
            ("Teambuilding.", ["povpraševanje"]),
            ("Kdaj ste odprti?", ["odprti"]),
        ]),
        # 22) menu then ok
        ("s22", [
            ("Miza.", ["datum"]),
            ("Kaj ponujate?", ["jedilnik"]),
            ("Ok.", ["datum"]),
        ]),
        # 23) room -> wifi -> date
        ("s23", [
            ("Soba.", ["datum"]),
            ("Imate wifi?", ["wi-fi", "wifi"]),
            ("12.6.2026", ["nočitev"]),
        ]),
        # 24) table -> ski
        ("s24", [
            ("Miza.", ["datum"]),
            ("Je kje smučišče?", ["pohorje"]),
        ]),
        # 25) info only about reservation process
        ("s25", [
            ("Kako deluje rezervacija?", ["datum", "rezerv"]),
        ]),
        # 26) bare yes
        ("s26", [
            ("Da.", ["kaj", "točno"]),
        ]),
        # 27) product -> yes
        ("s27", [
            ("Imate pesto?", ["pesto", "namaz"]),
            ("Ja.", ["katalog", "trgovina"]),
        ]),
        # 28) booking -> yes
        ("s28", [
            ("Miza.", ["datum"]),
            ("Ja.", ["datum"]),
        ]),
        # 29) booking -> no
        ("s29", [
            ("Miza.", ["datum"]),
            ("Ne.", ["preklical", "prekinil"]),
        ]),
        # 30) mixed intent
        ("s30", [
            ("Rad bi rezerviral mizo za 4 in kupil marmelado.", ["marmelad", "datum"]),
        ]),
        # 31) rooms info no booking
        ("s31", [
            ("Kakšne sobe imate?", ["sobe"]),
        ]),
        # 32) directions no booking
        ("s32", [
            ("Kako pridem do vas?", ["fram", "izvoz"]),
        ]),
        # 33) room price
        ("s33", [
            ("Koliko stane soba?", ["cenik", "soba"]),
        ]),
        # 34) lunch price
        ("s34", [
            ("Koliko stane kosilo?", ["kosilo"]),
        ]),
        # 35) working hours
        ("s35", [
            ("Delovni čas?", ["odprti"]),
        ]),
        # 36) monday open
        ("s36", [
            ("Ali ste odprti ob ponedeljkih?", ["ponedeljk"]),
        ]),
        # 37) ski areh
        ("s37", [
            ("Je kje smučišče?", ["pohorje"]),
            ("Areh", ["areh"]),
        ]),
        # 38) terme
        ("s38", [
            ("Katere terme so blizu?", ["terme"]),
        ]),
        # 39) inquiry -> table
        ("s39", [
            ("Teambuilding.", ["povpraševanje"]),
            ("Rad bi mizo.", ["datum"]),
        ]),
        # 40) inquiry -> room
        ("s40", [
            ("Poroka.", ["povpraševanje"]),
            ("Sobo bi.", ["datum"]),
        ]),
        # 41) stop
        ("s41", [
            ("Miza.", ["datum"]),
            ("Stop.", ["preklical", "prekinil"]),
        ]),
        # 42) konec
        ("s42", [
            ("Miza.", ["datum"]),
            ("Konec.", ["preklical", "prekinil"]),
        ]),
        # 43) past date room
        ("s43", [
            ("Soba.", ["datum"]),
            ("12.2.2024", ["nočitv"]),
        ]),
        # 44) past date table
        ("s44", [
            ("Miza.", ["datum"]),
            ("12.2.2024", ["prihodnosti"]),
        ]),
        # 45) min nights
        ("s45", [
            ("Soba.", ["datum"]),
            ("13.4.2026", ["nočitv"]),
        ]),
        # 46) late hour
        ("s46", [
            ("Miza.", ["datum"]),
            ("22.2.2026", ["ura"]),
            ("21:30", ["zadnji prihod"]),
        ]),
        # 47) table all-in-one
        ("s47", [
            ("Miza 21.2.2026 ob 13:00 za 4.", ["kontakt", "ime"]),
        ]),
        # 48) room all-in-one
        ("s48", [
            ("Soba 12.6.2026, 3 nočitve, 4 osebe.", ["kontakt", "ime"]),
        ]),
        # 49) info -> product -> table
        ("s49", [
            ("Kje ste?", ["planica"]),
            ("Imate pesto?", ["pesto"]),
            ("Miza.", ["datum"]),
        ]),
        # 50) info -> booking -> info -> booking
        ("s50", [
            ("Kdaj ste odprti?", ["odprti"]),
            ("Miza.", ["datum"]),
            ("Ali imate parking?", ["parkiri"]),
            ("15.2.2026", ["ura"]),
        ]),
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
        # wait for server to accept connections
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
