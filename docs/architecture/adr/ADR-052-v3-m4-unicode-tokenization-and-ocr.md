# ADR-052 — V3 M4: Unicode-first tokenization (diacritic folding) + OCR engine choice

- **Status:** Accepted
- **Level:** V3 M4 (Hindi/English/Hinglish Search)
- **Supersedes:** nothing
- **Related:** ADR-028 (NIR), ADR-030 (OCR policy), V3 audit A2, A3; open decision Q2

## Context

Blueprint V3 M4 makes Hindi documents findable for the first time. Audit A2
showed the old `[a-z0-9]+` tokenizer made Devanagari invisible, and that a
naive `\w+` "fix" shatters words at every combining mark (matra) — actively
worse. Audit A3 showed the database tokenizer is a *second* leg that must be
changed in lockstep: fixing only the Python query side leaves the index side
untouched, so search silently returns nothing.

Empirical findings at M4 (SQLite FTS5 `unicode61`, SQLite 3.46.1):

- `fts5` `unicode61` and PostgreSQL `simple` both split `गणित` into fragments
  at the matra (`गण` + `त`), because combining marks are not word characters.
- FTS5's `tokenchars` / `categories` tokenizer options — the portable way to
  reclassify combining marks — do not parse in this SQLite build, and there is
  no portable equivalent for PostgreSQL's `simple` config without a custom
  text-search dictionary/parser.

## Decision

1. **One canonical tokenizer** (`app/infrastructure/search/tokenizer.py`):
   - `mark_tokens` — the A2 mark-aware token class (word char or combining
     mark) over NFC text, marks kept. Used by the hashing embedder (no DB index
     to match, so it keeps full fidelity).
   - `fts_tokens` — `fold_diacritics` then mark-aware tokenize then lowercase.
2. **Diacritic folding for FTS parity.** `fold_diacritics` (NFC → NFD → drop
   Unicode Mark characters Mn/Mc/Me → NFC) is applied to the indexed text at
   `SQLFTSRepository.upsert()` and to the query in `fts_tokens()`. After
   folding, `गणित` → `गणत`, which the database tokenizers treat as ONE word —
   so query tokens and index tokens are identical *by construction*, on both
   SQLite and PostgreSQL, with no tokenizer reconfiguration. Folding is
   symmetric and a no-op for ASCII, so English is unaffected (no regression).
   The original text remains the source of truth in `document_contents`; the
   FTS projection is derived and rebuildable.
3. **OCR engine (Q2) resolved — Tesseract with `eng+hin`.** Tesseract is the
   only Devanagari-capable engine without a paid/proprietary service.
   `TesseractOcrEngine` gains a `lang` parameter defaulting to `"eng+hin"`;
   if the `hin` traineddata is absent the engine degrades to English
   (best-effort), which the blueprint accepts. `pytesseract` remains an
   optional, feature-flagged dependency (ADR-030): its pin is recorded in
   `requirements.txt` as a comment, not force-installed.
4. **PostgreSQL generated-column rebuild is deferred.** A3 correctly requires
   the PG `tsvector` generated column to fold text the same way (a full-table
   rewrite). Because `fold_diacritics` must run *before* `to_tsvector`, it
   needs a SQL helper function that PG cannot express inline in the generated
   column expression today. That rebuild is scoped to the moment PostgreSQL is
   exercised in CI; until then the SQLite path is the CI-verified parity
   proof, and the PG column continues to index the raw (unfolded) text —
   Hindi over PostgreSQL is explicitly *not yet claimed*.

## Consequences

**Positive**
- Hindi/Devanagari documents are searchable on SQLite today, with a test that
  asserts query tokens == index tokens (via `fts5vocab`) and a bilingual
  golden corpus. No English regression.
- One shared tokenizer; the hashing embedder and FTS no longer diverge.
- Q2 is closed with a defensible, free, reversible choice.

**Negative**
- Diacritic folding loses the matra distinction in the *index* (search is
  diacritic-insensitive); the original text is untouched, and exact display
  uses the source. Accepted: standard practice, symmetric, information-loss
  bounded to the derived FTS projection.

**Revisit when:** PostgreSQL becomes CI-exercised — then implement the
generated-column rebuild (fold function + rewrite) per A3, at which point
Hindi-over-PostgreSQL becomes a claimed capability.
