# L0 baseline record

Frozen at implementation of L0. Do not “fix” these numbers by growing
the patch farm.

| Field | Value |
|---|---|
| Repository | `https://github.com/vipin-oss/AcademicOS` |
| Branch | `feature/ai-knowledge-projection-p0` |
| `git rev-parse HEAD` | `07c434cad05ae87db741c191cc914625801147ea` |
| Tree | `ee9c7fdefe71f7d0647d4fca0df0a5ce0b54861d` |
| Commit | `feat(ai): add scalable knowledge search and document identity` |
| Backend pytest (SQLite) | **1864 passed, 2 skipped** |
| Frontend vitest | **101 passed** |
| Frontend `tsc --noEmit` | clean |
| Architecture tests at baseline | 19 collected |
| Existing eval tests at baseline | 24 collected |
| Alembic version files | **11** (`0001`…`0011_search_fts_identity`) |
| `ObjectType` members | 43 |
| `INTENT_*` codes | **34** |
| `re.compile(` in `intents.py` | **108** |
| `RULES` entries | **34** |
| `_answer_*` on `RuleBasedAssistantProvider` | **34** |
| `SUGGESTED_QUESTIONS` | **32** |
| `ROUTING_CASES` | **75** |
| `PRECEDENCE_CASES` | **10** |

The two skipped tests are the PostgreSQL-only JSONB containment cases in
`test_sqlalchemy_object_repository.py`.
