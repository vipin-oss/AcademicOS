# L0 patch-farm inventory (transitional)

This is the **legacy** question-routing brain. It is **not** the target
architecture. It remains in production for regression until L4 cutover
(ADR-020). L0 **freezes growth**. Shrink / deletion later **must pass**.

## Allowlisted files (may shrink, must not grow)

- `backend/app/application/assistant/intents.py`
- `backend/app/application/assistant/providers.py` (`rules-v1`)
- `backend/app/application/dtos/assistant.py` (`INTENT_*`, `SUGGESTED_QUESTIONS`)
- `backend/app/application/services/assistant_retrieval.py` (`retrieval_plan`)
- `backend/app/tests/unit/test_assistant_intents.py`
- `backend/app/tests/unit/test_retrieval_plan.py`

## Ceilings (`<=` — grow fails, shrink passes)

| Metric | File | Ceiling |
|---|---|---|
| `re.compile(` | `intents.py` | 108 |
| `RULES` entries | `intents.py` | 34 |
| `INTENT_* = "` codes | `dtos/assistant.py` | 34 |
| `SUGGESTED_QUESTIONS` | `dtos/assistant.py` | 32 |
| `_answer_*` on `RuleBasedAssistantProvider` | `providers.py` | 34 |
| `ROUTING_CASES` | `test_assistant_intents.py` | 75 |
| `PRECEDENCE_CASES` | `test_assistant_intents.py` | 10 |
| `re.compile(` | `assistant_retrieval.py` | 3 |
| `_DOMAIN_NOUN_TO_TYPE` keys | `assistant_retrieval.py` | 15 |
| `_QUERY_STOPWORDS` | `assistant_retrieval.py` | 96 |
| `_TOPIC_MARKERS` | `assistant_retrieval.py` | 5 |
| `_TYPE_COUNT_MARKERS` | `assistant_retrieval.py` | 5 |
| `_CAPITALIZED_COMMON_WORDS` | `assistant_retrieval.py` | 44 |
| Production `parse_question(` callers | `backend/app` excluding tests | 1 (`providers.py`) |

## Deletion target

L4 (ADR-020 enforcement): planner failure → frozen fast-path (≤15) →
clarify → refuse. `parse_question` and `RuleBasedAssistantProvider` are
deleted, not retained as a hidden fallback.

`FallbackAssistantProvider` still falls back to `rules-v1` today. That
path is the anti-pattern ADR-020 exists to remove. **Do not change it in
L0** (behavior freeze). **Do not grow it.**
