"""
Farm info module - farm data and info response functions.
"""

from .data import FARM_INFO, LOCATION_KEYWORDS, FARM_INFO_KEYWORDS
from .answers import answer_farm_info

__all__ = [
    "FARM_INFO",
    "LOCATION_KEYWORDS",
    "FARM_INFO_KEYWORDS",
    "answer_farm_info",
]
