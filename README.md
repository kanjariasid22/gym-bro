# GymBro

One chat. Two modes (**Guide** plans, **Trainer** logs). Shared workout ledger + long-term agent memory.

## Source of truth

Product scope, architecture, locked decisions, and build slices live in:

**[`GymBro - Project Description.md`](./GymBro%20-%20Project%20Description.md)**

## Layout

| Path | Role |
|------|------|
| `backend/` | FastAPI + SQLite (+ LangGraph/Cognis in later slices) |
| `frontend/` | Vite + React + TypeScript SPA |
| `docker-compose.yml` | Compose stub (slice 22) |
| `.env.example` | Required environment variables |

## Local run

```bash
cp .env.example .env
# set JWT_SECRET; add GROQ_API_KEY when you need LLM canonicalize / agents

# backend
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (separate terminal)
cd frontend
npm install
npm run dev
```

App: http://localhost:5173 · API: http://localhost:8000 · Docs: http://localhost:8000/docs

Optional frontend override: `VITE_API_BASE=http://localhost:8000` (default).
