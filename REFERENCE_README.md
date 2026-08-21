# Current Scheduler Reference

This is the latest scheduler source available from the working local MVP. It is included as a **reference baseline**, not as the final multi-business architecture.

## Current stack

- Python 3.11
- FastAPI + SQLModel
- SQLite
- OR-Tools scheduler
- React + Vite
- JWT username/password authentication
- Existing AI integration uses OpenAI and must be replaced by a provider abstraction whose first production provider is Claude/Anthropic.

## Local run

Backend, from this folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload
```

Frontend, in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

## Important caveats

- `backend/app/database.py` uses SQLite and lightweight ad-hoc migrations. Production work should move to PostgreSQL and Alembic.
- `frontend/src/api.js` currently hardcodes `http://127.0.0.1:8000`; replace it with an environment-driven API URL.
- Do not commit a real `.env` or provider key.
- Preserve the scheduler behavior while extracting it into a module of the larger product.
