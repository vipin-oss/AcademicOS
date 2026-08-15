# AcademicOS — L8 Cross-Domain Completion — Delivery Manifest

**Level:** L8 — Cross-Domain Completion
**Baseline (parent):** `f930f1421d6230fea151175977cbf52257b83678` (L7, Memory v2)
**Commit message:** `feat(l8): add cross-domain completion`
**Nature:** bounded multi-hop execution + cross-domain completion/synthesis layer (ADR-043).

## Scope
L8 executes the four already-frozen L8 capabilities (`cross_domain`, `absence`,
`temporal`, `compare`) as **additive execution capabilities/tools** integrated
through the existing L5 tool execution seam, reusing L4 `sub_plans[]`,
`GraphRuntimeService` (bounded multi-hop), `PermissionEvaluator`/`object_acl_scope`
(ACL), and downstream L6 evidence/citation + grounded-answer discipline. It does
NOT create a second planner, retrieval, ACL, evidence, or memory system; NO new
capability IDs; NO migration.

Includes the approved L7 test-sync correction:
`backend/app/tests/integration/test_assistant_api.py` — the stale `17` assistant
path-count assertion is updated to the actual `19` (L7 added `/assistant/memory`
and `/assistant/memory/{artifact_id}`), with matching assertions added. This is a
test-only sync fix, not a production behavior change.

## ZIP entries (repo-relative paths) — 21 files
1. `MANIFEST.md`
2. `backend/app/api/routes/tools.py`
3. `backend/app/application/capabilities/eval_schema.py`
4. `backend/app/application/services/cross_domain.py`
5. `backend/app/application/services/temporal.py`
6. `backend/app/application/services/tools/absence_tool.py`
7. `backend/app/application/services/tools/compare_tool.py`
8. `backend/app/application/services/tools/cross_domain_tool.py`
9. `backend/app/application/services/tools/registry.py`
10. `backend/app/application/services/tools/temporal_tool.py`
11. `backend/app/tests/architecture/test_l8_guardrails.py`
12. `backend/app/tests/eval/capabilities/test_golden_schema.py`
13. `backend/app/tests/eval/test_l8_eval_gate.py`
14. `backend/app/tests/integration/test_assistant_api.py` (L7 test-sync)
15. `backend/app/tests/integration/test_l8_tools_api.py`
16. `backend/app/tests/unit/test_cross_domain.py`
17. `backend/app/tests/unit/test_l8_tools.py`
18. `docs/architecture/LEVELS.md`
19. `docs/architecture/adr/ADR-043-l8-cross-domain-completion.md`
20. `docs/architecture/adr/ADR-044-l8-evaluation-gate.md`
21. `docs/architecture/adr/README.md`

## Test results (verified pre-commit)
- **L8 suite** (unit + tool + integration + eval gate + guardrails): **43 passed**
- **L7 regression**: 28 passed
- **L6 focused**: 16 passed
- **L5 focused** (tool/ACL/executor/registry/permission): 149 passed
- **L4 focused** (plan/planner/fast_path/validator): 101 passed
- **L1–L3** (claim/span/evidence/confirmation): 149 passed
- **Golden schema**: 20 passed
- **Architecture/freeze guardrails**: 102 passed
- `git diff --check`: clean

## Frozen-boundary status
- Capability registry unchanged (18 capabilities); `test_l0_freeze_artifacts.py`
  unchanged.
- No L4 planner, L5 executor/registry semantics, L6 evidence, L7 memory source
  modified. `assistant.py` production behavior untouched (test-sync only).
- No migration (`0015` not created). `container_policy.py` / `dffba2a` not touched.
- `ALLOWED_GATE_LEVELS` gains `"l8"` additively (ADR-044 precedent).
