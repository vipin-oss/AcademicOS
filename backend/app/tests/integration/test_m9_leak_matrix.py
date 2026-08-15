"""V3 M9 leak-matrix tests (ADR-056): cross-principal isolation + revocation.

The M9 gate: prove a principal can never read another principal's private
object (search pre-filter), and that revocation actually kills a token.
Run in deny-by-default mode (the second-user posture).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.outbox import to_outbox_row
from app.application.use_cases.auth.helpers import set_roles
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.session_revocation_model import (  # noqa: F401
    SessionRevocationModel,
)
from app.infrastructure.db.session import get_db
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.vector_db.fake import FakeVectorRepository
from app.main import app


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
        Base.metadata.drop_all(engine)
        engine.dispose()


def _user(obj_id, title) -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, title, created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId(obj_id),
    )


def _doc(obj_id, title, owner) -> UniversalObject:
    return UniversalObject.create(
        ObjectType.DOCUMENT, title, created_by=owner, status=ObjectStatus.ACTIVE,
        object_id=ObjectId(obj_id),
    )


def _seed(db, repo, embedder, *objects) -> FakeVectorRepository:
    vectors = FakeVectorRepository()
    for obj in objects:
        events = obj.pop_domain_events()
        repo.save(obj, outbox_events=[to_outbox_row(e) for e in events])
    SearchIndexApplier(db, vector_repository=vectors, embedder=embedder).apply_pending()
    return vectors


def test_search_pre_filter_hides_other_principals_private_docs(db):
    embedder = HashingEmbedder()
    repo = SQLAlchemyObjectRepository(db)
    alice = _user("obj:user:alice-0001", "alice")
    bob = _user("obj:user:bob-0001", "bob")
    bob_doc = _doc("obj:document:bob-private", "Bob's secret grant", owner="obj:user:bob-0001")
    vectors = _seed(db, repo, embedder, alice, bob, bob_doc)

    def run(principal_sub, roles=()):
        uc = SearchObjectsUseCase(
            SQLAlchemySearchRepository(db), repo,
            ObjectPermissionEvaluator(deny_by_default=True),
            vector_repository=vectors, embedder=embedder, parallel=False,
        )
        caller = _user(principal_sub, "caller")
        if roles:
            set_roles(caller, list(roles))
        return uc.execute(user=caller, text="grant", limit=10)

    # Bob (owner) sees his private doc.
    bob_hits = [h.object_id for h in run("obj:user:bob-0001")]
    assert "obj:document:bob-private" in bob_hits
    # Alice (non-owner, non-admin) does NOT — never ranked, never leaked.
    alice_hits = [h.object_id for h in run("obj:user:alice-0001")]
    assert "obj:document:bob-private" not in alice_hits
    # Admin sees it.
    admin_hits = [h.object_id for h in run("obj:user:admin-0001", roles=["admin"])]
    assert "obj:document:bob-private" in admin_hits


def test_logout_revokes_token_via_api(db):
    # Wire the override DB session.
    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as client:
            # register + login
            reg = client.post("/api/v1/auth/register", json={"username": "leakuser", "password": "pw-1234-secret"})
            assert reg.status_code in (200, 201), reg.text
            login = client.post("/api/v1/auth/login", json={"username": "leakuser", "password": "pw-1234-secret"})
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

            logout = client.post("/api/v1/auth/logout", headers=headers)
            assert logout.status_code == 200, logout.text
            assert logout.json()["revoked"] is True

            # revoked token is dead
            assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    finally:
        app.dependency_overrides.clear()
