# Change Report — `academicOS-env-fix`

**Branch:** `feature/m11-ai-workspace`
**Date:** 2026-08-10
**Scope:** Local configuration repair only — **no repository code changes.**

> **Revision 2 (this ZIP).** The first `APPLY_FIX.ps1` failed to parse under
> Windows PowerShell 5.1 with *"Missing closing '}' in statement block"* (lines
> ~84/105). Root cause: the script contained 8 em-dash characters (UTF-8 bytes
> `E2 80 94`) and was saved **UTF-8 without BOM**, so Windows PowerShell 5.1
> read it as the system ANSI code page and mis-tokenized those bytes, cascading
> into the brace errors. A secondary incompatibility (`ConvertTo-Json -Compress`,
> which does not exist before PowerShell 6) was also present.
>
> **Fixes applied (script only, no repo change):**
> - Rewritten in **pure ASCII** and saved **UTF-8 with BOM** + **CRLF** line
>   endings — parses identically on Windows PowerShell 5.1 and PowerShell 7+.
> - Replaced `ConvertTo-Json -Compress` with a small, version-safe manual
>   serializer (preserves all provider fields, including `embedding_model`).
> - Forced `@(Get-Content ...)` everywhere (a one-line `.env` would otherwise
>   index by character, not by line, on Windows PowerShell 5.1).
>
> **Validation:** the actual `APPLY_FIX.ps1` was executed under PowerShell 7.4.6
> across 9 scenarios (exact malformed URL, idempotent re-run, cloud provider
> preserved, mixed providers, malformed non-local left unchanged, invalid JSON
> replaced, missing line appended, missing `.env` copied from example, extra
> fields preserved) plus the user's default-path invocation (no `-RepoRoot`,
> run from the repo root) — **all pass**.

---

## 1. Root cause (exact)

The user's local `backend/.env` contains a malformed value in
`AI_PROVIDERS_JSON`. A Markdown link was pasted into the `base_url` field:

```
[[http://localhost:11434/v1](http://localhost:11434/v1)](http://localhost:11434/v1](http://localhost:11434/v1))
```

`pydantic-settings` reads this verbatim as the provider `base_url` (it is valid
JSON string content, so parsing succeeds — only the value is wrong). At request
time, `OpenAIProvider._url()` builds
`[[http://localhost:11434/v1](...)...)]/chat/completions` and `httpx` rejects it:

> `Request URL is missing an 'http://' or 'https://' protocol.`

`OpenAIProvider` retries 3× then raises `LlmProviderError`; the chat use case's
gateway boundary degrades to the honest `available=False` fallback. From the UI
this looks like "AI chat is broken / unavailable."

The intended literal value is:

```
http://localhost:11434/v1
```

## 2. Repository code is correct (no production change)

Direct inspection + a real end-to-end smoke test confirm the repository is
correct. Nothing in the repo was changed, so there is **no commit and no push**
(nothing to commit). Specifically verified:

| Area | File | Status |
|---|---|---|
| Provider endpoint build | `backend/app/infrastructure/ai/llm/openai.py` `_url()` → `{base_url.rstrip('/')}/chat/completions` | Correct |
| Provider timeout from config | `openai.py` `_client_or_build()` uses `config.timeout_seconds` | Correct (120 s reaches httpx) |
| Config parsing | `app/application/ai/providers/config.py` `parse_provider_configs` | Correct (reads `timeout_seconds`, `base_url`, etc.) |
| Composition root | `app/infrastructure/ai/provider_factory.py` `build_ai_core` | Correct; default provider resolves to `local-ollama` |
| Frontend AI timeout | `frontend/src/lib/api/client.ts` `DEFAULT_AI_TIMEOUT_MS = 120_000` | Correct |
| Frontend AI client | `frontend/src/lib/api/ai.ts` passes `timeoutMs: DEFAULT_AI_TIMEOUT_MS` | Correct |
| Template | `backend/.env.example` has the **literal** URL + `timeout_seconds:120` | Correct |

`backend/.env` is gitignored (`!.env.example` is the only tracked env file), so
the malformed value exists **only** on the user's machine — it was never in the
repo. The repo's `.env.example` already carries the correct literal URL.

## 3. What was changed

**Repository files changed:** none.

**Local file changed (by the user, via the script):** `backend/.env`
- `AI_PROVIDERS_JSON` `base_url` normalized from the malformed Markdown link to
  `http://localhost:11434/v1`.
- `AI_DEFAULT_PROVIDER` ensured = `local-ollama`.
- Original preserved at `backend/.env.bak-<timestamp>`.

## 4. Tests run

| Suite | Result |
|---|---|
| Backend `pytest` (full) | **1591 passed, 2 skipped** |
| Frontend `vitest` | **76 passed (16 files)** |
| Frontend `tsc --noEmit` | **clean (exit 0)** |
| Frontend `next build` | **clean (exit 0)** |
| Architecture guardrails | pass (part of backend suite) |

## 5. End-to-end AI smoke test (real provider path)

Because this sandbox cannot run the `llama3.2` container, a local
OpenAI-compatible HTTP server stood in for Ollama and the **real** AcademicOS
code path was exercised:

1. **Provider path** — `build_ai_core(settings)` (settings built from the same
   `AI_PROVIDERS_JSON` shape as `.env.example`) → `core.gateway().generate()`
   → real `httpx` POST `{base_url}/chat/completions` → response parsed.
   - `provider_id = 'local-ollama'`, `model = 'llama3.2'`, response text came
     from the endpoint. `httpx` client timeout = `Timeout(timeout=120.0)` — the
     configured 120 s reached the transport. **PASS**
2. **Full route** — FastAPI `TestClient` `POST /api/v1/ai/chat` with the real
   gateway injected → **HTTP 200**, `available=True`, `provider_id=local-ollama`,
   `model=llama3.2`, answer came from the endpoint, `conversation_id` returned
   (M19 persistence). **PASS**
3. **Root-cause negative test** — the exact malformed `base_url` was fed to the
   provider; it raised `LlmProviderError`
   ("Request URL is missing an 'http://' or 'https://' protocol"). The corrected
   literal URL configured cleanly → endpoint
   `http://localhost:11434/v1/chat/completions`. **PASS**

(Smoke-test harness: `/home/user/smoke_test_ai_chat.py`; not shipped — it is a
throwaway verifier with sandbox-specific paths.)

## 6. Why no commit / no `files/` in the ZIP

The repo is already correct; the defect is a local gitignored `.env`. Per the
stated rule *"If the malformed URL is only a local .env issue and the repository
code is correct, do NOT invent a production-code change."* The delivery is a
config-repair script, not a code patch. There are therefore **no repo-relative
replacement files** in this ZIP — only the repair tooling.

## 7. The repair script (`APPLY_FIX.ps1`) — safety properties

- Idempotent: re-running on an already-correct `.env` is a no-op.
- Backs up `backend/.env` before editing.
- Only touches `AI_PROVIDERS_JSON` and `AI_DEFAULT_PROVIDER` lines.
- Leaves any **valid** base_url (`http(s)://…` with no brackets/parens)
  untouched — a real cloud provider is preserved.
- Only repairs base_urls that are **both** malformed **and** reference the local
  Ollama host (`localhost` / `127.0.0.1` / `:11434`); a malformed non-local URL
  is left unchanged with a warning (no guessing).
- Handles invalid/empty `AI_PROVIDERS_JSON` by inserting the canonical local
  config.
- Its core normalization logic was validated against 7 cases (exact malformed
  URL, idempotency, cloud-untouched, mixed providers, malformed-non-local,
  invalid JSON, empty) — all pass.
