# ADR register

Two numbering series coexist. **Do not rename existing repository ADRs.**
See [NUMBERING.md](NUMBERING.md).

## Repository ADRs (already enforced in code)

| ID | Title | Status | Where enforced |
|---|---|---|---|
| Repo ADR-001 | AI Core is the sole composition / config / gateway authority | in force | `test_ai_composition_authority.py`, `test_ai_config_authority.py`, `test_transport_ownership.py` |

## Freeze-Contract ADRs (Part 13)

| ID | Title | Law recorded | Mechanism lands |
|---|---|---|---|
| Freeze-Contract ADR-001 | Source identity (source is always a `document`) | Part 13.3.1 | L1 |
| ADR-002 / 002b | Fact/metadata boundary; content identity | Part 13.3.2–3 | L1 |
| ADR-019 | Extensible claim predicate catalogue | [ADR-019](ADR-019-extensible-claim-predicates.md) (L0) | L1 store |
| ADR-020 | Planner-failure semantics | [ADR-020](ADR-020-planner-failure-semantics.md) (L0) | L4 cutover |
| ADR-021 | File-version → claim/CDM supersession | [ADR-021](ADR-021-file-version-supersession.md) (L0) | L1 |
| ADR-022 | API / OpenAPI contract freeze for new surfaces | [ADR-022](ADR-022-api-contract-freeze.md) (L0) | L1 |
| ADR-035 | Model-driven query-understanding planner | [ADR-035](ADR-035-query-understanding-planner.md) (L4) | L4 |
| ADR-036 | Frozen deterministic fast-path | [ADR-036](ADR-036-frozen-fast-path.md) (L4) | L4 |
| ADR-037 | Tool registry & execution | [ADR-037](ADR-037-tool-registry-execution.md) (L5) | L5 |
| ADR-038 | Tool evaluation gate | [ADR-038](ADR-038-tool-evaluation-gate.md) (L5) | L5 |
| ADR-039 | Fact citation & confidence contract | [ADR-039](ADR-039-fact-citation-evidence-contract.md) (L6) | L6 |
| ADR-040 | L6 evaluation gate | [ADR-040](ADR-040-l6-evaluation-gate.md) (L6) | L6 |
| ADR-041 | L7 memory v2 persistent layer | [ADR-041](ADR-041-l7-memory-v2-persistent-layer.md) (L7) | L7 |
| ADR-042 | L7 evaluation gate | [ADR-042](ADR-042-l7-evaluation-gate.md) (L7) | L7 |
| ADR-043 | L8 cross-domain completion | [ADR-043](ADR-043-l8-cross-domain-completion.md) (L8) | L8 |
| ADR-044 | L8 evaluation gate | [ADR-044](ADR-044-l8-evaluation-gate.md) (L8) | L8 |
| ADR-045 | L9 hard capability gates | [ADR-045](ADR-045-l9-hard-capability-gates.md) (L9) | L9 |
| ADR-046 | L9 isolation matrix & scale budgets | [ADR-046](ADR-046-l9-isolation-matrix-and-scale-budgets.md) (L9) | L9 |
| ADR-047 | Q5 claim-store scaling decision | [ADR-047](ADR-047-claim-store-scaling-measurements.md) (L9) | L9 |
| ADR-048 | L10 ingestion scale worker pool & DLQ | [ADR-048](ADR-048-l10-ingestion-scale-worker-pool.md) (L10) | L10 |
| ADR-049 | L10 evaluation gate | [ADR-049](ADR-049-l10-evaluation-gate.md) (L10) | L10 |
| ADR-050 | Ollama configured as OpenAI-compatible provider | [ADR-050](ADR-050-ollama-openai-compatible-configuration.md) (V3 M1) | V3 M1 |
| ADR-051 | Two PDF-reader ports distinct; dead `/documents/ingest` removed | [ADR-051](ADR-051-v3-m2-pdf-reader-and-pipeline-reconciliation.md) (V3 M2) | V3 M2 |
| ADR-052 | Unicode-first tokenization (diacritic folding) + OCR engine choice | [ADR-052](ADR-052-v3-m4-unicode-tokenization-and-ocr.md) (V3 M4) | V3 M4 |
| ADR-053 | Document classification + Wave 1 predicate catalogue | [ADR-053](ADR-053-v3-m6-document-classification-and-predicate-waves.md) (V3 M6) | V3 M6 |
| ADR-054 | Review at scale + extraction-health correction loop | [ADR-054](ADR-054-v3-m7-review-at-scale-and-correction-loop.md) (V3 M7) | V3 M7 |
| ADR-055 | Retrieval speed, parallel fan-out, fact/dossier cache | [ADR-055](ADR-055-v3-m8-retrieval-speed-and-parallelism.md) (V3 M8) | V3 M8 |
| ADR-056 | Deny-by-default security posture, pre-filter, revocation | [ADR-056](ADR-056-v3-m9-security-deny-by-default.md) (V3 M9) | V3 M9 |
| ADR-057 | Durable jobs + separate worker/relay processes | [ADR-057](ADR-057-v3-m10-durable-jobs-and-worker-process.md) (V3 M10) | V3 M10 |
| ADR-058 | One document pipeline (revisions + quarantine) | [ADR-058](ADR-058-v3-m11-one-document-pipeline.md) (V3 M11) | V3 M11 |
| ADR-059 | One AI router + model budget/spend ledger | [ADR-059](ADR-059-v3-m12-one-ai-router.md) (V3 M12) | V3 M12 |
| ADR-060 | Ad-hoc query & export (saved views) | [ADR-060](ADR-060-v3-m13-adhoc-query-and-export.md) (V3 M13) | V3 M13 |
| ADR-061 | Multi-user UX & admin (roles + operational panel) | [ADR-061](ADR-061-v3-m14-multi-user-ux-and-admin.md) (V3 M14) | V3 M14 |
| ADR-062 | Multi-tenant isolation | [ADR-062](ADR-062-v3-m15-multi-tenant-isolation.md) (V3 M15) | V3 M15 |
| ADR-063 | Operational data normalization (wave framework + wave 1) | [ADR-063](ADR-063-v3-m16-operational-data-normalization.md) (V3 M16) | V3 M16 |
| ADR-064 | Temporal graph + identity resolution | [ADR-064](ADR-064-v3-m17-temporal-graph-and-identity-resolution.md) (V3 M17) | V3 M17 |
| ADR-065 | Accreditation workflow kernel | [ADR-065](ADR-065-v3-m18-accreditation.md) (V3 M18) | V3 M18 |
| ADR-066 | Production hardening (Docker/TLS/logging/backup) | [ADR-066](ADR-066-v3-m19-production-hardening.md) (V3 M19) | V3 M19 |
| ADR-067 | Intelligent document intake (classify → extract → route → review) | [ADR-067](ADR-067-v3-document-intake.md) (V3) | V3 |
| ADR-068 | Domain-record routing, prose extraction, conversational guard | [ADR-068](ADR-068-v3-domain-record-routing.md) (V3) | V3 |

Repo ADR-001 is preserved. Freeze-Contract ADR-001 is a different decision
and is referred to by its full title, never by overwriting the repo id.
