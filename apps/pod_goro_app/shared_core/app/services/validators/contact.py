"""
Contact validation utilities - email, phone extraction and validation.
"""

import re


def is_email(text: str) -> bool:
    """Check if text is a valid email address."""
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", text.strip()))


def extract_email(text: str) -> str:
    """Extract email address from text."""
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    """Extract phone number from text (minimum 7 digits)."""
    digits = re.sub(r"\D", "", text)
    return digits if len(digits) >= 7 else ""


def is_contact_request(message: str) -> bool:
    """Check if message is asking for contact information."""
    lowered = message.lower()
    return any(
        token in lowered
        for token in ["kontakt", "telefon", "email", "e-po", "klic", "pokli", "številk"]
    )
