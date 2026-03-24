"""
Booking state machine for Pod Goro V2.
Supports: room, table, bike, animals (srne/živali).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class BookingState:
    """State for a booking in progress."""
    type: str = ""  # "room", "table", "bike", "combined"
    step: str = "start"

    # Combined booking support
    combined_types: list[str] = field(default_factory=list)  # e.g. ["table", "bike"]

    # Collected data
    date: str = ""
    time: str = ""
    nights: int = 0
    adults: int = 0
    children: int = 0
    children_ages: list[int] = field(default_factory=list)
    name: str = ""
    phone: str = ""
    email: str = ""
    note: str = ""

    # Bike-specific
    bike_type: str = ""  # "gorsko" or "e-kolo"
    bike_count: int = 0

    # After save
    reservation_id: Optional[int] = None


def _save_single(service, state: BookingState, res_type: str, kids_str: str, total_people: int) -> Optional[int]:
    """Save one reservation record to DB."""
    note_parts = []
    if res_type == "bike":
        note_parts.append(f"Kolesa: {state.bike_count}x {state.bike_type}")
    if state.note:
        note_parts.append(state.note)
    note = "; ".join(note_parts) if note_parts else None

    return service.create_reservation(
        date=state.date,
        people=total_people,
        reservation_type=res_type,
        nights=state.nights if res_type == "room" else None,
        time=state.time if res_type == "table" else None,
        name=state.name,
        phone=state.phone,
        email=state.email if state.email else None,
        note=note,
        kids=kids_str if kids_str else None,
        source="chatbot",
        status="pending",
    )


def _save_reservation(state: BookingState) -> Optional[int]:
    """Save completed booking to database and send notifications."""
    try:
        from app.services.reservation_service import ReservationService
        from app.services.email_service import send_guest_confirmation, send_admin_notification

        service = ReservationService()
        total_people = state.adults + state.children

        kids_str = ""
        if state.children > 0:
            ages_str = ", ".join(str(a) for a in state.children_ages) if state.children_ages else ""
            kids_str = f"{state.children} ({ages_str} let)" if ages_str else str(state.children)

        # Combined booking - save multiple records
        if state.type == "combined" and state.combined_types:
            first_id = None
            for res_type in state.combined_types:
                rid = _save_single(service, state, res_type, kids_str, total_people)
                if first_id is None:
                    first_id = rid
                print(f"[BOOKING] Combined reservation #{rid} ({res_type}) saved")

            # Send one combined notification
            type_names = {"room": "nastanitev", "table": "kosilo", "bike": "kolesa"}
            combined_desc = " + ".join(type_names.get(t, t) for t in state.combined_types)
            email_data = {
                "id": first_id,
                "date": state.date,
                "people": total_people,
                "reservation_type": combined_desc,
                "name": state.name,
                "phone": state.phone,
                "email": state.email if state.email else None,
                "nights": state.nights if "room" in state.combined_types else None,
                "time": state.time if "table" in state.combined_types else None,
                "kids": kids_str if kids_str else None,
                "note": f"Kombinirana rezervacija: {combined_desc}",
                "source": "chatbot",
            }
            if state.email:
                send_guest_confirmation(email_data)
            send_admin_notification(email_data)
            return first_id

        # Single booking
        note_parts = []
        if state.type == "bike":
            note_parts.append(f"Kolesa: {state.bike_count}x {state.bike_type}")
        if state.note:
            note_parts.append(state.note)
        note = "; ".join(note_parts) if note_parts else None

        reservation_id = service.create_reservation(
            date=state.date,
            people=total_people,
            reservation_type=state.type,
            nights=state.nights if state.type == "room" else None,
            time=state.time if state.type == "table" else None,
            name=state.name,
            phone=state.phone,
            email=state.email if state.email else None,
            note=note,
            kids=kids_str if kids_str else None,
            source="chatbot",
            status="pending",
        )

        email_data = {
            "id": reservation_id,
            "date": state.date,
            "people": total_people,
            "reservation_type": state.type,
            "name": state.name,
            "phone": state.phone,
            "email": state.email if state.email else None,
            "nights": state.nights if state.type == "room" else None,
            "time": state.time if state.type == "table" else None,
            "kids": kids_str if kids_str else None,
            "note": note,
            "source": "chatbot",
        }

        if state.email:
            send_guest_confirmation(email_data)
        send_admin_notification(email_data)

        print(f"[BOOKING] Reservation #{reservation_id} saved to database")
        return reservation_id

    except Exception as e:
        print(f"[BOOKING] Error saving reservation: {e}")
        return None


def detect_booking_intent(message: str) -> str | None:
    """
    Detect if user wants to start a booking.
    Returns "room", "table", "bike", "ask" or None.
    Note: animals feeding is info-only, no reservation needed.
    """
    msg_l = message.lower()

    booking_phrases = (
        "rezervir", "rezervacij", "rezevir", "rezerir", "rezerv", "rezerw",
        "book", "zarezrv", "zarezev", "zarezerv",
        "rad bi rezerv", "bi rad rezerv", "rad bi rezev", "bi rad rezev",
        "želim rezerv", "zelim rezerv", "želim rezev", "zelim rezev",
        "bi radi rezerv", "hočemo rezerv", "hocemo rezerv",
        "lahko rezerv", "lahk rezerv", "lahko rezev", "lahk rezev",
        "bi rad nočil", "bi radi nočil", "bi rad nocil", "bi radi nocil",
        "bi rad prenočil", "bi radi prenočil",
        "bi rad izposodil", "bi radi izposodili", "izposoja",
        "rad bi prišel", "bi rad prišel", "pridemo",
    )

    has_booking = any(phrase in msg_l for phrase in booking_phrases)

    room_words = ("sobo", "soba", "sobi", "sobe", "nočitev", "nocitev", "prenočitev", "nastanitev")
    table_words = ("mizo", "miza", "mizi", "mize", "miz", "kosilo", "kosilom", "jedilnic", "zajtrk", "večerjo", "vecerjo", "obrok", "zvečer", "zvecer")
    bike_words = ("kolo", "kolesa", "koleso", "kolesarj", "koles", "e-kolo", "gorsk", "kolom", "kolesih")

    has_room = any(w in msg_l for w in room_words)
    has_table = any(w in msg_l for w in table_words)
    has_bike = any(w in msg_l for w in bike_words)

    if not has_booking:
        return None

    # Detect combined types
    types_found = []
    if has_room:
        types_found.append("room")
    if has_table:
        types_found.append("table")
    if has_bike:
        types_found.append("bike")

    if len(types_found) > 1:
        return "+".join(types_found)
    elif has_room:
        return "room"
    elif has_table:
        return "table"
    elif has_bike:
        return "bike"

    return "ask"


def start_booking(booking_type: str) -> tuple[BookingState, str]:
    """Start a new booking flow."""

    # Handle combined booking types (e.g. "table+bike", "room+bike")
    if "+" in booking_type:
        types = booking_type.split("+")
        state = BookingState(type="combined", step="awaiting_date", combined_types=types)
        type_names = {"room": "nastanitev", "table": "kosilo", "bike": "izposoja koles"}
        names = " in ".join(type_names.get(t, t) for t in types)
        reply = (
            f"Odlično! Rezerviramo **{names}** za isti dan — podatke zbere enkrat za vse.\n\n"
            "Za kateri datum? (npr. 20.7.2026)"
        )
        return state, reply

    state = BookingState(type=booking_type, step="awaiting_date")

    if booking_type == "room":
        reply = (
            "Odlično, rezervacija sobe!\n\n"
            "Za kateri datum prihoda razmišljate? (npr. 15.7.2026)"
        )
    elif booking_type == "table":
        reply = (
            "Odlično, rezervacija mize za kosilo!\n\n"
            "Za kateri datum razmišljate? (npr. nedelja 20.7.2026)"
        )
    elif booking_type == "bike":
        reply = (
            "Izposoja koles!\n\n"
            "Za kateri datum bi radi izposodili kolesa? (npr. 15.7.2026)"
        )
    else:
        reply = (
            "Z veseljem pomagam pri rezervaciji!\n\n"
            "Kaj želite rezervirati?\n"
            "- **Soba** (nastanitev)\n"
            "- **Miza** (kosilo)\n"
            "- **Kolesa** (izposoja)"
        )
        state.step = "awaiting_type"

    return state, reply


def _parse_date(text: str) -> str | None:
    match = re.search(r'(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?', text)
    if match:
        day, month = match.group(1), match.group(2)
        year = match.group(3) or str(datetime.now().year)
        return f"{int(day):02d}.{int(month):02d}.{year}"
    return None


def _parse_number(text: str) -> int | None:
    match = re.search(r'\d+', text)
    if match:
        return int(match.group())
    words = {"ena": 1, "en": 1, "dva": 2, "dve": 2, "tri": 3, "štiri": 4, "stiri": 4, "pet": 5, "šest": 6, "sest": 6}
    for word, num in words.items():
        if word in text.lower():
            return num
    return None


def _parse_phone(text: str) -> str | None:
    cleaned = re.sub(r'[\s\-\.\(\)]', '', text)
    match = re.search(r'(\+?386)?0?([0-9]{8,9})', cleaned)
    if match:
        return match.group(0)
    match = re.search(r'[\d\s+\-\.]{7,}', text)
    if match:
        return match.group().strip()
    return None


def _parse_email(text: str) -> str | None:
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group() if match else None


def _is_affirmative(text: str) -> bool:
    affirmatives = {"da", "ja", "yes", "ok", "okay", "v redu", "vredu", "seveda", "lahko", "prosim"}
    return text.strip().lower() in affirmatives


def _is_negative(text: str) -> bool:
    negatives = {"ne", "no", "nočem", "nocem", "brez", "ni treba", "ne hvala"}
    return text.strip().lower() in negatives


def _detect_add_type(message: str, current_types: list[str]) -> str | None:
    """
    Detect if user wants to add another booking type mid-flow.
    Returns the new type to add, or None.
    """
    msg_l = message.lower()
    add_phrases = ("tudi", "pa še", "in še", "ter še", "dodaj", "dodajte", "hkrati", "poleg tega", "bi rad še", "bi radi še", "še")
    if not any(p in msg_l for p in add_phrases):
        return None
    bike_words = ("kolo", "kolesa", "koleso", "kolesarj", "e-kolo", "gorsk")
    table_words = ("mizo", "miza", "mizi", "mize", "kosilo")
    room_words = ("sobo", "soba", "nočitev", "prenočitev")
    if any(w in msg_l for w in bike_words) and "bike" not in current_types:
        return "bike"
    if any(w in msg_l for w in table_words) and "table" not in current_types:
        return "table"
    if any(w in msg_l for w in room_words) and "room" not in current_types:
        return "room"
    return None


def _wants_to_cancel(message: str) -> bool:
    msg_l = message.lower().strip()
    cancel_phrases = (
        "prekliči", "preklici", "storniraj", "ustavi", "pusti", "pozabi",
        "ne želim", "ne zelim", "nočem", "nocem", "ne bom", "nehaj",
        "cancel", "stop", "quit", "exit",
        "ne morem", "premislil", "premislila",
    )
    return any(phrase in msg_l for phrase in cancel_phrases)


def process_booking(state: BookingState, message: str) -> tuple[BookingState, str]:
    """Process a message in the booking flow."""
    msg_l = message.lower().strip()

    if _wants_to_cancel(message):
        state.step = "cancelled"
        return state, "Rezervacija je preklicana. Če si premislite, sem tu!"

    # Detect mid-flow "add another type" request (only at steps before name collection)
    safe_steps = ("awaiting_adults", "awaiting_children_count", "awaiting_contact")
    if state.step in safe_steps:
        current = state.combined_types if state.type == "combined" else [state.type]
        new_type = _detect_add_type(message, current)
        if new_type:
            # Upgrade to combined
            if state.type != "combined":
                state.combined_types = [state.type]
                state.type = "combined"
            state.combined_types.append(new_type)
            type_names = {"room": "nastanitev", "table": "kosilo", "bike": "kolesa"}
            all_names = " + ".join(type_names.get(t, t) for t in state.combined_types)
            # Continue with new type's specific questions
            if new_type == "bike":
                state.step = "awaiting_bike_type"
                return state, (
                    f"Super, dodajamo še **kolesa**! Rezervacija bo: {all_names}.\n\n"
                    "Kakšna kolesa? **Gorska** (15 €/dan) ali **E-kolesa** (25 €/dan)?"
                )
            elif new_type == "table":
                state.step = "awaiting_time"
                return state, (
                    f"Super, dodajamo še **kosilo**! Rezervacija bo: {all_names}.\n\n"
                    "Ob kateri uri bo kosilo? (npr. 13:00)"
                )
            elif new_type == "room":
                state.step = "awaiting_nights"
                return state, (
                    f"Super, dodajamo še **sobo**! Rezervacija bo: {all_names}.\n\n"
                    "Koliko nočitev?"
                )

    # Type selection (generic ask)
    if state.step == "awaiting_type":
        if any(w in msg_l for w in ("sobo", "soba", "nastanitev", "nočitev", "nocitev")):
            state.type = "room"
            state.step = "awaiting_date"
            return state, "Za kateri datum prihoda razmišljate? (npr. 15.7.2026)"
        if any(w in msg_l for w in ("mizo", "miza", "kosilo")):
            state.type = "table"
            state.step = "awaiting_date"
            return state, "Za kateri datum razmišljate? (npr. nedelja 20.7.2026)"
        if any(w in msg_l for w in ("kolo", "kolesa", "kolesarj", "e-kolo")):
            state.type = "bike"
            state.step = "awaiting_date"
            return state, "Za kateri datum bi radi izposodili kolesa? (npr. 15.7.2026)"
        if any(w in msg_l for w in ("srn", "živali", "zivali", "hranjenje", "nahranit")):
            state.type = "animals"
            state.step = "awaiting_animal_type"
            return state, "Vas zanima **hranjenje srn**, **hranjenje kmečkih živali** ali **oboje**?"
        return state, "Prosim povejte: želite rezervirati **sobo**, **mizo**, **kolesa** ali **hranjenje živali**?"

    # Animals type selection
    if state.step == "awaiting_animal_type":
        if any(w in msg_l for w in ("srn", "srne", "jelen")):
            state.animal_type = "srne"
        elif any(w in msg_l for w in ("kmečk", "krav", "koz", "kokoš", "zajc", "prašič", "prasic")):
            state.animal_type = "zivali"
        elif any(w in msg_l for w in ("oboje", "vse", "oba", "obe")):
            state.animal_type = "oboje"
        else:
            state.animal_type = "oboje"  # default

        state.step = "awaiting_date"
        animal_desc = {
            "srne": "hranjenje srn",
            "zivali": "hranjenje kmečkih živali",
            "oboje": "hranjenje srn in kmečkih živali",
        }.get(state.animal_type, "hranjenje živali")
        return state, f"Odlično, {animal_desc}!\n\nZa kateri datum? (npr. 15.7.2026)"

    # Date
    if state.step == "awaiting_date":
        date = _parse_date(message)
        if date:
            state.date = date
            if state.type == "combined":
                # Combined: first collect type-specific data in order
                if "room" in state.combined_types:
                    state.step = "awaiting_nights"
                    return state, f"Datum prihoda: {date}\n\nKoliko nočitev? (npr. 2)"
                elif "table" in state.combined_types:
                    state.step = "awaiting_time"
                    return state, f"Datum: {date}\n\nOb kateri uri bo kosilo? (npr. 13:00)"
                elif "bike" in state.combined_types:
                    state.step = "awaiting_bike_type"
                    return state, f"Datum: {date}\n\nKakšna kolesa? **Gorska** (15 €/dan) ali **E-kolesa** (25 €/dan)?"
                else:
                    state.step = "awaiting_adults"
                    return state, f"Datum: {date}\n\nKoliko odraslih oseb?"
            elif state.type == "room":
                state.step = "awaiting_nights"
                return state, f"Datum prihoda: {date}\n\nKoliko nočitev? (npr. 2)"
            elif state.type == "table":
                state.step = "awaiting_adults"
                return state, f"Datum: {date}\n\nKoliko odraslih oseb?"
            elif state.type == "bike":
                state.step = "awaiting_bike_type"
                return state, f"Datum: {date}\n\nKakšna kolesa? **Gorska** (15 €/dan) ali **E-kolesa** (25 €/dan)?"
        return state, "Prosim vpišite datum v obliki DD.MM.YYYY (npr. 15.7.2026)"

    # Time (for table)
    if state.step == "awaiting_time":
        time_match = re.search(r'\d{1,2}[:\.]?\d{0,2}', message)
        if time_match:
            state.time = time_match.group()
        elif any(w in msg_l for w in ("zjutraj", "jutro", "8", "8:00")):
            state.time = "8:00"
        elif any(w in msg_l for w in ("opoldne", "12", "12:00")):
            state.time = "12:00"
        elif any(w in msg_l for w in ("13", "13:00")):
            state.time = "13:00"
        elif any(w in msg_l for w in ("zvečer", "večer", "17", "17:00", "18", "18:00")):
            state.time = "17:00"
        elif any(w in msg_l for w in ("popoldne", "14", "14:00", "15", "15:00")):
            state.time = "14:00"
        else:
            return state, "Prosim vpišite uro prihoda (npr. 13:00)"
        # Combined: after table time, continue to bike if needed
        if state.type == "combined" and "bike" in state.combined_types:
            state.step = "awaiting_bike_type"
            return state, f"Ura kosila: {state.time}\n\nKakšna kolesa? **Gorska** (15 €/dan) ali **E-kolesa** (25 €/dan)?"
        state.step = "awaiting_adults"
        return state, f"Ura: {state.time}\n\nKoliko odraslih oseb?"

    # Bike type
    if state.step == "awaiting_bike_type":
        if any(w in msg_l for w in ("e-kolo", "elektr", "e kolo", "elektricn")):
            state.bike_type = "e-kolo"
        else:
            state.bike_type = "gorsko"
        state.step = "awaiting_bike_count"
        price = 25 if state.bike_type == "e-kolo" else 15
        return state, f"Tip: {state.bike_type} kolo ({price} €/dan)\n\nKoliko koles potrebujete?"

    # Bike count
    if state.step == "awaiting_bike_count":
        num = _parse_number(message)
        if num and num > 0:
            state.bike_count = num
            price = 25 if state.bike_type == "e-kolo" else 15
            # If adults already known (bike was added mid-flow), skip to contact
            if state.adults > 0:
                state.step = "awaiting_contact"
                return state, f"Število koles: {num} × {state.bike_type} ({num * price} €)\n\nVaše ime in priimek?"
            state.step = "awaiting_adults"
            return state, f"Število koles: {num} × {state.bike_type} ({num * price} €)\n\nKoliko odraslih oseb?"
        return state, "Koliko koles potrebujete? (npr. 2)"

    # Nights (room only)
    if state.step == "awaiting_nights":
        nights = _parse_number(message)
        if nights and nights > 0:
            month = int(state.date.split('.')[1]) if state.date else 0
            min_nights = 3 if month in (6, 7, 8) else 2
            if nights < min_nights:
                return state, f"Minimalno število nočitev je {min_nights} ({'junij–avgust' if min_nights == 3 else 'ostali meseci'}). Koliko nočitev?"
            state.nights = nights
            # Combined: continue to next type-specific step
            if state.type == "combined":
                if "table" in state.combined_types:
                    state.step = "awaiting_time"
                    return state, f"Število nočitev: {nights}\n\nOb kateri uri bo kosilo? (npr. 13:00)"
                elif "bike" in state.combined_types:
                    state.step = "awaiting_bike_type"
                    return state, f"Število nočitev: {nights}\n\nKakšna kolesa? **Gorska** (15 €/dan) ali **E-kolesa** (25 €/dan)?"
            state.step = "awaiting_adults"
            return state, f"Število nočitev: {nights}\n\nKoliko odraslih oseb?"
        return state, "Koliko nočitev želite? (npr. 2)"

    # Adults
    if state.step == "awaiting_adults":
        num = _parse_number(message)
        if num and num > 0:
            state.adults = num
            state.step = "awaiting_children_count"
            return state, f"Število odraslih: {num}\n\nAli boste imeli otroke? Če da, koliko? (ali 'ne' če brez)"
        return state, "Koliko odraslih oseb? (npr. 2)"

    # Children count
    if state.step == "awaiting_children_count":
        if _is_negative(msg_l) or any(w in msg_l for w in ("brez", "nimamo", "samo odrasl")):
            state.children = 0
            state.step = "awaiting_contact"
            return state, "V redu, brez otrok.\n\nVaše ime in priimek?"
        num = _parse_number(message)
        if num is not None and num >= 0:
            if num == 0:
                state.children = 0
                state.step = "awaiting_contact"
                return state, "V redu, brez otrok.\n\nVaše ime in priimek?"
            state.children = num
            state.step = "awaiting_children_ages"
            if num == 1:
                return state, f"Število otrok: {num}\n\nKoliko let ima otrok?"
            return state, f"Število otrok: {num}\n\nKoliko let imajo otroci? (npr. '5 in 8')"
        return state, "Koliko otrok? (število ali 'ne' če brez)"

    # Children ages
    if state.step == "awaiting_children_ages":
        ages = re.findall(r'\d+', message)
        if ages:
            state.children_ages = [int(a) for a in ages[:state.children]]
            if len(state.children_ages) < state.children:
                return state, f"Prosim vpišite starost za vseh {state.children} otrok (npr. '5 in 8')"
            state.step = "awaiting_contact"
            ages_str = ", ".join(str(a) for a in state.children_ages)
            return state, f"Starost otrok: {ages_str} let\n\nVaše ime in priimek?"
        return state, f"Prosim vpišite starost {'otroka' if state.children == 1 else 'otrok'}"

    # Contact - name
    if state.step == "awaiting_contact":
        words = message.strip().split()
        if len(words) >= 1 and not any(c.isdigit() for c in message):
            state.name = message.strip().title()
            state.step = "awaiting_phone"
            return state, f"Ime: {state.name}\n\nVaša telefonska številka?"
        return state, "Prosim vpišite vaše ime in priimek."

    # Phone
    if state.step == "awaiting_phone":
        phone = _parse_phone(message)
        if phone:
            state.phone = phone
            state.step = "awaiting_email"
            return state, f"Telefon: {phone}\n\nVaš email naslov? (za potrditev, ali 'preskoči')"
        return state, "Prosim vpišite telefonsko številko (npr. 041 123 456)"

    # Email (optional)
    if state.step == "awaiting_email":
        skip_words = ("preskoči", "preskoci", "ne", "nimam", "brez", "skip", "-")
        if msg_l in skip_words or any(w in msg_l for w in skip_words):
            state.email = ""
            state.step = "awaiting_confirm"
            return state, _build_confirmation(state)

        email = _parse_email(message)
        if email:
            state.email = email
            state.step = "awaiting_confirm"
            return state, _build_confirmation(state)
        return state, "Prosim vpišite veljaven email (npr. janez@example.com) ali 'preskoči'"

    # Confirmation
    if state.step == "awaiting_confirm":
        if _is_affirmative(msg_l):
            reservation_id = _save_reservation(state)
            state.reservation_id = reservation_id
            state.step = "confirmed"

            if reservation_id:
                return state, (
                    f"Rezervacija #{reservation_id} je sprejeta!\n\n"
                    "Kontaktirali vas bomo za potrditev.\n"
                    "Za vprašanja: 041 123 456 ali info@podgoro.si\n\n"
                    "Hvala in se vidimo na Kmetiji Pod Goro!"
                )
            else:
                return state, (
                    "Rezervacija je sprejeta!\n\n"
                    "Kontaktirali vas bomo za potrditev.\n"
                    "Za vprašanja: 041 123 456 ali info@podgoro.si\n\n"
                    "Hvala in se vidimo na Kmetiji Pod Goro!"
                )
        if _is_negative(msg_l) or "prekli" in msg_l:
            state.step = "cancelled"
            return state, "Rezervacija je preklicana. Če si premislite, sem tu!"
        return state, "Prosim potrdite z 'da' ali prekličite z 'ne'."

    return state, "Oprostite, nisem razumel. Kako vam lahko pomagam?"


def _build_confirmation(state: BookingState) -> str:
    """Build confirmation message."""
    lines = ["Povzetek rezervacije:\n"]

    if state.type == "combined":
        lines.append(f"Datum: {state.date}")
        for t in state.combined_types:
            if t == "room":
                lines.append(f"• Nastanitev – {state.nights} nočitev")
            elif t == "table":
                ura = f" ob {state.time}" if state.time else ""
                lines.append(f"• Kosilo{ura}")
            elif t == "bike":
                price = 25 if state.bike_type == "e-kolo" else 15
                lines.append(f"• Kolesa: {state.bike_count}× {state.bike_type} ({state.bike_count * price} €)")
    elif state.type == "room":
        lines.append(f"Tip: Nastanitev")
        lines.append(f"Datum prihoda: {state.date}")
        lines.append(f"Število nočitev: {state.nights}")
    elif state.type == "table":
        lines.append(f"Tip: Kosilo")
        lines.append(f"Datum: {state.date}")
        if state.time:
            lines.append(f"Ura: {state.time}")
    elif state.type == "bike":
        lines.append(f"Tip: Izposoja koles")
        lines.append(f"Datum: {state.date}")
        lines.append(f"Kolesa: {state.bike_count}x {state.bike_type}")
        price = 25 if state.bike_type == "e-kolo" else 15
        lines.append(f"Cena: {state.bike_count * price} € ({price} €/kolo/dan)")

    people = f"{state.adults} odrasl{'a' if state.adults == 2 else 'ih' if state.adults > 2 else ''}"
    if state.children:
        people += f" + {state.children} otrok"
        if state.children_ages:
            ages_str = ", ".join(str(a) for a in state.children_ages)
            people += f" ({ages_str} let)"
    lines.append(f"Osebe: {people}")
    lines.append(f"Ime: {state.name}")
    lines.append(f"Telefon: {state.phone}")
    if state.email:
        lines.append(f"Email: {state.email}")

    lines.append("\nAli potrjujete rezervacijo? (da/ne)")
    return "\n".join(lines)


def is_booking_active(state: BookingState | None) -> bool:
    """Check if booking flow is active."""
    if state is None:
        return False
    return state.step not in ("", "confirmed", "cancelled")
