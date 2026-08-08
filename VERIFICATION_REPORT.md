# Verification Report — Sprint M13.3.1 (Corrective — Related Documents Defects)

**Baseline:** `7d93a39` (M13.3) · **Commit:** `836d60d` · **Date:** 2026-08-08
**Branch:** `feature/m11-ai-workspace` · **Runtime:** Python 3.13 · **Scope:** corrective only.

---

## 1. DEFECT 1 — feature gate executes too late

### Root cause
`GET /ai/related` declared `get_embedder`/`get_vector_repository` as signature `Depends()`. FastAPI resolves **all** declared dependencies during the dependency-solving phase — **before** the path-operation function body runs. The feature gate lived in the body, so it executed **after** `get_embedder`/`get_vector_repository` had already run: a disabled feature still resolved the AI embedder and provisioned/queried the Qdrant/vector collection.

### Fix (smallest correct)
The embedder and vector repository are now resolved **inline, inside the handler, immediately after the gate**:
```python
if not core.config.enabled or not core.config.feature_flags.get("related_documents", False):
    raise HTTPException(status_code=404)
embedder = get_embedder(core)              # AFTER the gate
vector_repository = get_vector_repository(embedder)  # AFTER the gate
```
This is unambiguous: the gate is a plain `if … raise` that precedes the calls, with no reliance on FastAPI dependency-resolution ordering. The same `get_embedder`/`get_vector_repository` functions `/search` uses are reused (identical embedder identity + M12 dimensions).

### Regression tests (`TestFeatureGateResolutionOrder` + `TestSearchUnchanged`, integration)
| Test | Asserts |
|---|---|
| `test_embedder_not_resolved_when_flag_off` | `related_documents=false` → 404; **get_embedder/get_vector_repository call log empty**. |
| `test_embedder_not_resolved_when_master_off_flag_on` | `AI_ENABLED=false` + flag on → 404; **call log empty**. |
| `test_ai_disabled_blocks_related_even_when_flag_on` | master off → 404. |
| `test_embedder_resolved_when_enabled` | flag on + master on → 404 (source not found, not gate); **embedder+vector each resolved exactly once**. |
| `test_reuses_same_hashing_embedder_identity_as_search` | the shared `get_embedder` is called (no second abstraction). |
| `test_search_still_responds` | `GET /search` → 200 (unchanged). |

The embedder/vector "not resolved" is proven by monkeypatching the inline `app.api.routes.ai.get_embedder` / `get_vector_repository` and asserting the call log is empty when disabled. (The two prior M13.3 tests used the old `Depends`-override mechanism, which masked resolution; they are updated — not weakened — to strictly prove non-resolution.)

## 2. DEFECT 2 — returns non-document objects

### Root cause
`RelatedDocumentsUseCase._select()` returned any object type present in the global vector index (e.g. a `research_project` or `publication` that happened to be a nearest neighbour).

### Fix
- **Source must be a document:** after the READ check, `if source.object_type is not ObjectType.DOCUMENT: raise ValidationError`. The READ check precedes the type check so the type of an unauthorized object is never leaked.
- **Candidates filtered to documents:** in `_select`, `if obj.object_type is not ObjectType.DOCUMENT: continue` — using the **authoritative object** type (not the possibly-stale index row) before result construction.

Permission filtering, self-exclusion, ordering (vector-search rank), score (existing RRF convention) and limit behaviour are unchanged.

### Regression tests (`TestDocumentTypeRestriction`, unit)
| Test | Asserts |
|---|---|
| `test_non_document_source_rejected` | non-document source → `ValidationError` ("not a document"). |
| `test_non_document_candidate_excluded` | a project candidate is dropped; the document candidate is kept. |
| `test_document_candidate_returned_among_non_documents` | exactly the document is returned. |
| `test_permission_and_source_exclusion_still_hold_with_type_filter` | source self-excluded, unreadable doc filtered, non-doc filtered, readable doc kept — all in one pass. |

Existing tests already cover source exclusion, unauthorized-result filtering, source READ denial, ordering, limit, zero results and honest degradation — all still green with the new type filter.

## 3. Architecture verification

| Constraint | Status |
|---|---|
| No new embedding abstraction / vector repository / search pipeline / provider / transport owner / AI Core | ✓ |
| AI Core remains composition authority (route constructs nothing) | ✓ |
| Route constructs no httpx clients / embedding adapters | ✓ |
| Application framework-free guardrail holds | ✓ |
| `/search` route + response contract unchanged | ✓ |
| Architecture guardrails | ✓ 16/16 |

## 4. Test execution

### 4.1 Targeted (M13.x + search + architecture)
```
$ python -m pytest app/tests/unit/test_related_documents.py app/tests/integration/test_ai_related_api.py \
    app/tests/unit/test_grounded_qa.py app/tests/unit/test_enrich_document.py \
    app/tests/unit/test_summarize_document.py app/tests/integration/test_ai_summarize_api.py \
    app/tests/integration/test_semantic_search_activation.py app/tests/architecture/ -q
117 passed in 7.77s
```

### 4.2 Full backend regression
```
$ python -m pytest app/tests/ -q
1534 passed, 2 skipped in 347.78s
```
1527 → **1534** (+3 integration, +4 unit; **0 failures**). M13.1/M13.2/M13.2.1/M13.3/M12/M11 all green.

### 4.3 Frontend (unaffected — backend-only)
```
$ npx vitest run        → 70 passed (15 files)
$ npx tsc --noEmit      → exit 0
```

### 4.4 Lint
```
$ ruff check <changed files>   → 0 non-B008/non-E402 errors
```
(`ai.py`: only the pre-existing FastAPI `B008 Depends()` idiom; integration test: only the accepted `pytest.importorskip` `E402` pattern.)

## 5. Limitations (for the fresh audit)
- Related-docs embedder still follows the `semantic_search` flag (shared `get_embedder`): with semantic search off it uses the `HashingEmbedder` fallback — unchanged from M13.3, the same honest degradation `/search` uses.
- The inline resolution is the smallest correct fix; an alternative (a gate dependency short-circuiting siblings) would rely on FastAPI dependency-resolution order and was rejected as less robust.

## 6. Deliverables
- **Patch ZIP:** `releases/m13.3.1/m13.3.1-patch.zip`
- **Patch diff:** `releases/m13.3.1/m13.3.1.patch`
- **Manifest:** `PATCH_MANIFEST.md`
- **Changelog:** `CHANGELOG.md` (M13.3.1 entry prepended)

M13 approval is **not** claimed; the repository is left ready for a completely fresh independent audit.
