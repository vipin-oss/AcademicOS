"""V3 M12 AcademicAiRouter unit tests (ADR-059)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.ports.spend_ledger import SpendLedger, SpendRecord
from app.application.services.academic_ai_router import (
    NO_EXTERNAL_SEARCH,
    AcademicAiRouter,
)
from app.application.services.claim_service import ClaimService
from app.application.services.model_budget import (
    ON_BUDGET_BLOCK,
    ModelBudgetPolicy,
    ModelBudgetPolicyConfig,
)
from app.application.use_cases.ai.rung0 import Rung0ClaimAnswerer
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.persistence.spend_ledger import SQLSpendLedger


class _FakeLedger(SpendLedger):
    def __init__(self):
        self.records = []

    def record(self, spend: SpendRecord) -> SpendRecord:
        self.records.append(spend)
        return spend

    def total_for_user(self, user_id: str) -> float:
        return 0.0

    def total_for_tenant(self, tenant_id: str) -> float:
        return 0.0


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(obj_id="obj:user:alice-0001") -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId(obj_id),
    )


def _router(db, budget=None, grounded=None):
    rung0 = Rung0ClaimAnswerer(SQLClaimStore(db), permission_evaluator=ObjectPermissionEvaluator())
    return AcademicAiRouter(
        rung0=rung0,
        budget_policy=budget or ModelBudgetPolicy(_FakeLedger(), ModelBudgetPolicyConfig()),
        spend_ledger=_FakeLedger(),
        grounded_qa=grounded,
    )


def test_rung0_answers_claims_for_free(db):
    service = ClaimService(SQLClaimStore(db))
    claim = service.propose(
        predicate_id="sanctioned_amount", raw_value="1000", source_text="1000",
        source_document_id="obj:document:1", source_version=1, spans=[], acl_scope=None,
    )
    service.confirm(claim.claim_id)
    db.commit()

    result = _router(db).route("What is the sanctioned amount?", _user())
    assert result.rung == 0
    assert result.source_class == "claims"
    assert result.free is True
    assert result.estimated_cost_usd == 0.0


def test_no_answerable_rung_refuses_honestly(db):
    result = _router(db).route("random question with no facts", _user())
    assert result.rung >= 0
    assert result.source_class in ("refused", "degraded")
    assert result.free is True


def test_source_policy_is_internal(db):
    router = _router(db)
    assert router.source_policy == "internal"
    assert NO_EXTERNAL_SEARCH is True


class _FakeGrounded:
    def __init__(self, result):
        self._result = result

    def execute(self, question, user):
        return self._result


class _QAResult:
    answer = "grounded answer"
    available = True
    provider_id = "openai"
    model = "gpt-test"
    input_tokens = 100
    output_tokens = 50
    citations = ({"object_id": "obj:document:1", "title": "x"},)


def test_grounded_qa_records_spend_when_allowed(db):
    ledger = _FakeLedger()
    router = AcademicAiRouter(
        rung0=Rung0ClaimAnswerer(SQLClaimStore(db), permission_evaluator=ObjectPermissionEvaluator()),
        budget_policy=ModelBudgetPolicy(ledger, ModelBudgetPolicyConfig()),
        spend_ledger=ledger,
        grounded_qa=_FakeGrounded(_QAResult()),
    )
    result = router.route("tell me about quantum dots", _user())
    assert result.rung == 6
    assert result.free is False
    assert result.provider_id == "openai"
    assert len(ledger.records) == 1


def test_budget_block_denies_paid_path(db):
    # tenant budget already exhausted with block policy
    policy = ModelBudgetPolicy(
        SQLSpendLedger(db),
        ModelBudgetPolicyConfig(tenant_budget_usd=0.001, on_budget_exhausted=ON_BUDGET_BLOCK),
    )
    # pre-fill the ledger so the check fails
    SQLSpendLedger(db).record(SpendRecord(
        id="s1", tenant_id="default", user_id="obj:user:alice-0001",
        provider_id="openai", model="m", input_tokens=0, output_tokens=0,
        estimated_cost_usd=0.01, created_at="2026-01-01T00:00:00+00:00",
    ))
    db.commit()

    router = AcademicAiRouter(
        rung0=Rung0ClaimAnswerer(SQLClaimStore(db), permission_evaluator=ObjectPermissionEvaluator()),
        budget_policy=policy,
        spend_ledger=SQLSpendLedger(db),
        grounded_qa=_FakeGrounded(_QAResult()),
    )
    result = router.route("tell me about quantum dots", _user())
    # budget blocked -> degraded (free, no gateway, no spend recorded)
    assert result.free is True
    assert result.source_class in ("degraded", "refused")
