from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Tuple

os.environ.setdefault("USE_UNIFIED_ROUTER", "true")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
import app.services.chat_router as chat_router  # noqa: E402

chat_router.USE_FULL_KB_LLM = False


client = TestClient(app)


Scenario = Tuple[str, List[Tuple[str, str]]]

SCENARIOS: List[Scenario] = [
    (
        "greeting_then_info",
        [
            ("zdravo", "Pozdrav"),
            ("kdaj ste odprti", "Odprti"),
        ],
    ),
    (
        "info_parking",
        [
            ("ali imate parking", "Parkirišče"),
        ],
    ),
    (
        "product_pesto",
        [
            ("imate čemažev pesto", "Trgovina"),
        ],
    ),
    (
        "booking_table_flow",
        [
            ("rad bi rezerviral mizo", "datum"),
            ("15.2.2026", "Ob kateri"),
            ("13:00", "koliko"),
        ],
    ),
    (
        "booking_room_flow",
        [
            ("rad bi rezerviral sobo", "datum"),
            ("12.6.2026", "Koliko nočitev"),
        ],
    ),
    (
        "booking_with_info_interrupt",
        [
            ("rad bi rezerviral mizo", "datum"),
            ("ali imate parking", "Parkirišče"),
        ],
    ),
    (
        "inquiry_teambuilding",
        [
            ("bi organiziral teambuilding", "povpraševanje"),
        ],
    ),
    (
        "info_location",
        [
            ("kje se nahajate", "Planica"),
        ],
    ),
    (
        "info_zajtrk",
        [
            ("kaj je za zajtrk", "Zajtrk"),
        ],
    ),
    (
        "info_vecerja",
        [
            ("koliko stane večerja", "Večerja"),
        ],
    ),
    (
        "menu_request",
        [
            ("kaj imate za kosilo", "Jedilnik"),
        ],
    ),
    (
        "product_marmelada",
        [
            ("kakšne marmelade imate", "marmelad"),
        ],
    ),
    (
        "product_liker",
        [
            ("imate liker", "liker"),
        ],
    ),
    (
        "booking_room_then_product",
        [
            ("rezerviral bi sobo", "datum"),
            ("imate bučni namaz", "Trgovina"),
        ],
    ),
    (
        "booking_table_then_info",
        [
            ("rezerviral bi mizo", "datum"),
            ("kakšna je kapaciteta mize", "Jedilnica"),
        ],
    ),
    (
        "info_wine",
        [
            ("kakšna vina imate", "vina"),
        ],
    ),
    (
        "goodbye",
        [
            ("hvala, adijo", "Adijo"),
        ],
    ),
    (
        "reservation_typo",
        [
            ("rezrviral bi sobo", "datum"),
        ],
    ),
    (
        "general_question",
        [
            ("kaj ponujate", "Jedilnik"),
        ],
    ),
    (
        "info_min_nights",
        [
            ("minimalno nočitev", "Minimalno"),
        ],
    ),
    (
        "info_prijava_odjava",
        [
            ("prijava in odjava", "Prijava"),
        ],
    ),
    (
        "info_placilo",
        [
            ("ali lahko plačam s kartico", "plačil"),
        ],
    ),
    (
        "info_pets",
        [
            ("ali so psi dovoljeni", "ljubljen"),
        ],
    ),
    (
        "info_klima",
        [
            ("imate klimo", "klimat"),
        ],
    ),
    (
        "info_wifi",
        [
            ("imate wifi", "Wi"),
        ],
    ),
    (
        "info_contact",
        [
            ("kakšna je telefonska", "Kontakt"),
        ],
    ),
    (
        "product_general",
        [
            ("katere izdelke prodajate", "izdelke"),
        ],
    ),
    (
        "inquiry_poroka",
        [
            ("ali lahko pri vas organiziram poroko", "povpraševanje"),
        ],
    ),
    (
        "interrupt_inquiry_with_info",
        [
            ("bi organiziral teambuilding", "povpraševanje"),
            ("kdaj ste odprti", "Odprti"),
        ],
    ),
    (
        "booking_room_then_cancel",
        [
            ("rad bi rezerviral sobo", "datum"),
            ("ne, pustimo", "prekinil"),
        ],
    ),
    (
        "booking_table_then_cancel",
        [
            ("rad bi rezerviral mizo", "datum"),
            ("ne", "prekinil"),
        ],
    ),
    (
        "info_hours_monday",
        [
            ("ali ste odprti ob ponedeljkih", "ponedel"),
        ],
    ),
    (
        "info_last_arrival",
        [
            ("kdaj je zadnji prihod na kosilo", "15:00"),
        ],
    ),
    (
        "info_breakfast_included",
        [
            ("ali je zajtrk vključen", "vključen"),
        ],
    ),
    (
        "info_dinner_price",
        [
            ("koliko stane večerja", "25"),
        ],
    ),
    (
        "info_min_nights_summer",
        [
            ("kakšno je minimalno število nočitev poleti", "Minimalno"),
        ],
    ),
    (
        "info_checkin_checkout",
        [
            ("kdaj je prijava in odjava", "Prijava"),
        ],
    ),
    (
        "info_wifi",
        [
            ("ali imate wifi", "Wi"),
        ],
    ),
    (
        "info_ac",
        [
            ("imate klimo v sobah", "klimat"),
        ],
    ),
    (
        "info_payment",
        [
            ("ali lahko plačam s kartico", "plačil"),
        ],
    ),
    (
        "info_pets",
        [
            ("ali so hišni ljubljenčki dovoljeni", "ljubljen"),
        ],
    ),
    (
        "info_capacity",
        [
            ("kakšna je kapaciteta jedilnice", "Jedilnica"),
        ],
    ),
    (
        "info_contact_email",
        [
            ("kakšen je vaš kontakt", "Kontakt"),
        ],
    ),
    (
        "info_family",
        [
            ("kdo ste vi in družina", "druž"),
        ],
    ),
    (
        "info_farm",
        [
            ("povej kaj o kmetiji", "kmetij"),
        ],
    ),
    (
        "info_gibanica",
        [
            ("kaj je pohorska gibanica", "gibanica"),
        ],
    ),
    (
        "product_namaz",
        [
            ("kakšne namaze imate", "namaz"),
        ],
    ),
    (
        "product_pasteta",
        [
            ("imate jetrno pašteto", "pašt"),
        ],
    ),
    (
        "product_sirup",
        [
            ("ali prodajate sirup", "sirup"),
        ],
    ),
    (
        "product_caj",
        [
            ("kakšne čaje imate", "čaj"),
        ],
    ),
    (
        "product_mesnine",
        [
            ("imate suho salamo", "sal"),
        ],
    ),
    (
        "product_bundle",
        [
            ("kakšne darilne pakete imate", "paket"),
        ],
    ),
    (
        "product_general_link",
        [
            ("kje kupim vaše izdelke", "katalog"),
        ],
    ),
    (
        "info_menu_weekend",
        [
            ("kaj ponujate za vikend kosila", "Jedilnik"),
        ],
    ),
    (
        "menu_dinner",
        [
            ("kaj je za večerjo", "Jedilnik"),
        ],
    ),
    (
        "booking_room_then_info",
        [
            ("rad bi rezerviral sobo", "datum"),
            ("ali imate wifi", "Wi"),
        ],
    ),
    (
        "booking_table_then_product",
        [
            ("rad bi rezerviral mizo", "datum"),
            ("imate marmelado", "marmelad"),
        ],
    ),
    (
        "inquiry_catering",
        [
            ("potreboval bi catering za dogodek", "povpraševanje"),
        ],
    ),
    (
        "inquiry_bulk_order",
        [
            ("rad bi 30 marmelad", "povpraševanje"),
        ],
    ),
    (
        "general_fallback",
        [
            ("kaj mi priporočate", "Kako"),
        ],
    ),
]


def run_scenario(name: str, turns: List[Tuple[str, str]], idx: int) -> List[str]:
    failures = []
    session_id = f"test_{idx}_{name}"
    for msg, expected in turns:
        resp = client.post("/chat", json={"message": msg, "session_id": session_id})
        if resp.status_code != 200:
            failures.append(f"{name}: HTTP {resp.status_code} on '{msg}'")
            continue
        reply = resp.json().get("reply", "")
        if expected and expected.lower() not in reply.lower():
            failures.append(f"{name}: expected '{expected}' in reply to '{msg}'\nReply: {reply}")
    return failures


def main() -> None:
    all_failures: List[str] = []
    for idx, (name, turns) in enumerate(SCENARIOS, start=1):
        all_failures.extend(run_scenario(name, turns, idx))

    if all_failures:
        print("\nFAILURES:")
        for fail in all_failures:
            print("-", fail)
        raise SystemExit(1)

    print("All scenarios passed.")


if __name__ == "__main__":
    main()
