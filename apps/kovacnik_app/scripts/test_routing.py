from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Tuple

os.environ.setdefault("USE_UNIFIED_ROUTER", "true")
os.environ.setdefault("STRICT_POLICY", "true")
os.environ.setdefault("DISABLE_INQUIRY", "true")
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
            ("imate čemažev pesto", "/izdelek/"),
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
            ("bi organiziral teambuilding", "info@"),
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
            ("kakšne marmelade imate", "/izdelek/"),
        ],
    ),
    (
        "product_liker",
        [
            ("imate liker", "/izdelek/"),
        ],
    ),
    (
        "booking_room_then_product",
        [
            ("rezerviral bi sobo", "datum"),
            ("imate bučni namaz", "/izdelek/"),
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
            ("katere izdelke prodajate", "/izdelek/"),
        ],
    ),
    (
        "inquiry_poroka",
        [
            ("ali lahko pri vas organiziram poroko", "info@"),
        ],
    ),
    (
        "interrupt_inquiry_with_info",
        [
            ("bi organiziral teambuilding", "info@"),
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
            ("kakšne čaje imate", "/izdelek/"),
        ],
    ),
    (
        "product_mesnine",
        [
            ("imate suho salamo", "/izdelek/"),
        ],
    ),
    (
        "product_bundle",
        [
            ("kakšne darilne pakete imate", "/izdelek/"),
        ],
    ),
    (
        "product_general_link",
        [
            ("kje kupim vaše izdelke", "/izdelek/"),
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
            ("kaj je za večerjo", "Večerja"),
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
            ("imate marmelado", "/izdelek/"),
        ],
    ),
    (
        "inquiry_catering",
        [
            ("potreboval bi catering za dogodek", "info@"),
        ],
    ),
    (
        "inquiry_bulk_order",
        [
            ("rad bi 30 marmelad", "info@"),
        ],
    ),
    (
        "info_smuce",
        [
            ("kje je najbližje smučišče", "Pohorje"),
        ],
    ),
    (
        "info_terme",
        [
            ("katere terme so v bližini", "Terme"),
        ],
    ),
    (
        "info_izleti",
        [
            ("kaj je zanimivo v okolici", "okolici"),
        ],
    ),
    (
        "info_transport",
        [
            ("kako pridem do vas", "Planica"),
        ],
    ),
    (
        "info_kontakt_email",
        [
            ("kakšen je email", "Email"),
        ],
    ),
    (
        "info_kontakt_phone",
        [
            ("kakšna je telefonska številka", "Kontakt"),
        ],
    ),
    (
        "info_checkin",
        [
            ("kdaj je prijava v sobo", "Prijava"),
        ],
    ),
    (
        "info_checkout",
        [
            ("kdaj je odjava", "odjava"),
        ],
    ),
    (
        "info_min_nights_again",
        [
            ("koliko nočitev je minimum", "Minimalno"),
        ],
    ),
    (
        "info_breakfast_included",
        [
            ("ali je zajtrk vključen", "Zajtrk"),
        ],
    ),
    (
        "info_evening_service",
        [
            ("ali imate večerjo", "Večerja"),
        ],
    ),
    (
        "info_menu_weekend",
        [
            ("kaj ponujate za vikend kosila", "Jedilnik"),
        ],
    ),
    (
        "product_caj",
        [
            ("imate čaj", "/izdelek/"),
        ],
    ),
    (
        "product_sirup",
        [
            ("imate sirup", "/izdelek/"),
        ],
    ),
    (
        "product_paket",
        [
            ("kakšni paketi so na voljo", "/izdelek/"),
        ],
    ),
    (
        "product_bunka",
        [
            ("imate pohorsko bunko", "/izdelek/"),
        ],
    ),
    (
        "product_pasteta",
        [
            ("imate jetrno pašteto", "/izdelek/"),
        ],
    ),
    (
        "product_salama",
        [
            ("imate salamo", "/izdelek/"),
        ],
    ),
    (
        "product_liker_repeat",
        [
            ("borovničevi likerji", "/izdelek/"),
        ],
    ),
    (
        "product_gibanica_email",
        [
            ("imate pohorsko gibanico", "info@"),
        ],
    ),
    (
        "booking_room_then_wifi",
        [
            ("rezerviral bi sobo", "datum"),
            ("imate wifi", "Wi"),
        ],
    ),
    (
        "booking_room_then_parking",
        [
            ("rad bi rezerviral sobo", "datum"),
            ("ali imate parking", "Parkirišče"),
        ],
    ),
    (
        "booking_table_then_parking",
        [
            ("rad bi rezerviral mizo", "datum"),
            ("ali imate parking", "Parkirišče"),
        ],
    ),
    (
        "booking_table_then_last_arrival",
        [
            ("rad bi rezerviral mizo", "datum"),
            ("kdaj je zadnji prihod na kosilo", "15:00"),
        ],
    ),
    (
        "switch_topic_command",
        [
            ("zamenjaj temo", "zamenjamo"),
        ],
    ),
    (
        "greeting_then_product",
        [
            ("živjo", "Pozdrav"),
            ("imate čemažev pesto", "/izdelek/"),
        ],
    ),
    (
        "greeting_then_info",
        [
            ("pozdravljeni", "Pozdrav"),
            ("kdaj ste odprti", "Odprti"),
        ],
    ),
    (
        "cancel_reservation",
        [
            ("rad bi rezerviral mizo", "datum"),
            ("ne, pustimo", "prekinil"),
        ],
    ),
    (
        "event_teambuilding_email",
        [
            ("radi bi teambuilding", "info@"),
        ],
    ),
    (
        "event_poroka_email",
        [
            ("ali organizirate poroke", "info@"),
        ],
    ),
    (
        "general_fallback",
        [
            ("kaj mi priporočate", "Trenutno"),
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
