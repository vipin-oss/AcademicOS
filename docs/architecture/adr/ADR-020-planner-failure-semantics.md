# ADR-020 — Planner-failure semantics (M-2)

**Status:** law ratified at L0. **Code enforcement at L4 cutover.**
`rules-v1` remains in production for regression until then and **must
not grow**.

## Decision

On planner failure the only legal chain is:

```
planner failure
    → frozen deterministic fast-path (≤15 commands; list cannot grow)
    → clarify
    → refuse
```

Never:

```
planner failure
    → regex parser
    → new intent
    → special-case branch
    → rules-v1 resurrection
```

## Rules

1. Regex-based intent parsing (`parse_question`, `intents.py` `RULES`)
   is **deleted at L4 cutover**, never invoked after cutover, never
   resurrected as a “safety net”.
2. The deterministic fast-path is a **frozen** list of at most 15
   commands. Once frozen at L4 it **cannot grow**. New commands go
   through the planner.
3. Plan-validation failure never degrades to substring matching.
4. `FallbackAssistantProvider` → `rules-v1` is the current anti-pattern.
   L0 does **not** change its behavior (regression). L4 removes it.
5. Raising any L0 patch-farm ceiling to “fix” a failed question is an
   ADR-020 violation.

## Consequences

A new phrasing of a user question requires **zero** production routing
code. It is evaluation data under `tests/eval/capabilities/golden/`.
