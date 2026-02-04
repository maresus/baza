#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "apps" / "kovacnik_app" / "app" / "services",
    ROOT / "apps" / "pod_goro_app" / "app" / "services",
]
EXCLUDE_SUFFIXES = {
    "session/state_writer.py",
    "session/unified_state.py",
}

# Direct writes that bypass single state writer.
PATTERN = re.compile(
    r"\b(reservation_state|inquiry_state|availability_state|state)\[[^\]]+\]\s*="
)


def main() -> int:
    failures: list[str] = []
    for base in TARGETS:
        for py in base.rglob("*.py"):
            rel = py.relative_to(base).as_posix()
            if rel in EXCLUDE_SUFFIXES:
                continue
            text = py.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), start=1):
                if PATTERN.search(line):
                    failures.append(f"{py}:{i}: {line.strip()}")
    if failures:
        print("Found direct state writes (must use state_writer):")
        for item in failures:
            print(item)
        return 1
    print("OK: no direct state[...] writes outside state_writer/unified_state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
