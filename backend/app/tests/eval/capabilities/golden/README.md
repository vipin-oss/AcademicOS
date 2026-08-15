# Capability golden sets (evaluation DATA)

These JSON files are **not** routing rules.

To add a new phrasing of an existing capability:

1. Append a case to the matching `*.json` (`language` `en` or `hi-en`).
2. Do **not** add an `intent` field.
3. Do **not** add a regex, `INTENT_*`, `_answer_*`, or `retrieval_plan` row.
4. Set `gate_level` to the level that will hard-gate the case (`l4` / `l5` / `l9`).
   L0 only registers data.

A new capability requires an ADR amendment, a new golden file, and later a tool.
