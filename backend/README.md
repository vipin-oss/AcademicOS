# Backend — AcademicOS (FastAPI)

Folder skeleton only. No business logic or configuration yet.

Implements **Clean Architecture** with the **Repository Pattern** and **SOLID**
principles. Dependency direction is strictly inward:

```
api ──▶ application ──▶ domain ◀── infrastructure
```

- `domain/` holds enterprise rules and **abstract** repository interfaces.
- `application/` holds use cases; depends only on `domain` abstractions.
- `api/` adapts HTTP (FastAPI routers, dependencies, middleware).
- `infrastructure/` provides concrete adapters (PostgreSQL, Qdrant, JWT, storage).

## Layer Responsibilities

| Folder | Responsibility |
|---|---|
| `domain/entities` | Core business objects (User, Document, Space, Tag, …) |
| `domain/repositories` | Abstract repository **ports** (e.g. `DocumentRepository`) |
| `domain/services` | Pure domain logic with no I/O |
| `application/use_cases` | One use case per feature group |
| `application/ports` | Interfaces the application layer requires |
| `application/dtos` | Input/output data shapes |
| `api/routes` | FastAPI routers (auth, documents, search, ai, storage) |
| `api/dependencies` | DI: DB sessions, auth context, repository wiring |
| `infrastructure/db` | PostgreSQL ORM models + session factory |
| `infrastructure/repositories` | Concrete repository implementations |
| `infrastructure/vector_db` | Qdrant client + collection management |
| `infrastructure/auth` | JWT issue / verify |
| `infrastructure/storage` | `local` · `google_drive` · `onedrive` adapters |
| `infrastructure/ai` | AI provider integrations |
| `core` | config, logging, exception hierarchy |

## Use-Case Folder Map

| Folder | Coverage |
|---|---|
| `use_cases/auth` | Login, token refresh, session |
| `use_cases/documents` | Upload, understanding, readers, versioning |
| `use_cases/metadata` | Tags, categories, metadata, linking, dedup |
| `use_cases/search` | Semantic search, related files |
| `use_cases/ai` | QA, summarization, AI chat |
| `use_cases/research` | Research / teaching / publication / admin assistants |

## Migration & Tooling

- `alembic/` — PostgreSQL schema migrations (config to be added).
- `scripts/` — Operational / seeding scripts.
- `tests/` — `unit` (domain/use-cases), `integration` (API+infra), `e2e`.

## API — Phase 1 (Objects slice)

Implemented endpoints (currently supported by the frozen Application layer):

| Method | Path | Purpose | Use case |
|---|---|---|---|
| `GET` | `/api/v1/objects` | List Objects (paginated) | `ListObjectsUseCase` |
| `GET` | `/api/v1/objects/{id}` | Fetch a Universal Object | `GetObjectUseCase` |
| `POST` | `/api/v1/objects` | Create a Universal Object | `CreateObjectUseCase` |
| `PUT` | `/api/v1/objects/{id}` | Update a Universal Object | `UpdateObjectUseCase` |
| `DELETE` | `/api/v1/objects/{id}` | Delete a Universal Object | `DeleteObjectUseCase` |

Request body for `POST /api/v1/objects`:
```json
{
  "object_type": "course",
  "title": "Intro to CS",
  "created_by": "faculty:1",
  "status": "draft",
  "metadata": [{ "key": "code", "value": "CS101" }]
}
```

`PUT /api/v1/objects/{id}` (partial update of status and/or metadata):
```json
{
  "updated_by": "faculty:1",
  "status": "archived",
  "metadata": [{ "key": "note", "value": "x" }]
}
```

`GET /api/v1/objects` query params: `page` (>=1, default 1), `page_size` (1–100,
default 20). Response includes `items`, `total_count`, `page`, `page_size`.

Status codes: `200` (ok), `201` (created), `204` (deleted), `400`/`422` (validation),
`404` (not found), `409` (conflict), `500` (unexpected).

> Note: deletion is a **hard delete** (repository `delete`). `PUT` updates only
> `status` and `metadata` — the Domain aggregate has no title setter, so `title`
> is immutable post-creation by design.
