# AcademicOS M12.2 — Incremental Patch Manifest (Embedding Capability)

**Baseline:** `980a77b` (M12.1.1) · **Commit:** `c694399` · **Date:** 2026-08-08

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/infrastructure/ai/embedding/openai_embedding_adapter.py` | `OpenAIEmbeddingAdapter(Embedder)` — real embeddings via `/v1/embeddings`. |
| `backend/app/tests/unit/test_embedding_adapter.py` | 14 tests (adapter, dimensions, retries, lifecycle, AiCore.embedder(), build_ai_core). |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/application/dtos/ai.py` | `ProviderConfig.embedding_model` + `embedding_dimensions`. |
| `backend/app/application/ai/providers/config.py` | Parse `embedding_model` + `embedding_dimensions` from `AI_PROVIDERS_JSON`. |
| `backend/app/application/ai/core.py` | `AiCore.embedder()` method + `_embedder` field + lifecycle cleanup. |
| `backend/app/infrastructure/ai/provider_factory.py` | `build_ai_core` constructs the embedder (real adapter or HashingEmbedder). |
| `backend/app/tests/architecture/test_ai_guardrails.py` | Factory exempt from all infra imports. |
| `backend/app/tests/architecture/test_transport_ownership.py` | Two transport owners (gen + embed). |

## Verification
- Backend: **1430 passed, 2 skipped** · Architecture: **16/16** · ruff clean.
