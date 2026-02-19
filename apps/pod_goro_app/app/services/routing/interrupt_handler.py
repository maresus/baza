from __future__ import annotations

from typing import Optional

from app.services.reservation_flow import get_booking_continuation


def handle_interrupt(answer: str, current_step: Optional[str]) -> str:
    # Ne silimo uporabnika v "nadaljevanje"; interrupt naj odgovori in zakljuci.
    # get_booking_continuation obdrzimo le za kompatibilnost/diagnostiko.
    _ = get_booking_continuation(current_step or "", {})
    return answer
