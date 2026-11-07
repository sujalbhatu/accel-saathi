@echo off
REM Windows: creates a virtualenv on first run, then starts the app on http://localhost:8000
cd /d %~dp0
if not exist .env copy .env.example .env
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r backend\requirements.txt
cd backend
python -m uvicorn app.main:app --port 8000
