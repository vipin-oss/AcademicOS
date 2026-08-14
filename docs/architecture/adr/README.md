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

Repo ADR-001 is preserved. Freeze-Contract ADR-001 is a different decision
and is referred to by its full title, never by overwriting the repo id.
