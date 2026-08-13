# AcademicOS — L5 ACL-Filtered Tool Layer

**Scope:** the L5 Tool Layer (Freeze Contract §18, ADR-037/038). A frozen,
explicit tool registry + central tool executor + durable tool-call audit, with
deterministic data tools wrapping the existing ObjectRepository.

## Tools implemented (ACL-filtered, deterministic, principal-carrying, audited)
- inventory, count, list, lookup (wrap ObjectRepository)

## Architecture
- `ToolSpec`/`ToolInvocation`/`ToolResult`/`ToolCallRecord` contracts (§18 shape)
- `ToolRegistry` + `InMemoryToolRegistry` (explicit, duplicate-safe, schema-validated)
- `ToolExecutor` (resolve → validate → ACL → execute → normalize → audit → result)
- `tool_call_log` audit (idempotent by call_id)
- API: GET /tools, POST /tools/{name}/invoke, GET /tools/calls
- ADR-037 (tool registry & execution), ADR-038 (tool evaluation gate)
- Migration 0014 (tool_call_log)

## Verification
- L5 focused tests: 28 passed
- Architecture guardrails: 84 passed
- Full backend: 2102 passed / 2 skipped (one pre-existing timing-sensitive
  intake test flaked under heavy parallel load; passes standalone)
- Frontend vitest: 101 passed; tsc clean
- git diff --check: clean
- Migration head: 0014 (chains off 0013)
