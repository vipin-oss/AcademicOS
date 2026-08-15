"""V3 M12 model budget policy unit tests (ADR-059)."""

from __future__ import annotations

from app.application.ports.spend_ledger import SpendLedger, SpendRecord
from app.application.services.model_budget import (
    ON_BUDGET_ALLOW,
    ON_BUDGET_BLOCK,
    ON_BUDGET_DEGRADE,
    ModelBudgetPolicy,
    ModelBudgetPolicyConfig,
)


class _FakeLedger(SpendLedger):
    def __init__(self, by_user=None, by_tenant=None):
        self._by_user = by_user or {}
        self._by_tenant = by_tenant or {}
        self.records = []

    def record(self, spend: SpendRecord) -> SpendRecord:
        self.records.append(spend)
        return spend

    def total_for_user(self, user_id: str) -> float:
        return self._by_user.get(user_id, 0.0)

    def total_for_tenant(self, tenant_id: str) -> float:
        return self._by_tenant.get(tenant_id, 0.0)


def test_unlimited_when_no_caps():
    policy = ModelBudgetPolicy(_FakeLedger(), ModelBudgetPolicyConfig())
    d = policy.check(tenant_id="t", user_id="u", estimated_cost_usd=100.0)
    assert d.allowed and d.action == "allow"


def test_tenant_budget_blocks_when_exceeded():
    ledger = _FakeLedger(by_tenant={"t": 90.0})
    policy = ModelBudgetPolicy(
        ledger,
        ModelBudgetPolicyConfig(tenant_budget_usd=100.0, on_budget_exhausted=ON_BUDGET_BLOCK),
    )
    d = policy.check(tenant_id="t", user_id="u", estimated_cost_usd=20.0)
    assert not d.allowed and d.action == ON_BUDGET_BLOCK


def test_tenant_budget_degrades_when_exceeded():
    ledger = _FakeLedger(by_tenant={"t": 90.0})
    policy = ModelBudgetPolicy(
        ledger,
        ModelBudgetPolicyConfig(tenant_budget_usd=100.0, on_budget_exhausted=ON_BUDGET_DEGRADE),
    )
    d = policy.check(tenant_id="t", user_id="u", estimated_cost_usd=20.0)
    assert not d.allowed and d.action == ON_BUDGET_DEGRADE


def test_user_cap_blocks():
    ledger = _FakeLedger(by_user={"u": 9.0})
    policy = ModelBudgetPolicy(
        ledger,
        ModelBudgetPolicyConfig(per_user_cap_usd=10.0, on_budget_exhausted=ON_BUDGET_BLOCK),
    )
    d = policy.check(tenant_id="t", user_id="u", estimated_cost_usd=2.0)
    assert not d.allowed and d.action == ON_BUDGET_BLOCK


def test_on_budget_allow_passes_through():
    ledger = _FakeLedger(by_tenant={"t": 90.0})
    policy = ModelBudgetPolicy(
        ledger,
        ModelBudgetPolicyConfig(tenant_budget_usd=100.0, on_budget_exhausted=ON_BUDGET_ALLOW),
    )
    d = policy.check(tenant_id="t", user_id="u", estimated_cost_usd=20.0)
    assert d.allowed and d.action == ON_BUDGET_ALLOW
