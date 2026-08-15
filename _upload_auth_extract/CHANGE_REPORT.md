# AcademicOS — Upload Auth Fix (P0) — Change Report

**ZIP:** `AcademicOS_Upload_Auth_Fix.zip`
**Date:** 2026-08-11
**Branch (target):** `feature/m11-ai-workspace` on `E:\AcademicOS` (baseline `f746ac0`)
**Scope:** frontend-only, one function. No backend, no DB, no `.env`, no Ollama/Docker, no retrieval/RAG/streaming changes. Nothing committed or pushed.

---

## 1. Problem

Uploading a document through the Documents UI failed in the browser: `POST /api/v1/documents → 401 Unauthorized`, UI showed *"Your session has expired"*, while `GET /api/v1/objects` worked (200) in the same session.

## 2. Root cause

`uploadDocument()` in `frontend/src/lib/api/documents.ts` uses a raw `XMLHttpRequest` for upload-progress reporting and **never attaches the bearer token** — it bypasses the shared API client's `attachAuthorization()`. The backend `/documents` router unconditionally requires a valid bearer token (`get_current_user()` in `backend/app/api/dependencies/auth.py` → `HTTPBearer(auto_error=False)` → missing header raises `UnauthorizedError("Missing bearer token")` → HTTP 401 via `main.py`). The same session's GETs work because the shared client attaches the token; the upload does not.

## 3. Evidence (PROVEN)

- **Code:** zero `setRequestHeader` calls exist in `documents.ts` (grep-verified).
- **jsdom/vitest forensic recording-XHR experiment:** `headers sent: {}`, `setRequestHeader calls: 0` — no Authorization, no manual Content-Type, FormData intact.
- **Live backend experiment (real app, real JWT):** `POST /documents` without token → 401 `{"error":{"code":"unauthorized","message":"Missing bearer token"}}`; with valid token → **201**; `GET /objects` with token → 200. Same backend, same session — the only variable is the header.
- **Real-browser smoke test (puppeteer/Chrome):** see §8 — the browser's own request showed `Authorization: Bearer <token>` after the fix and returned **201**.

## 4. Exact files changed

| File | Action |
|---|---|
| `frontend/src/lib/api/documents.ts` | **overwrite** (modified) |
| `frontend/src/lib/api/documents.test.ts` | **new** (11 focused tests) |
| `APPLY_STEPS.md`, `CHANGE_REPORT.md` | new (docs) |

## 5. Exact functions changed

`uploadDocument()` in `frontend/src/lib/api/documents.ts`:

- Added import: `import { getAccessToken } from "@/lib/auth/token";`
- Between `xhr.open("POST", ...)` and `xhr.send(formData)`:
  ```ts
  const token = getAccessToken();
  if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
  ```
- Nothing else changed: FormData construction, progress handler, abort wiring, error normalization, response parsing, endpoint, method all byte-identical.

## 6. Why this is the smallest correct fix

- Reuses the **existing** token accessor (`getAccessToken`) — the single source of truth already used by the shared client's `attachAuthorization()`; no new auth/session architecture, no second refresh implementation, no new HTTP client.
- One function, +1 import, +8 lines; the XHR stays (multipart + real upload progress preserved).
- Backend untouched — its auth contract is correct and unchanged.
- No-token behavior is deterministic and matches the shared client (no header when anonymous).

## 7. Tests performed

| Suite | Result |
|---|---|
| `documents.test.ts` (new — Authorization present, Bearer format, no-token determinism, FormData intact, no manual Content-Type, progress, abort-before-send, abort-mid-flight, success parsing, 401 error normalization, endpoint/method) | **11 passed** |
| `client.test.ts` (existing shared-client auth — unchanged behavior pinned) | 4 passed |
| **Full frontend suite** (`npx vitest run`) | **101 passed** (20 files) |
| `npm run typecheck` (`tsc --noEmit`) | **exit 0** |
| `git diff --check` | clean |

Backend suites are unaffected (zero backend changes); the backend was live-verified during the browser smoke test instead.

## 8. Browser smoke-test result (real Chrome via puppeteer)

Sandbox environment: backend (uvicorn, scratch SQLite) on `127.0.0.1:8000` + frontend (Next.js dev) on `127.0.0.1:3000` + real Chrome.

```
[OK] login succeeded (redirected from /login)
[OK] access token stored in localStorage
[OK] documents page loaded (GET /documents works)
[OK] upload modal opened
[OK] POST /documents was sent by the browser
[OK] POST /documents returned 201 status=201
[OK] browser XHR sent Authorization: Bearer <token>   ← the fix, observed in the real browser
[OK] uploaded document appears in the UI
[OK] /search finds the body-only fact status=200 hits=3
[OK] AI route authenticated + reachable (200/404; 401 would mean auth failure) status=404
SMOKE TEST: ALL PASSED
```

Downstream chain verified on the browser-uploaded document (no LLM needed to prove the pipeline):

- `document_contents` row **EXISTS** (`source_item_id` = document id, body contains the date) — Fix A's upload-time indexing ran.
- Grounded-QA prompt (production wiring) contains **3 `<<<SOURCE TEXT>>>` blocks** and the body-only fact `"14 to 18 July 2025"` with citation `[1] Opaque Certificate` — the LLM receives the body and a valid citation target.
- **Honest limitation:** the final LLM token generation needs your local Ollama (not present in the sandbox); the 404 on `/ai/chat/stream` is the sandbox feature flag (`chat` disabled without a `.env`), not an auth failure — the request passed `get_current_user` (401 otherwise).

## 9. Before / after behavior

| Aspect | Before | After |
|---|---|---|
| Browser upload request headers | `{}` (no Authorization) | `Authorization: Bearer <access-token>` |
| `POST /api/v1/documents` | **401** "Missing bearer token" → UI "Your session has expired" | **201**, document created |
| Multipart FormData | preserved | preserved (unchanged) |
| Content-Type | browser-generated (boundary) | browser-generated (NOT manually set) |
| Progress / abort / error handling / response parsing | as-is | unchanged |
| Anonymous (no token) upload | 401 | 401 (no header sent — same as shared client's public behavior) |

## 10. Security implications

- No new surface: the upload now rides the same bearer-token contract as every other API call; the backend auth gate (`get_current_user`, ACL dependency) was already in place and is unchanged.
- The token is read from localStorage at request time and only sent over the same-origin/configured API base URL already used by the app.
- No credentials in the URL, no cookies added, no CORS change.
- NOT A PROBLEM (verified): the 401 path is an availability gap, not an exposure; content-indexing ACL filtering is covered by existing integration tests.

## 11. What was deliberately NOT changed

- Backend (`auth.py`, `documents.py`, `main.py`) — zero backend edits.
- `frontend/src/lib/api/client.ts` — shared client and its refresh interceptor untouched (its behavior is pinned by `client.test.ts`).
- Fix A document-content indexing, retrieval/`assistant_retrieval.py`, RAG, Ollama/keep_alive, streaming, `AiChatPanel.tsx`, UploadModal UI, middleware, token storage.
- No `.env`, no migration, no Docker config.

## 12. Remaining P1/P2 findings (from the forensic audit — NOT in this ZIP)

| # | Finding | Class | Priority |
|---|---|---|---|
| 1 | Upload has no 401 refresh/retry (expired token mid-upload still fails; would require exporting the existing single-flight refresh from client.ts) | PROVEN gap | P1 |
| 2 | Error message for upload 401s is misleading ("session expired") — backend envelope `{"error":{"message"}}` is not parsed by the upload error path | PROVEN | P1 |
| 3 | Pre-Fix-A documents (uploaded before the content-indexing fix) have no `document_contents` rows and the rebuild skips them | PROVEN | P1 |
| 4 | Count questions ("how many …") cap retrieved items at 8 | LIKELY | P1 |
| 5 | Retrieval verb-fallback plans (e.g. 'held') and 'which papers … 2025' empty-retrieval path | LIKELY / POSSIBLE | P2 |
| 6 | `belongs_to` target object not ACL-checked at upload; no duplicate-upload detection; no XHR timeout; UploadModal abort wiring unused | POSSIBLE / PROVEN | P2 |

Each is independent of this fix and can be reviewed/packaged separately.
