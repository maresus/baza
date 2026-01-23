from typing import Optional

from pydantic import BaseModel


class ReservationRequest(BaseModel):
    date: str
    people: int
    note: str | None = None


class ReservationResponse(BaseModel):
    confirmed: bool
    message: str


class ReservationCreate(BaseModel):
    date: str
    people: int
    reservation_type: str  # "appointment" for BETNAVA
    nights: int | None = None
    rooms: int | None = None
    time: str | None = None
    location: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    note: str | None = None
    status: Optional[str] = None
    # BETNAVA specific fields
    service_type: str | None = None  # "DERMATOLOG", "ORTOPED", "OKULIST", ...
    duration_minutes: int | None = None  # 30 or 60
    patient_age: int | None = None
    patient_health_card: str | None = None
    reason: str | None = None  # Razlog obiska


class ReservationRecord(BaseModel):
    id: int
    date: str
    people: int
    source: str
    created_at: str
    reservation_type: str
    rooms: int | None = None
    nights: int | None = None
    time: str | None = None
    location: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    note: str | None = None
    status: Optional[str] = None
    birth_date: str | None = None
    time_window: str | None = None
    # BETNAVA specific fields
    service_type: str | None = None
    duration_minutes: int | None = None
    patient_age: int | None = None
    patient_health_card: str | None = None
    reason: str | None = None
