# ADR-001 numbering collision

## The collision

| Series | “ADR-001” means | Where it lives today |
|---|---|---|
| **Repository ADR-001** | AI Core is the sole composition, configuration, and gateway authority | Code comments and architecture tests (`test_ai_composition_authority.py`, `AskQuestionUseCase`, assistant routes) |
| **Freeze-Contract ADR-001** | Source identity: a source is always a `document` object; domain objects are separate projections | Freeze Contract Part 13.3.1 |

These are **different decisions**. They share a number because the
repository series predates the Freeze-Contract register.

## Rule (L0)

- **Do not rename** repository ADR-001 in code, tests, or comments.
- **Do not reuse** the bare token `ADR-001` for the source-identity law
  in new files. Write **“Freeze-Contract ADR-001 (source identity)”**.
- New Freeze-Contract ADRs minted from L0 onward use **ADR-019+**
  (already distinct).
- A future tidy-up that aliases the two series requires its own ADR
  amendment. It is not L0 work.
