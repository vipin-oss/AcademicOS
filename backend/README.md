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

## API — Phase 2 (Documents slice)

A **Document is a Universal Object** with `object_type = document` (Blueprint
§2): it lives in the same `objects` table, reuses the same repository, and its
file facts (`file_name`, `file_size`, `mime_type`, `file_path`) ride as L2
system metadata while `document_type`, `description` and `tags` are L6
human-asserted metadata. The link to another Object is an asserted
`belongs_to` relationship (Blueprint §4). Uploads are stored through the
`FileStorage` application port (`infrastructure/storage/local` adapter).

| Method | Path | Purpose | Use case |
|---|---|---|---|
| `GET` | `/api/v1/documents` | List Documents (paginated, `?object_id=` filter) | `ListDocumentsUseCase` |
| `GET` | `/api/v1/documents/{id}` | Fetch a Document | `GetDocumentUseCase` |
| `POST` | `/api/v1/documents` | Upload a Document (multipart, file + metadata) | `CreateDocumentUseCase` |
| `PUT`/`PATCH` | `/api/v1/documents/{id}` | Update title/status/metadata/link (no re-upload) | `UpdateDocumentUseCase` |
| `DELETE` | `/api/v1/documents/{id}` | Delete Document + stored blob | `DeleteDocumentUseCase` |
| `GET` | `/api/v1/documents/{id}/download` | Download the stored blob | — |

Upload form fields (`multipart/form-data`): `title`, `document_type`
(`pdf|docx|xlsx|pptx|txt|zip|image|video|unknown`), `uploaded_by`, `file`,
optional `object_id`, `description`, `tags` (JSON string array), `status`
(default `draft`).

`PUT`/`PATCH` body (all optional; `object_id: null` unlinks, absent leaves as-is):
```json
{
  "title": "CS101 Syllabus v2",
  "object_id": "obj:course:AB12CD34EF56GH78",
  "document_type": "pdf",
  "description": "Updated",
  "tags": ["syllabus", "fall-2026"],
  "status": "active",
  "uploaded_by": "faculty:1"
}
```

List query params: `page` (>=1, default 1), `page_size` (1–100, default 20),
`object_id` (filter to documents linked to that Object). Lifecycle transitions
follow the universal rules (`draft → active/archived`, `active → archived`; an
illegal move returns `422`). Configuration: `STORAGE_DIR` (blob root, default
`./storage`) and `PUBLIC_BASE_URL` (used to build the absolute `url` download
link in responses).
