# GymBro — Dual-Mode Training Companion

A single-chat training companion with two agent modes: **Guide** plans programs, **Trainer** logs live workouts. Mode is driven by workout session state (plus intent routing), not by separate chat threads. Exact lifts and programs live in a database; a persistent **agent memory layer** carries goals, preferences, and session summaries across days so planning and logging stay coherent without manual copy-paste.

Inspired by a real workflow: planning in one ChatGPT chat, logging sets in another, and manually copy-pasting summaries between them. GymBro closes that loop.

**Pitch:** One chat. Two modes. Shared workout ledger + long-term agent memory.  
**v1 product shape:** Session companion (ship first). Dual-agent studio UI is v2.  
**Stack:** FastAPI + LangGraph + Groq + SQLite + agent memory (Cognis) | simple TypeScript frontend | AWS free-tier EC2.

---

## What It Does

1. User registers / logs in with **email + password**.
2. Talks in **one continuous chat**. Guide helps create a plan (after asking goals + plan end date), or the user pastes/types an existing plan.
3. User **starts a training session** (UI button or chat tool). UI shows **Trainer · Workout in progress**.
4. During the session, user logs sets in natural language (e.g. `lat pd 3x10 50kg`). Trainer parses, normalizes the exercise name, and writes structured set rows.
5. User **ends the session** (UI button or chat tool). Trainer writes a summary into the DB and memory layer → Guide follows up with next guidance.
6. User opens **History**, picks a past session, sees a **table** of sets, and can **edit/delete** mistaken entries.

---

## Real-World Workflow → Product Mapping

| Manual ChatGPT habit | GymBro |
|----------------------|--------|
| Training Guide chat | **Guide** mode (planning agent) |
| Trainer chat | **Trainer** mode (logging / session coach) |
| Copy-paste routine into trainer chat | Shared **program** in SQL; both modes read it |
| Type sets / weights / reps in trainer chat | NL logging → `set_logs` (+ session strip) |
| Paste trainer summary back into guide chat | **Handoff** on complete → memory + Guide turn |
| Separate chats forever | **One chat**, mode chip + session state |

---

## Architecture

```
                  ┌──────────────────────────────────────┐
                  │         TypeScript frontend          │
                  │  Auth · Chat · Mode chip · Start/End │
                  │  Session strip · History table       │
                  └──────────────────┬───────────────────┘
                                     │ HTTPS / JSON / SSE
                                     ▼
┌────────────────────────────────────────────────────────────────┐
│                         FastAPI                                 │
│  Auth (JWT/cookie) · REST (program/sessions/sets/history)      │
│  POST /chat → orchestrator                                      │
└────────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                     LangGraph orchestrator                      │
│                                                                 │
│   hard session state ──► intent router ──► Guide | Trainer     │
│                              │                                  │
│                              ▼                                  │
│                    tools (shared domain layer)                  │
│         start/complete/cancel · log_sets · upsert_program      │
│         resolve_exercise_name · get_today_plan · handoff       │
└───────────────┬─────────────────────────────┬──────────────────┘
                │                             │
                ▼                             ▼
        ┌───────────────┐             ┌─────────────────┐
        │ SQLite (SoR)  │             │ Agent memory    │
        │ users         │             │ short-term msgs │
        │ programs      │             │ long-term facts │
        │ sessions      │             │ hybrid retrieval│
        │ set_logs      │             │ per-user/agent  │
        │ chat_messages │             └─────────────────┘
        └───────────────┘
```

**System of record vs memory:**
- **SQLite** — exact programs, sessions, sets, chat persistence, edits.
- **Agent memory** — preferences, goals, constraints, session narratives, and handoff context Guide needs after a workout. Not a replacement for set rows.

---

## Agent Modes & State Machine

### Modes

| Mode | When | Responsibility |
|------|------|----------------|
| **Guide** | No active workout (idle / planning) | Intake goals & end date; create/update plan; accept pasted plan; post-workout adaptation |
| **Trainer** | `workout_sessions.status == active` | Log sets; light same-day exercise swap; coach the live session; complete/cancel |

### Session state machine

| State | UI | Default agent | Transitions |
|-------|-----|---------------|-------------|
| `idle` / `planning` | Mode chip: **Guide**; Start enabled | Guide | → `workout_active` via Start (UI or tool) |
| `workout_active` | Mode chip: **Trainer · live**; End/Cancel enabled | Trainer | → `completed` or `cancelled` |
| `handoff` (brief) | Still post-Trainer | Trainer summary → memory → Guide | → `planning` with Guide follow-up |

**Rules:**
- Only **one active session** per user.
- While active → default **Trainer**. Full Guide replan is blocked; user should End first.
- **Manual Start / End / Cancel always wins** over classifier guesses.
- Classifier may *propose* starting a session if the user starts logging with no active session (“Want me to start today’s workout?”) unless they already used Start/tool.
- Mid-workout: **Trainer-only** for chat routing. Trainer may do a **light same-day swap** (replace one exercise for today). Full mesocycle replan = after End (Guide).

### Intent router

Inputs: user message + hard session state + recent context.

Labels: `plan` | `log` | `meta` | `start_workout` | `end_workout` | `cancel_workout`.

Routing priority:
1. Hard session state
2. Explicit tools / slash overrides if added (`/guide`, `/trainer` optional)
3. Intent classification
4. User confirmation when ambiguous (e.g. logging with no session)

---

## Chat UX

- **One continuous chat thread** per user (not per day / per workout).
- UI focuses on **today**; **Load earlier messages** paginates history.
- Assistant turns show a **mode badge** (Guide / Trainer).
- Optional side/session strip while live: today’s planned exercises + logged sets so far.
- Workout session IDs are separate from the chat thread; Trainer memory is scoped to the **workout session id** when live; planning uses a stable planning session id (implement consistently).

---

## Guide intake & planning

Before creating a plan, Guide must obtain (ask if missing):

1. **Goals** — what the user wants to achieve  
2. **Plan end date** — until when the plan should run  

Then Guide produces a program covering from now through that date.

**Alternate path:** user **pastes or types** an existing plan; Guide structures it into the program store (still may confirm goals/end date if useful).

Program is multi-day through the end date (not “today only”).

---

## Trainer logging

Example utterance: `lat pd 3x10 @ 50kg` or `bench 80lbs 5 5 4`

**Parsed into structured fields:**
- exercise (raw → canonical)
- sets / reps
- weight + **unit** (`kg` | `lbs`)
- optional **notes**

**Not in v1:** RPE, failure flags, rest timers.

---

## Exercise naming (free text + LLM normalization)

No global exercise database in v1. Names are free text; the system **canonicalizes on write**.

### Fields on planned exercises and set logs

| Field | Example | Purpose |
|-------|---------|---------|
| `raw_name` | `lat pd` | Exactly what was typed / said |
| `canonical_name` | `Lat Pulldown` | Display + history table |
| `normalized_key` | `lat pulldown` | Match key (lowercase, strip punctuation) |

### `resolve_exercise_name(user_id, raw_text)`

1. **Cheap match (no LLM):** against this user’s recent `normalized_key` values — exact or simple fuzzy/contains → reuse existing `canonical_name`.
2. **LLM on miss (Groq):** return Title Case gym name; merge abbreviations/plurals; don’t invent equipment the user didn’t imply; JSON `{ "canonical_name": "..." }`.
3. Persist `raw_name`, `canonical_name`, `normalized_key`.

**Runs on:** set log, plan write/update, history edit of exercise name.

**UI:** always show `canonical_name`. Keep `raw_name` for audit.

**Out of v1:** shared taxonomy, muscle groups, synonym admin UI, bulk merge of divergent canonicals. Optional “Logged as X — OK?” confirm is nice-to-have, not required to ship.

---

## Units

- User preference: **kg** and **lbs** both supported.
- Store weight with the **unit the user entered** (and/or preference default when omitted).
- Do not force a single global unit.

---

## Session controls (dual path, one backend)

| Action | Manual UI | Chat / tools |
|--------|-----------|--------------|
| Start | **Start workout** | `start_workout` |
| Complete | **End workout** | `complete_workout` |
| Cancel | **Cancel session** | `cancel_workout` |

Manual and agent paths call the **same domain functions / API**. UI and mode chip stay in sync.

- **Complete** → summary + memory handoff + Guide follow-up.  
- **Cancel** → close session **without** full progression handoff (optional short note only).

---

## Handoff loop (core showcase)

On **complete_workout**:

1. Persist session as `completed` in SQLite.  
2. Trainer generates a structured/natural summary of what was done.  
3. Write the summary into agent memory, scoped to that user / Trainer / workout session.  
4. State → planning; Guide loads relevant memory context for that user.  
5. Guide replies with next-session / plan adjustments.

---

## Agent memory layer

Agents need more than the current prompt window: goals and preferences should survive across days, and Trainer’s post-workout summary should be available to Guide without the user pasting anything.

**Implementation (v1):** Cognis (open-source library) running locally on the app server beside SQLite. Chosen because it supports short-term session messages, long-term extracted facts, hybrid retrieval, and clean scoping across users and agent roles — without standing up a separate vector DB service on free tier.

### Scoping

```
owner_id   = user id
agent_id   = "guide" | "trainer"
session_id = workout session id  |  planning session id
```

Guide and Trainer each build role-appropriate memory while sharing the same user (`owner_id`). That keeps planning context and live-logging context from contaminating each other, while handoff summaries still reach Guide.

### Usage pattern per chat turn

1. Resolve mode from state + router.  
2. Load memory context for that `agent_id` (recent turns + relevant long-term facts).  
3. Agent responds with tools.  
4. Write structured data to SQLite.  
5. Append the turn to memory so facts can be extracted for later retrieval.

### What belongs where

| Memory layer (semantic) | SQLite (exact) |
|-------------------------|----------------|
| Goals, preferences, constraints | Programs / days / exercises |
| “Hit all top sets”, shoulder twinge | Set rows (weight, reps, notes) |
| Handoff narratives | Session status, timestamps |
| Cross-session recall | Editable history source of truth |

**Do not** dump every set as a memory fact; store sets in SQL; memory holds meaning and continuity.

---

## Auth & multi-user

| v1 | Later |
|----|-------|
| Email + password register / login / logout | OAuth (Google/Apple/etc.) |
| JWT or HTTP-only session cookie | Magic links |
| Per-user data isolation | Teams / coach seats |
| Open signup (no marketing assumed) | Email verification / password-reset polish (optional if time) |

`GET /me` returns current user (id, email, unit preference, etc.).

---

## Frontend (simple TypeScript)

Keep it simple and understandable — correct over fancy.

### Screens

1. **Auth** — register / login (email + password).  
2. **App shell** — continuous chat, mode chip, Start / End / Cancel.  
3. **Session strip** (when live) — planned lifts + logged sets.  
4. **History** — list past sessions → open one → **sets table** (exercise, set #, weight, unit, reps, notes, time) → **edit/delete** rows.  
5. Chat pagination — **Load earlier messages**.

No marketing landing required; the app is the hosted product.  
Raw AWS URL fine until a domain exists; then HTTPS (Caddy/nginx + Let’s Encrypt).

---

## Data model (minimum)

### `users`
- `id`, `email` (unique), `password_hash`, `unit_preference` (`kg`|`lbs`), `created_at`

### `programs` / `program_days` / `planned_exercises`
- Plan through user-chosen end date  
- Planned exercise: `raw_name`, `canonical_name`, `normalized_key`, targets (sets/reps/notes as applicable), day/date linkage

### `workout_sessions`
- `id`, `user_id`, `status` (`active`|`completed`|`cancelled`), `started_at`, `ended_at`, optional summary text

### `set_logs`
- `id`, `session_id`, `user_id`  
- `raw_name`, `canonical_name`, `normalized_key`  
- `set_index`, `weight`, `unit`, `reps`, `notes` (nullable), `created_at`, `updated_at`

### `chat_messages`
- Persist for UI reload / pagination (`user_id`, `role`, `content`, `mode`, `created_at`, …)

---

## API surface (v1)

### Auth
- `POST /auth/register`  
- `POST /auth/login`  
- `POST /auth/logout`  
- `GET /me`

### Program
- `GET /program` — current plan  
- `PUT /program` — replace/update plan (also used by Guide tools)

### Sessions
- `POST /sessions/start`  
- `POST /sessions/{id}/complete`  
- `POST /sessions/{id}/cancel`  
- `GET /sessions/active`  
- `GET /sessions` — recent list  
- `GET /sessions/{id}` — detail + sets (history table)

### Sets
- `POST /sessions/{id}/sets` — create (Trainer tools use same domain)  
- `PATCH /sets/{id}` — edit (history corrections)  
- `DELETE /sets/{id}`

### Chat
- `POST /chat` — message in; Guide/Trainer out (JSON or SSE)  
- `GET /chat/messages` — paginated history (`before` cursor / Load earlier)

### Ops
- `GET /health`

---

## LangGraph-shaped orchestration (conceptual)

```text
START
  → load_user_state (active session?, program?, memory context)
  → route_intent
      ├─ (if workout_active or intent=log/start/end/cancel) → trainer_node
      └─ else → guide_node
  → persist_sql
  → cognis_add
  → END (response + ui_hints: mode, active_session, …)
```

Shared tools (examples):
- `start_workout`, `complete_workout`, `cancel_workout`
- `log_sets`, `get_today_plan`, `upsert_program`
- `resolve_exercise_name`
- `swap_exercise_today` (light Trainer swap only)

Typed state should include at least: `user_id`, `message`, `mode`, `active_session_id`, `intent`, `assistant_reply`, `ui_hints`, `tool_results`.

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Backend | FastAPI (Python only) | Async, clear API, matches ReviewMesh learning path |
| Agents | LangGraph (router + Guide + Trainer) | Explicit state machine; clear multi-agent roles |
| Validation | Pydantic | Request/response + structured LLM output |
| LLM (primary) | **Groq** | Fast/cheap inference for router + agents |
| LLM (optional later) | OpenAI | Fallback / upgrade; not required to start |
| Memory | Cognis (OSS, local) | Persistent short/long-term memory with user + agent scoping; no extra managed vector service |
| DB | SQLite on disk | Free-tier friendly system of record |
| Frontend | Simple TypeScript (Vite/React or similar) | Hostable SPA; keep UI thin |
| Deploy | Docker Compose on AWS EC2 t2/t3.micro | Free tier; nginx serves SPA + proxies API |
| HTTPS | Later with domain | Let’s Encrypt when domain exists |

**AWS v1 layout:** single EC2, Compose services `api` + `web` (or api + nginx static), SQLite + memory data on EBS. Avoid RDS/ECS/ALB for v1.

---

## Scope Boundaries

| ✅ IN (v1) | ❌ OUT (v2+) |
|-----------|-------------|
| Email + password auth | OAuth |
| Open signup | Marketing site, teams |
| Single continuous chat + load earlier | Separate Guide/Trainer chat UIs |
| Mode chip + session state machine | Dual-agent studio timeline (product shape “2”) |
| Manual Start / End / Cancel + same via tools | Wearables, voice, camera form check |
| Guide intake (goals + end date) then plan | Auto periodization engine |
| Paste/type existing plan | Template marketplace |
| Trainer NL logging (weight, reps, notes, unit) | RPE, failure, rest timers |
| Free-text exercises + LLM canonicalization | Global exercise DB / muscles |
| kg + lbs preference / entry | Plate calculator, etc. |
| Complete → memory handoff → Guide | Mid-workout full Guide replan |
| Light same-day exercise swap (Trainer) | Multi-active sessions |
| History list + **individual session table** | Cross-session **analytics / charts / PR dashboards** |
| Edit/delete sets in history | Social / sharing |
| Local agent memory on EC2 (Cognis OSS) | Separate managed vector DB / memory SaaS required |
| Groq primary | Multi-provider playground UI |
| SQLite + single EC2 Docker deploy | RDS, Fargate, complex AWS |
| Simple TS frontend that works | Native mobile app (PWA later) |
| Finish the product | Seeded demo account as ship requirement |

---

## Acceptance criteria (v1 is done when)

1. New user can **register with email** and log in on the hosted URL.  
2. Guide can **intake goals + end date** and produce a plan through that date, **or** accept a pasted/typed plan.  
3. User can **manually start** a workout; chip shows Trainer live; controls match state.  
4. User can log sets in NL; rows appear in **session strip** and SQLite with canonical exercise names.  
5. User can **manually end** workout → summary persisted → Guide follow-up using that context.  
6. User can also start/end via **chat tools**; UI stays in sync.  
7. **Cancel** ends without full handoff.  
8. **History**: list sessions → open one → see sets table → **edit/delete** a mistaken set.  
9. Chat supports **Load earlier messages**.  
10. After logout/login later, Guide still uses memory + SQL history (not a blank slate).  
11. Users cannot see each other’s data.  
12. App runs on **AWS free-tier** with DB + memory data on disk.

---

## Build Slices (do in order)

1. **Project skeleton** — backend package, frontend app, env example, gitignore, Docker Compose stub  
2. **Config** — Groq key, memory data dir, JWT secret, DB path  
3. **Health API** — `GET /health`  
4. **DB models + migrations/schema** — users, program*, sessions, set_logs, chat_messages  
5. **Auth** — register / login / logout / `GET /me` (email + password)  
6. **Program CRUD API** — get/put current plan  
7. **Session API** — start / complete / cancel / active / list / detail  
8. **Sets API** — create / patch / delete + wire to session detail table  
9. **Exercise resolver** — history match + Groq canonicalization  
10. **Frontend auth + shell** — login/register, empty chat layout, mode chip placeholders  
11. **Frontend session controls** — Start/End/Cancel calling REST; session strip  
12. **Frontend history** — list + detail table + edit/delete  
13. **Chat persistence + pagination** — store messages; Load earlier  
14. **LLM client** — Groq chat + structured JSON helper  
15. **Memory wiring** — init local Cognis, add / get_context / search with user + agent + session scoping  
16. **Trainer node + tools** — log sets, start/complete/cancel, light swap  
17. **Guide node + tools** — intake, upsert plan, accept pasted plan, post-handoff follow-up  
18. **Router + LangGraph** — state machine; hard state beats intent  
19. **`POST /chat`** — end-to-end Guide/Trainer with ui_hints  
20. **Handoff path** — complete → summary → memory → Guide reply  
21. **Hardening** — auth on all routes, one-active-session enforcement, errors, basic rate limits  
22. **Docker + EC2 deploy** — Compose, nginx, EBS paths for SQLite + memory data  
23. **README** — architecture, memory vs DB split, how to run, how to walk the full loop  

**Ship cut line:** slices 1–20 + 22. Do 21 and 23 before calling it portfolio-ready.

---

## Design highlights (worth explaining)

- Multi-agent **roles** behind a **single chat**, with an explicit **session state machine**.  
- **Memory scoped by user + agent role + session** so Guide and Trainer don’t contaminate each other, while handoff summaries still reach Guide.  
- **Memory vs system of record** — semantic continuity in the memory layer; editable, exact sets in SQL.  
- Tools + deterministic session APIs so **buttons and agents cannot diverge**.  
- LLM used for routing, planning, parsing, and **name normalization** — not as the database.  
- Deployed, multi-user, email-auth product on AWS free tier — not a notebook demo.

---

## Locked decisions (do not reopen without explicit change)

| Topic | Decision |
|-------|----------|
| Product shape | Session companion now; dual-agent studio later |
| Chat | One continuous thread; today-first; load earlier |
| Mid-workout Guide | No full replan; Trainer-only + light same-day swap |
| Session control | Manual UI **and** tools; same backend |
| Auth | Email + password; OAuth later |
| Signup | Open |
| Planning | Goals + end date intake, or paste/type plan |
| Logging fields | Weight, reps, notes, unit — no RPE |
| Exercises | Free text + LLM canonicalization; per-user history match first |
| Units | kg and lbs |
| History | Individual session table; editable sets; analytics later |
| Memory | Local agent memory on EC2 (Cognis OSS) |
| LLM | Groq primary |
| Backend | Python only |
| Frontend | Simple TypeScript |
| Host | AWS free-tier single EC2; domain/HTTPS when ready |
| Demo seed | Not a ship requirement; finish the product |

---

## v2+ backlog (explicitly not now)

- Dual visible agent panels / activity studio  
- OAuth  
- In-depth cross-session analytics, charts, PR dashboards  
- Mid-workout full Guide replanning  
- Exercise taxonomy / muscle maps  
- RPE / failure / rest  
- PWA / native mobile  
- Swap memory backend (hosted API or other providers) behind the same interface  
- Password reset / email verification polish  
- Seeded demo account (optional later)
