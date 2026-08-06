"""Use case: search objects through the persistent search projection (Sprint-5 M1).

Coordination only — the index is queried through the ``SearchRepository``
port, then every candidate is authorized through the R4
``PermissionEvaluator`` port before anything is returned: unauthorized
items never leak, and the search index itself never becomes the source of
truth (objects remain authoritative — the use case re-loads candidates from
the ``ObjectRepository`` to evaluate their ACL).

Search behaviour is limited to the roadmap-approved surface: exact object
type, exact (case-insensitive) title, and literal-substring full-text over
title + metadata text. No ranking — deterministic ``object_id`` order.
"""
from __future__ import annotations

from app.application.exceptions import ValidationError
from app.application.ports.permission import PermissionEvaluator
from app.application.use_cases.auth.helpers import get_roles
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.repositories.search_repository import SearchRepository
from app.domain.value_objects.enums import PermissionAction
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.search import SearchDocument


class SearchObjectsUseCase:
    def __init__(
        self,
        search_repository: SearchRepository,
        object_repository: ObjectRepository,
        permission_evaluator: PermissionEvaluator,
    ) -> None:
        self._search_repository = search_repository
        self._object_repository = object_repository
        self._permission_evaluator = permission_evaluator

    def execute(
        self,
        *,
        user: UniversalObject,
        text: str | None = None,
        object_type: str | None = None,
        title: str | None = None,
        limit: int = 50,
    ) -> list[SearchDocument]:
        text = text.strip() if text else None
        title = title.strip() if title else None
        object_type = object_type.strip() if object_type else None
        if text is None and title is None and object_type is None:
            raise ValidationError("At least one search criterion is required.")

        candidates = self._search_repository.search(
            text=text, object_type=object_type, title=title, limit=limit
        )
        if not candidates:
            return []

        # Authorize the candidate set through the R4 seam before returning
        # anything: the index is derived data, the object is the authority.
        objects = self._object_repository.find_by_ids(
            [ObjectId(doc.object_id) for doc in candidates]
        )
        by_id = {str(obj.id): obj for obj in objects}
        principal = {"sub": str(user.id), "roles": get_roles(user)}
        allowed: list[SearchDocument] = []
        for candidate in candidates:
            obj = by_id.get(candidate.object_id)
            if obj is None:
                # Index row for an object that no longer exists: never leak.
                continue
            if self._permission_evaluator.can(
                principal=principal,
                scope=object_acl_scope(obj),
                action=PermissionAction.READ,
            ):
                allowed.append(candidate)
        return allowed
