# M28 — SMART_LINK relationship proposals

Status: **IMPLEMENTED (backend) — M28.** The deterministic proposal engine
and the human review flow are shipped; the review-queue UI and LLM-assisted
proposal generation are DEFERRED (documented below). This document records
the exact boundary, interfaces and review workflow so the feature composes
over existing seams and never bypasses human approval.

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

## Implemented flow (M28 — mirrors intake M9)

1. **Propose** — `POST /objects/{id}/links/propose` (WRITE on the source).
   The use case (`application/use_cases/ai/propose_links.py`) is the T0
   deterministic tier of the AI architecture: it scans compatible object
   types, matches metadata field-pair evidence (e.g. publication `authors`
   ↔ faculty `name`), and for each match creates a `SMART_LINK` edge on the
   source with `provenance=INFERRED`, a deterministic `confidence`, and the
   matching `evidence` quotes. Candidates the principal cannot READ are
   skipped (no leakage through proposals); already-linked or already-decided
   targets are never re-proposed. Proposal bookkeeping lives in
   `ai.proposal.<target>` L5 metadata (kind, confidence, evidence, status,
   created_at).
2. **Review** — `GET /objects/{id}/links/proposals` lists the SMART_LINK
   proposals (READ on source). `POST /objects/{id}/links/{target}/approve`
   and `.../reject` (WRITE on source via the dependency, WRITE on the target
   checked in the use case):
   - approve: the SMART_LINK edge is removed and re-added with the proposed
     kind (e.g. `AUTHORED_BY`) and `Provenance.ASSERTED` — the human decision
     is human-asserted; `ai.review.<target>` L6 metadata records
     `reviewed_by` / `reviewed_at` / status / original confidence.
   - reject: the SMART_LINK edge is removed; the L6 review record records the
     rejection.
3. **Propagate** — the aggregate's domain events (`RelationshipAdded` /
   `RelationshipRemoved`, re-used — no new event types) ride the existing
   transactional outbox for the audit trail; the graph runtime reads edges
   live, so accepted edges are immediately visible to graph traversal and AI
   retrieval. The `search_documents` projection indexes title/metadata only
   (not edges), so no index update is required for relationship changes.

### Deliberate M28 decisions (documented)

- **No new domain events** (`LinkProposed`/`LinkApproved`/`LinkRejected`):
  the existing `RelationshipAdded`/`RelationshipRemoved` events carry the
  same audit information through the outbox; adding event types would
  duplicate functionality.
- **No LLM in the proposal path**: generation is the deterministic T0
  evidence engine (architecture tier T0 — rules/classical, CPU-stateless).
  LLM-assisted proposal generation is deferred; the engine stays the
  fallback either way.
- **Review-queue UI deferred**: the API is the review surface for now
  (`GET /objects/{id}/links/proposals`); a UI tab in the Academic AI
  workspace is future work (mirrors AssistantLabs "review").

## Explicitly out of scope for M28

- chunking/segment models; persistent citation objects; policy engine;
  agent tool execution; any autonomous edge creation; entity-extraction NLP
  pipeline (the first version works off existing metadata + retrieval, not
  raw PDF parsing).

## First consumers (status)

- `enrich_document` output gains relationship proposals (publication ↔
  project/faculty via author metadata) — DEFERRED;
- intake commit proposals (document ↔ linked course/project) — DEFERRED;
- review queue UI tab in the AI workspace (mirrors AssistantLabs "review") —
  DEFERRED (the API is the current review surface).

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
