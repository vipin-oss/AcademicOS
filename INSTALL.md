# AcademicOS — Installation & Quickstart (Windows / Linux / macOS)

AcademicOS is a two-process application: a FastAPI backend (Python 3.11+)
and a Next.js frontend (Node 18+). Everything below works identically on
Windows (PowerShell), Linux and macOS.

---

## One-command startup (Windows)

On Windows 10/11 (PowerShell 5.1+), the entire stack — Ollama (+ the
configured model), database migrations, backend, frontend, and browser — is
brought up with **one command** from the repository root:

```powershell
cd E:\AcademicOS
.\start_academicos.ps1
```

What it does, in order:

1. **Environment checks** — Python 3.11+, Node/npm, backend/frontend dirs,
   backend venv (prefers `backend\.venv` when present).
2. **Ollama** — checks `http://127.0.0.1:11434/api/tags`; starts `ollama serve`
   if installed but not running; verifies the model named in
   `AI_PROVIDERS_JSON` is present and `ollama pull`s it if missing.
3. **Backend config** — reads `backend/.env` (never overwrites it) and reports
   the active AI provider's `base_url`/model.
4. **PostgreSQL** — started if a `postgresql*` service exists (reused if
   already running).
5. **Docker Desktop / Qdrant** — the script reuses an already-ready Docker
   daemon. If the daemon is down it discovers Docker Desktop (running process
   → registry → `Program Files` / `Program Files (x86)` / `%LOCALAPPDATA%` →
   `PATH`), starts it if it is not already running (never launches a second
   copy), and **polls `docker info` for up to 180s** — Docker Desktop can take
   30–120s to boot its Linux engine. Progress is shown as
   `Docker Desktop not running -> starting` … `Waiting for Docker daemon...`
   … `Docker daemon ready`. If Docker Desktop is not installed, or the daemon
   never comes up, the script prints one concise actionable message and
   continues without Qdrant (vector search then runs lexical-only). Skippable
   with `-SkipDocker`.
6. **Dependencies + migrations** — `pip install -r requirements.txt` and
   `npm install` only when missing; runs `init_db.py` (SQLite) or
   `alembic upgrade head` (PostgreSQL).
7. **Backend** — `uvicorn app.main:app` on http://127.0.0.1:8000, then waits
   for `GET /api/v1/health` → HTTP 200, `GET /api/v1/ai/health` → configured
   provider, and `GET /api/v1/health/ready` → AI model resident (i.e. the
   backend actually reached Ollama).
8. **Frontend** — `npm run dev`, detects the actual port it bound (default
   3000), waits for HTTP 200.
9. **Browser** — opens the frontend (only when it was actually started by this
   run, so repeated runs don't stack browser windows).

Stop only what the startup system launched:

```powershell
.\stop_academicos.ps1
```

Useful switches: `.\start_academicos.ps1 -NoOpenBrowser`, `-SkipDocker`,
`-SkipOllama`. For a PASS/FAIL health report run `.\health.ps1`. The manual
instructions below remain available for running backend/frontend
independently.

---

## Option A — SQLite quickstart (zero infrastructure, fastest)

1. **Backend**
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1        # Windows
   # source .venv/bin/activate         # Linux / macOS
   pip install -r requirements.txt
   Copy-Item .env.example .env         # Windows: copy .env.example .env
   ```
   Edit `.env` and set:
   ```
   DATABASE_URL=sqlite:///./academicos.db
   JWT_SECRET=change-me-to-a-long-random-string
   ```
   Create the database and start the server (stay in `backend/` — the env
   file is anchored to `backend/.env`, not the process CWD; starting from
   the repo root silently skips it and every AI flag falls back to OFF):
   ```powershell
   python scripts/init_db.py
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   Health check: http://127.0.0.1:8000/api/v1/health

2. **Frontend**
   ```powershell
   cd ..\frontend
   npm install
   Copy-Item .env.example .env.local   # optional; defaults already work
   npm run dev
   ```
   Open **http://127.0.0.1:3000** (or http://localhost:3000 — both are
   CORS-allowed). Register an account on the sign-up page, sign in, done.

## Option B — PostgreSQL + Qdrant (full stack)

1. `docker compose up -d db qdrant` (or install PostgreSQL 16 locally).
2. Backend `.env`:
   ```
   DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/academicos
   QDRANT_URL=http://localhost:6333
   ```
3. Run migrations: `alembic upgrade head`
4. Start backend + frontend exactly as in Option A.

## Notes

- **First admin**: after registering a user, set
  `BOOTSTRAP_ADMIN_USERNAME=<that-username>` in `backend/.env` and restart
  the backend once — the account is promoted to ADMIN idempotently.
- **Password reset**: no email gateway ships in this release; the reset
  token is returned by `POST /auth/forgot-password` in the response body
  (see the reset-password page flow).
- **LLM assistant**: the assistant works out of the box with the
  deterministic rules provider. To use an OpenAI-compatible endpoint, set
  `ASSISTANT_MODELS_JSON` (see `.env.example`).
- **Windows**: the frontend defaults to the IPv4 literal
  `http://127.0.0.1:8000/api/v1` to avoid `localhost` → `::1` resolution
  mismatches; the backend binds `127.0.0.1` and CORS allows
  `localhost`, `127.0.0.1` and `[::1]` on port 3000.
