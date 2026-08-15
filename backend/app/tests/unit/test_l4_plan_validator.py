"""L4 plan validator tests (ADR-035): deterministic, schema/type/scope."""

from __future__ import annotations

import pytest

from app.application.services.plan_validator import (
    PlanValidationError,
    PlanValidator,
)


def test_valid_plan():
    plan = PlanValidator().validate(
        {"operation": "list", "domains": ["faculty"], "entities": ["Prof X"],
         "output_kind": "answer", "evidence_required": False}
    )
    assert plan.operation == "list"
    assert plan.domains == ("faculty",)


def test_invalid_operation_rejected():
    with pytest.raises(PlanValidationError):
        PlanValidator().validate({"operation": "hack", "output_kind": "answer"})


def test_missing_operation_rejected():
    with pytest.raises(PlanValidationError):
        PlanValidator().validate({"domains": []})


def test_non_dict_rejected():
    with pytest.raises(PlanValidationError):
        PlanValidator().validate(["not", "a", "dict"])


def test_entities_must_be_strings():
    with pytest.raises(PlanValidationError):
        PlanValidator().validate({"operation": "list", "entities": [1, 2, 3]})


def test_filters_bounded():
    with pytest.raises(PlanValidationError):
        PlanValidator().validate(
            {"operation": "list", "filters": {str(i): i for i in range(100)}}
        )


def test_invalid_output_kind_rejected():
    with pytest.raises(PlanValidationError):
        PlanValidator().validate({"operation": "list", "output_kind": "sql"})


def test_subplans_bounded_depth():
    deep = {"operation": "list", "sub_plans": [
        {"operation": "list", "sub_plans": [
            {"operation": "list", "sub_plans": [
                {"operation": "list", "sub_plans": [{"operation": "list"}]}
            ]}
        ]}
    ]}
    with pytest.raises(PlanValidationError):
        PlanValidator().validate(deep)


def test_valid_clarify_refuse_plans():
    assert PlanValidator().validate({"operation": "clarify"}).operation == "clarify"
    assert PlanValidator().validate({"operation": "refuse"}).operation == "refuse"
