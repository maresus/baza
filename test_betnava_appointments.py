"""
Test script za Zdravstveni center rezervacijski sistem
Testira vse tipe zdravstvenih terminov
"""

from app.services.reservation_service import ReservationService
from app.services.health_center_extensions import (
    validate_appointment_rules,
    format_appointment_summary,
    get_available_time_slots,
    get_service_info,
    format_all_services_summary,
)


def test_dermatolog_appointment():
    print("\n" + "=" * 60)
    print("TEST 1: DERMATOLOŠKI PREGLED")
    print("=" * 60)

    rs = ReservationService()

    # Test: Dermatolog termin
    print("\n1a) Validacija: 15.03.2026, 10:00, Dermatolog")
    valid, error = validate_appointment_rules(
        date_str="15.03.2026",
        time_str="10:00",
        service_type="dermatolog",
        patient_name="Janez Novak",
        patient_phone="031123456",
    )
    print(f"  Valid: {valid}")
    if not valid:
        print(f"  Error: {error}")

    if valid:
        # Povzetek
        print("\n1b) Povzetek:")
        summary = format_appointment_summary("15.03.2026", "10:00", "dermatolog", "Janez Novak")
        print(summary)

        # Ustvari rezervacijo
        print("\n1c) Ustvarjam termin...")
        res_id = rs.create_reservation(
            date="15.03.2026",
            people=1,
            reservation_type="appointment",
            time="10:00",
            service_type="DERMATOLOG",
            duration_minutes=30,
            name="Janez Novak",
            phone="031123456",
            email="janez@example.com",
            reason="Pregled kožnega znamenja",
            patient_age=45,
            source="test",
        )
        print(f"  ✅ Termin ustvarjen! ID: {res_id}")

        reservation = rs.get_reservation(res_id)
        print(f"  Service type: {reservation['service_type']}")
        print(f"  Duration: {reservation['duration_minutes']} min")


def test_ortoped_appointment():
    print("\n" + "=" * 60)
    print("TEST 2: ORTOPEDSKI PREGLED")
    print("=" * 60)

    rs = ReservationService()

    # Validacija
    print("\n2a) Validacija: 20.03.2026, 14:30, Ortoped")
    valid, error = validate_appointment_rules(
        date_str="20.03.2026",
        time_str="14:30",
        service_type="ortoped",
        patient_name="Ana Kovač",
        patient_phone="031987654",
    )
    print(f"  Valid: {valid}")

    if valid:
        # Povzetek
        print("\n2b) Povzetek:")
        summary = format_appointment_summary("20.03.2026", "14:30", "ortoped", "Ana Kovač")
        print(summary)

        # Ustvari rezervacijo
        print("\n2c) Ustvarjam termin...")
        res_id = rs.create_reservation(
            date="20.03.2026",
            people=1,
            reservation_type="appointment",
            time="14:30",
            service_type="ORTOPED",
            duration_minutes=30,
            name="Ana Kovač",
            phone="031987654",
            email="ana@example.com",
            reason="Bolečine v kolenu",
            patient_age=32,
            source="test",
        )
        print(f"  ✅ Termin ustvarjen! ID: {res_id}")


def test_okulist_appointment():
    print("\n" + "=" * 60)
    print("TEST 3: OKULISTIČNI PREGLED")
    print("=" * 60)

    rs = ReservationService()

    # Validacija
    print("\n3a) Validacija: 25.03.2026, 9:00, Okulist")
    valid, error = validate_appointment_rules(
        date_str="25.03.2026",
        time_str="9:00",
        service_type="okulist",
        patient_name="Marko Zupan",
        patient_phone="040111222",
    )
    print(f"  Valid: {valid}")

    if valid:
        # Povzetek
        print("\n3b) Povzetek:")
        summary = format_appointment_summary("25.03.2026", "9:00", "okulist", "Marko Zupan")
        print(summary)

        # Ustvari rezervacijo
        print("\n3c) Ustvarjam termin...")
        res_id = rs.create_reservation(
            date="25.03.2026",
            people=1,
            reservation_type="appointment",
            time="9:00",
            service_type="OKULIST",
            duration_minutes=30,
            name="Marko Zupan",
            phone="040111222",
            email="marko@example.com",
            reason="Predpis očal",
            patient_age=28,
            patient_health_card="SI123456789",
            source="test",
        )
        print(f"  ✅ Termin ustvarjen! ID: {res_id}")


def test_kozmetika_appointment():
    print("\n" + "=" * 60)
    print("TEST 4: KOZMETIČNI SALON")
    print("=" * 60)

    rs = ReservationService()

    # Validacija (60 min)
    print("\n4a) Validacija: 28.03.2026, 16:00, Kozmetika (60 min)")
    valid, error = validate_appointment_rules(
        date_str="28.03.2026",
        time_str="16:00",
        service_type="kozmetika",
        patient_name="Sara Novak",
        patient_phone="031555666",
    )
    print(f"  Valid: {valid}")

    if valid:
        # Povzetek
        print("\n4b) Povzetek:")
        summary = format_appointment_summary("28.03.2026", "16:00", "kozmetika", "Sara Novak")
        print(summary)

        # Ustvari rezervacijo
        print("\n4c) Ustvarjam termin...")
        res_id = rs.create_reservation(
            date="28.03.2026",
            people=1,
            reservation_type="appointment",
            time="16:00",
            service_type="KOZMETIKA",
            duration_minutes=60,  # Kozmetika je 60 min
            name="Sara Novak",
            phone="031555666",
            email="sara@example.com",
            reason="Nega obraza",
            source="test",
        )
        print(f"  ✅ Termin ustvarjen! ID: {res_id}")


def test_available_slots():
    print("\n" + "=" * 60)
    print("TEST 5: PROSTI TERMINI")
    print("=" * 60)

    # Test: Prosti termini za dermatolog
    print("\n5a) Prosti termini za dermatolog - 15.03.2026:")
    slots = get_available_time_slots("15.03.2026", "dermatolog")
    print(f"  Skupaj slotov: {len(slots)}")
    print(f"  Prvi 5 slotov: {slots[:5]}")
    print(f"  Zadnji 3 sloti: {slots[-3:]}")


def test_read_all_appointments():
    print("\n" + "=" * 60)
    print("TEST 6: BRANJE VSEH TERMINOV")
    print("=" * 60)

    rs = ReservationService()

    # Preberi vse termine
    all_res = rs.read_reservations(limit=100)
    print(f"\nSkupaj terminov: {len(all_res)}")

    # Po storitvah
    service_counts = {}
    for r in all_res:
        if r.get("service_type"):
            service_type = r["service_type"]
            service_counts[service_type] = service_counts.get(service_type, 0) + 1

    print("\nPo storitvah:")
    for service, count in service_counts.items():
        print(f"  - {service}: {count}")


def test_service_info():
    print("\n" + "=" * 60)
    print("TEST 7: INFORMACIJE O STORITVAH")
    print("=" * 60)

    print("\n7a) Seznam vseh storitev:")
    summary = format_all_services_summary()
    print(summary)

    print("\n\n7b) Informacije o ortopedskem pregledu:")
    info = get_service_info("ortoped")
    print(f"  Naziv: {info['name']}")
    print(f"  Trajanje: {info['duration_minutes']} min")
    print(f"  Cena: {info['price_range']}")
    print(f"  Opis: {info['description']}")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "ZDRAVSTVENI CENTER - TEST TERMINOV" + " " * 13 + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        test_dermatolog_appointment()
        test_ortoped_appointment()
        test_okulist_appointment()
        test_kozmetika_appointment()
        test_available_slots()
        test_read_all_appointments()
        test_service_info()

        print("\n" + "=" * 60)
        print("✅ VSI TESTI SO USPEŠNO ZAKLJUČENI!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ NAPAKA: {e}")
        import traceback

        traceback.print_exc()
