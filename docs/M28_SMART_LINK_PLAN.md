# M28 — SMART_LINK relationship proposals: implementation plan

Status: **PLANNED — not implemented.** This document fixes the exact boundary,
interfaces and review workflow so the feature composes over existing seams and
never bypasses human approval.

## Principle

> AI proposes. Human approves. AcademicOS records.

AI must NEVER silently create authoritative relationships. Every AI-proposed
edge is created as a `SMART_LINK` proposal (inferred provenance, confidence,
evidence) and only a human decision promotes it to a real relationship.

## Existing seams this reuses (all verified present)

| Seam | Location | Role |
|---|---|---|
| `RelationshipKind.SMART_LINK` | `domain/value_objects/enums.py` | declared edge kind — never produced yet |
| `Relationship` (confidence, evidence, acl_scope) | `domain/value_objects/relationship.py` | carries confidence + evidence quotes |
| `Provenance.INFERRED` | `domain/value_objects/enums.py` | marks AI-proposed values |
| `object_relationships` table + unique identity | migration 0002 | persistence of proposals (kind=SMART_LINK, provenance=inferred) |
| `MetadataLayer.L1/L5` | domain | proposal bookkeeping metadata (`ai.proposal.*`) |
| Intake review workflow (proposal → review → commit) | `application/intake/proposal_engine.py`, `commit_engine.py`, M9 review UI | the review-loop pattern to mirror |
| `AiCore.gateway/select_provider` | `application/ai/core.py` | provider resolution (no second gateway) |
| Outbox → search projection | `infrastructure/outbox/relay.py` + `search/index_applier.py` | propagation of accepted edges |
| ACL (`require_object_acl`) | `api/dependencies/auth.py` | proposals are object-scoped: only users with WRITE on BOTH endpoints may review |

## Proposed flow (mirrors intake M9)

1. **Propose** — `POST /objects/{id}/links/propose` (or `POST /ai/links/propose`
   with `{source_id, hint}`). The use case (`application/use_cases/ai/propose_links.py`):
   - runs the shared retrieval to gather candidates (permission-filtered);
   - for each candidate emits a `SMART_LINK` edge on the source object with
     `provenance=INFERRED`, `confidence` (0..1), `evidence` (source-text quotes),
     and `acl_scope` = intersection of both endpoints' ACL scopes;
   - records `ai.proposal.status = pending`, `ai.proposal.reviewed_by = ""` in
     L5 metadata; writes an outbox event `LinkProposed`.
2. **Review** — `GET /objects/{id}/links/proposals` lists pending proposals
   (READ on source). `POST /objects/{id}/links/{target}/approve` and
   `.../reject`:
   - approve: `change_relationship_kind` SMART_LINK → the proposed kind
     (e.g. `AUTHORED_BY`) with provenance upgraded to `ASSERTED`-by-human
     (record `reviewed_by`, `reviewed_at` in L6 metadata — human decision is
     human-asserted); outbox event `LinkApproved`.
   - reject: remove the SMART_LINK edge; outbox event `LinkRejected`.
3. **Propagate** — outbox consumers (search projection) pick up the new edges;
   the graph runtime exposes them for AI retrieval; provenance stays
   queryable via `audit` metadata and outbox history.

## Explicitly out of scope for M28

- chunking/segment models; persistent citation objects; policy engine;
  agent tool execution; any autonomous edge creation; entity-extraction NLP
  pipeline (the first version works off existing metadata + retrieval, not
  raw PDF parsing).

## First consumers (when built)

- `enrich_document` output gains relationship proposals (publication ↔
  project/faculty via author metadata);
- intake commit proposals (document ↔ linked course/project);
- a review queue UI tab in the AI workspace (mirrors AssistantLabs "review").

## Acceptance criteria

- No relationship with `Provenance.ASSERTED` is ever created by AI code
  (architecture guardrail test);
- every SMART_LINK carries confidence + evidence;
- approve/reject is permission-checked on both endpoints (WRITE);
- denied user cannot read proposals (READ);
- accepted edges are visible to search and graph traversal; rejected edges
  are removed atomically with an outbox record;
- full flow covered by integration tests (propose → approve → traverse,
  propose → reject → gone).
