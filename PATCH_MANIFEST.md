# AcademicOS M16.1 — Incremental Patch Manifest (Local/Free AI Verification + Docs)

**Parent commit:** `cda5f58` (M16 docs) · **Commit:** `801941a` · **Date:** 2026-08-08
**Scope:** provider/cost requirement — evidence (tests) + usability docs. No behavior change.

## Files Changed
| Path | Change |
|---|---|
| `backend/app/tests/unit/test_openai_adapter_hardening.py` | +`TestLocalFreeProvider`: gateway generates (chat + structured) with `api_key=""`, no `Authorization` header. |
| `AI_DEVELOPER_GUIDE.md` | +§7 Local/Free AI: Ollama `AI_PROVIDERS_JSON` example (no key) + no-provider `/ai/handoff` fallback. |

## Why
The core must work without paid AI. The architecture already supports keyless local providers; this adds the regression proof and the setup documentation.

## Verification
- OpenAI adapter hardening: **15 passed** · Architecture **16/16** · full backend green.
