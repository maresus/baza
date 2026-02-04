#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_TOKEN="${ADMIN_TOKEN:-test-token}"

if [[ ! -x "$VENV_PY" ]]; then
  echo "[DEPLOY GATE FULL] .venv manjka. Ustvari ga in namesti dependencies:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

export USE_UNIFIED_ROUTER="${USE_UNIFIED_ROUTER:-true}"
export ENABLE_EMAIL_REMINDERS="${ENABLE_EMAIL_REMINDERS:-false}"
export ENABLE_SMS_REMINDERS="${ENABLE_SMS_REMINDERS:-false}"

echo "[DEPLOY GATE FULL] Root: $ROOT_DIR"
echo "[DEPLOY GATE FULL] BASE_URL=$BASE_URL"
echo "[DEPLOY GATE FULL] USE_UNIFIED_ROUTER=$USE_UNIFIED_ROUTER"

echo "[1/2] Routing gates"
"$ROOT_DIR/scripts/deploy_gate.sh"

echo "[2/2] API smoke gate"
if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
  echo "[API] Uporabljam obstoječi server na $BASE_URL"
else
  echo "[API] Server ne teče, zaganjam začasni uvicorn"
  (
    cd "$ROOT_DIR"
    "$VENV_PY" -m uvicorn main:app --host 127.0.0.1 --port 8000 > "$ROOT_DIR/data/deploy_gate_server.log" 2>&1
  ) &
  SERVER_PID=$!

  for _ in {1..30}; do
    if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  if ! curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
    echo "[API] Server se ni zagnal. Poglej log: $ROOT_DIR/data/deploy_gate_server.log"
    exit 1
  fi
fi

(
  cd "$ROOT_DIR"
  BASE_URL="$BASE_URL" ADMIN_TOKEN="$ADMIN_TOKEN" bash tests/smoke_test.sh
)

echo "[DEPLOY GATE FULL] OK - routing + API smoke testi so uspešni."
