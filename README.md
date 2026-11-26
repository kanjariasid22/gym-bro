# GymBro

One chat. Two modes (**Guide** plans, **Trainer** logs). Shared workout ledger + long-term agent memory.

## Source of truth

**[`GymBro - Project Description.md`](./GymBro%20-%20Project%20Description.md)** — product scope, locked decisions, build slices.

## Architecture (local)

| Layer | Role |
|-------|------|
| **SQLite** | System of record — users, programs, sessions, set_logs, chat_messages |
| **Memory** | Semantic continuity — goals/preferences/handoff narratives. Uses Cognis when `GEMINI_API_KEY` is set; otherwise a local Groq-backed store under `MEMORY_DATA_DIR` with the same `owner_id` / `agent_id` / `session_id` scoping |
| **LangGraph-shaped router** | Hard session state beats intent → Guide or Trainer |
| **Shared domain tools** | Start/complete/cancel, log sets, upsert program — used by REST buttons and agents |

## Layout

| Path | Role |
|------|------|
| `backend/` | FastAPI + agents + SQLite + memory |
| `frontend/` | Vite + React + TypeScript SPA |
| `docker-compose.yml` | Deploy stub (not required for local) |

## Local run

```bash
cp .env.example .env
# set JWT_SECRET and GROQ_API_KEY
# GROQ_MODEL defaults to qwen/qwen3.8-27b (must be a model your Groq key can access)

# API
cd backend
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# UI (other terminal)
cd frontend
npm install
npm run dev
```

- App: http://localhost:5173  
- API docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health (`groq_configured`, `memory_backend`)

## Walk the full loop

1. Register / log in.
2. In chat (Guide): share **goals** + **plan end date**, or paste a plan. Guide may call `upsert_program`.
3. Open **Plan** to view/edit the active plan (save archives the previous version). **Plan history** lists archived plans (read-only).
4. Click **Start workout** (or ask in chat). Mode chip → **Trainer · live**.
5. Log sets in chat (`lat pd 3x10 @ 50kg`) and/or use the session strip form.
6. Click **End workout** (or ask Trainer to complete) → summary → memory → Guide follow-up.
7. Open **History** (workouts) → session table → edit/delete a set.
8. Use **Load earlier** to paginate chat.

**Cancel** closes the session without the full Guide handoff.

## Memory vs DB

- Exact lifts, edits, session status → **SQLite**
- Goals, preferences, workout narratives for next planning → **memory layer**
