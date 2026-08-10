"""M28 — SMART_LINK relationship proposals (AI proposes, human approves).

The proposal engine is the T0 deterministic tier of the AI architecture:
candidates are academic objects whose metadata shares field-pair evidence
with the source object (e.g. a publication's ``authors`` matching a faculty
member's ``name``). Every proposal is materialised as a ``SMART_LINK`` edge
with ``Provenance.INFERRED``, a deterministic confidence and the matching
evidence quotes — never as an authoritative relationship.

Review (the human step) promotes the edge to its proposed kind with
``Provenance.ASSERTED`` — the human decision is human-asserted and recorded
in L6 metadata — or removes it. AI code in this module never creates an
``ASSERTED`` edge (enforced by an architecture guardrail test).

Reuses existing seams: the universal object aggregate (relationships +
metadata + domain events), the transactional outbox (events ride the same
``repo.save``), the R4 permission evaluator (candidates are READ-filtered;
review requires WRITE on both endpoints), and the ``SMART_LINK``
relationship kind (declared since S2, produced here for the first time).
"""
from __future__ import annotations

import datetime as dt
import json

from app.application.dtos.links import (
    LinkDecisionResult,
    LinkProposalOutput,
    ListLinkProposalsResult,
    ProposeLinksResult,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    PermissionDeniedError,
)
from app.application.ports.permission import PermissionEvaluator
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.exceptions import RelationshipConflictError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    PermissionAction,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId

PROPOSAL_KEY_PREFIX = "ai.proposal."
REVIEW_KEY_PREFIX = "ai.review."

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

MAX_PROPOSALS_PER_CALL = 20

#: Metadata layers that count as evidence (L4 understanding, L5 inferred,
#: L6 human-asserted). System/file/format layers never become evidence.
_MIN_EVIDENCE_LAYER = 4

#: Volatile/system key prefixes never used as evidence.
_SKIPPED_KEY_PREFIXES = ("intake.", "acl.", "ai.", "auth.")

#: Source type -> target type -> the relationship kind an approval promotes to.
TYPE_KIND_MAP: dict[tuple[ObjectType, ObjectType], RelationshipKind] = {
    (ObjectType.PUBLICATION, ObjectType.FACULTY): RelationshipKind.AUTHORED_BY,
    (ObjectType.FACULTY, ObjectType.PUBLICATION): RelationshipKind.AUTHORS,
    (ObjectType.FACULTY, ObjectType.RESEARCH_PROJECT): RelationshipKind.LEADS,
    (ObjectType.PUBLICATION, ObjectType.RESEARCH_PROJECT): RelationshipKind.RELATED_TO,
    (ObjectType.RESEARCH_PROJECT, ObjectType.PUBLICATION): RelationshipKind.RELATED_TO,
    (ObjectType.PUBLICATION, ObjectType.DOCUMENT): RelationshipKind.RELATED_TO,
    (ObjectType.DOCUMENT, ObjectType.PUBLICATION): RelationshipKind.RELATED_TO,
    (ObjectType.GRANT, ObjectType.FUNDING_AGENCY): RelationshipKind.FUNDED_BY,
}

#: Source metadata key -> target metadata key compared as evidence, per pair.
FIELD_MAP: dict[tuple[ObjectType, ObjectType], tuple[tuple[str, str], ...]] = {
    (ObjectType.PUBLICATION, ObjectType.FACULTY): (("authors", "name"),),
    (ObjectType.FACULTY, ObjectType.PUBLICATION): (("name", "authors"),),
    (ObjectType.FACULTY, ObjectType.RESEARCH_PROJECT): (
        ("name", "pi"),
        ("department", "department"),
    ),
    (ObjectType.PUBLICATION, ObjectType.RESEARCH_PROJECT): (
        ("project_id", "project_code"),
        ("department", "department"),
    ),
    (ObjectType.RESEARCH_PROJECT, ObjectType.PUBLICATION): (
        ("project_code", "project_id"),
        ("department", "department"),
    ),
    (ObjectType.PUBLICATION, ObjectType.DOCUMENT): (("keywords", "tags"),),
    (ObjectType.DOCUMENT, ObjectType.PUBLICATION): (("tags", "keywords"),),
    (ObjectType.GRANT, ObjectType.FUNDING_AGENCY): (("funding_agency", "name"),),
}

#: Target types the engine may propose against (never users/system objects).
_ALLOWED_TARGET_TYPES = frozenset(
    {
        ObjectType.FACULTY,
        ObjectType.PUBLICATION,
        ObjectType.RESEARCH_PROJECT,
        ObjectType.DOCUMENT,
        ObjectType.GRANT,
        ObjectType.FUNDING_AGENCY,
    }
)


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def proposal_key(target_id: str) -> str:
    return f"{PROPOSAL_KEY_PREFIX}{target_id}"


def review_key(target_id: str) -> str:
    return f"{REVIEW_KEY_PREFIX}{target_id}"


def _meta(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


def _evidence_matches(source_value: str, target_value: str) -> bool:
    """Case-insensitive equality or token containment (author lists, tags)."""
    a = source_value.casefold().strip()
    b = target_value.casefold().strip()
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


def _confidence(n_matches: int) -> float:
    """Deterministic confidence from the number of matched field pairs."""
    return round(min(0.95, 0.25 + 0.30 * n_matches), 2)


class ProposeLinksUseCase:
    """The SMART_LINK lifecycle: propose -> list -> approve/reject."""

    def __init__(
        self,
        repository: ObjectRepository,
        permission_evaluator: PermissionEvaluator,
    ) -> None:
        self._repository = repository
        self._permissions = permission_evaluator

    # ------------------------------------------------------------------ propose
    def propose(
        self,
        source_id: ObjectId,
        *,
        actor: str,
        principal: dict,
        limit: int = MAX_PROPOSALS_PER_CALL,
    ) -> ProposeLinksResult:
        """Scan compatible objects, propose SMART_LINK edges for matched
        evidence. Candidates the principal cannot READ are skipped (no
        leakage through proposals)."""
        source = self._require_object(source_id)
        pair_field_map = {
            (st, tt): fields
            for (st, tt), fields in FIELD_MAP.items()
            if st is source.object_type
        }
        if not pair_field_map:
            return ProposeLinksResult(items=(), created=0)

        by_target: dict[str, UniversalObject] = {}
        for (st, tt), _fields in pair_field_map.items():
            for candidate in self._repository.find_by_type(tt):
                by_target[str(candidate.id)] = candidate

        created: list[LinkProposalOutput] = []
        for target in by_target.values():
            if len(created) >= limit:
                break
            if target.id == source.id:
                continue
            if not self._can_read(target, principal):
                continue
            if self._already_linked(source, target.id):
                continue
            if self._proposal_exists(source, target.id):
                continue
            outcome = self._evidence_for(source, target)
            if not outcome:
                continue
            evidence, matches = outcome
            kind = TYPE_KIND_MAP[(source.object_type, target.object_type)]
            confidence = _confidence(len(matches))
            try:
                source.add_relationship(
                    target.id,
                    RelationshipKind.SMART_LINK,
                    Provenance.INFERRED,
                    actor=actor,
                    confidence=confidence,
                    evidence=evidence,
                )
            except RelationshipConflictError:
                continue  # duplicate SMART_LINK edge — skip
            source.set_metadata(
                MetadataEntry(
                    proposal_key(str(target.id)),
                    json.dumps(
                        {
                            "kind": kind.value,
                            "confidence": confidence,
                            "evidence": list(evidence),
                            "status": STATUS_PENDING,
                            "created_at": _utcnow_iso(),
                        },
                        ensure_ascii=False,
                    ),
                    MetadataLayer.L5_INFERRED,
                    Provenance.INFERRED,
                ),
                actor=actor,
            )
            created.append(
                LinkProposalOutput(
                    target_id=str(target.id),
                    target_type=target.object_type.value,
                    target_title=target.title,
                    kind=kind.value,
                    confidence=confidence,
                    evidence=evidence,
                    status=STATUS_PENDING,
                )
            )

        if created:
            self._save(source)
        return ProposeLinksResult(items=tuple(created), created=len(created))

    # ------------------------------------------------------------------ list
    def list_proposals(self, source_id: ObjectId) -> ListLinkProposalsResult:
        """Every SMART_LINK proposal of the source (pending and decided),
        deterministic order by target id."""
        source = self._require_object(source_id)
        rows: list[LinkProposalOutput] = []
        targets: list[ObjectId] = []
        for rel in source.relationships:
            if rel.kind is RelationshipKind.SMART_LINK:
                targets.append(rel.target)
        by_id = {
            str(obj.id): obj
            for obj in self._repository.find_by_ids(targets)
        }
        for target_id in sorted(by_id, key=str):
            target = by_id[target_id]
            proposal = self._proposal_of(source, target_id)
            rows.append(
                LinkProposalOutput(
                    target_id=target_id,
                    target_type=target.object_type.value,
                    target_title=target.title,
                    kind=str(proposal.get("kind", RelationshipKind.SMART_LINK.value)),
                    confidence=float(proposal.get("confidence", 0.0)),
                    evidence=tuple(proposal.get("evidence") or ()),
                    status=str(proposal.get("status", STATUS_PENDING)),
                    reviewed_by=str(proposal.get("reviewed_by", "")),
                    reviewed_at=proposal.get("reviewed_at"),
                )
            )
        return ListLinkProposalsResult(items=tuple(rows))

    # ----------------------------------------------------------------- approve
    def approve(
        self,
        source_id: ObjectId,
        target_id: ObjectId,
        *,
        actor: str,
        principal: dict,
    ) -> LinkDecisionResult:
        """Human approval: promote the SMART_LINK edge to its proposed kind
        with ASSERTED provenance (human-asserted) and record the decision in
        L6 metadata."""
        source = self._require_object(source_id)
        target = self._require_object(target_id)
        if not self._can_write(target, principal):
            raise PermissionDeniedError(
                f"Missing permission: {PermissionAction.WRITE.value} on target {target_id}."
            )
        proposal = self._require_pending_proposal(source, target_id)
        kind = RelationshipKind(str(proposal["kind"]))
        source.remove_relationship(
            target_id, RelationshipKind.SMART_LINK, Provenance.INFERRED, actor=actor
        )
        try:
            source.add_relationship(
                target_id,
                kind,
                Provenance.ASSERTED,
                actor=actor,
                confidence=float(proposal.get("confidence") or 0.0),
                evidence=tuple(proposal.get("evidence") or ()),
            )
        except RelationshipConflictError as exc:
            raise ObjectAlreadyExistsError(
                f"An asserted {kind.value} relationship to {target_id} already exists."
            ) from exc
        self._record_decision(
            source, target_id, kind, STATUS_APPROVED, actor=actor, proposal=proposal
        )
        self._save(source)
        return LinkDecisionResult(
            target_id=str(target_id),
            target_type=target.object_type.value,
            target_title=target.title,
            kind=kind.value,
            status=STATUS_APPROVED,
        )

    # ------------------------------------------------------------------ reject
    def reject(
        self,
        source_id: ObjectId,
        target_id: ObjectId,
        *,
        actor: str,
        principal: dict,
    ) -> LinkDecisionResult:
        """Human rejection: remove the SMART_LINK edge and record the
        decision in L6 metadata."""
        source = self._require_object(source_id)
        target = self._require_object(target_id)
        if not self._can_write(target, principal):
            raise PermissionDeniedError(
                f"Missing permission: {PermissionAction.WRITE.value} on target {target_id}."
            )
        proposal = self._require_pending_proposal(source, target_id)
        source.remove_relationship(
            target_id, RelationshipKind.SMART_LINK, Provenance.INFERRED, actor=actor
        )
        self._record_decision(
            source, target_id, None, STATUS_REJECTED, actor=actor, proposal=proposal
        )
        self._save(source)
        return LinkDecisionResult(
            target_id=str(target_id),
            target_type=target.object_type.value,
            target_title=target.title,
            kind="",
            status=STATUS_REJECTED,
        )

    # ------------------------------------------------------------- internals
    def _require_object(self, object_id: ObjectId) -> UniversalObject:
        obj = self._repository.get_by_id(object_id)
        if obj is None:
            raise ObjectNotFoundError(f"Object not found: {object_id}")
        return obj

    def _require_pending_proposal(
        self, source: UniversalObject, target_id: ObjectId
    ) -> dict:
        proposal = self._proposal_of(source, str(target_id))
        if not proposal or proposal.get("status") != STATUS_PENDING:
            raise ObjectAlreadyExistsError(
                f"No pending proposal for target {target_id}."
            )
        return proposal

    def _proposal_of(self, source: UniversalObject, target_id: str) -> dict:
        raw = source.metadata.get_value(proposal_key(target_id))
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _proposal_exists(self, source: UniversalObject, target_id: str) -> bool:
        if source.metadata.get_value(proposal_key(target_id)):
            return True
        if source.metadata.get_value(review_key(target_id)):
            return True
        return False

    def _already_linked(self, source: UniversalObject, target_id: ObjectId) -> bool:
        return any(rel.target == target_id for rel in source.relationships)

    def _can_read(self, obj: UniversalObject, principal: dict) -> bool:
        return self._permissions.can(
            principal=principal,
            scope=object_acl_scope(obj),
            action=PermissionAction.READ,
        )

    def _can_write(self, obj: UniversalObject, principal: dict) -> bool:
        return self._permissions.can(
            principal=principal,
            scope=object_acl_scope(obj),
            action=PermissionAction.WRITE,
        )

    def _evidence_for(
        self, source: UniversalObject, target: UniversalObject
    ) -> tuple[tuple[str, ...], list[tuple[str, str]]] | None:
        """Shared field-pair evidence between source and target metadata."""
        fields = FIELD_MAP.get((source.object_type, target.object_type))
        if not fields:
            return None
        source_meta = _meta(source)
        target_meta = _meta(target)
        evidence: list[str] = []
        matched: list[tuple[str, str]] = []
        for source_key, target_key in fields:
            source_value = source_meta.get(source_key)
            target_value = target_meta.get(target_key)
            if source_value is None or target_value is None:
                continue
            if not _evidence_matches(source_value, target_value):
                continue
            evidence.append(f"{source_key} matches {target_key} ({source_value!r})")
            matched.append((source_key, target_key))
        if not matched:
            return None
        return tuple(evidence), matched

    def _record_decision(
        self,
        source: UniversalObject,
        target_id: ObjectId,
        kind: RelationshipKind | None,
        status: str,
        *,
        actor: str,
        proposal: dict,
    ) -> None:
        target_str = str(target_id)
        source.set_metadata(
            MetadataEntry(
                proposal_key(target_str),
                json.dumps(
                    {
                        "kind": proposal.get("kind", ""),
                        "confidence": proposal.get("confidence", 0.0),
                        "evidence": proposal.get("evidence") or [],
                        "status": status,
                        "created_at": proposal.get("created_at", ""),
                        "reviewed_by": actor,
                        "reviewed_at": _utcnow_iso(),
                    },
                    ensure_ascii=False,
                ),
                MetadataLayer.L5_INFERRED,
                Provenance.INFERRED,
            ),
            actor=actor,
        )
        source.set_metadata(
            MetadataEntry(
                review_key(target_str),
                json.dumps(
                    {
                        "status": status,
                        "kind": kind.value if kind else "",
                        "reviewed_by": actor,
                        "reviewed_at": _utcnow_iso(),
                        "original_confidence": proposal.get("confidence", 0.0),
                    },
                    ensure_ascii=False,
                ),
                MetadataLayer.L6_HUMAN_ASSERTED,
                Provenance.ASSERTED,
            ),
            actor=actor,
        )

    def _save(self, source: UniversalObject) -> None:
        events = source.pop_domain_events()
        self._repository.save(
            source, outbox_events=[to_outbox_row(event) for event in events]
        )
