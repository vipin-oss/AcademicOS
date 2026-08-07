# AcademicOS

The Academic Operating System — an object-centric knowledge graph platform
for academic institutions: students, teaching, research, publications,
faculty, committees, finance, events, documents, intake, reports, and a
grounded AI assistant.

## Release status

**M10 Release Candidate 1 (RC1)** — feature-frozen, production hardening
only. See **[FINAL_RELEASE_NOTES.md](FINAL_RELEASE_NOTES.md)** for the
full release statement, verification results, and the list of improvements
deferred to Sprint M11.

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
| AI Core (M11.1) | Provider-independent `LanguageModelGateway` port · provider registry (OpenAI / Anthropic / Google / Ollama / Local placeholders) · health API · no LLM calls yet |

## AI Foundation (Sprint M11.1)

AcademicOS's AI Core is in place as **infrastructure only**: a
provider-independent gateway port, a provider registry with five honest
"Not Configured" placeholders, central AI configuration, and a JSON
health surface.

- `GET /api/v1/ai/health` — aggregate AI health (public)
- `GET /api/v1/ai/providers` — provider catalogue (authenticated)
- `GET /api/v1/ai/models` — model catalogue (authenticated)
- UI: **Settings → AI Settings** (`/settings/ai`)

No generation, chat, RAG, memory, agents or embeddings exist yet — every
capability flag is OFF and no LLM is called. Future sprints add providers
by implementing only an adapter (see `AI_DEVELOPER_GUIDE.md`).

Configuration lives in `backend/.env.example` under the `AI_*` keys
(`AI_PROVIDERS_JSON`, `AI_DEFAULT_PROVIDER`, feature flags, …).

## Repository Layout

```
academicos/
├── backend/        # FastAPI service (Clean Architecture)
│   ├── alembic/    # Migrations 0001..0008
│   ├── app/        # api / application / domain / infrastructure
│   │   └── application/ai + infrastructure/ai   # AI Core (M11.1)
│   ├── scripts/    # init_db.py (SQLite quickstart), seed_regression.py
│   └── tests/      # unit + integration + architecture guardrails (1300+)
├── frontend/       # Next.js client (App Router, src/)
│   ├── src/app/    # (auth)/ + (main)/ route groups (incl. /settings/ai)
│   ├── src/lib/    # api clients, auth session, constants
│   └── tests/      # vitest unit tests + scripted e2e flows
└── AI_DEVELOPER_GUIDE.md  # how to add an AI provider / capability
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

---

## Windows Development Automation (Sprint M10.1)

AcademicOS ships one-command PowerShell tooling for Windows 10/11
(PowerShell 5.1+). From the project root:

| Command | Purpose |
|---|---|
| `.\start.ps1` | Verify/start PostgreSQL, Docker Desktop + Engine, Qdrant; install missing deps; run migrations; start backend + frontend; open http://localhost:3000 |
| `.\stop.ps1` | Gracefully stop backend + frontend (+ optional Qdrant container). PostgreSQL is never touched |
| `.\health.ps1` | PASS/FAIL for PostgreSQL, DB connection, Docker, Qdrant, backend, frontend, storage, Alembic, node_modules, Python packages |
| `.\apply_patch.ps1 AcademicOS_M11_Patch.zip` | Apply an incremental patch ZIP with backup, extract, replace, manifest-deleted files, conflict detection, summary + exit code |
| `scripts\windows\reset_academicos.ps1` | Interactive menu (frontend / backend / database / Qdrant / everything) with confirmation |
| `scripts\windows\validate_environment.ps1` | Detect missing Python / Node / npm / Docker / PostgreSQL / Git / ports / deps with fix instructions |

### First-time setup

1. Install Python 3.11+, Node 18+ LTS, Docker Desktop, Git (see `validate_environment.ps1`).
2. `.\validate_environment.ps1` — resolves any missing tooling.
3. `.\start.ps1` — provisions everything (installs deps, initialises the DB,
   starts services) and opens the app.

### Daily startup

```
.\start.ps1
```

### Daily shutdown

```
.\stop.ps1
```

### Applying future patches

```
.\apply_patch.ps1 AcademicOS_M11_Patch.zip
```

The script backs up every replaced file, extracts the patch preserving
paths, applies it, deletes obsolete files from `PATCH_MANIFEST.md`, prints
Added / Modified / Deleted / Failed counts, and exits 0 on success (non-zero
on failure). Run `cd frontend && npm install` and `cd backend && alembic
upgrade head` when the manifest reports new dependencies or migrations.

### Health check

```
.\health.ps1
```

### Troubleshooting

- **Backend won't start** — `$env:TEMP\academicos_backend.log`
- **Frontend won't start** — `$env:TEMP\academicos_frontend.log`
- **Qdrant unreachable** — `docker start academicos-qdrant` (or re-run `.\start.ps1`)
- **Ports in use** — stop other dev servers; `stop_academicos.ps1` clears 8000/3000
- **DB reset** — `scripts\windows\reset_academicos.ps1` (option 3)
