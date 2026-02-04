from __future__ import annotations

from typing import Any, Dict


def set_state_field(state: Dict[str, Any], key: str, value: Any) -> None:
    """Single write point for mutable flow/session dict fields."""
    state[key] = value


def set_state_fields(state: Dict[str, Any], **fields: Any) -> None:
    for key, value in fields.items():
        set_state_field(state, key, value)
