"""
Menu formatting utilities.
"""

import os
from datetime import datetime
from typing import Optional

from .data import SEASONAL_MENUS, MENU_INTROS


# Global index for rotating menu intros
_menu_intro_index = 0

# Short mode setting
SHORT_MODE = os.getenv("SHORT_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}


def next_menu_intro() -> str:
    """Get the next menu intro phrase (rotates through options)."""
    global _menu_intro_index
    intro = MENU_INTROS[_menu_intro_index % len(MENU_INTROS)]
    _menu_intro_index += 1
    return intro


def format_current_menu(month_override: Optional[int] = None, force_full: bool = False) -> str:
    """Format the current seasonal menu.

    Args:
        month_override: Override the current month (1-12)
        force_full: Force full menu display even in SHORT_MODE

    Returns:
        Formatted menu string
    """
    now = datetime.now()
    month = month_override or now.month

    # Find the menu for the given month
    current = None
    for menu in SEASONAL_MENUS:
        if month in menu["months"]:
            current = menu
            break
    if not current:
        current = SEASONAL_MENUS[0]

    lines = [
        next_menu_intro(),
        f"{current['label']}",
    ]

    # Filter out price line from items
    items = [item for item in current["items"] if not item.lower().startswith("cena")]

    if SHORT_MODE and not force_full:
        # Show abbreviated menu
        for item in items[:4]:
            lines.append(f"- {item}")
        lines.append("Cena: 36 EUR odrasli, otroci 4-12 let -50%.")
        lines.append("")
        lines.append("Za celoten sezonski meni recite: \"celoten meni\".")
    else:
        # Show full menu
        for item in items:
            lines.append(f"- {item}")
        lines.append("Cena: 36 EUR odrasli, otroci 4-12 let -50%.")
        lines.append("")
        lines.append(
            "Jedilnik je sezonski; če želiš meni za drug mesec, samo povej mesec (npr. 'kaj pa novembra'). "
            "Vege ali brez glutena uredimo ob rezervaciji."
        )

    return "\n".join(lines)
