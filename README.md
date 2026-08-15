# AcademicOS

The Academic Operating System — an object-centric knowledge graph platform
for academic institutions: students, teaching, research, publications,
faculty, committees, finance, events, documents, intake, reports, and a
grounded AI assistant.

## Release status

**Active branch: `feature/ai-knowledge-projection-p0` (frozen baseline
`07c434cad05ae87db741c191cc914625801147ea`).** Architecture is frozen at
**L0** — see [`docs/architecture/`](docs/architecture/) (Part 13 Freeze
Contract, level register, ADR-019…022, capability evaluation). Do not add
regexes, intents, or answer builders for failed questions.

M1–M25 delivered: object-centric knowledge graph, documents + intake with
human review, ERP modules (students, teaching, research, grants,
publications, faculty, committees, finance, events, reports, productivity,
settings), global hybrid search, and the AI layer (AI Core, grounded QA,
chat, summarization, enrichment, related documents, external handoff, and
the M21–M25 domain assistants).

Status legend used throughout this repository:

- **IMPLEMENTED** — shipped, tested, and exercised by the runtime.
- **PARTIAL** — implemented for the documented slice; the rest is PLANNED.
- **PLANNED** — designed (spec/blueprint) but not built.
- **DEFERRED** — consciously postponed; see `docs/` for the roadmap.

`main` is intentionally frozen at M10-era state; all milestone work lands on
the feature branch and is verified by CI before merge. Historical release
documents live in `docs/archive/`.

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

> **Environment file.** The backend reads `backend/.env` (anchored to the
> repository, never to the process CWD — M26). Start uvicorn from
> `backend/` or set `ACADEMICOS_ENV_FILE` explicitly; starting from the repo
> root silently skips the file and every AI feature flag falls back to OFF.

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
| Auth | JWT (access + refresh), bcrypt, role-based access + object-level ACL |
| Storage | Local filesystem adapter (Google Drive / OneDrive slots reserved) |
| AI | Provider-independent AI Core (`LanguageModelGateway` port) · OpenAI-compatible adapter (httpx, no SDKs) · local/free AI via Ollama · grounded QA/chat · summarization · enrichment · related documents · domain assistants (research/teaching/publication/administration) · external-AI handoff |

## AI layer (M11–M25) — IMPLEMENTED

AcademicOS's AI Core is the single authority for provider/model/config/
credentials/selection and runtime execution (ADR-001): a provider-id-keyed
catalogue built from `AI_PROVIDERS_JSON`, one real OpenAI-compatible adapter
(any local or cloud endpoint — Ollama, vLLM, LM Studio — works with no API
key), honest placeholders for other kinds, and a three-state health surface
(configured / executable / operational).

Capabilities (each gated by its own feature flag in `backend/.env.example`):

- `POST /ai/summarize` — document summarization with provenance
- `POST /ai/enrich` — structured metadata extraction (title/summary/tags)
- `POST /ai/qa` + `/ai/qa/stream` — grounded QA with verified citations
- `GET /ai/related` — related documents over the semantic index
- `POST /ai/chat` + `/ai/chat/stream` — conversational grounded chat
- `GET /ai/assistants`, `POST /ai/assistants/{role}` + `/stream` —
  M21–M25 domain assistants (research, teaching, publication, administration)
- `POST /ai/handoff` — grounded prompt bundle for external AI (no provider
  required; works with AI disabled)
- `GET /ai/health`, `/ai/providers`, `/ai/models` — the health surface
- UI: **Academic AI** workspace (`/ai`, sidebar "Academic AI") with five
  modes — General, Research, Teaching, Publication, Administration — and
  **Settings → AI Settings**

The deterministic **Academic Intelligence Assistant** (`/assistant`) is a
separate, non-LLM capability: rules-based answers over your live AcademicOS
data with links back to every module, plus conversation memory, a human
review queue and evaluation history. It works with no AI provider configured
and is reachable from the Academic AI workspace.

All LLM generation is grounded in the caller's readable documents,
permission-filtered, citation-verified, and honestly degraded (no provider →
`available=false` fallback). Human review exists for intake commits;
AI-proposed graph relationships (SMART_LINK — "AI proposes, human approves",
`POST /objects/{id}/links/propose` → `.../approve` | `.../reject`) are
implemented as M28 — see `docs/M28_SMART_LINK_PLAN.md`.

**Search (M27):** the global search (`/search`, header box) is hybrid lexical +
semantic over titles, metadata, and — since M27 — the extracted text of
committed documents (`document_contents` projection, written at intake
commit, rebuildable via `POST /search/content/rebuild`, removed on document
deletion, permission-filtered through the same gate as every other hit).
Document content is a derived projection; the extracted-text blob remains
authoritative. SQLite quickstart users: `python scripts/init_db.py` creates
the new table (stamp 0009); existing databases need `alembic upgrade head`.

## Repository Layout

```
academicos/
├── backend/        # FastAPI service (Clean Architecture)
│   ├── alembic/    # Migrations 0001..0008
│   ├── app/        # api / application / domain / infrastructure
│   │   ├── application/ai + infrastructure/ai   # AI Core (M11.1+)
│   │   └── tests/  # unit + integration + architecture guardrails
│   ├── scripts/    # init_db.py (SQLite quickstart), seed_regression.py
│   └── README.md   # backend architecture overview
├── frontend/       # Next.js client (App Router, src/)
│   ├── src/app/    # (auth)/ + (main)/ route groups (incl. /ai, /search, /settings/ai)
│   ├── src/lib/    # api clients, auth session, constants
│   ├── e2e/        # Puppeteer browser suites (npm run test:e2e)
│   └── tests/      # vitest setup
├── .github/workflows/ci.yml  # pytest + vitest + tsc + build on push
├── docker-compose.yml   # PostgreSQL + Qdrant + Ollama (infrastructure only)
├── INSTALL.md      # Windows/Linux/macOS installation guide
├── docs/           # roadmap + archive of historical release documents
└── *.md            # Product/architecture specifications (see status legend)
```

## Verification

- Backend: `cd backend && python -m pytest -q` (SQLite test DB; 1600+ tests)
- Backend architecture guardrails: `cd backend && python -m pytest app/tests/architecture -q`
- Frontend: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
- Browser e2e: `cd frontend && npm run test:e2e` (requires running backend + `next start`)
- CI: every push runs the full suite (`.github/workflows/ci.yml`); no green
  CI = no claim of a verified milestone.
- Backend boots with `uvicorn app.main:app`; health at
  `http://127.0.0.1:8000/api/v1/health`

Milestone history and verification numbers: `CHANGELOG.md`. Engineering
decisions: `AI_DEVELOPER_GUIDE.md` and `docs/`.

---

## Windows Development Automation (one-command startup)

AcademicOS ships one-command PowerShell tooling for Windows 10/11
(PowerShell 5.1+). **The canonical way to run the whole stack is one command
from the repository root:**

```powershell
cd E:\AcademicOS
.\start_academicos.ps1
```

That single command verifies the environment, starts **Ollama** (pulling the
configured model if missing), runs database migrations, starts the **backend**
(`uvicorn` on http://127.0.0.1:8000) and the **frontend** (Next.js dev server),
waits for real HTTP readiness (not just "process exists"), verifies the backend
can actually reach Ollama, and opens the app in your browser. Re-running it
while everything is up reuses the healthy services instead of piling up
duplicates.

To stop only what the startup system launched (never PostgreSQL, never
pre-existing processes):

```powershell
.\stop_academicos.ps1
```

| Command | Purpose |
|---|---|
| `.\start_academicos.ps1` | **One-command startup**: environment checks → Ollama (+ model) → PostgreSQL/Docker/Qdrant → deps + migrations → backend → AI/Ollama connectivity check → frontend → browser. Options: `-NoOpenBrowser`, `-SkipDocker`, `-SkipOllama` |
| `.\stop_academicos.ps1` | Stop ONLY the backend/frontend/Ollama processes this system launched (PID-tracked). PostgreSQL and unrelated processes are never touched. `-KeepQdrant` leaves the Qdrant container running |
| `.\health.ps1` | PASS/FAIL for PostgreSQL, DB connection, Docker, Qdrant, backend, frontend, storage, Alembic, node_modules, Python packages |
| `.\start.ps1` / `.\stop.ps1` | Legacy aliases (delegate to the same `scripts\windows\*.ps1`); kept for compatibility |
| `scripts\windows\reset_academicos.ps1` | Interactive menu (frontend / backend / database / Qdrant / everything) with confirmation |
| `scripts\windows\validate_environment.ps1` | Detect missing Python / Node / npm / Docker / PostgreSQL / Git / ports / deps with fix instructions |

### First-time setup

1. Install Python 3.11+, Node 18+ LTS, Docker Desktop, Git, and
   [Ollama](https://ollama.com) (see `validate_environment.ps1`).
2. `.\validate_environment.ps1` — resolves any missing tooling.
3. `.\start_academicos.ps1` — provisions everything (installs deps, initialises
   the DB, pulls the Ollama model, starts services) and opens the app.

### Daily startup

```
.\start_academicos.ps1
```

### Daily shutdown

```
.\stop_academicos.ps1
```

### Health check

```
.\health.ps1
```

### Troubleshooting

- **Backend won't start** — `$env:TEMP\academicos_backend.out.log` / `.err.log`
- **Frontend won't start** — `$env:TEMP\academicos_frontend.out.log` / `.err.log`
- **Qdrant unreachable** — `docker start academicos-qdrant` (or re-run `.\start_academicos.ps1`)
- **Ollama not running** — the startup script reports this and attempts to
  start `ollama serve`. If Ollama is installed elsewhere, start it manually and
  re-run. Model missing → the script runs `ollama pull <model-from-.env>`.
- **AI flags ignored / assistants "not enabled" despite `.env`** — the backend
  was started from a directory other than `backend/` (the env file is anchored
  to `backend/.env`; starting from the repo root silently skips it). Start
  from `backend/`, or set `ACADEMICOS_ENV_FILE`, then restart the process.
  (`start_academicos.ps1` starts uvicorn from `backend/`, so this is handled.)
- **Ports in use** — stop other dev servers; `stop_academicos.ps1` clears the
  backend/frontend ports it owns (8000/3000)
- **DB reset** — `scripts\windows\reset_academicos.ps1` (option 3)
