"""Unit tests for the GraphRuntimeService (Sprint-2 M2)."""
from __future__ import annotations

import json

import pytest

from app.application.exceptions import ObjectNotFoundError
from app.application.services.graph_runtime import (
    MAX_DEPTH,
    MAX_NODES,
    GraphRuntimeService,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.object_id import ObjectId


class InMemoryGraphRepository(ObjectRepository):
    """Minimal double: store + outbound/inbound edge maps."""

    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}
        self.out: dict[str, list[str]] = {}
        self.inn: dict[str, list[str]] = {}

    def save(self, entity: UniversalObject) -> None:
        self._store[str(entity.id)] = entity
        for rel in entity.relationships:
            src, tgt = str(entity.id), str(rel.target)
            self.out.setdefault(src, []).append(tgt)
            self.inn.setdefault(tgt, []).append(src)

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(str(id))

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[str(i)] for i in ids if str(i) in self._store]

    def exists(self, id: ObjectId) -> bool:
        return str(id) in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(str(id), None)

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        return []

    def find_related(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        return [ObjectId(i) for i in self.out.get(str(object_id), [])]

    def find_inbound(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        return [ObjectId(i) for i in self.inn.get(str(object_id), [])]

    def find(self, *, object_type=None, status=None, metadata_key=None,
             metadata_value=None, page=1, page_size=0, sort_by=None, order="asc"):
        return self.list()

    def count(self, *, object_type=None, status=None, metadata_key=None,
              metadata_value=None) -> int:
        return len(self.list())


def _node(repo: InMemoryGraphRepository, name: str) -> UniversalObject:
    obj = UniversalObject.create(ObjectType.COURSE, name, created_by="f:1")
    obj.pop_domain_events()
    repo.save(obj)
    return obj


def _link(repo: InMemoryGraphRepository, src: UniversalObject, tgt: UniversalObject) -> None:
    src.add_relationship(tgt.id, RelationshipKind.PREREQUISITE_OF, Provenance.ASSERTED)
    repo.save(src)


@pytest.fixture()
def world():
    repo = InMemoryGraphRepository()
    a, b, c, d = _node(repo, "A"), _node(repo, "B"), _node(repo, "C"), _node(repo, "D")
    # chain A->B->C plus A->D (diamond-ish: B->C and D->C)
    _link(repo, a, b)
    _link(repo, a, d)
    _link(repo, b, c)
    _link(repo, d, c)
    return {"repo": repo, "a": a, "b": b, "c": c, "d": d}


def _svc(repo, evaluator=None):
    from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator

    return GraphRuntimeService(repo, evaluator or ObjectPermissionEvaluator())


def _ids(items):
    return [i["id"] for i in items]


def test_bfs_depth_1_matches_old_single_hop(world):
    out = _svc(world["repo"]).traverse(
        world["a"].id, direction="outgoing", kind=None, depth=1, mode="bfs", principal={}
    )
    assert set(_ids(out["items"])) == {str(world["b"].id), str(world["d"].id)}
    assert all(i["level"] == 1 for i in out["items"])
    assert out["total_count"] == 2
    assert out["has_cycle"] is False
    assert out["truncated"] is False
    # title/object_type preserved (additive shape)
    assert {i["title"] for i in out["items"]} == {"B", "D"}


def test_bfs_depth_2_reaches_leaf(world):
    out = _svc(world["repo"]).traverse(
        world["a"].id, direction="outgoing", kind=None, depth=2, mode="bfs", principal={}
    )
    assert set(_ids(out["items"])) == {
        str(world["b"].id), str(world["d"].id), str(world["c"].id),
    }
    levels = {i["id"]: i["level"] for i in out["items"]}
    assert levels[str(world["c"].id)] == 2


def test_incoming_direction(world):
    out = _svc(world["repo"]).traverse(
        world["c"].id, direction="incoming", kind=None, depth=1, mode="bfs", principal={}
    )
    assert set(_ids(out["items"])) == {str(world["b"].id), str(world["d"].id)}


def test_dfs_reaches_chain(world):
    out = _svc(world["repo"]).traverse(
        world["a"].id, direction="outgoing", kind=None, depth=2, mode="dfs", principal={}
    )
    assert set(_ids(out["items"])) == {
        str(world["b"].id), str(world["d"].id), str(world["c"].id),
    }


def test_cycle_detection():
    repo = InMemoryGraphRepository()
    a, b, c = _node(repo, "A"), _node(repo, "B"), _node(repo, "C")
    _link(repo, a, b)
    _link(repo, b, c)
    _link(repo, c, a)  # cycle A->B->C->A
    out = _svc(repo).traverse(
        a.id, direction="outgoing", kind=None, depth=3, mode="bfs", principal={}
    )
    assert out["has_cycle"] is True
    assert len(out["cycle_nodes"]) >= 2


def test_self_loop_terminates():
    repo = InMemoryGraphRepository()
    a = _node(repo, "A")
    _link(repo, a, a)  # self-loop
    out = _svc(repo).traverse(
        a.id, direction="outgoing", kind=None, depth=3, mode="bfs", principal={}
    )
    assert out["has_cycle"] is True
    assert _ids(out["items"]) == []  # self-loop yields no new nodes
    assert out["truncated"] is False


def test_depth_validation(world):
    with pytest.raises(ValueError):
        _svc(world["repo"]).traverse(world["a"].id, direction="outgoing", kind=None,
                                     depth=0, mode="bfs", principal={})
    with pytest.raises(ValueError):
        _svc(world["repo"]).traverse(world["a"].id, direction="outgoing", kind=None,
                                     depth=MAX_DEPTH + 1, mode="bfs", principal={})
    with pytest.raises(ValueError):
        _svc(world["repo"]).traverse(world["a"].id, direction="outgoing", kind=None,
                                     depth=1, mode="sideways", principal={})


def test_missing_root_raises(world):
    with pytest.raises(ObjectNotFoundError):
        _svc(world["repo"]).traverse(
            ObjectId.generate(ObjectType.COURSE), direction="outgoing",
            kind=None, depth=1, mode="bfs", principal={},
        )


def _grant_read(obj, *principals) -> None:
    from app.domain.value_objects.enums import Provenance
    from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer

    obj.set_metadata(
        MetadataEntry(
            "acl.readers",
            json.dumps(list(principals)),
            MetadataLayer.L1_SYSTEM,
            Provenance.SYSTEM,
        ),
        actor="system",
    )


def test_acl_filtering_hides_protected_nodes(world):
    repo = world["repo"]
    stranger = {"sub": "obj:user:STRANGER", "roles": []}
    # Grant B to the stranger; restrict D to someone else.
    _grant_read(world["b"], "obj:user:STRANGER")
    _grant_read(world["d"], "obj:user:OWNER")
    repo.save(world["b"])
    repo.save(world["d"])

    out = _svc(repo).traverse(
        world["a"].id, direction="outgoing", kind=None, depth=1, mode="bfs",
        principal=stranger,
    )
    # Only B is visible to the stranger; D is hidden by its ACL.
    assert set(_ids(out["items"])) == {str(world["b"].id)}


def test_deny_all_yields_empty_but_terminates(world):
    from app.application.ports.permission import PermissionEvaluator

    class DenyAll(PermissionEvaluator):
        def can(self, *, principal, scope, action) -> bool:
            return False

    out = _svc(world["repo"], DenyAll()).traverse(
        world["a"].id, direction="outgoing", kind=None, depth=2, mode="bfs", principal={}
    )
    assert _ids(out["items"]) == []
    assert out["truncated"] is False


def test_deleted_target_skipped():
    repo = InMemoryGraphRepository()
    a = _node(repo, "A")
    b = _node(repo, "B")
    _link(repo, a, b)
    repo.delete(b.id)  # dangling edge
    out = _svc(repo).traverse(
        a.id, direction="outgoing", kind=None, depth=1, mode="bfs", principal={}
    )
    assert _ids(out["items"]) == []


def test_node_cap_truncates():
    repo = InMemoryGraphRepository()
    root = _node(repo, "ROOT")
    leaves = [_node(repo, f"N{i}") for i in range(MAX_NODES + 10)]
    for leaf in leaves:
        _link(repo, root, leaf)
    out = _svc(repo).traverse(
        root.id, direction="outgoing", kind=None, depth=1, mode="bfs", principal={}
    )
    assert out["truncated"] is True
    assert len(_ids(out["items"])) < MAX_NODES


def test_shortest_path(world):
    result = _svc(world["repo"]).find_shortest_path(
        world["a"].id, world["c"].id, direction="outgoing",
        kind=None, max_hops=3, principal={},
    )
    assert result["found"] is True
    assert result["path"] == [str(world["a"].id), str(world["b"].id), str(world["c"].id)]
    assert result["hops"] == 2


def test_shortest_path_hop_limit(world):
    result = _svc(world["repo"]).find_shortest_path(
        world["a"].id, world["c"].id, direction="outgoing",
        kind=None, max_hops=1, principal={},
    )
    assert result["found"] is False
    assert result["path"] == []


def test_shortest_path_acl_filtered(world):
    repo = world["repo"]
    # Hide B from the stranger: only the A->D->C route is visible.
    _grant_read(world["b"], "obj:user:OWNER")
    repo.save(world["b"])
    stranger = {"sub": "obj:user:STRANGER", "roles": []}
    result = _svc(repo).find_shortest_path(
        world["a"].id, world["c"].id, direction="outgoing",
        kind=None, max_hops=3, principal=stranger,
    )
    assert result["found"] is True
    assert result["path"] == [str(world["a"].id), str(world["d"].id), str(world["c"].id)]
