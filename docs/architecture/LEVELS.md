# AcademicOS level register

Status values: `not_started` | `in_progress` | `done` | `deferred`.

Only **one** level may be `in_progress` at a time. Nothing after L1 may
rewrite L1. PDF/OCR is the first **engine** of L2, not a level of its own.

| Level | Name | Status | Produces | Must not start until |
|---|---|---|---|---|
| L0 | Freeze & Evaluation Harness | `done` | contract in-repo, capability catalog + harness, anti-patch ceilings, ADR-019…022 law text, scale law | — |
| L1 | Knowledge-Plane Contracts | `done` | claim/CDM/span/acl_scope schemas and ports; OpenAPI for new surfaces | L0 `done` |
| L2 | Document Intelligence Engines | `done` | NIR, format detection, PDF/DOCX/XLSX/PPTX/image/OCR adapters, container/package expander, CDM writer | L1 `done` |
| L3 | Human-in-the-Loop | `done` | confirmation / correction queues, decision audit, extraction→claim bridge | L1 `done` |
| L4 | Query Understanding v2 | `done` | model planner, frozen ≤15 fast-path, `rules-v1` deletion (ADR-020 enforcement) | L1 `done` (parallel with L2) |
| L5 | Tool Layer | `done` | ACL-filtered tools (inventory, SQL, FTS, vector, graph, …) | L1 `done` |
| L6 | Evidence & Citation Extension | `in_progress` | fact citations, confidence UI | L1 + L5 |
| L7 | Memory v2 | `not_started` | persistent memory | L1 + L5 |
| L8 | Cross-Domain Completion | `not_started` | multi-hop, absence, temporal, compare | L4 + L5 |
| L9 | Evaluation v1 | `not_started` | hard capability gates, isolation matrix, scale budgets | L1–L8 |
| L10 | Ingestion Scale | `not_started` | worker pool, DLQ | L2 |
| L11 | Storage Scale | `not_started` | object storage behind port | L2 |
| L12 | Tenancy | `not_started` | partition keys, isolation | L1 stamping |
| L13 | Semantic Retrieval Upgrade | `not_started` | real embedder + alias swap | L1 |
| L14 | Advanced Document Intelligence | `deferred` | figures / equations / handwriting | L2 |
| L15 | Agent / Assistant Surface | `deferred` | agent surface | L4–L8 |

Mark L0 `done` only after the L0 acceptance checklist in the implementation
plan passes. Do not flip L1+ in the same change.
