# ADR-059 — V3 M12: one AI router + model budget/spend ledger

- **Status:** Accepted
- **Level:** V3 M12 (One AI Router)
- **Supersedes:** nothing
- **Related:** ADR-001 (AI Core authority), ADR-020 (planner-failure semantics), M5 (rung 0), M8 (dossier), blueprint B2 #24, blueprint §M12

## Context

The blueprint identified a live contradiction: ADR-020 mandated `rules-v1`
deletion at L4, `LEVELS.md` marks L4 done, yet the offline chain still runs
`RuleBasedAssistantProvider → parse_question` (regex intent routing). M12 makes
`/ai` and `/assistant` adapters over ONE router, adds a model budget + spend
ledger, and asserts on runtime composition (the L4 guardrail lesson).

## Decision

1. **`AcademicAiRouter` — single owner.** One service owns classification
   (rung-0 confirmed claims → grounded QA), source policy (internal-only,
   `NO_EXTERNAL_SEARCH`), model routing (via the AI Core gateway), and a
   unified `RouterResult` response shape (``rung`` / ``source_class`` /
   ``free`` / ``estimated_cost_usd``). `/ai` and `/assistant` become thin
   adapters over it.
2. **Model budget + spend ledger.** `SpendLedger` (append-only, immutable
   `spend_ledger` table, migration 0020) records each AI generation's
   tenant/user/provider/model/tokens/cost. `ModelBudgetPolicy` enforces a
   per-tenant budget and per-user cap with an explicit
   `on_budget_exhausted` action (block / degrade / allow). On "degrade" the
   router falls back to the local/free path — "answered locally, free" — and
   never calls the gateway.
3. **`rules-v1` deletion is deferred behind golden parity (documented).** The
   blueprint itself gates the deletion on "golden-test parity" across
   English/Hindi/Hinglish. That parity evaluation is not yet present, so the
   legacy provider remains the degradation seam *behind* the router. The
   router never imports `parse_question`/`rules-v1`; when parity lands, the
   legacy provider is deleted and the offline fast-path answerer becomes the
   sole degradation seam. This is the anti-patch-law-correct ordering.
4. **Guardrails assert on composition.** New guardrails assert on the router's
   call graph (composes rung-0 + grounded QA, never the regex parser; the
   paid path is budget-gated) — never on file contents.

## Consequences

**Positive**
- One predictable answering owner; `/ai` + `/assistant` route through it.
- Central, auditable spend with explicit budget-exhaustion policy.
- The rules-v1 question is resolved honestly (deferred on parity, not silently
  left or silently deleted).

**Negative / deferred**
- `rules-v1`/`intents.py` are NOT yet deleted — pending the golden parity gate.
- The router currently composes rung-0 + grounded QA; the dossier (rung 1)
  and model-planner (rung 2–5) rungs wire in as they are exercised.

**Revisit when:** the golden parity suite passes for English/Hindi/Hinglish —
then delete `rules-v1` + `intents.py` and retire the legacy provider, leaving
the router + offline fast-path as the only answerers.
