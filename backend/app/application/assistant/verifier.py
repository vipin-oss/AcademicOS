"""Answer verification — the anti-hallucination gate (Sprint-6 M3 Phase 5).

After the provider responds, every citation is checked against the
AUTHORITATIVE store before it is attached to the answer:

1. **exists** — the cited object must still be present (a deletion between
   retrieval and verification drops the citation);
2. **READ permission** — the asker must still be able to read the object
   (an ACL change between retrieval and verification drops it — hidden
   objects are never leaked through a stale citation);
3. **valid ids** — malformed object ids are dropped;
4. **duplicates removed** — one citation per object_id (first kept).

Survivors are renumbered 1..k contiguously, preserving their relative
order, so numbering stays deterministic for the same repository state.

Uses ONLY the existing R4 ``PermissionEvaluator`` port + ``object_acl_scope``
helper — no duplicated permission logic. Application-pure.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.application.dtos.assistant import AssistantCitation
from app.application.ports.permission import PermissionEvaluator
from app.application.use_cases.auth.helpers import get_roles
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import PermissionAction
from app.domain.value_objects.object_id import ObjectId


class AnswerVerifier:
    """Validates a citation set against the authoritative store."""

    def __init__(self, permission_evaluator: PermissionEvaluator) -> None:
        self._evaluator = permission_evaluator

    def verify(
        self,
        citations: Sequence[AssistantCitation],
        repository: ObjectRepository,
        user: UniversalObject,
    ) -> tuple[AssistantCitation, ...]:
        """The citations that remain valid, renumbered 1..k in order."""
        principal = {"sub": str(user.id), "roles": get_roles(user)}
        seen: set[str] = set()
        kept: list[AssistantCitation] = []
        for citation in citations:
            if citation.object_id in seen:
                continue  # duplicate removal
            seen.add(citation.object_id)
            obj = self._load(repository, citation.object_id)
            if obj is None:
                continue  # deleted or malformed id
            if not self._evaluator.can(
                principal=principal,
                scope=object_acl_scope(obj),
                action=PermissionAction.READ,
            ):
                continue  # hidden object — never leak via a stale citation
            kept.append(citation)
        return tuple(
            replace(citation, number=index)
            for index, citation in enumerate(kept, start=1)
        )

    @staticmethod
    def _load(repository: ObjectRepository, object_id: str) -> UniversalObject | None:
        try:
            return repository.get_by_id(ObjectId.parse(object_id))
        except ValueError:
            return None
