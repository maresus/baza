from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class BrandConfig:
    name: str
    address: str
    phone: str
    mobile: str
    email: str
    website: str
    location_description: str
    parking: str
    opening_hours: Dict[str, str]
    facilities: List[str]
    activities: List[str]
    greetings: List[str]
    thanks_responses: List[str]
    unknown_responses: List[str]
    menu_intros: List[str]
    seasonal_menus: List[Dict[str, Any]]
    weekly_experiences: List[Dict[str, Any]]
