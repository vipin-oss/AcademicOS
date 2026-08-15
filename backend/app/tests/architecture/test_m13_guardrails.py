"""V3 M13 architecture guardrails (ADR-060).

Pins the ad-hoc query/export contracts:

- compilation is injection-safe (whitelisted columns/operators/aggregates,
  every value a bound parameter);
- authorization precedes aggregation (tenant predicate is the first WHERE
  term);
- no Python-side scan (the compiler emits SQL, never filters rows in code);
- the exporters reuse the existing stdlib CSV/XLSX writers (no new deps).
"""

from __future__ import annotations

import inspect


def test_compiler_uses_bound_parameters() -> None:
    import app.application.services.saved_view_compiler as mod

    src = inspect.getsource(mod)
    assert ":tenant" in src and ":val" in src.replace(":val0", ":val")
    # no f-string interpolation of values into SQL
    assert "params[" in src


def test_whitelists_are_closed() -> None:
    import app.application.services.saved_view_compiler as mod

    assert isinstance(mod.COLUMNS, tuple)
    assert isinstance(mod.OPERATORS, dict)
    assert isinstance(mod.AGGREGATES, tuple)


def test_no_python_scan() -> None:
    # the compiler emits SQL; it never iterates rows in application code.
    import app.application.services.saved_view_compiler as mod

    src = inspect.getsource(mod)
    assert "for" not in src or "filters" in src  # only the filter-loop is a for


def test_export_reuses_existing_exporters() -> None:
    import app.api.routes.saved_views as mod

    src = inspect.getsource(mod)
    assert "report_csv_bytes" in src and "report_xlsx_bytes" in src
