# AcademicOS — Project Structure

Monorepo skeleton for **AcademicOS**, the Academic Operating System. This
repository currently contains **folder structure only** — no business logic,
no framework configuration files yet. The architecture documents
(`AcademicOS_SRS.md`, `AcademicOS_UI_Spec.md`, `AcademicOS_AI_Architecture.md`)
define the requirements this code structure is built to satisfy.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (latest, App Router) · React · TypeScript · TailwindCSS · ShadCN |
| Backend | FastAPI · Python |
| Relational DB | PostgreSQL |
| Vector DB | Qdrant |
| Auth | JWT |
| Storage | Local Storage · Google Drive · OneDrive |

## Architectural Principles

- **Clean Architecture** — dependencies point inward; the domain knows nothing
  about frameworks.
- **Repository Pattern** — domain defines repository *interfaces*; infrastructure
  provides the *implementations* (PostgreSQL, Qdrant).
- **SOLID** — single-responsibility modules, open/closed boundaries between
  layers, interface-segregated ports, dependency inversion via DI containers.

## Top-Level Layout

```
academicos/
├── frontend/      # Next.js client (presentation + state)
├── backend/       # FastAPI service (Clean Architecture)
├── docs/          # Additional developer documentation
└── *.md           # Product/architecture specifications
```

## Backend — Clean Architecture Layers

```
backend/app/
├── domain/            # Enterprise business rules (innermost)
│   ├── entities/         # Plain domain models
│   ├── value_objects/    # Immutable typed values
│   ├── repositories/     # ABSTRACT repository interfaces (ports)
│   └── services/         # Pure domain services
├── application/       # Use cases / application business rules
│   ├── use_cases/        # One use case per feature (auth, documents, …)
│   ├── services/         # Application-level orchestration
│   ├── dtos/             # Data transfer objects / request-response shapes
│   └── ports/            # Interfaces the app layer depends on
├── api/               # Interface adapters (outermost, frameworks)
│   ├── routes/           # FastAPI routers (controllers)
│   ├── dependencies/     # DI wiring (DB sessions, auth, repos)
│   └── middleware/        # Cross-cutting HTTP middleware
├── infrastructure/    # Frameworks & drivers (outermost)
│   ├── db/               # PostgreSQL: ORM models + session
│   ├── repositories/     # CONCRETE repository implementations
│   ├── vector_db/        # Qdrant client + collections
│   ├── auth/             # JWT issuing/verifying
│   ├── storage/          # local / google_drive / onedrive adapters
│   ├── ai/               # AI provider integrations
│   └── external/         # Other 3rd-party clients
├── core/              # Cross-cutting: config, logging, exceptions
└── tests/             # unit / integration / e2e
```

**Dependency rule:** `api` → `application` → `domain`; `infrastructure` →
`domain`/`application` (through interfaces only). `domain` never imports
`infrastructure`.

## Frontend — Feature-First Structure

```
frontend/src/
├── app/               # Next.js App Router
│   ├── (auth)/           # Route group: unauthenticated screens
│   ├── (main)/           # Route group: authenticated app (one folder per screen)
│   └── api/              # Optional BFF route handlers
├── components/
│   ├── ui/               # ShadCN primitives (generated)
│   ├── layout/           # Sidebar / Topbar / Shell
│   ├── common/           # Shared widgets
│   └── features/         # One folder per screen/module
├── lib/
│   ├── api/              # Typed API client
│   ├── auth/             # JWT storage + refresh
│   ├── storage/          # Local / Google Drive / OneDrive clients
│   └── utils/            # Helpers
├── hooks/             # React hooks
├── stores/            # Client state (e.g. Zustand)
├── types/             # Shared TypeScript types
├── config/            # Environment / runtime config
└── styles/            # Tailwind / global styles
```

## Next Steps (not yet done)

- Framework config scaffolding (`package.json`, `tsconfig.json`,
  `next.config`, `tailwind.config`, `requirements.txt`, `pyproject.toml`,
  `alembic.ini`).
- Domain entities, DTOs, and repository interfaces.
- Feature implementations following the use-case-per-folder convention.
