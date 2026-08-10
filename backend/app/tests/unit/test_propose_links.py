"""Unit tests: M28 SMART_LINK proposal lifecycle (AI proposes, human approves).

Pins the deterministic evidence engine and the review semantics:

- proposals are SMART_LINK edges with INFERRED provenance, confidence and
  evidence — never ASSERTED (AI boundary, guardrail-tested too);
- candidates the principal cannot READ are skipped;
- approval promotes the edge to its proposed kind with ASSERTED provenance
  and records the human decision in L6 metadata;
- approval/rejection requires WRITE on the target;
- rejection removes the edge;
- already-linked / already-decided targets are never re-proposed.
"""
from __future__ import annotations

import json

import pytest

from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    PermissionDeniedError,
)
from app.application.ports.permission import PermissionEvaluator
from app.application.use_cases.ai.propose_links import (
    ProposeLinksUseCase,
    proposal_key,
    review_key,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    PermissionAction,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class InMemoryObjectRepository(ObjectRepository):
    """Minimal in-memory double for the proposal use case."""

    def __init__(self) -> None:
        self._store: dict[ObjectId, UniversalObject] = {}

    def save(self, entity, *, outbox_events=()) -> None:
        self._store[entity.id] = entity

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(id)

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[i] for i in ids if i in self._store]

    def exists(self, id: ObjectId) -> bool:
        return id in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(id, None)

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status):
        return [o for o in self._store.values() if o.status == status]

    def find_by_metadata(self, key, value=None):
        return []

    def find_related(self, object_id, kind=None):
        obj = self._store.get(object_id)
        if obj is None:
            return []
        return [r.target for r in obj.relationships if kind is None or r.kind == kind]

    def find_inbound(self, object_id, kind=None):
        return []

    def find(self, **kwargs):
        return list(self._store.values())

    def count(self, **kwargs):
        return len(self._store)


class AllowAllPermissions(PermissionEvaluator):
    def can(self, *, principal, scope, action) -> bool:
        return True


class DenyOwnerPermissions(PermissionEvaluator):
    """Denies READ/WRITE for objects owned by ``denied_owner`` (the ACL
    scope carries the owner — object ids are not part of the scope)."""

    def __init__(self, denied_owner: str) -> None:
        self._denied_owner = denied_owner

    def can(self, *, principal, scope, action) -> bool:
        import json as _json

        try:
            acl = _json.loads(scope or "{}")
        except (ValueError, TypeError):
            acl = {}
        return str(acl.get("owner", "")) != self._denied_owner


def _entry(key: str, value: str, layer: MetadataLayer = MetadataLayer.L6_HUMAN_ASSERTED):
    return MetadataEntry(key, value, layer, Provenance.ASSERTED)


def _obj(
    object_type: ObjectType,
    title: str,
    metadata: list[MetadataEntry] | None = None,
    *,
    owner: str = "user:1",
    seq: int = 1,
) -> UniversalObject:
    return UniversalObject.create(
        object_type=object_type,
        title=title,
        created_by=owner,
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=tuple(metadata or [])),
        object_id=ObjectId(f"obj:{object_type.value}:{seq:016X}"),
    )


def _publication(repo, *, authors: str, seq: int = 1) -> UniversalObject:
    pub = _obj(
        ObjectType.PUBLICATION,
        f"Paper {seq}",
        [_entry("authors", authors), _entry("keywords", "quantum")],
        seq=seq,
    )
    pub.pop_domain_events()
    repo.save(pub)
    return pub


def _faculty(repo, *, name: str, seq: int = 101, owner: str = "user:1") -> UniversalObject:
    fac = _obj(ObjectType.FACULTY, name, [_entry("name", name)], owner=owner, seq=seq)
    fac.pop_domain_events()
    repo.save(fac)
    return fac


PRINCIPAL = {"sub": "obj:user:test-0001", "roles": []}


def test_propose_creates_inferred_smart_link_with_evidence():
    repo = InMemoryObjectRepository()
    pub = _publication(repo, authors="Alice;Bob")
    fac = _faculty(repo, name="Alice")

    result = ProposeLinksUseCase(repo, AllowAllPermissions()).propose(
        pub.id, actor="ai", principal=PRINCIPAL
    )

    assert result.created == 1
    item = result.items[0]
    assert item.target_id == str(fac.id)
    assert item.kind == RelationshipKind.AUTHORED_BY.value
    assert item.status == "pending"
    assert item.confidence > 0.0
    assert any("authors" in e and "name" in e for e in item.evidence)

    saved = repo.get_by_id(pub.id)
    assert any(
        r.kind is RelationshipKind.SMART_LINK
        and r.provenance is Provenance.INFERRED
        and r.confidence == item.confidence
        and r.evidence == item.evidence
        for r in saved.relationships
    ), "edge must be SMART_LINK with INFERRED provenance"
    proposal = json.loads(saved.metadata.get_value(proposal_key(str(fac.id))))
    assert proposal["kind"] == "authored_by"
    assert proposal["status"] == "pending"


def test_propose_skips_already_linked_and_decided_targets():
    repo = InMemoryObjectRepository()
    pub = _publication(repo, authors="Alice")
    fac = _faculty(repo, name="Alice")
    fac2 = _faculty(repo, name="Alice", seq=102)

    # already linked
    pub.add_relationship(fac2.id, RelationshipKind.RELATED_TO, actor="u")
    pub.pop_domain_events()
    repo.save(pub)
    # decided (has a review record)
    pub.set_metadata(
        MetadataEntry(
            review_key(str(fac.id)),
            json.dumps({"status": "rejected", "reviewed_by": "u"}),
            MetadataLayer.L6_HUMAN_ASSERTED,
            Provenance.ASSERTED,
        ),
        actor="u",
    )
    pub.pop_domain_events()
    repo.save(pub)

    result = ProposeLinksUseCase(repo, AllowAllPermissions()).propose(
        pub.id, actor="ai", principal=PRINCIPAL
    )
    assert result.created == 0


def test_propose_skips_targets_the_principal_cannot_read():
    repo = InMemoryObjectRepository()
    pub = _publication(repo, authors="Alice")
    # Owned by someone else → the evaluator denies READ → skipped.
    _faculty(repo, name="Alice", owner="obj:user:someone-else")
    denied = DenyOwnerPermissions("obj:user:someone-else")

    result = ProposeLinksUseCase(repo, denied).propose(
        pub.id, actor="ai", principal=PRINCIPAL
    )
    assert result.created == 0


def test_approve_promotes_to_asserted_kind_and_records_review():
    repo = InMemoryObjectRepository()
    pub = _publication(repo, authors="Alice")
    fac = _faculty(repo, name="Alice")
    use_case = ProposeLinksUseCase(repo, AllowAllPermissions())
    proposed = use_case.propose(pub.id, actor="ai", principal=PRINCIPAL)
    assert proposed.created == 1

    decision = use_case.approve(
        pub.id, fac.id, actor="obj:user:reviewer-0001", principal=PRINCIPAL
    )
    assert decision.status == "approved"
    assert decision.kind == RelationshipKind.AUTHORED_BY.value

    saved = repo.get_by_id(pub.id)
    kinds = {r.kind for r in saved.relationships}
    assert RelationshipKind.SMART_LINK not in kinds
    assert RelationshipKind.AUTHORED_BY in kinds
    edge = next(r for r in saved.relationships if r.kind is RelationshipKind.AUTHORED_BY)
    assert edge.provenance is Provenance.ASSERTED
    assert edge.confidence == proposed.items[0].confidence

    review = json.loads(saved.metadata.get_value(review_key(str(fac.id))))
    assert review["status"] == "approved"
    assert review["reviewed_by"] == "obj:user:reviewer-0001"
    assert review["reviewed_at"]
    # Human decision is human-asserted (L6).
    entry = saved.metadata.get(review_key(str(fac.id)))
    assert entry.layer is MetadataLayer.L6_HUMAN_ASSERTED
    assert entry.source is Provenance.ASSERTED


def test_reject_removes_edge_and_records_review():
    repo = InMemoryObjectRepository()
    pub = _publication(repo, authors="Alice")
    fac = _faculty(repo, name="Alice")
    use_case = ProposeLinksUseCase(repo, AllowAllPermissions())
    use_case.propose(pub.id, actor="ai", principal=PRINCIPAL)

    decision = use_case.reject(pub.id, fac.id, actor="reviewer", principal=PRINCIPAL)
    assert decision.status == "rejected"
    assert decision.kind == ""

    saved = repo.get_by_id(pub.id)
    assert all(r.kind is not RelationshipKind.SMART_LINK for r in saved.relationships)
    review = json.loads(saved.metadata.get_value(review_key(str(fac.id))))
    assert review["status"] == "rejected"
    assert review["reviewed_by"] == "reviewer"


def test_approve_requires_write_on_target():
    repo = InMemoryObjectRepository()
    pub = _publication(repo, authors="Alice")
    fac = _faculty(repo, name="Alice", owner="obj:user:someone-else")
    use_case = ProposeLinksUseCase(repo, AllowAllPermissions())
    use_case.propose(pub.id, actor="ai", principal=PRINCIPAL)

    denied = DenyOwnerPermissions("obj:user:someone-else")
    with pytest.raises(PermissionDeniedError):
        ProposeLinksUseCase(repo, denied).approve(
            pub.id, fac.id, actor="reviewer", principal=PRINCIPAL
        )


def test_approve_non_pending_raises_conflict():
    repo = InMemoryObjectRepository()
    pub = _publication(repo, authors="Alice")
    fac = _faculty(repo, name="Alice")
    use_case = ProposeLinksUseCase(repo, AllowAllPermissions())
    use_case.propose(pub.id, actor="ai", principal=PRINCIPAL)
    use_case.approve(pub.id, fac.id, actor="reviewer", principal=PRINCIPAL)

    with pytest.raises(ObjectAlreadyExistsError):
        use_case.approve(pub.id, fac.id, actor="reviewer2", principal=PRINCIPAL)


def test_unknown_source_raises_not_found():
    repo = InMemoryObjectRepository()
    with pytest.raises(ObjectNotFoundError):
        ProposeLinksUseCase(repo, AllowAllPermissions()).propose(
            ObjectId("obj:publication:0000000000000001"),
            actor="ai",
            principal=PRINCIPAL,
        )
