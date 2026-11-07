#!/usr/bin/env sh
# Mac/Linux: creates a virtualenv on first run, then starts the app on http://localhost:8000
set -e
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r backend/requirements.txt
cd backend && python -m uvicorn app.main:app --port 8000
