# PHASE2_RELATIONSHIP_TRAVERSAL_AUDIT.md

## Original vulnerability

`SQLAlchemyObjectRepository.find_by_ids(ids)` — the batch-lookup method used throughout the codebase to resolve relationship/link targets for response enrichment (e.g., attaching a linked document's title to an event, a linked vendor's name to a purchase proposal, a linked faculty member's name to a committee) — had **no ownership filtering at all**. It accepted a list of object ids and returned every matching row regardless of who owned it.

## Exact attack / data-leak path

1. Object O (owned by user X) carries a relationship edge to object T.
2. A use case resolves O's links via `repository.find_by_ids([T.id, ...])` to enrich its response (title, name, metadata).
3. If T is ever owned by a different user Y — through a bug, a migration artifact, or any future code path that doesn't check ownership before creating a relationship — `find_by_ids` would return T's full object regardless, and its title/content would be attached directly into O's response, visible to whoever is legitimately reading O (including X, who has no right to see Y's private record).

This is distinct from, and not covered by, the Phase 1 fix: Phase 1 closed direct list/count/dashboard/export endpoints and `get_by_id`-gated single-object routes. `find_by_ids` is reached only internally, by id, for enrichment — never directly from an HTTP route — so it fell outside every Phase 1 check.

## Affected call sites

~55 production call sites across every domain: documents, events, publications, research (projects/grants), students, finance (vendors/proposals), teaching (classes/assignments/submissions), committees, faculty, plus two AI/relationship use cases. Full list captured in the repository-wide verification section below.

## Root cause

`find_by_ids` was implemented as a plain `WHERE id IN (...)` query with no predicate tying results to a requesting or referencing owner — an oversight parallel to, but independent of, the Phase 1 `find`/`count`/`find_by_type` gap (those were fixed; this method was missed because it's reached by id, not by a list query).

## Investigation findings (classification, per the required framework)

- **Category A — same-user relationship (the vast majority, ~50 sites).** This codebase has no sharing/collaboration feature anywhere; every relationship a user's object holds is, by design, created within that same user's own data. Fixed by owner-scoping.
- **Category C — already covered by an existing, verified authorization mechanism (no fix needed):**
  - `app/api/routes/search.py:232` — the ids passed in (`hits`) are already, per the code's own comment, "permission pre-filtered through the R4 evaluator" before this call.
  - `app/application/services/graph_runtime.py::_load_objects` — its caller applies `self._can_read(obj, principal)` to every result before use.
  - `app/application/use_cases/ai/related_documents.py` — candidates are authorized against the evaluator immediately after this call, per the method's own docstring and confirmed by reading the code.
  - `app/application/use_cases/search/search_objects.py::_authorized` — this method *is* the authorization check; the raw fetch feeds directly into an ownership/ACL gate before anything is returned.
- **Category D — genuine gap found and fixed, distinct from the main pattern:**
  - `app/application/use_cases/ai/propose_links.py::list_proposals` had **no authorization check of any kind**, unlike the sibling `propose()`/`approve()` methods in the same class. Fixed by scoping to the source object's own owner.
- **Related but explicitly out of scope, documented only per your instruction:**
  - `app/application/services/graph_integrity.py::validate_edges` uses `find_by_ids` to check that a relationship target exists and has the expected type during edge creation. This is an *existence-oracle* concern (a caller could learn whether some object id exists, though not its content), a different issue class from content-enrichment during read. Not fixed in this phase.

## Exact fix

1. **Repository (centralized fix point):** `find_by_ids(ids, *, owner_user_id: str | None = None)` — optional, backward-compatible, filters in SQL against the same indexed `owner_user_id` column Phase 1 already established. The abstract contract on both `domain/repositories/base.py`'s generic `Repository[T]` mixin and the concrete `SQLAlchemyObjectRepository` adapter were updated to match, so any future second implementation inherits an accurate signature.
2. **Every Category-A call site** threads `owner_user_id` using one consistent, centrally-derived rule — never a client-supplied value:
   - **List use cases:** `query.owner_user_id` (already established and authenticated in Phase 1's `ListXQuery` pattern).
   - **Get/Create/Update use cases:** the *referencing* object's own owner — `obj.audit.created_by` (or `cls`/`source`/`project`, whichever variable names the primary object) — available in every case because the primary object is always fetched or just created before enrichment runs. This is deliberately **not** "the current HTTP caller's id": it is correct to resolve O's own links using O's own owner, so that a legitimate future shared-read path (if one is ever added) would still resolve O's links correctly rather than silently returning nothing.
3. **`propose_links.py::list_proposals`** scoped to the source object's own owner, closing the one genuine authorization gap found outside the main enrichment pattern.

## Authorization model

Unchanged from Phase 1 in spirit, extended to a new access path: ownership is derived server-side from the authenticated session or from the referencing object's own immutable `audit.created_by`, never from client input. No new sharing, tenant, or role model was introduced. `security_tenant_enforcement` was not touched or enabled.

## Tests added

- `app/tests/unit/test_sqlalchemy_object_repository.py` — 4 new repository-level tests:
  - **Test 1 (same-user):** all of User A's own ids are returned correctly.
  - **Test 2 (cross-user):** none of User B's ids are returned to User A — empty result, not an error.
  - **Test 3 (mixed):** `[A-owned, B-owned, nonexistent]` returns only the A-owned record; B's id and the nonexistent id are indistinguishable in the result.
  - Backward-compatibility test: omitting `owner_user_id` preserves the original unfiltered behavior, for the verified Category C call sites that don't need it.
- `app/tests/integration/test_events_api.py::test_event_enrichment_never_exposes_a_cross_owner_linked_document` — **Test 4**, a real production HTTP path: Alice's own event is directly given a relationship edge to Bob's document (constructed manually, since no legitimate write path can produce a cross-owner edge — which is exactly why this needs an explicit test), then `GET /events/{id}` as Alice is asserted to never surface Bob's document title or id anywhere in the response.
- **Test 5:** the full existing Phase 1 regression suite (`test_reports_isolation.py`, 21 tests; `test_events_year_filter_scale.py`, 3 tests) re-run and confirmed green, unaffected by this phase.

## Test results

- Focused tests: all pass (4 repository-level + 1 HTTP-level = 5/5).
- Phase 1 regression suite: 24/24 pass, unchanged.
- Domain unit test sweep (publications, research, events, committees, students, finance, faculty, teaching, documents, AI): 199/199 pass.
- Full canonical backend suite (`pytest -q -m "not slow_timing" --deselect ...test_l10_dlq_scale_ci_safe[10000]`): **3,024 passed, 13 failed, 7 skipped, 13 deselected** — identical failure set to the Phase 1 baseline (12 pre-existing R1 defects unrelated to this work, 1 missing-Qdrant environment issue), zero new failures, zero regressions.
- Along the way, fixed 6 pre-existing test-double gaps (`InMemoryObjectRepository.find_by_ids` in `test_reports_use_cases.py` and `test_list_pagination_smoke.py`) and 2 test-fixture actor-consistency issues (`test_events_use_cases.py`, `test_finance_use_cases.py`, `test_teaching_use_cases.py`) that the old unscoped `find_by_ids` had silently tolerated — the same "fix the fixture, not the invariant" precedent from Phase 1.

## Repository-wide call-site verification

Every production call site of `find_by_ids` was individually re-inspected after the fix. Result: every site either (a) passes `owner_user_id` explicitly, or (b) is one of the five verified Category C/D-resolved exceptions listed above, with the reasoning for each recorded in code comments at the call site. `git diff --check`: clean, no whitespace errors. No ambiguous or undocumented call sites remain.

## Remaining related risks (documented, not fixed — outside this phase's scope)

- `graph_integrity.py::validate_edges` — existence-oracle during edge-creation validation (a different issue class from content-enrichment).

## Final determination

**`find_by_ids()` is now safe against cross-user ID enumeration/data enrichment**, for every call site reachable in production code, verified by direct code inspection, backward-compatibility-preserving repository tests, and a real cross-owner relationship constructed and read through the actual HTTP/use-case stack. The four call sites left intentionally unscoped are each independently protected by an existing, verified downstream authorization mechanism — not by omission.
