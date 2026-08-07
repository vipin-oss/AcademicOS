# AcademicOS

The Academic Operating System — an object-centric knowledge graph platform
for academic institutions: students, teaching, research, publications,
faculty, committees, finance, events, documents, intake, reports, and a
grounded AI assistant.

## Quickstart

Follow **[INSTALL.md](INSTALL.md)** — a fresh Windows/Linux/macOS machine
can be up in minutes:

```powershell
# Backend (SQLite quickstart — zero infrastructure)
cd backend
pip install -r requirements.txt
copy .env.example .env          # set DATABASE_URL=sqlite:///./academicos.db
python scripts/init_db.py
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd ..\frontend
npm install
npm run dev                     # http://127.0.0.1:3000  → register → sign in
```

Full-stack (PostgreSQL + Qdrant) instructions, Docker Compose for the
infrastructure services, and configuration reference are in `INSTALL.md`
and `backend/.env.example`.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router) · React 18 · TypeScript · TailwindCSS |
| Backend | FastAPI · Python 3.11+ · Clean Architecture (domain / application / infrastructure) |
| Relational DB | PostgreSQL 16 (SQLite supported for local quickstart) |
| Vector DB | Qdrant (optional — search degrades to lexical-only) |
| Auth | JWT (access + refresh), bcrypt, role-based access |
| Storage | Local filesystem adapter (Google Drive / OneDrive slots reserved) |

## Repository Layout

```
academicos/
├── backend/        # FastAPI service (Clean Architecture)
│   ├── alembic/    # Migrations 0001..0007
│   ├── app/        # api / application / domain / infrastructure
│   ├── scripts/    # init_db.py (SQLite quickstart), seed_regression.py
│   └── tests/      # unit + integration + architecture guardrails (1200+)
├── frontend/       # Next.js client (App Router, src/)
│   ├── src/app/    # (auth)/ + (main)/ route groups
│   ├── src/lib/    # api clients, auth session, constants
│   └── tests/      # vitest unit tests + scripted e2e flows
├── docker-compose.yml   # PostgreSQL + Qdrant for the full stack
├── INSTALL.md      # Windows/Linux/macOS installation guide
└── *.md            # Product/architecture specifications
```

## Verification

- Backend: `cd backend && python -m pytest -q` (SQLite test DB)
- Frontend: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
- Backend boots with `uvicorn app.main:app`; health at
  `http://127.0.0.1:8000/api/v1/health`

See `AcademicOS_Execution_Roadmap.md` for the delivery history and
`AcademicOS_Engineering_Review.md` for engineering decisions.
