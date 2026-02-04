from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple, Union

Turn = Tuple[str, Union[str, List[str]]]
Scenario = Tuple[str, List[Turn]]


def _next_weekday(start: datetime, target_weekday: int) -> datetime:
    d = start
    for _ in range(14):
        if d.weekday() == target_weekday:
            return d
        d += timedelta(days=1)
    return start


def _next_weekend_date() -> str:
    today = datetime.now()
    saturday = _next_weekday(today, 5)  # 5 = Saturday
    return saturday.strftime("%d.%m.%Y")


def _next_weekday_date() -> str:
    today = datetime.now()
    wednesday = _next_weekday(today, 2)  # 2 = Wednesday
    return wednesday.strftime("%d.%m.%Y")


def build_scenarios(
    base_url: str,
    location_token: str,
    email_token: str,
    include_booking: bool = True,
) -> List[Scenario]:
    product_link = f"{base_url}/izdelek/"

    single_turn: List[Scenario] = [
        ("info_hours", [("kdaj ste odprti", "Odprti")]),
        ("info_monday", [("ali ste odprti ob ponedeljkih", "ponedel")]),
        ("info_last_arrival", [("kdaj je zadnji prihod na kosilo", "15:00")]),
        ("info_location", [("kje se nahajate", location_token)]),
        ("info_parking", [("ali imate parking", "Parkiri")]),
        ("info_wifi", [("imate wifi", "Wi")]),
        ("info_checkin", [("kdaj je prijava", "Prijava")]),
        ("info_checkout", [("kdaj je odjava", "odjava")]),
        ("info_min_nights", [("minimalno nočitev", "Minimalno")]),
        ("info_breakfast", [("ali je zajtrk vključen", "Zajtrk")]),
        ("info_dinner", [("ali imate večerjo", "Večerja")]),
        ("info_allergies", [("ali imate veganske možnosti", "alerg")]),
        ("info_contact_phone", [("kakšna je telefonska", "Kontakt")]),
        ("info_contact_email", [("kakšen je email", "Email")]),
        ("info_smuce", [("kje je najbližje smučišče", "Pohorje")]),
        ("info_terme", [("katere terme so v bližini", "Terme")]),
        ("info_turizem", [("kaj je zanimivo v okolici", "okolici")]),
        ("info_transport", [("kako pridem do vas", location_token)]),
        ("info_rooms", [("koliko sob imate", "sobe")]),
        ("info_table_capacity", [("kakšna je kapaciteta mize", "Jedilnic")]),
        ("product_pesto", [("imate čemažev pesto", product_link)]),
        ("product_marmelada", [("kakšne marmelade imate", product_link)]),
        ("product_liker", [("imate liker", product_link)]),
        ("product_bunka", [("imate pohorsko bunko", product_link)]),
        ("product_pasteta", [("imate jetrno pašteto", product_link)]),
        ("product_salama", [("imate salamo", product_link)]),
        ("product_caj", [("imate čaj", product_link)]),
        ("product_sirup", [("imate sirup", product_link)]),
        ("product_paket", [("kakšni paketi so na voljo", product_link)]),
        ("product_general", [("katere izdelke prodajate", product_link)]),
        ("product_buy", [("kje kupim vaše izdelke", product_link)]),
        ("product_gibanica", [("imate pohorsko gibanico", "info@")]),
        ("bulk_order", [("rad bi 30 marmelad", "info@")]),
        ("event_teambuilding", [("bi organiziral teambuilding", "info@")]),
        ("event_poroka", [("ali organizirate poroke", "info@")]),
    ]

    booking: List[Scenario] = []
    if include_booking:
        table_date = _next_weekend_date()
        room_date = _next_weekday_date()
        booking = [
            (
                "booking_table_flow",
                [
                    ("rad bi rezerviral mizo", "datum"),
                    (table_date, "ur"),
                    ("12:30", "oseb"),
                ],
            ),
            (
                "booking_room_flow",
                [
                    ("rad bi rezerviral sobo", "datum"),
                    (room_date, "nočitev"),
                    ("2", "oseb"),
                ],
            ),
            (
                "booking_table_interrupt_info",
                [
                    ("rezerviral bi mizo", "datum"),
                    ("ali imate parking", "Parkiri"),
                ],
            ),
            (
                "booking_room_interrupt_product",
                [
                    ("rezerviral bi sobo", "datum"),
                    ("imate marmelado", product_link),
                ],
            ),
            (
                "booking_switch_room_to_table",
                [
                    ("rad bi rezerviral sobo", "datum"),
                    ("raje bi mizo", "datum"),
                ],
            ),
            (
                "booking_switch_table_to_room",
                [
                    ("rad bi rezerviral mizo", "datum"),
                    ("raje bi sobo", "datum"),
                ],
            ),
                (
                    "booking_cancel",
                    [
                        ("rad bi rezerviral mizo", "datum"),
                        ("ne, pustimo", "preklical"),
                    ],
                ),
            (
                "booking_info_last_arrival",
                [
                    ("rad bi rezerviral mizo", "datum"),
                    ("kdaj je zadnji prihod na kosilo", "15:00"),
                ],
            ),
        ]

    return single_turn + booking


def slice_scenarios(scenarios: List[Scenario], count: int) -> List[Scenario]:
    if len(scenarios) >= count:
        return scenarios[:count]
    out = list(scenarios)
    i = 0
    while len(out) < count:
        out.append(scenarios[i % len(scenarios)])
        i += 1
    return out
