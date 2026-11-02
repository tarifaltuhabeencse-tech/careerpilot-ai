# CareerPilot AI — Runnable Local MVP

## Included
- FastAPI backend, SQLite persistence, password hashing, JWT login, per-user analysis ownership.
- PDF/DOCX text extraction with upload validation and scanned-PDF error handling.
- Deterministic, explainable CV/job keyword matching; saved analyses; dashboard UI.
- API tests and Dockerfile.

## Limitations
This is a local MVP, not a production SaaS. AI-provider generation, OCR, password recovery, billing, email verification, and subscription enforcement are not implemented. Match score is a heuristic, not a hiring-success prediction. CV extraction is basic text extraction, not full structured parsing. Use PostgreSQL, migrations, secure storage, HTTPS, rate limits, backups, deletion/retention controls, and a security review before public deployment. No AI provider receives CV content in this version.

## Windows setup (Command Prompt)
1. Extract the ZIP.
2. Open the extracted folder in File Explorer, type `cmd` in the address bar and press Enter.
3. Run:
```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
copy .env.example .env
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```
4. Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs. Health: http://127.0.0.1:8000/health.
5. Tests: `.venv\Scripts\python.exe -m pytest -q`

If `py` is unavailable, use `python`. You do not need to activate the virtual environment.

## Configuration
Copy `.env.example` to `.env`; replace `CAREERPILOT_SECRET_KEY` with a long random secret before any non-local use. The app loads `.env` automatically.

## Scoring
The deterministic score combines required skill coverage (60%), preferred skill coverage (20%), and simple evidence signals for experience (10%), projects (5%), education/certifications (5%). If a preferred category is absent, active weights are normalized. Synonym handling is limited and the detected requirements should be reviewed.

## Structure
- `backend/app/main.py`: API, auth, database models, extraction, matching.
- `frontend/index.html`: responsive browser UI.
- `tests/test_api.py`: API smoke/security tests.
- `.env.example`: safe example config.
- `docs/SECURITY.md`: security limitations.
