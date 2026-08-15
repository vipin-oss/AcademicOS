"""Saved-view SQL compiler (V3 M13, ADR-060).

Compiles a saved-view definition into PARAMETERIZED SQL over the ``objects``
table — never Python scans, never string-interpolated values (injection-safe
by construction: every value is a bound parameter; every column/operator is
whitelisted). Authorization precedes aggregation: the tenant predicate is
always the first WHERE term, so counts/aggregates can never leak across
tenants (blueprint §M13 "authorization before aggregation").

Whitelists are closed and small — the anti-patch law: a new queryable column
is an additive whitelist row, never a schema/feature rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Whitelisted columns (scalar object columns only — JSON metadata is not
#: orderable/filterable in SQL and is deliberately excluded).
COLUMNS = ("id", "object_type", "title", "status", "version", "tenant_id", "owner_user_id")

#: Whitelisted operators -> parameterized SQL fragment (``%s``-style via :v).
OPERATORS = {
    "eq": "= :val",
    "neq": "!= :val",
    "contains": "LIKE :val",
}

#: Whitelisted sort directions.
DIRECTIONS = ("asc", "desc")

#: Whitelisted aggregate functions.
AGGREGATES = ("count",)


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    params: dict


class SavedViewCompiler:
    """Deterministic, injection-safe compiler for a saved-view definition."""

    @staticmethod
    def compile(definition: dict, *, tenant_id: str, limit: int = 500) -> CompiledQuery:
        columns = definition.get("columns") or ["id", "object_type", "title", "status"]
        for col in columns:
            if col not in COLUMNS:
                raise ValueError(f"Column not queryable: {col}")

        aggregate = definition.get("aggregate")
        group_by = definition.get("group_by")

        if aggregate is not None:
            if aggregate not in AGGREGATES:
                raise ValueError(f"Aggregate not supported: {aggregate}")
            select_cols = []
            if group_by:
                if group_by not in COLUMNS:
                    raise ValueError(f"Group-by column not queryable: {group_by}")
                select_cols.append(group_by)
            select_cols.append("COUNT(*) AS count")
        else:
            select_cols = list(columns)

        params: dict = {"tenant": tenant_id, "lim": limit}
        where = ["tenant_id = :tenant"]
        for i, f in enumerate(definition.get("filters") or []):
            col = f.get("column")
            op = f.get("op")
            if col not in COLUMNS:
                raise ValueError(f"Filter column not queryable: {col}")
            if op not in OPERATORS:
                raise ValueError(f"Filter operator not supported: {op}")
            key = f"val{i}"
            value = f.get("value")
            if op == "contains":
                value = f"%{value}%"
            params[key] = value
            where.append(f"{col} {OPERATORS[op].replace(':val', ':' + key)}")

        sql = "SELECT " + ", ".join(select_cols) + " FROM objects WHERE " + " AND ".join(where)

        if aggregate is not None and group_by:
            sql += f" GROUP BY {group_by}"

        sort = definition.get("sort")
        if aggregate is None and sort:
            col = sort.get("column")
            direction = sort.get("direction", "asc")
            if col not in COLUMNS:
                raise ValueError(f"Sort column not queryable: {col}")
            if direction not in DIRECTIONS:
                raise ValueError(f"Sort direction not supported: {direction}")
            sql += f" ORDER BY {col} {direction.upper()}"

        sql += " LIMIT :lim"
        return CompiledQuery(sql=sql, params=params)


__all__ = ["AGGREGATES", "COLUMNS", "DIRECTIONS", "OPERATORS", "CompiledQuery", "SavedViewCompiler"]
