# ADR-060 — V3 M13: ad-hoc query & export (saved views)

- **Status:** Accepted
- **Level:** V3 M13 (Ad-hoc Query & Export)
- **Supersedes:** nothing
- **Related:** ADR-022 (API freeze), M9 (authorization), blueprint §M13

## Context

"University ne data maanga" → 3 clicks → correct XLSX. The blueprint wants
saved, re-runnable ad-hoc queries that compile to SQL (never Python scans),
with authorization applied before aggregation so counts never leak, plus CSV/
XLSX/PDF export.

## Decision

1. **Saved views as data.** A `saved_views` table (migration 0021) stores the
   definition as JSON; the row is owner-scoped (only the owner, or an admin,
   may read/run/delete it).
2. **Injection-safe compiler.** `SavedViewCompiler` compiles a definition to
   parameterized SQL over the scalar object columns: every value is a bound
   parameter; every column/operator/aggregate/sort-direction is a closed
   whitelist (the anti-patch law: a new queryable column is one whitelist row,
   never a rewrite). Invalid definitions are rejected at save time (422).
3. **Authorization before aggregation.** The tenant predicate is always the
   first WHERE term, so aggregate counts can never leak across tenants.
4. **Export reuses the existing stdlib exporters.** The saved-view result is
   projected onto the existing `ReportView` and exported via the M12-era
   `report_csv_bytes` / `report_xlsx_bytes` writers (CSV + XLSX; PDF is the
   same projection, available to the exporters). No new dependencies.
5. **Command palette (Ctrl+K) is frontend** — deferred; the backend contract
   (save/run/export) is what the palette will call.

## Consequences

**Positive**
- Ad-hoc queries are safe (parameterized, whitelisted) and re-runnable.
- Exports match on-screen data exactly (same SQL, same projection).
- Authorization holds on every aggregate.

**Negative / deferred**
- The queryable surface is the scalar object columns (no JSON-metadata
  filtering yet) — a deliberate, bounded start; richer columns are additive
  whitelist rows.
- PDF export is available via the shared exporters but the route currently
  serves CSV/XLSX; the UI + command palette are M14 frontend work.

**Revisit when:** tenants need metadata-column filtering — extend the
whitelist (additive), never a schema rewrite.
