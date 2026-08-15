# AcademicOS architecture (frozen)

**Authority:** Part 13 of
[`AcademicOS_Final_Audit_Freeze_Contract.md`](AcademicOS_Final_Audit_Freeze_Contract.md).

That document is the permanent in-repo architectural contract for
implementation. Master Blueprint v2.0 is ratified by the Freeze Contract
but is **not reconstructed here**.

## How to diagnose a failed question

```
failure
  → classify: document intelligence | extraction/entity | retrieval/tool
              | query understanding/planner | evidence/provenance | generation
  → architectural / reusable fix
  → capability-level golden case (tests/eval/capabilities/golden/)
  → measurement
```

**Never:**

```
failure → new regex / new INTENT_* / new _answer_* / new retrieval branch
```

Natural-language formulations (English or Hinglish) are **evaluation
data**, not routing rules. See `backend/app/tests/eval/capabilities/golden/`.

## Index

| Document | Role |
|---|---|
| [AcademicOS_Final_Audit_Freeze_Contract.md](AcademicOS_Final_Audit_Freeze_Contract.md) | Frozen contract (Part 13 = law) |
| [LEVELS.md](LEVELS.md) | L0…L15 register; only one level at a time |
| [L0_BASELINE.md](L0_BASELINE.md) | Frozen SHA, tree, verified test counts |
| [L0_PATCH_FARM_INVENTORY.md](L0_PATCH_FARM_INVENTORY.md) | Transitional `rules-v1` / regex / `retrieval_plan` ceilings |
| [OPEN_DECISIONS.md](OPEN_DECISIONS.md) | Q1–Q10, undecided |
| [SCALE_LAW.md](SCALE_LAW.md) | 1M-document doctrine (M-5) |
| [adr/README.md](adr/README.md) | ADR register (repo ADR-001 preserved) |
| [adr/NUMBERING.md](adr/NUMBERING.md) | ADR-001 collision (do not rename) |

## Level order (contract)

L0 Freeze & Eval Harness → L1 Knowledge-Plane Contracts → L2 Document
Intelligence (PDF/OCR first) → later planner / tools / tenancy levels.

Do not start a later level before the previous is `done`.
