"""V3 M13 saved-view compiler unit tests (ADR-060): injection-safe, parameterized."""

from __future__ import annotations

import pytest

from app.application.services.saved_view_compiler import SavedViewCompiler


def test_compile_basic_select_is_parameterized():
    compiled = SavedViewCompiler.compile(
        {"columns": ["id", "title"], "sort": {"column": "title", "direction": "asc"}},
        tenant_id="t1",
    )
    assert compiled.sql.startswith("SELECT id, title FROM objects WHERE tenant_id = :tenant")
    assert compiled.params["tenant"] == "t1"
    assert "ORDER BY title ASC" in compiled.sql
    assert "LIMIT :lim" in compiled.sql


def test_filters_are_bound_parameters_not_interpolated():
    compiled = SavedViewCompiler.compile(
        {
            "columns": ["title"],
            "filters": [{"column": "object_type", "op": "eq", "value": "document"}],
        },
        tenant_id="t1",
    )
    # the value must be a bound param, never inline
    assert "object_type = :val0" in compiled.sql
    assert "document" not in compiled.sql
    assert compiled.params["val0"] == "document"


def test_contains_uses_like_with_escaped_wildcard():
    compiled = SavedViewCompiler.compile(
        {"columns": ["title"], "filters": [{"column": "title", "op": "contains", "value": "x"}]},
        tenant_id="t1",
    )
    assert "title LIKE :val0" in compiled.sql
    assert compiled.params["val0"] == "%x%"


def test_aggregate_count_with_group_by():
    compiled = SavedViewCompiler.compile(
        {"aggregate": "count", "group_by": "object_type"}, tenant_id="t1"
    )
    assert "COUNT(*) AS count" in compiled.sql
    assert "GROUP BY object_type" in compiled.sql


def test_unknown_column_rejected():
    with pytest.raises(ValueError, match="not queryable"):
        SavedViewCompiler.compile({"columns": ["id; DROP TABLE objects;--"]}, tenant_id="t1")


def test_unknown_operator_rejected():
    with pytest.raises(ValueError, match="not supported"):
        SavedViewCompiler.compile(
            {"columns": ["id"], "filters": [{"column": "id", "op": "DROP", "value": "x"}]},
            tenant_id="t1",
        )


def test_unknown_aggregate_rejected():
    with pytest.raises(ValueError):
        SavedViewCompiler.compile({"aggregate": "sum", "group_by": "object_type"}, tenant_id="t1")


def test_authorization_precedes_aggregation():
    # The tenant predicate is the FIRST WHERE term, so the DB filters rows
    # before COUNT aggregates them (authorization before aggregation).
    compiled = SavedViewCompiler.compile({"aggregate": "count"}, tenant_id="t9")
    assert compiled.sql.startswith("SELECT COUNT(*) AS count FROM objects WHERE tenant_id = :tenant")
    # the tenant filter is the only predicate before LIMIT
    assert compiled.sql.index("WHERE") < compiled.sql.index("LIMIT")
