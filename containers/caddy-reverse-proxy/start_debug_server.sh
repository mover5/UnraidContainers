#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/web"

if [ ! -x .venv/bin/python ]; then
    echo "[start] creating venv..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
fi

if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
    echo "[start] installing requirements..."
    .venv/bin/pip install --quiet -r requirements.txt
    touch .venv/.installed
fi

export CADDY_BACKEND=mock
export FLASK_DEBUG=1
export FLASK_PORT="${FLASK_PORT:-9998}"

echo
echo "[start] caddy-admin UI (mock mode, hot-reload on)"
echo "[start] http://localhost:${FLASK_PORT}"
echo

exec .venv/bin/python app.py
