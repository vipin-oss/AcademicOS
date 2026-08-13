# AcademicOS — FINAL ADVERSARIAL ARCHITECTURE AUDIT & FREEZE CONTRACT

**Role:** Final Independent Adversarial Architecture Auditor
**Repository audited:** `https://github.com/vipin-oss/AcademicOS`
**Baseline (independently verified this audit):** branch `feature/ai-knowledge-projection-p0`, commit `07c434cad05ae87db741c191cc914625801147ea` — "feat(ai): add scalable knowledge search and document identity", tree `ee9c7fdefe71f7d0647d4fca0df0a5ce0b54861d`, working tree clean. GitHub API independently confirms the same SHA/tree/message.
**Document under audit:** AcademicOS_Master_Blueprint v2.0 (598 lines, 40 sections + audit parts + ADR register)
**Date:** 2026-08-12
**Rule honored:** architecture audit only. No code, no patches, no commands, no implementation.

---

# PART 1 — INDEPENDENT REPOSITORY VERIFICATION

All statements below were re-verified at source in this session on the exact baseline commit (fresh `git rev-parse` = `07c434c…`, `git status` clean, GitHub API matching). The full test suite for this byte-identical tree was executed earlier in this conversation: **backend 1864 passed / 2 skipped; frontend 101 passed; typecheck clean.**

| Area | Verified fact | Blueprint claim matches? |
|---|---|---|
| Backend architecture | FastAPI + SQLAlchemy 2.0 + Pydantic v2; clean layering domain → application (use cases/commands/queries/services/ports) → infrastructure → api/routes | ✔ |
| Frontend architecture | Next.js 14 App Router, module pages (research, teaching, publications, admin, finance, events, committees, students, documents, reports, productivity) + assistant/chat/AI/assistants pages | ✔ |
| Database schema | PostgreSQL 16 (SQLite dev/CI); 12 Alembic migrations (objects, relationships, outbox, versions, search docs, eval, reviews, annotations, contents, chunks, FTS/identity) | ✔ |
| Object model | Single `UniversalObject` aggregate; 43 `ObjectType` members; lifecycle draft/active/archived/superseded; optimistic concurrency; domain events | ✔ |
| Object relationships | Typed directed `RelationshipKind`; graph runtime (BFS/DFS/path/cycles, depth≤5, nodes≤200, ACL-gated, batched loads) | ✔ |
| Document model | `document` object type; upload→stage→extract→review→commit; direct-upload path indexes content synchronously in the request (`_index_direct_upload_content`) | ✔ |
| Document identity | Content-hash registry (normalized text → canonical document; duplicates counted; recompute/rebuild) | ✔ |
| Versions | Version snapshots + per-projection version keys; outbox version-aware upserts | ✔ |
| Metadata/provenance | 7-layer metadata (L1–L7), per-entry `Provenance` (asserted/inferred/system) + optional confidence; FR-MET-009 (human-asserted never overwritten by machines) | ✔ |
| ACL/permissions | `ObjectPermissionEvaluator` (owner/readers/writers/managers + role entries; no-ACL objects open by default — legacy), `RoleBasedPermissionEvaluator`, `AllowAll` default; retrieval pre-filters through READ gate; SQL-level internal-type exclusion | ✔ |
| Outbox | Outbox table + relay (at-least-once, idempotent, version-aware); deletes emitted in the same transaction | ✔ |
| Projections | FTS (`document_search_fts`, generated tsvector + GIN / FTS5), Qdrant vectors, chunks, search documents, identity — each one writer, atomic rebuild from snapshots | ✔ |
| FTS | Verified as above; `to_tsvector('simple')`, deterministic; no `acl_scope` on rows | ✔ |
| Qdrant/vector | Versioned base collection + `search_objects_active` alias swap; deterministic cosine search; payload lacks ACL scope | ✔ |
| Chunking | Deterministic 1000-char/120-overlap, normalized-content hash; chunks have start/end spans but no page/block anchors | ✔ |
| Evidence system | Evidence gate (document-named questions need named doc + extractable text in ACL-filtered evidence); bounded chunk evidence (≤3 chunks / ≤2000 chars); `available=False` honesty | ✔ |
| Citation system | Citation builder + verifier; only search-hit items citable; graph-only neighbors never citable (leak fixed at `e14aa6b`); citations verified against store | ✔ |
| Grounded QA | `grounded_qa.py` (686 lines): retrieve → context budget → prompt → generate → verify; streaming with completion-only delivery; provenance (provider/model/prompt id+version/tokens/latency) | ✔ |
| Assistant/retrieval | Two personalities: `rules-v1` (36 `_answer_*` builders) + LLM grounded QA; retrieval = hybrid (lexical+semantic RRF k=60) + graph BFS, dedupe, deterministic order | ✔ |
| Intent/rules architecture | `intents.py`: 108 `re.compile` patterns over ordered rule table; phrase→intent routing tests (`test_routing`, `test_shadow_precedence`) | ✔ |
| AI gateway/provider | `AiCore` provider catalogue (5 kinds), OpenAI-compatible httpx gateway (streaming, T=0, bounded retries, cost accounting), placeholders, feature flags default OFF | ✔ |
| Memory | Conversation recall (hybrid search scoped to `ai_conversation` + graph), review-ranked, consolidation (Jaccard ≥ 0.7 supersede-not-delete); no persistent knowledge layer | ✔ |
| Intake pipeline | Staged runner: stage (MIME sniff, SHA-256) → extract → review → commit; idempotent resume, per-item isolation, junk hygiene | ✔ |
| Extraction | Parsers: pypdf, python-docx, text-family (txt/md/markdown/csv/json). `SUPPORTED_FORMATS` has **no xlsx, no pptx, no images** | ✔ |
| OCR status | **None.** Only `needs_ocr` flag for zero-character PDFs; no tesseract/paddleocr/easyocr anywhere in non-test code | ✔ |
| Classification status | Deferred: `DEFERRED_STAGE_MILESTONES` = CLASSIFY→M5, MATCH→M7, PROPOSE→M8 | ✔ |
| Entity extraction | None in the document pipeline (only structured-object `propose_links` for manually entered records) | ✔ |
| Relationship extraction | None from documents; Smart Link (INFERRED, review-gated) exists for structured objects | ✔ |
| Fact/claim storage | **None.** Metadata entries only; no claim store | ✔ |
| Review/confirmation | Intake review workspace + review decisions + annotations exist; no document-intelligence confirmation queues | ✔ |
| Background jobs | stdlib `threading` + `queue.Queue` (single worker) + outbox relay thread; no worker pool | ✔ |
| Frontend AI surfaces | assistant page, chat, AI home, domain assistants (research/teaching/publication/admin), eval history UI | ✔ |
| Startup/dev workflow | `start.ps1` → `scripts/windows/start_academicos.ps1` (PostgreSQL service-or-Docker, Docker Desktop, Qdrant, backend deps+migrations, backend+frontend); `stop.ps1`, `health_check.ps1`, `reset_academicos.ps1`; `docker-compose.yml` (pg16 + qdrant + ollama) | ✔ |
| Tests | 1864 passed / 2 skipped (reproduced); frontend 101 (reproduced); architecture guardrail tests (import isolation, composition authority, provider isolation) | ✔ |
| CI | `.github/workflows/ci.yml`: 3 jobs — backend pytest+architecture on SQLite; frontend vitest+tsc+build; PostgreSQL repository contract. Qdrant not a CI service (in-process emulator) | ✔ |

**Result:** every repository claim in the blueprint checks out. No factual error found. One caveat the blueprint itself carries and which is confirmed: `WORKSPACE`/`SPACE`/`MEMORY_ARTIFACT`/`PROACTIVE_INSIGHT` are enum members with **no exercised data model** — tenancy is not yet a runtime concept.

---

# PART 2 — PRODUCT VISION AUDIT

The blueprint is checked against the 24-point vision. Coverage:

| # | Vision requirement | Where covered in blueprint | Status |
|---|---|---|---|
| 1 | preserve original file | §9 pipeline stage 1; §11 (file is authority) | ✔ |
| 2 | identify format | §9 type detection; §10 parsers registry | ✔ |
| 3 | extract digital text | §10 digital parser; §31 KEEP extraction | ✔ |
| 4 | detect scanned | §10 detection cascade (per-page text density) | ✔ |
| 5 | OCR scanned | §10 OCR engine behind port; §39 handwriting deferred | ✔ |
| 6 | page/source preservation | §10 per-page model; §13 source_binding; §21 span citations | ✔ |
| 7 | document structure | §11 CDM block model (heading/section/table/figure/caption/footnote/header/footer/equation) | ✔ |
| 8 | extract metadata | §9 metadata stage; §15 projection | ✔ |
| 9 | classify into domains | §9 multi-label classification + §23 confirmation; multi-domain explicit (A.4.13) | ✔ |
| 10 | identify entities | §12 entity model + resolution; §18 resolve_entity tool | ✔ |
| 11 | dates/amounts/references/facts | §13 claim model (predicate/value incl. money/date); §10 references | ✔ |
| 12 | connect to existing objects | §14 relationship model (document→object edges) | ✔ |
| 13 | discover relationships | §9 relationship proposal (INFERRED, review-gated) | ✔ |
| 14 | searchable knowledge | §15 projections (FTS, vectors, adjacency) | ✔ |
| 15 | semantic representations | §15 + §19 vector; §28 embed policy; §31 NEW real embedder | ✔ |
| 16 | available to AI | §8 knowledge plane + §18 tools (ACL-filtered) | ✔ |
| 17 | English/Hinglish questions | §16 query understanding (Hinglish normalization is model-driven) | ✔ |
| 18 | cross-domain questions | §26 cross-domain reasoning; §17 capability registry | ✔ |
| 19 | evidence and citations | §20/§21 evidence + citation architecture | ✔ |
| 20 | ask confirmation when uncertain | §23 human confirmation + §16 clarify | ✔ |
| 21 | learn from corrections | §24 correction/supersession; rejections feed evaluation | ✔ |
| 22 | provenance and history | §13/§15/§22; as-of queries (§24); ADR-006/007/008 | ✔ |
| 23 | respect permissions | §27 ACL/security laws | ✔ |
| 24 | never silently invent | §20 evidence gate; §A.6 never-list; claim verifier | ✔ |

**Verdict:** the blueprint captures the complete vision — not a subset, and not the "five tabs + AI box" anti-vision. The Product Mission (§2) encodes the mandated transformation chain (RAW → UNDERSTANDING → STRUCTURED → CONNECTED → RETRIEVAL → REASONING → VERIFIED ANSWER). Complete.

---

# PART 3 — PDF/DOCUMENT INTELLIGENCE AUDIT

## 3.1 The three-level distinction

The blueprint explicitly distinguishes (and this audit confirms each):

- **PDF TEXT EXTRACTION** — exists in repo (pypdf). Blueprint: KEEP (§31), with the reading-order caveat documented.
- **DOCUMENT UNDERSTANDING** — structure → CDM: **net-new**, fully specified (§10, §11): block model, page furniture, tables as grids, figures/captions, footnotes, references, reading order as data.
- **KNOWLEDGE EXTRACTION** — metadata/classification/entities/facts/relationships with confidence, provenance, spans: **net-new**, fully specified (§12, §13, §14, §22) and contract-gated by ADR-001…010.

The blueprint nowhere equates "PDF parser exists" with "document intelligence exists." It explicitly flags the pipeline stops at text today (§7) and sequences the full chain.

## 3.2 The 29-point checklist

Verified coverage in v2.0: identification ✔, digital extraction ✔, scanned detection ✔, OCR ✔, page provenance ✔, reading order ✔, headings ✔, sections ✔, tables ✔, figures ✔, captions ✔, footnotes ✔, headers/footers ✔, references ✔, metadata ✔, classification ✔, entity extraction ✔, fact extraction ✔, relationship extraction ✔, confidence ✔, provenance ✔, human confirmation ✔, correction ✔, reprocessing ✔, versioning ✔, idempotency ✔, failure/retry ✔, deletion ✔, ACL propagation ✔. Document identity: covered by ADR-002b (§14 of audit, ADR register §37).

## 3.3 Dependency-safe path

FILE → TEXT → STRUCTURE → METADATA → CLASSIFICATION → ENTITIES → FACTS → RELATIONSHIPS → VERIFIED KNOWLEDGE → AI RETRIEVAL is fully mapped: §9 (stages), §11 (CDM), §12 (entities), §13 (facts), §14 (relations), §23 (confirmation → verified), §18/§19/§20 (retrieval + evidence). Each stage is an idempotent, resumable, engine-version-stamped job with per-item isolation and DLQ (§9, §36).

**Is PDF intelligence the first implementation level?** The blueprint's evidence-based decision (A.5): **No as literal level 1 — contracts (L1) precede engines (L2); within L2, PDF/OCR is the first engine sub-deliverable.** This audit agrees: engines writing into an undesigned fact model would be rebuilt; the patch freeze (L0) is order-independent and urgent. The user's intuition ("PDFs are the biggest missing capability") is honored *within* the correct dependency structure.

---

# PART 4 — KNOWLEDGE-PLANE CONTRACT AUDIT (the critical one)

Checklist against the mandate, with the blueprint's resolution:

| # | Question | Blueprint resolution | Complete? |
|---|---|---|---|
| 1 | Document vs domain-object identity | ADR-001: source stays a document; domain objects are separate projections; auto-proposed objects DRAFT + INFERRED, promoted by confirmation | ✔ |
| 2 | Metadata vs facts/claims | ADR-002: claim store is the single AI-visible fact source; object metadata = committed projection of confirmed claims; engines never write metadata | ✔ |
| 3 | Extracted vs inferred vs confirmed | Claim provenance (EXTRACTED/INFERRED/ASSERTED) + status (PROPOSED/CONFIRMED/REJECTED/SUPERSEDED); only CONFIRMED/ASSERTED auto-usable | ✔ |
| 4 | Correction vs overwrite | ADR-006: correction → ASSERTED, immutable by engines; engines propose, never silently replace | ✔ |
| 5 | Supersession | Supersede-not-delete; `supersedes_fact_id` chain; history queryable | ✔ |
| 6 | Deletion | ADR-007: outbox cascade to projections; claims orphaned+flagged (kept for audit); blobs grace-deleted; citations invalidate | ✔ |
| 7 | Re-upload | ADR-002b: canonical per content-hash; duplicates linked, never silently merged | ✔ |
| 8 | File versions | ADR-002b: explicit new-version semantics — **but the cascade "new file version → old claims/CDM superseded → re-extraction proposes new claims" is only implied, not a law.** See mandatory change M-3. | **Gap** |
| 9 | Engine versions | ADR-008: every artifact stamped engine+version; reprocessing on upgrade | ✔ |
| 10 | Provenance | Layers + provenance per value + engine version + reviewer | ✔ |
| 11 | Source spans | ADR-003: every claim binds ≥1 span (document_id, block/chunk, page, chars) | ✔ |
| 12 | ACL inheritance | ADR-009: `acl_scope` on every derived row, recomputed on ACL change | ✔ |
| 13 | Tenant ownership | ADR-017: owner/acl_scope stamped at creation; partition later; legacy quarantined | ✔ |
| 14 | Historical truth / as-of | Supersede chain + versioned claims; answers state as-of date | ✔ |
| 15 | Reprocessing | ADR-008: rebuild = re-run jobs with provenance; byte-identical only for unchanged engines | ✔ |

**Answer to the mandate's decisive question — "Can an engineer build the PDF intelligence layer without later discovering the knowledge model itself must be redesigned?":**

**YES, with two caveats, both contract-text amendments, not architecture changes:**
1. The claim predicate in §13 is specified as a "typed enum." A closed enum is a future-rewrite trap the day a new fact kind appears. The contract must declare predicates a **versioned, registry-driven catalogue** (predicate id + per-predicate value schema + validation) — additive, never a schema rewrite. (M-1)
2. The file-version → claim supersession cascade must be an explicit law (M-3). Without it, a revised sanction letter leaves old claims standing as if current.

With M-1 and M-3, the knowledge model is closed and extensible in the right directions, and the PDF layer is dependency-safe.

---

# PART 5 — AI REASONING ARCHITECTURE AUDIT

The mandated chain `USER QUESTION → QUERY UNDERSTANDING → CAPABILITY → PLAN → PLAN VALIDATION → TOOL SELECTION → TOOL EXECUTION → RETRIEVAL → EVIDENCE → VERIFICATION → ANSWER` is fully specified:

- **Canonical capability registry** — §17, frozen taxonomy (inventory, lookup, list, count, search, filter, summarize, compare, aggregate, timeline, document_qa, relationship, cross_domain, absence, temporal, navigate, clarify, refuse); additive-only.
- **Plan schema** — §16 `{operation, domains[], entities[], time_range, filters{}, output_kind, evidence_required, sub_plans[]}`; frozen in L1.
- **Structured output** — §16 (LLM produces the plan as structured output), §A.6.
- **Validation** — §16 deterministic validation (schema, types, entity resolution, ACL scope).
- **Clarification protocol** — §16 clarify on ambiguous entity/range; §23; §17 `clarify` capability.
- **Deterministic fast path** — §16 (≤15 frozen commands), offline-capable.
- **LLM planner** — §16 + §38.4 model budget; degrades to fast-path/clarify/refuse, never wrong retrieval.
- **Tool registry** — §18 `{name, input_schema, output_schema, acl_scope, deterministic, cost_class}`; initial tools incl. SQL, aggregate, FTS, vector, graph, document-QA, inventory, fact-recall, memory-recall, resolve-entity, resolve-time.
- **Retrieval router** — §19 operation→mechanism matrix (SQL/FTS/vector/graph/anti-join/chunks).
- **SQL/FTS/vector/graph/document-QA/aggregation/temporal tools** — §18 + §19, all ACL-filtered.
- **Evidence envelope** — §20 (bounded, provenance-carrying, logged).
- **Citation validation** — §21 (citation ∈ evidence, ids/spans valid, graph-neighbors banned).
- **Refusal logic** — §20/§A.6; honest `available=False` retained.
- **Ambiguity handling** — §16/§23.
- **Hinglish** — §16 model-driven normalization (never regex lists).
- **Multi-step** — sub_plans; §26 cross-domain chains.
- **Cross-domain** — §26 entity-anchored multi-hop.

**Deterministic vs model vs tool vs never** — sharply drawn in §A.6: ACL, verification, evidence gate, arithmetic, aggregation, refusal triggers deterministic (never LLM); query understanding, extraction refinement, synthesis model-driven (validated); SQL/FTS/vector/graph/aggregation tool-driven; model self-citations, access decisions, existence claims, and arithmetic never left to the LLM.

**Decisive question — "Can a new user question be supported by adding a CAPABILITY or TOOL rather than modifying dozens of unrelated rules?"** Yes, by construction: language variability is absorbed in query understanding (model), operations are a frozen registry, new capabilities are additive registry entries + tool implementations (§17/§18). The only vector back into the patch farm is the fast-path growing or a hidden regex fallback — closed by mandatory change M-2 and the Anti-Pattern Policy.

---

# PART 6 — SECURITY / CORRECTNESS AUDIT

| Guarantee | Blueprint | Verified |
|---|---|---|
| ACL enforcement | §27 invariant: no path returns unreadable content; pre-filter + re-verify | ✔ |
| Tenant isolation | §27/§28 + ADR-017; isolation matrix gate | ✔ |
| Citation safety | §21 citable set + verification | ✔ |
| Evidence safety | §20 evidence envelope, bounded, logged | ✔ |
| No graph-only citations | §21 (banned; repo fix `e14aa6b` kept as regression) | ✔ |
| No conversation-memory-as-evidence | ADR-015; §20 | ✔ |
| Deterministic arithmetic/aggregation | §A.6; §19 (SQL aggregation; LLM arithmetic never) | ✔ |
| No unauthorized retrieval | §27 tools carry user principal; planner never queries | ✔ |
| No LLM-controlled access decisions | §A.6 never-list | ✔ |
| No LLM-controlled citations | §21 verification; model self-citations rejected | ✔ |
| Provenance for every derived fact | §13/§15/§22 | ✔ |
| Human-confirmed facts cannot be silently overwritten | ADR-006 (ASSERTED immutable) | ✔ |
| Deleted documents cannot produce valid evidence | ADR-007 (claims orphaned+flagged; citations invalidate) | ✔ |
| Stale projections cannot become authoritative | §15 (projections derived, engine+version stamped, rebuild semantics) | ✔ |

**Gaps found: none at the architecture level.** Two enforcement notes, both already in the contract: (a) the isolation matrix must be a *release gate* (it is, §27/§29/§34/§35); (b) legacy no-ACL objects must be migrated or quarantined at L1 (ADR-017).

---

# PART 7 — ROADMAP DEPENDENCY AUDIT

Dependency graph (producer → consumer):

```
L0 Freeze+EvalHarness ──────► everything (gates)
   │
   ▼
L1 Knowledge-Plane Contracts ◄── consumed by L2, L3, L4, L5, L6, L7, L8, L12, L13
   ├────────────► L2 Document Intelligence ──► L10 (workers), L11 (storage)
   ├────────────► L3 HITL
   ├────────────► L4 Query Understanding ──► L8 Cross-domain
   ├────────────► L5 Tools ──► L6 Evidence, L7 Memory, L8
   └────────────► L13 Semantic upgrade
L9 Evaluation gates ── consumes L1–L8
L12 Tenancy ── consumes L1 stamping
L14/L15 ── deferred, consume L2 / L4–L8
```

Per-level audit:

| Level | Prereq | Produces | Consumed by | Independent? | Rewrites an earlier level? |
|---|---|---|---|---|---|
| L0 | — | freeze + harness + inventory | all | yes | no |
| L1 | L0 | schemas/ports/ADRs/acl_scope/citation schema | L2–L8, L12, L13 | yes | no |
| L2 | L1 | engines (PDF/OCR first) writing to L1 | L3, L10, L11 | no | no (L1 frozen) |
| L3 | L1 | queues, correction | users, eval | partly | no |
| L4 | L1 (parallel L2) | planner, fast-path, validation | L8 | partly | no |
| L5 | L1 | tools | L6, L7, L8 | no | no |
| L6 | L1, L5 | fact citations, confidence UI | eval | no | no |
| L7 | L1, L5 | persistent memory | L8 | no | no |
| L8 | L4, L5 | multi-hop, absence, temporal, compare | L15 | no | no |
| L9 | L1–L8 | gates | all | no | no |
| L10 | L2 | workers/queue/DLQ | L11 | no | no (thread→pool behind same jobs) |
| L11 | L2 | object storage | L12 | no | no (storage behind port) |
| L12 | L1 stamping | partition keys, isolation | university | no | no (stamping from L1) |
| L13 | L1 | real embedder | retrieval | no | no (port + alias swap) |
| L14 | L2 | figures/equations/handwriting | future | — | deferred (correctly) |
| L15 | L4–L8 | agent/assistant surface | future | — | deferred (correctly) |

**Verdict:** ordering is correct. No level builds an engine before its output contract exists (L1 precedes L2/L4/L5). Evaluation is introduced at L0 (skeleton) and hardens at L9 — early enough to prevent phrase-regression culture. PDF/OCR engines are sequenced after L1 contracts and before other engines. AI planner work (L4) is sequenced to run in parallel with L2 so the patch regime ends early. No level can force a rewrite of an earlier level, because L1 freezes contracts and everything downstream is additive behind ports.

---

# PART 8 — SCALE AUDIT (incl. 1M documents)

Blueprint table covers 1k/10k/100k (§28). The mandate additionally demands 1M — this audit extends the contract:

| Concern | 10 | 1k | 10k | 100k | 1M (planned mechanisms) |
|---|---|---|---|---|---|
| Storage | local | local | object storage (behind port) | object storage + tiering | object storage + tiering + cold archive |
| FTS | PG | PG | PG (GIN) | partition by tenant/time | partition + optional read replicas; no new engine without measured evidence |
| Chunks | PG | PG | PG | PG (partitioned) | PG (partitioned); chunk store is simple keyed rows |
| Vectors | Qdrant | Qdrant | Qdrant | Qdrant multi-tenancy | Qdrant multi-node/sharding; alias swap retained |
| Workers | thread | thread | worker pool | workers + priority queues | horizontal worker pool + batch reprocessing |
| Outbox | ok | ok | ok | ok | ok (single relay; scale via batch sizes) |
| Rebuild | ok | ok | ok | windowed rebuild | windowed/parallel rebuild |
| ACL filtering | in-memory | candidate-level | acl_scope WHERE | acl_scope + partitions | acl_scope + partitions + cached scopes |
| Ingestion latency | ms | s | async (job) | async | async, prioritized |
| Query latency | ms | ms | <300ms p95 | <300ms p95 | <300ms p95 (cache frequent queries) |
| Memory budgets | fixed | fixed | fixed | fixed | fixed (indexes, never context) |
| Multi-user isolation | n/a | n/a | stamping | partition keys | partition keys + isolation matrix |

Doctrine preserved at every scale: one writer per projection; all projections rebuildable; dedupe prevents duplicate embedding cost; no Kafka/Elasticsearch/Temporal/microservices/new DB without measured evidence (the blueprint's over-engineering firewall, §A.7, is correct). **The 1M row is added to the contract in Part 13 (scale law).**

---

# PART 9 — SINGLE-COMMAND DEVELOPER EXPERIENCE

Requirement: one command starts backend + frontend + PostgreSQL + Qdrant + Ollama + migrations + health checks.

Verified current state: `start.ps1` → `scripts/windows/start_academicos.ps1` already orchestrates PostgreSQL (service or Docker), Docker Desktop check, Qdrant container, backend dependency install + migrations, backend + frontend startup, and there is a `health_check.ps1`; `docker-compose.yml` declares pg16 + qdrant + ollama. **The requirement is already met in essence today** — the two gaps are: Ollama model pull is a documented manual step, and health checks are a separate command.

Where the requirement belongs in the contract: §30 (Developer Experience) — polish only: automated Ollama pull, migration auto-run on start, health check folded into start, eval CLI, seeded demo corpus. This is an operational enhancement to an existing working mechanism — zero architecture risk. **Verdict: requirement is preserved and realistic; it belongs to L0/L1 tooling, not to the core contract.**

---

# PART 10 — ANTI-PATCH GUARANTEE

Scenario: six months post-freeze, "mere HSRF project ke documents aur publications ka summary do" fails.

**Would the blueprint force B (capability diagnosis) or allow A (regex patch)?**

Forced path B — by contract:
1. The failure is a question; the only code paths are the LLM planner → plan validation → tools. There is no regex intent table left (REPLACE, §31; Anti-Pattern Policy §32.1).
2. Diagnosis is capability-level: which capability (cross_domain + summarize + document_qa) failed? Which tool? Which evidence? (§17/§18/§19; audit trail of plan+tool calls, §34 L6).
3. The fix is a reusable change: a tool, a plan-validation rule, a prompt, or a retrieval/evidence improvement — plus a **capability-level regression test** (§29) and measurement (§35).
4. Merge gates block A: no new regex/intent/branch (§32), no phrase→intent test tables (§32.3), "tests pass" never equals convergence (§32.4).

**Places where the architecture could accidentally regress into A — the watchlist (all closed by the contract, but enumerated so implementers cannot miss them):**
1. **Fast-path growth** — the ≤15 frozen commands must never grow (frozen at L4 cutover; new commands go through the planner).
2. **Planner-failure fallback** — must be clarify/refuse (and offline fast-path for its frozen list), **never** a hidden regex parser. (M-2 makes this law.)
3. **Retained `rules-v1`** — must be deleted at cutover, not kept as a "fallback" that keeps growing (ADR, §31, §36.9).
4. **Plan-validation bypass** — validation failure must not degrade to substring matching.
5. **Test-shape regression** — any new `(question → intent)` table is a policy violation.
6. **Domain-assistant logic duplication** — role specialization stays prompt/guardrail level (§32.9).

Verdict: the blueprint structurally forces B and mechanically blocks A, provided the four freeze conditions + M-1/M-2/M-3 hold.

---

# PART 11 — FREEZE TEST (attempting to break the blueprint)

The blueprint's own A.10 covers 12 classic failure scenarios with mitigations. This audit adds independent attack cases:

| Future need | Risk | Why | Missing contract? | Required ADR |
|---|---|---|---|---|
| New fact kinds (exam dates, venue capacity, lab equipment) | Claim predicate enum is closed → schema migration → fact model redesign | §13 "typed enum" | Predicate = versioned registry with per-predicate value schema | **ADR-019 (M-1)** |
| Planner unavailable / low-quality output | Engineer "fixes" it with a regex fallback → patch farm returns | Fast-path/fallback boundary implicit | Law: planner failure → clarify/refuse; regex intent parsing deleted; fast-path frozen | **ADR-020 (M-2)** |
| User uploads revised sanction letter | Old claims stay current → wrong "as-of" answers → cascade redesign | ADR-002b implies but doesn't command the cascade | Law: file-version replacement supersedes old claims/CDM; re-extraction proposes new; nothing merges silently | **ADR-021 (M-3)** |
| Frontend/backend drift on new surfaces | Claims/CDM/confirmation/plans endpoints drift without frozen API contracts | No API-contract clause in blueprint | L1 freezes OpenAPI contracts for all new surfaces; UI consumes only those | **ADR-022 (M-4)** |
| 1M documents / university deployment | Capacity plan stops at 100k | §28 table | 1M row + trigger conditions + measured-evidence rule | **Scale law (M-5)** |
| Confirmation inbox scale | Queues grow unbounded without triage | — (minor) | Batch ops + priorities in L3 acceptance | fold into L3 |
| Graph traversal hot at scale | BFS over PG at 1M objects | — (future) | Dedicated graph store only with measured evidence (already the rule) | fold into §28 |
| Embedding cost explosion | Re-embedding churn | — | Embed-once + dedupe + alias swap (ADR-016) | already covered |
| Role-context ACL (faculty+HoD+committee) | Current role sets may be insufficient | Open question §38.8 | Resolve as ADR during L0/L1 | per §38 |

**Result:** after the five amendments (M-1…M-5), no attack case produces a required *architectural* rewrite. Every residual risk is either an ADR amendment (localized, impact-analyzed) or an explicitly deferred future with a measured trigger.

---

# PART 12 — FINAL VERDICT

# YELLOW — FREEZE AFTER SPECIFIC CHANGES

The blueprint v2.0 is architecturally sound and repository-grounded; every factual claim verified; the vision captured completely; the dependency order correct; the anti-patch mechanism structural. It is not, however, safe to freeze *as written*, because five specific contract items would otherwise be discovered mid-implementation:

**Mandatory changes (each: Problem · Evidence · Required ADR · Why it prevents rewrite · Level):**

**M-1 — Claim predicate catalogue must be registry-driven, not a closed enum.**
- *Problem:* §13 specifies `predicate (typed enum: sanctioned_amount, principal_investigator, issue_date, …)`. A closed enum means every new fact kind is a schema migration — the classic "fact model cannot support X" rewrite.
- *Evidence:* no claim store exists yet (verified); the contract is being written now, so the extensibility decision is free.
- *Required ADR:* **ADR-019** — predicates are a versioned catalogue (predicate_id, per-predicate value schema, validation); additions are additive data, never schema changes; unknown predicates stored as `raw` with extraction text, never dropped.
- *Why it prevents rewrite:* the fact model's shape is fixed once; new domains/fact kinds never touch the schema.
- *Level:* L1.

**M-2 — The planner-failure fallback law must be explicit: never regex, never a hidden intent parser.**
- *Problem:* §16 and §31 say the regex layer is replaced and rules-v1 retired, but the exact failure semantics of the LLM planner are only implicit. The single most likely re-entry point for the patch farm is "planner failed → fall back to the old parser."
- *Evidence:* 108 regexes / 36 builders exist today; the fallback temptation is documented history (the repo's own "forensic fix" comments).
- *Required ADR:* **ADR-020** — on planner failure: deterministic fast-path (frozen list only) → clarify → refuse. Regex-based intent parsing is deleted at cutover, never invoked, never resurrected; fast-path list is frozen and cannot grow.
- *Why it prevents rewrite:* it is the mechanical guarantee of the anti-patch objective; without it, "freeze" is aspirational.
- *Level:* L4 (law ratified at L0, enforced at L4 cutover).

**M-3 — File-version → claim/CDM supersession cascade must be a law.**
- *Problem:* ADR-002b defines content identity and versions but does not command what happens to old claims when a document is replaced by a newer version.
- *Evidence:* identity store flags duplicates today; no merge/replace policy exists (verified).
- *Required ADR:* **ADR-021** — replacing a file supersedes its claims and CDM; re-extraction proposes new claims (PROPOSED); nothing is silently merged or deleted; "as-of" answers use the supersede chain.
- *Why it prevents rewrite:* prevents the "current vs historical truth" corruption that would otherwise force a redesign of the fact layer.
- *Level:* L1.

**M-4 — L1 must freeze API contracts for all new surfaces.**
- *Problem:* the blueprint never mentions API stability for claims/CDM/confirmation/plans/tools; frontend and backend would drift during L2/L3.
- *Evidence:* the current repo has a stable route layer; new surfaces have no contract clause.
- *Required ADR:* **ADR-022** — L1 ships OpenAPI contracts for every new surface; UI consumes only contracted APIs; contract changes require ADR amendment.
- *Why it prevents rewrite:* UI/API churn is a major source of "rewrite" perception; freezing contracts isolates it.
- *Level:* L1.

**M-5 — Scale law must extend to 1M documents with measured-trigger doctrine.**
- *Problem:* the mandate asks for 1M; §28 stops at 100k.
- *Evidence:* no scale design exists in the repo; the blueprint's PG+Qdrant+worker doctrine is the right base.
- *Required:* scale law — at 1M: PG partitioning (L12), Qdrant multi-node/sharding, storage tiering, horizontal workers, cached ACL scopes; **no new database/queue/event-bus/microservice without measured evidence** (Kafka/Elasticsearch/Temporal explicitly out unless proven).
- *Why it prevents rewrite:* codifies the smallest-working-architecture principle so scale is additive, not a migration.
- *Level:* L1 (doctrine) / L10–L12 (mechanisms).

**After M-1…M-5 are written into the contract text (they are, in Part 13 below): the amended contract is GREEN.**

---

# PART 13 — FINAL FROZEN CONTRACT

*(This contract incorporates M-1…M-5. It is the permanent reference for implementation chats. It supersedes the v2.0 text only by adding ADR-019…022 and the scale law; everything else in v2.0 is ratified unchanged.)*

## 13.1 Product Vision
AcademicOS is a unified, permission-bound Academic Operating System for university faculty: one knowledge system in which uploaded files (especially PDFs) are automatically transformed — via digital extraction, OCR where needed, structure and metadata extraction, multi-label classification, entity and relationship discovery, and fact projection — into confirmed-or-confirmable knowledge connected to the faculty member's structured data; and one model-based AI reasoning layer answers natural-language questions (English and Hinglish) across the entire accessible knowledge base with deterministic planning, ACL-gated retrieval, and evidence-verified, span-cited answers. It is not a CRUD app, document store, search engine, or chatbot. Tabs are views; the AI has no tabs.

## 13.2 Core Architectural Laws
1. **One knowledge system, one AI reasoning layer, multiple views.** No per-tab AI logic, no per-question code.
2. **Smallest working architecture.** PostgreSQL + Qdrant + one worker pool + existing Next.js + existing LLM gateway. No new database, queue, event bus, or microservice without measured evidence.
3. **Derived state is never authoritative.** Every projection has exactly one writer, is versioned, and is rebuildable from authoritative state; rebuild is byte-identical when engines are unchanged.
4. **Everything downstream is additive behind ports.** A port earns its place with ≥2 consumers or ≥2 adapters.
5. **Level order is contract: L0 → L1 → L2 → …** No engine before its output contract; nothing built early without a level.

## 13.3 Knowledge Model Laws
1. **Source identity (ADR-001).** A source is always a `document` object; domain objects are separate projections; auto-proposed objects are DRAFT with INFERRED links, promoted only by user confirmation.
2. **Fact/metadata boundary (ADR-002).** The claim store is the single AI-visible fact source; object metadata is the committed projection of confirmed claims; engines never write metadata directly; FR-MET-009 semantics extend to claims.
3. **Content identity (ADR-002b).** Canonical document per normalized-content hash; re-uploads link to the canonical (duplicate record, never a silent merge).
4. **Extensible predicates (ADR-019).** Predicates are a versioned catalogue with per-predicate value schemas; new fact kinds are additive, never schema migrations; unparseable values are stored as raw with the source text, never dropped.
5. **Lifecycle (ADR-005/006/021).** Claims: PROPOSED → CONFIRMED/REJECTED → SUPERSEDED (never deleted). Correction → ASSERTED, immutable by engines. Replacing a file supersedes its claims and CDM; re-extraction proposes new claims; as-of answers use the supersede chain.
6. **Deletion (ADR-007).** Outbox cascade to projections; claims orphaned + flagged (kept for audit); blobs grace-deleted; citations to deleted sources invalidate.
7. **Reprocessing (ADR-008).** Every artifact stamped engine+version; rebuild = re-run jobs with provenance.
8. **Entities (ADR-010).** Typed nodes; domain is a tag, never a type; gazetteer (object graph + aliases) first, NER second, unresolved → proposal.

## 13.4 Document Intelligence Laws
1. **PDF text extraction ≠ document understanding ≠ knowledge extraction.** All three are distinct stages; the pipeline maps FILE → TEXT → STRUCTURE (CDM) → METADATA → CLASSIFICATION → ENTITIES → FACTS → RELATIONSHIPS → VERIFIED KNOWLEDGE → AI RETRIEVAL.
2. **PDF/OCR is the first engine sub-deliverable of L2** (after L1 contracts).
3. **Per-page model.** Page index on chunks, spans, CDM blocks, citations; OCR text and confidence stored per page, never silently merged with digital text.
4. **Reading order is data, not a claim.** Best-effort ordering stored on blocks; page furniture (headers/footers/footnotes) detected and excluded from body order.
5. **Multi-label classification** with per-domain confidence; never a single-domain assignment.
6. **Confidence contract (ADR-004).** Composition rule (engine × OCR × corroboration × gazetteer); OCR-derived values capped at medium; tiers high/medium/low; disclosed in UI and answers.
7. **Idempotency, retries, DLQ, per-item isolation** for every stage; unsupported status is honest; reprocessing on engine upgrade.
8. **ACL inheritance (ADR-009).** Every derived artifact carries the source's `acl_scope`.

## 13.5 AI Reasoning Laws
1. **Query understanding is model-driven** (LLM structured plan; Hinglish normalization in the model). A new phrasing requires zero code.
2. **Deterministic fast-path** of ≤15 frozen commands; the list is frozen and cannot grow; new commands go through the planner.
3. **Planner failure semantics (ADR-020):** fast-path (frozen) → clarify → refuse. Regex intent parsing is deleted at cutover and never invoked; `rules-v1` is deleted, not retained.
4. **Plan validation is deterministic** (schema, types, entity resolution, ACL scope); validation failure never degrades to substring matching.
5. **Capabilities are a frozen registry (ADR-014).** New capability = additive registry entry + tool implementation + capability-level tests.
6. **Tools carry the user's principal; the planner never queries data.** Every tool call is logged for audit.

## 13.6 Evidence/Citation Laws
1. **Evidence gate.** Document-named questions require the named document in the ACL-filtered evidence with extractable source text; otherwise refuse.
2. **Citable set.** Search-hit items + CONFIRMED/ASSERTED claims with source spans. Graph-only neighbors are never citable; conversation memory is context, never evidence (ADR-015).
3. **Citations are verified deterministically** (citation ∈ evidence; ids, spans, fact status valid). Model self-citations are rejected.
4. **Bounded evidence.** Chunk caps (≤3 chunks / ≤2000 chars per document); budgets preserved.
5. **Every answer's evidence set and plan are logged** for audit and reproduction.

## 13.7 Security Laws
1. **No path — SQL, FTS, vector, graph, memory, facts, citations — returns unreadable content.** Pre-filter at query; re-verify at assembly.
2. **`acl_scope` on every derived row**, recomputed on ACL change.
3. **No LLM-controlled access or citation decisions.** Deterministic everywhere access is judged.
4. **Legacy no-ACL objects** are migrated or quarantined (ADR-017).
5. **Automated no-leak isolation matrix** (cross-user × cross-role × all mechanisms) is a release gate.

## 13.8 Evaluation Laws
1. **Capability-level evaluation from L0**, replacing phrase→intent tables and substring checks.
2. **Golden sets per capability** (≥5 phrasings, English + Hinglish) with deterministic checks: retrieval recall/precision, evidence presence, verbatim verification, count correctness, refusal honesty, no-leak matrix.
3. **Regression = capability regression**, never phrase regression.
4. **Release gates:** no capability regression; no patch-farm code; isolation matrix green; latency budgets at synthetic 1k/10k/100k/1M corpora; LLM-as-judge only where unavoidable and cross-checked.

## 13.9 Roadmap Levels
L0 Freeze & Eval Harness → L1 Knowledge-Plane Contracts → L2 Document Intelligence Engines (PDF/OCR first) → L3 Human-in-the-Loop → L4 Query Understanding v2 (parallel with L2) → L5 Tool Layer → L6 Evidence & Citation Extension → L7 Memory v2 → L8 Cross-Domain Completion → L9 Evaluation v1 → L10 Ingestion Scale → L11 Storage Scale → L12 Tenancy → L13 Semantic Retrieval Upgrade → L14 Advanced Document Intelligence (deferred) → L15 Agent/Assistant Surface (deferred). Dependency law: L1 before L2/L4/L5; nothing after L1 can rewrite it.

## 13.10 Anti-Pattern Laws (merge gates)
1. No regex/intent/branch per failed query. 2. No retrieval-planner special cases per failure. 3. No phrase→intent test tables. 4. "Tests pass" is not convergence. 5. No prompt-only safety. 6. No data-in-context instead of indexes. 7. No documenting the dream while coding the regexes. 8. No synchronous heavy work in requests. 9. No per-domain AI logic duplication. 10. No silent acceptance of extracted data. 11. No neighbor-citation drift. 12. No AI surface before the pipeline. **Replacement loop: failure → capability-level diagnosis → architectural solution → reusable capability → tests → measurement → regression.**

## 13.11 Definition of Done (every level)
(a) acceptance criteria pass as automated capability-level tests; (b) zero new patch-farm code (CI anti-pattern guard); (c) isolation matrix green for any data-touching path; (d) touched ADRs ratified and recorded; (e) rebuild test green (projections byte-identical for unchanged engines); (f) developer docs updated; (g) performance budgets measured and recorded.

## 13.12 Open Decisions to be ratified as ADRs during L0/L1 (unchanged from v2.0 §38, now numbered)
Q1 workspace/tenant semantics · Q2 OCR engine choice (incl. Devanagari) · Q3 embedding model · Q4 planner model budget · Q5 claim-store scaling (decide at L9 with measurements) · Q6 classification granularity · Q7 citation rendering surface · Q8 role-context ACL · Q9 bilingual scope · Q10 direct-upload/intake merge timing.

---

# FINAL ANSWER

**Question:** *"Can AcademicOS now be built level-by-level from this blueprint, with each completed level frozen and verified before moving to the next, without returning to random command-by-command AI fixes?"*

**Answer: Yes — from the amended contract (Part 13).** The blueprint v2.0 as written is YELLOW; the amended contract incorporating M-1…M-5 (ADR-019…022 + the 1M scale law) is GREEN and safe to freeze as the permanent architectural contract.

The reasons this answer is honest, not optimistic:

1. **The architecture is structurally anti-patch.** Language variability is absorbed by a model-based query-understanding layer; operations are a frozen capability registry; execution is ACL-filtered tools; verification is deterministic. The only re-entry points to the patch farm (fast-path growth, hidden regex fallback, retained rules-v1, validation bypass, phrase-shaped tests) are each closed by an explicit law with a CI merge gate.
2. **The knowledge plane cannot be redesigned out from under the PDF layer.** Identity, fact/metadata boundary, claim lifecycle, supersession, deletion, engine versioning, ACL inheritance, and tenancy stamping are settled ADRs; the predicate catalogue is now registry-extensible (M-1); the version-cascade is law (M-3). An engineer can build PDF intelligence on L1 without discovering the knowledge model must be redesigned.
3. **The roadmap is dependency-correct.** L1 contracts precede every engine and planner; evaluation exists from L0 and hardens at L9; nothing later can force a rewrite of an earlier level because everything is additive behind ports and projections are rebuildable.
4. **The freeze conditions are enforceable, not aspirational.** The anti-pattern merge gates, capability-level evaluation, ADR immutability (amendment only via impact analysis), and the isolation matrix are all CI-verifiable.

One caveat, stated plainly: no contract eliminates the possibility of *localized* change. What this contract guarantees is that future change is an ADR amendment with impact analysis — never an architectural rewrite and never a question-specific patch. That is the maximum protection any architecture can honestly provide.

*— Final audit complete. Architecture review only; no code, patches, or implementation produced. Repository verification: HEAD `07c434cad05ae87db741c191cc914625801147ea`, clean tree, GitHub API cross-checked; full test results for this tree (backend 1864 passed / 2 skipped; frontend 101 passed) reproduced earlier in this conversation.*
