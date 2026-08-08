# AcademicOS M13.3 — Incremental Patch Manifest (Provenance Retrofit + Related Documents)

**Baseline:** `0d93094` (M13.2.1) · **Commit:** `97da723` · **Date:** 2026-08-08
**Scope:** final M13 sprint — two Blueprint capabilities. Reuse-only: no new retrieval/embedding/vector/provider/transport/AI Core/prompt framework, no persistence, no RAG/agents/memory.

## Files Added

| Path | Purpose |
|---|---|
| `backend/app/application/use_cases/ai/related_documents.py` | `RelatedDocumentsUseCase` — semantic related documents reusing the existing embedder + vector repository + permission gate. |
| `backend/app/tests/unit/test_related_documents.py` | 16 unit tests (source handling, honest degradation, result contract, embedder reuse). |
| `backend/app/tests/integration/test_ai_related_api.py` | 8 integration tests (flag, auth, master-switch gate, error mapping, embedder identity). |

## Files Modified

| Path | Change |
|---|---|
| `backend/app/application/dtos/ai.py` | M13.1 provenance contract retrofitted onto `SummarizeResult`; new `RelatedDocumentItem`, `RelatedDocumentsResult`, `related_documents_result_dict`; `__all__` updated. |
| `backend/app/application/use_cases/ai/summarize_document.py` | Populate provenance from the actual `GenerationResult` (success); consistent fallback provenance; prompt identity `ai.summarize` v1. |
| `backend/app/api/routes/ai.py` | `SummarizeResponseModel` provenance fields; `GET /ai/related` + `RelatedDocumentItemModel`/`RelatedDocumentsResponseModel`; `Query` import. |
| `backend/app/core/config.py` | `ai_related_documents_enabled: bool = False`. |
| `backend/app/application/ai/config.py` | `"related_documents"` projected onto `AiConfigView.feature_flags`. |
| `backend/app/tests/unit/test_summarize_document.py` | +3 provenance tests; `provider_id` on the mock gateway. |
| `backend/app/tests/unit/test_ai_config_view.py` | `related_documents` in stub + expected flag dict. |

## Reuse map (constraints honoured)
- **AiCore** = single composition authority (route constructs no providers/embedders/httpx clients).
- **Embedder port** reused (resolved via the same `get_embedder` dep as `/search` → identical identity + dimensions). No second embedding abstraction.
- **VectorRepository.search** reused (existing cosine NN + deterministic ordering). No new vector pipeline/client.
- **DocumentAnnotationService** + intake pipeline (source text). **PermissionEvaluator** (R4 READ gate). **Existing search RRF scoring** (no new ranking algorithm).
- Architecture guardrails: **16/16** (incl. application framework-free — the related use case uses the domain `VectorRepository`/`Embedder` ports only).

## Configuration authority
`related_documents` flag (default OFF), gated via `core.config.enabled AND feature_flags["related_documents"]`. `AI_ENABLED=false` (+ flag on) and flag off both disable with no embedding call. `settings` is never read directly.

## Verification
- Backend: **1527 passed, 2 skipped** (+27 new; zero regressions)
- Frontend: **70 vitest passed** · `tsc --noEmit` clean
- Architecture guardrails: **16/16** · ruff clean on changed files
- App boots, 269 routes (`/ai/related` registered)

## Limitations (for the fresh audit)
- Related documents reuses the embedder resolved by the `semantic_search` flag (via the shared `get_embedder` dependency): when semantic search is off, related docs use the `HashingEmbedder` fallback (deterministic, non-semantic) — the honest degradation already used by `/search`.
- Scores reuse the search reciprocal-rank-fusion convention applied to the semantic rank (the vector repository does not expose raw cosine similarity); ordering is the existing vector-search order.
- Summarization provenance is read-only metadata; the existing summarization behaviour is unchanged.
