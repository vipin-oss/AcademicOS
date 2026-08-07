# AcademicOS — Installation & Quickstart (Windows / Linux / macOS)

AcademicOS is a two-process application: a FastAPI backend (Python 3.11+)
and a Next.js frontend (Node 18+). Everything below works identically on
Windows (PowerShell), Linux and macOS.

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
   Create the database and start the server:
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
