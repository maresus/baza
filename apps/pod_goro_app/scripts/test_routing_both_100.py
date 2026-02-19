from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> None:
    py = sys.executable
    kovacnik_100 = [py, str(REPO_ROOT / "apps" / "kovacnik_app" / "scripts" / "test_routing_kovacnik_100.py")]
    podgoro_100 = [py, str(REPO_ROOT / "apps" / "pod_goro_app" / "scripts" / "test_routing_podgoro_100.py")]

    print("Running Kovačnik 100...")
    _run(kovacnik_100)
    print("Running Pod Goro 100...")
    _run(podgoro_100)

    print("Both 100-scenario suites passed.")


if __name__ == "__main__":
    main()
