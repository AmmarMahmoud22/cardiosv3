#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv311"
BACKEND_PORT="${BACKEND_PORT:-49232}"
FRONTEND_PORT="${FRONTEND_PORT:-5176}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
BACKEND_HEALTH_HOST="${BACKEND_HEALTH_HOST:-127.0.0.1}"

export PATH="/opt/homebrew/bin:$PATH"

require_free_port() {
  local port="$1"
  local label="$2"

  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "$label port $port is already in use." >&2
    echo "Stop the existing process or change the port, then re-run this script." >&2
    exit 1
  fi
}

pick_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return
  fi

  if [ -x "/opt/homebrew/bin/python3.11" ]; then
    echo "/opt/homebrew/bin/python3.11"
    return
  fi

  echo "Python 3.11 is required. Install it first, then re-run this script." >&2
  exit 1
}

ensure_backend_env() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python 3.11 virtual environment..."
    "$(pick_python)" -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  if ! python - <<'PY' >/dev/null 2>&1
import flask
import pandas
import sklearn
import tensorflow
import xgboost
PY
  then
    echo "Installing backend dependencies..."
    python -m pip install --upgrade pip
    python -m pip install -r "$ROOT_DIR/requirements.txt"
  fi
}

ensure_frontend_env() {
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "Node.js and npm are required. Install them first, then re-run this script." >&2
    exit 1
  fi

  if [ ! -d "$ROOT_DIR/node_modules" ] || [ ! -x "$ROOT_DIR/node_modules/.bin/vite" ]; then
    echo "Installing frontend dependencies..."
    (cd "$ROOT_DIR" && npm install)
    return
  fi

  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ] && [ ! -d "$ROOT_DIR/node_modules/@rollup/rollup-darwin-arm64" ]; then
    echo "Installing frontend dependencies..."
    (cd "$ROOT_DIR" && npm install)
  fi
}

wait_for_backend() {
  local tries=30
  for _ in $(seq 1 "$tries"); do
    if curl -fsS "http://$BACKEND_HEALTH_HOST:$BACKEND_PORT/" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "Backend did not become ready on http://$BACKEND_HEALTH_HOST:$BACKEND_PORT" >&2
  return 1
}

cleanup() {
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

require_free_port "$BACKEND_PORT" "Backend"
require_free_port "$FRONTEND_PORT" "Frontend"

ensure_backend_env
ensure_frontend_env

echo "Starting backend (bind $BACKEND_HOST) on port $BACKEND_PORT ..."
(
  cd "$ROOT_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  FLASK_HOST="$BACKEND_HOST" FLASK_PORT="$BACKEND_PORT" FLASK_DEBUG=0 python backend/app.py
) &
BACKEND_PID=$!

wait_for_backend

echo "Backend is ready."
echo "Starting frontend (bind $FRONTEND_HOST) on port $FRONTEND_PORT ..."
echo "Press Ctrl+C to stop both services."

cd "$ROOT_DIR"
npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort &
FRONTEND_PID=$!
wait "$FRONTEND_PID"
