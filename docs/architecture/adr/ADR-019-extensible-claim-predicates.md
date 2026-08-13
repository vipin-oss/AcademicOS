# ADR-019 — Extensible claim predicate catalogue (M-1)

**Status:** law recorded at L0. Claim **store** is L1. This ADR does not
create tables, writers, or engines.

## Decision

Predicates are a **versioned, registry-driven catalogue**, not a closed
enum.

Each predicate has:

- `predicate_id` (stable string)
- `version` (positive integer)
- a per-predicate **value schema**
- validation against that schema

## Rules

1. Adding a new fact kind is **additive data** (a new catalogue entry).
   It must **not** require a database schema rewrite.
2. Unknown or unparseable values are stored as **`raw`** together with
   the source extraction text. They are **never silently dropped**.
3. The catalogue is the single list of known predicates. L1’s claim
   store binds `predicate_id` + version; it does not encode the
   predicate set in a SQL enum or a frozen Python `Enum` of fact kinds.
4. Seed entries may exist as in-process data
   (`application/knowledge/predicate_catalogue.py`) so L1 cannot invent
   a closed enum. That module is **not** a store.

## Consequences

L2 engines write proposed claims against this catalogue. New domains
(exam dates, venue capacity, lab equipment, …) extend the catalogue
without migrating the fact table.
