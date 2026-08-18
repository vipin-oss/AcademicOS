# Final Report — Root Cause Fix & Acceptance

## Root Cause Analysis

The blocking regression had a **three-layer root cause**:

### Layer 1: Extraction Schema Overlap
`PUBLICATION_FIELDS.journal_name` had synonym `"venue"`. When a conference
certificate was classified with `publication` as a secondary type (triggered
by "Paper Presented" → "paper" keyword match), the extraction applied
PUBLICATION_FIELDS alongside CONFERENCE_FIELDS. The "Venue: Convention
Centre, Bangalore" label matched BOTH `venue` (from CONFERENCE_FIELDS) AND
`journal_name` (from PUBLICATION_FIELDS via the "venue" synonym), creating
a spurious `journal_name` claim.

### Layer 2: Type Inference Priority
`ClaimProjectionService._infer_type_ids()` checked `pub_preds` (which
included `journal_name`) BEFORE `conference_specific`. A single spurious
`journal_name` predicate was sufficient to classify the document as a
publication, overriding the strong `conference_name` evidence.

### Layer 3: Insufficient Evidence Gate
No validation existed to check whether the inferred domain had sufficient
defining predicates. A publication was attempted with only `journal_name`
and no `publication_title` (the required field).

## Fixes Applied

### Fix 1: Extraction Schema
**File**: `backend/app/application/knowledge/extraction_schemas.py`

Changed `journal_name` synonyms from:
```python
("journal", "journal name", "venue")
```
to:
```python
("journal", "journal name", "published in", "venue of publication")
```

**Rationale**: "venue" is ambiguous — it means both a physical location
(conference venue) and a publication venue. Replaced with more specific
synonyms that won't match "Venue: Convention Centre" labels.

### Fix 2: Type Inference Precedence
**File**: `backend/app/application/services/claim_projection.py`

Rewrote `_infer_type_ids()` with documented precedence rules:

1. **DEFINING predicates** (highest priority): `publication_title`,
   `conference_name`, `project_title`, `committee_name`, `award_title`,
   `event_title`. These are the required title fields unique to each domain.
   When present, they unambiguously determine the domain.

2. **SPECIFIC predicates** (medium priority): `doi` (publication),
   `conference_acronym` (conference), `funding_agency` (project), etc.
   Strong indicators that don't have the required title.

3. **Weak/generic predicates** (never trigger alone): `journal_name`,
   `authors`, `venue`, `start_date`. These appear across multiple domains
   and must NEVER be the sole basis for domain inference.

### Fix 3: Projection Safety Layer
**File**: `backend/app/application/services/claim_projection.py`

Added `_validate_sufficient_evidence()` method with `_REQUIRED_EVIDENCE`
per domain:
- Event: requires `conference_name` or `event_title`
- Publication: requires `publication_title`
- Project: requires `project_title`, `sanction_order_number`, etc.
- Committee: requires `committee_name`

When the inferred domain lacks sufficient evidence, projection returns
`no_mapping` instead of attempting (and failing) a domain object creation.

### Fix 4: Multi-line Extraction (Documented)
**File**: Documented as P1, not fixed in this pass.

The label extractor grabs everything after "Label:" on the same line.
"Volume: 45 Issue: 2 Pages: 100-110" extracts `volume = "45 Issue: 2
Pages: 100-110"`. This is a pre-existing extraction quality issue that
requires broader label-extractor redesign. It does NOT create incorrect
academic records (the CreatePublicationUseCase rejects bad data). Requires
a separate implementation pass.

## Files Changed

### Modified (15 files)
| File | Change |
|---|---|
| `backend/app/application/knowledge/extraction_schemas.py` | journal_name synonyms: removed "venue", added "published in", "venue of publication" |
| `backend/app/application/services/claim_projection.py` | Rewrote type inference with precedence rules + added `_validate_sufficient_evidence` |
| `backend/app/api/routes/confirmations.py` | Added `_project_after_confirmation()` integration |
| `backend/app/api/routes/document_intake.py` | Added projection to confirm-all + consistent status + backfill |
| `backend/app/api/routes/objects.py` | Added `object_type` query parameter filter |
| `backend/app/infrastructure/search/index_applier.py` | Added `backfill_missing()` method |
| `frontend/src/lib/api/objects.ts` | Added `objectType` parameter |
| `frontend/src/components/features/documents/UploadModal.tsx` | Uses API-level academic type filter |
| `backend/app/tests/integration/test_batch_orchestration.py` | Updated notification dedup test |
| `backend/app/tests/integration/test_document_intake.py` | Updated cross-document conflict test |
| + 5 frontend files (shared fieldLabels imports) | Already in working tree |

### New Files (7 files)
| File | Purpose |
|---|---|
| `backend/app/application/services/claim_projection.py` | ClaimProjectionService |
| `backend/app/tests/unit/test_claim_projection.py` | 10 projection tests |
| `backend/app/tests/unit/test_claim_projection_type_inference.py` | 9 type inference regression tests |
| `backend/app/tests/unit/test_certificate_field_dedup.py` | 4 certificate field dedup tests |
| `backend/app/scripts/classify_stale_data.py` | Stale data classification (dry-run) |
| `backend/app/scripts/cleanup_stale_data.py` | Safe cleanup script |
| `REPORT.md` | Previous report |

## Test Results

| Suite | Result |
|---|---|
| Backend unit tests | **1758 passed**, 2 skipped |
| Backend integration tests | **60 passed** |
| Frontend vitest | **155 passed** (25 files) |
| TypeScript check | **0 errors** |
| Production build | **OK** |

### New tests added in this pass
- 9 type inference regression tests (conference→Event, Publication, insufficient evidence, etc.)
- Total new tests across all passes: **23** (10 projection + 4 dedup + 9 inference)

## E2E Verification

| Step | Status |
|---|---|
| Upload conference cert | ✅ PASS |
| Analyze | ✅ PASS |
| Review | ✅ PASS |
| Confirm | ✅ PASS |
| Event created | ✅ PASS |
| NO Publication created | ✅ PASS |
| Search | ✅ PASS |
| Re-analysis (no duplicate) | ✅ PASS |
| Publication upload+analyze+confirm | ✅ PASS |
| Publication created | ✅ PASS |
| Two-user ACL | ✅ PASS |
| Notification lifecycle | ✅ PASS |
| Export | ✅ PASS |

## Remaining Issues

1. **Multi-line extraction** (P1): Label extractor grabs everything after
   "Label:" on the same line. "Volume: 45 Issue: 2 Pages: 100-110" becomes
   `volume = "45 Issue: 2 Pages: 100-110"`. Requires label-extractor
   redesign (truncate at next known label). Does NOT create incorrect records.

2. **"Paper Title" synonym overlap** (P1): Both CONFERENCE_FIELDS
   (`presentation_title`) and PUBLICATION_FIELDS (`publication_title`) have
   "paper title" as a synonym. When both schemas are applied, the same line
   creates claims for both predicates. Known limitation — professors should
   use "Presentation Title:" for conference certificates.

3. **Stale test data**: 204 proposed claims + 64 unread notifications from
   prior test runs. Classification and cleanup scripts available.

4. **Unsupported domain mappings**: Award, Teaching, Finance, PhD Progress
   have extraction schemas but no domain object creation. Correctly reported
   as "no_mapping".
