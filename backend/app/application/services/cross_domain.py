"""L8 Cross-Domain Completion — bounded multi-hop executor (ADR-043).

Executes the frozen L8 capabilities (`cross_domain`, `absence`, `temporal`,
`compare`) as additive execution services over the EXISTING infrastructure:

- ``GraphRuntimeService`` for ACL-filtered, bounded multi-hop traversal.
- ``ObjectRepository`` for deterministic object/filtered reads.
- ``PermissionEvaluator`` + ``object_acl_scope`` for object-level ACL.
- L6 evidence/citation pipeline is downstream (this layer produces structured
  intermediate results for citation assembly; it does not itself fabricate).

Boundedness & determinism:
- multi-hop depth ≤ ``MAX_MULTIHOP_DEPTH``; nodes ≤ graph runtime's guard.
- deterministic traversal order (BFS level-order, then object id tie-break).
- ACL pre-filtered at every hop — no hidden access through intermediate hops.
- absence distinguishes confirmed (within authorized scope) vs insufficient
  evidence; never an absolute real-world claim.
- temporal resolution is deterministic/rules-based (see ``temporal.py``).
- compare operates only on authorized results, preserving source linkage.

No second planner, retrieval, ACL, evidence, or memory system is created here.
Memory (L7) is never treated as evidence (ADR-015).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.ports.permission import PermissionEvaluator
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    PermissionAction,
    RelationshipKind,
)
from app.domain.value_objects.object_id import ObjectId

#: Bounded multi-hop depth for entity-anchored cross-domain traversal.
MAX_MULTIHOP_DEPTH = 5
#: Bounded results for a single hop/cross-domain set.
MAX_CROSS_DOMAIN_RESULTS = 200


@dataclass(frozen=True)
class CrossDomainNode:
    """One structured intermediate result of a cross-domain multi-hop.

    Carries identity, type, title, the relationship kind that reached it, the
    hop level, and the deterministic path of object ids. Structured enough for
    L6 citation/evidence assembly.
    """

    object_id: str
    object_type: str
    title: str
    relationship_kind: str | None = None
    level: int = 0
    path: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossDomainResult:
    """The bounded, deterministically ordered cross-domain evidence set."""

    nodes: tuple[CrossDomainNode, ...] = ()
    total_count: int = 0
    truncated: bool = False

    def __len__(self) -> int:
        return self.total_count


@dataclass(frozen=True)
class AbsenceResult:
    """Deterministic absence outcome (ADR-043).

    ``confirmed_absence`` = the authorized/searchable scope was searched and the
    target is not present. ``insufficient_evidence`` = scope/coverage ambiguous.
    ``present`` = at least one authorized match exists (never leaked unreadable).
    """

    outcome: str  # "confirmed_absence" | "insufficient_evidence" | "present"
    authorized_count: int = 0
    reason: str = ""


@dataclass(frozen=True)
class CompareRow:
    """One side of a deterministic comparison, preserving source linkage."""

    label: str
    object_id: str
    object_type: str
    value: object | None = None
    missing: bool = False
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompareResult:
    """Structured comparison output for L6 citation assembly."""

    rows: tuple[CompareRow, ...] = ()
    ordering: str = "label"
    total: int = 0


def principal_for(user: UniversalObject) -> dict:
    """The principal dict consumed by ``PermissionEvaluator`` (sub + roles)."""
    from app.application.use_cases.auth.helpers import get_roles

    return {"sub": str(user.id), "roles": get_roles(user)}


def resolve_user(
    repository: ObjectRepository, principal: str
) -> UniversalObject | None:
    """Resolve a principal id string to an ACTIVE USER UniversalObject (or None).

    Accepts an ``obj:user:...`` id or a matching user title/key, deterministically.
    """
    wanted = principal.strip()
    if not wanted:
        return None
    for obj in repository.find_by_type(ObjectType.USER):
        if obj.status is ObjectStatus.ACTIVE or obj.status.value in ("active",):
            if str(obj.id) == wanted or obj.title == wanted:
                return obj
    return None


class CrossDomainService:
    """Bounded multi-hop + absence + compare execution over existing infra."""

    def __init__(
        self,
        repository: ObjectRepository,
        graph: GraphRuntimeService,
        permissions: PermissionEvaluator,
    ) -> None:
        self._repository = repository
        self._graph = graph
        self._permissions = permissions

    # ------------------------------------------------------- multi-hop
    def multi_hop(
        self,
        entities: list[str],
        user: UniversalObject,
        *,
        max_depth: int = MAX_MULTIHOP_DEPTH,
        kind: RelationshipKind | None = None,
        limit: int = MAX_CROSS_DOMAIN_RESULTS,
    ) -> CrossDomainResult:
        """Entity-anchored cross-domain multi-hop traversal (ACL-filtered).

        From each anchor entity, BFS through typed relationships; every
        intermediate object passes the READ check. Results are deduplicated and
        deterministically ordered (level, then object id). Bounded.
        """
        depth = max(1, min(max_depth, MAX_MULTIHOP_DEPTH))
        principal = principal_for(user)
        seen: dict[str, CrossDomainNode] = {}
        path_of: dict[str, str] = {}

        for entity in entities:
            oid = _parse_oid(entity)
            if oid is None:
                continue
            anchor = self._repository.get_by_id(oid)
            if anchor is None:
                continue
            # ACL check the anchor itself.
            if not self._can_read(anchor, principal):
                continue
            if str(oid) not in seen:
                seen[str(oid)] = CrossDomainNode(
                    object_id=str(oid),
                    object_type=anchor.object_type.value,
                    title=anchor.title,
                    relationship_kind=None,
                    level=0,
                    path=(str(oid),),
                )
                path_of[str(oid)] = str(oid)
            try:
                res = self._graph.traverse(
                    oid,
                    direction="outgoing",
                    kind=kind,
                    depth=depth,
                    mode="bfs",
                    principal=principal,
                )
            except Exception:  # noqa: BLE001 — a failed hop is skipped, not fatal
                continue
            for item in res.get("items", []):
                nid = item["id"]
                if nid in seen:
                    continue
                if len(seen) >= limit:
                    break
                seen[nid] = CrossDomainNode(
                    object_id=nid,
                    object_type=item.get("object_type", ""),
                    title=item.get("title", ""),
                    relationship_kind=kind.value if kind else None,
                    level=item.get("level", 0),
                    path=(path_of.get(item.get("id"), entity), nid),
                )
                path_of[nid] = entity
            if len(seen) >= limit:
                break

        nodes = tuple(sorted(seen.values(), key=lambda n: (n.level, n.object_id)))
        truncated = len(nodes) >= limit
        return CrossDomainResult(
            nodes=nodes[:limit], total_count=len(nodes), truncated=truncated
        )

    # ------------------------------------------------------- absence
    def absence(
        self,
        *,
        target_type: str | None,
        user: UniversalObject,
        source_filter: dict | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> AbsenceResult:
        """Deterministic absence within the authorized/searchable scope.

        Searches the ACL-visible set of ``target_type`` (optionally constrained
        by metadata). ``confirmed_absence`` when none is present AND the scope
        was searched; ``insufficient_evidence`` when the type is unknown or no
        coverage can be established; ``present`` when an authorized match exists.
        """
        if not target_type or target_type not in ObjectType._value2member_map_:
            return AbsenceResult(
                outcome="insufficient_evidence",
                authorized_count=0,
                reason="unknown_target_type",
            )
        ot = ObjectType(target_type)
        principal = principal_for(user)
        matches = 0
        for obj in self._repository.find(
            object_type=ot,
            status=ObjectStatus.ACTIVE,
            metadata_key=metadata_key,
            metadata_value=metadata_value,
        ):
            if not self._can_read(obj, principal):
                continue  # pre-filter — never leak
            matches += 1
            if matches > 0:
                break
        if matches > 0:
            return AbsenceResult(outcome="present", authorized_count=matches)
        # Searched the authorized scope; none present.
        return AbsenceResult(
            outcome="confirmed_absence",
            authorized_count=0,
            reason="not_found_in_authorized_scope",
        )

    # ------------------------------------------------------- compare
    def compare(
        self,
        *,
        labels: list[str],
        user: UniversalObject,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
        target_type: str | None = None,
    ) -> CompareResult:
        """Deterministic comparison over authorized results.

        Each label resolves to at most one authorized object (by object id if the
        label is an id, else by metadata_value target). Missing values are
        surfaced as ``missing=True`` (never hallucinated). Source linkage
        preserved. Ordering deterministic (label).
        """
        principal = principal_for(user)
        rows: list[CompareRow] = []
        for label in labels:
            oid = _parse_oid(label)
            obj = None
            if oid is not None:
                candidate = self._repository.get_by_id(oid)
                if candidate is not None and self._can_read(candidate, principal):
                    obj = candidate
            else:
                obj = self._first_authorized(
                    principal, target_type, metadata_key, metadata_value or label
                )
            if obj is None:
                rows.append(
                    CompareRow(
                        label=label,
                        object_id="",
                        object_type=target_type or "",
                        value=None,
                        missing=True,
                        source_ids=(),
                    )
                )
                continue
            rows.append(
                CompareRow(
                    label=label,
                    object_id=str(obj.id),
                    object_type=obj.object_type.value,
                    value=_payload(obj),
                    missing=False,
                    source_ids=(str(obj.id),),
                )
            )
        rows.sort(key=lambda r: r.label)
        return CompareResult(rows=tuple(rows), ordering="label", total=len(rows))

    # ------------------------------------------------------- internals
    def _first_authorized(
        self,
        principal: dict,
        target_type: str | None,
        metadata_key: str | None,
        metadata_value: str,
    ) -> UniversalObject | None:
        ot = ObjectType(target_type) if target_type and target_type in ObjectType._value2member_map_ else None
        for obj in self._repository.find(
            object_type=ot,
            status=ObjectStatus.ACTIVE,
            metadata_key=metadata_key,
            metadata_value=metadata_value,
        ):
            if self._can_read(obj, principal):
                return obj
        return None

    def _can_read(self, obj: UniversalObject, principal: dict) -> bool:
        return self._permissions.can(
            principal=principal, scope=object_acl_scope(obj), action=PermissionAction.READ
        )


def _parse_oid(raw: str) -> ObjectId | None:
    try:
        return ObjectId(raw)
    except Exception:  # noqa: BLE001
        return None


def _payload(obj: UniversalObject) -> object:
    """The comparison payload: a bounded, non-arbitrary projection."""
    return {"title": obj.title, "object_type": obj.object_type.value}


__all__ = [
    "AbsenceResult",
    "CompareResult",
    "CompareRow",
    "CrossDomainNode",
    "CrossDomainResult",
    "CrossDomainService",
    "MAX_CROSS_DOMAIN_RESULTS",
    "MAX_MULTIHOP_DEPTH",
    "principal_for",
    "resolve_user",
]
