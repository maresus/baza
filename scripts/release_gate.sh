#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[release_gate] Checking for direct state writes..."
python3 "$ROOT/scripts/check_no_direct_state_writes.py"

echo "[release_gate] Running routing suites..."
if [[ -x "$ROOT/../KOVACNIK AI/.venv/bin/python" ]]; then
  PYBIN="$ROOT/../KOVACNIK AI/.venv/bin/python"
else
  PYBIN="python3"
fi

"$PYBIN" "$ROOT/apps/kovacnik_app/scripts/test_routing_kovacnik_100.py"
"$PYBIN" "$ROOT/apps/pod_goro_app/scripts/test_routing_podgoro_100.py"
"$PYBIN" "$ROOT/apps/kovacnik_app/scripts/test_routing_both_100.py"

echo "[release_gate] OK"
