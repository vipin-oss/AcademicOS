# AcademicOS — L7 Memory v2 Persistent Layer — Delivery Manifest

**Level:** L7 — Memory v2 (persistent memory)
**Commit:** `f930f1421d6230fea151175977cbf52257b83678`
**Parent:** `b79c296d62badd7127e152609f2dca80a21f5981` (L6, Evidence & Citation Extension)
**Commit message:** `feat(l7): add memory v2 persistent layer`

## Scope
L7 adds a **persistent memory layer** (ADR-041): durable, principal-scoped,
provenance-carrying memory artifacts stored as `UniversalObject` metadata on the
existing `objects` table. **No new table, no migration** (alembic head stays `0014`).
Memory is **context, never evidence** (ADR-015).

- Persistent-memory DTOs / port / service (`write`/`recall`/`list`/`forget`).
- Review gate (pending/rejected content recalls empty); ACL pre-filtering via
  `PermissionEvaluator` + `object_acl_scope`; provenance (ASSERTED/INFERRED/SYSTEM)
  with FR-MET-009 protection for human-asserted memory.
- `memory-recall` L5 tool registered in the existing `ToolExecutor` registry.
- Additive API endpoints on the assistant router (`POST/GET/DELETE /assistant/memory`).
- L7 evaluation gate (`test_l7_eval_gate.py`) + L7 architecture guardrails
  (`test_l7_guardrails.py`) + additive `gate_level="l7"` support in the L0 eval schema.

Reuses existing `ObjectRepository`, `UniversalObject`, `PermissionEvaluator`,
`object_acl_scope`, `MetadataEntry`/`MetadataLayer`/`Provenance`,
`MemoryConsolidationService`, and the L5 `ToolExecutor`/registry. Does NOT create
a second memory store, retrieval system, ACL system, planner, tool registry, or
evidence system.

## ZIP entries (repo-relative paths)
1. `MANIFEST.md`
2. `backend/app/api/routes/assistant.py`
3. `backend/app/api/routes/tools.py`
4. `backend/app/application/capabilities/eval_schema.py`
5. `backend/app/application/dtos/memory.py`
6. `backend/app/application/ports/persistent_memory.py`
7. `backend/app/application/services/persistent_memory.py`
8. `backend/app/application/services/tools/memory_recall_tool.py`
9. `backend/app/application/services/tools/registry.py`
10. `backend/app/tests/architecture/test_l7_guardrails.py`
11. `backend/app/tests/eval/capabilities/test_golden_schema.py`
12. `backend/app/tests/eval/test_l7_eval_gate.py`
13. `backend/app/tests/integration/test_l7_memory_api.py`
14. `backend/app/tests/unit/test_memory_recall_tool.py`
15. `backend/app/tests/unit/test_persistent_memory.py`
16. `docs/architecture/LEVELS.md`
17. `docs/architecture/adr/ADR-041-l7-memory-v2-persistent-layer.md`
18. `docs/architecture/adr/ADR-042-l7-evaluation-gate.md`
19. `docs/architecture/adr/README.md`

Matches exactly the L7 commit diff (`git diff b79c296..f930f14`) plus `MANIFEST.md`.

## Test results (verified)
- **L7 tests** (unit + tool + integration + eval gate + guardrails): **48 passed**
- **Existing memory regression** (`test_assistant_memory`, `test_memory_consolidation`): **39 passed**
- **L5 focused** (tool/ACL/executor/registry/permission): **138 passed**
- **L6 focused**: **16 passed**
- **L1–L4 relevant regression**: **231 passed**
- **All architecture/freeze guardrails**: **94 passed**
- **`test_capability_registry_is_exactly_the_frozen_18`**: PASSED (registry stays at 18)
- `git diff --check`: clean

## Frozen-boundary status
- L0 capability registry unchanged (18 capabilities); `test_l0_freeze_artifacts.py`
  unchanged.
- Only additive L0 change: `ALLOWED_GATE_LEVELS` gains `"l7"` in `eval_schema.py`
  (and the matching assertion in `test_golden_schema.py`), per ADR-042.
- No L1 claim/span schema, L4 planner/fast-path, L5 executor/tool_registry, or L6
  evidence files modified.
- No `memory.json` in the frozen capability suite; no `0015` migration.
- `dffba2a` / `container_policy.py`: NOT touched.
