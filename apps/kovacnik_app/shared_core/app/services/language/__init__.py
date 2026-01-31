"""
Language detection and translation module.
"""

from .detection import detect_language
from .translation import maybe_translate, translate_reply, translate_response

__all__ = [
    "detect_language",
    "maybe_translate",
    "translate_reply",
    "translate_response",
]
