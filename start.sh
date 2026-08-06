#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON="${PYTHON:-python3}"

cd "$ROOT_DIR"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON not found. Install Python 3.11+ or set PYTHON=python3.11"
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creating virtual environment..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

echo "==> Installing dependencies..."
pip install -q -r requirements.txt

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
else
  echo "WARNING: No .env file found. Copy .env.example and set GOOGLE_APPLICATION_CREDENTIALS."
fi

PORT="${FLASK_PORT:-5001}"

free_port() {
  local port="$1"
  local pids

  if ! command -v lsof >/dev/null 2>&1; then
    echo "WARNING: lsof not found; skipping port check for :$port"
    return 0
  fi

  pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    echo "==> Port $port is free"
    return 0
  fi

  echo "==> Port $port in use; stopping process(es): $pids"
  kill $pids 2>/dev/null || true
  sleep 1

  pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "==> Force-stopping process(es): $pids"
    kill -9 $pids 2>/dev/null || true
  fi
}

free_port "$PORT"

echo "==> Starting FirmShake API on http://localhost:$PORT"
exec python app.py
