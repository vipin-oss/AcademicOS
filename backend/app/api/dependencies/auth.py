"""Authentication dependencies for the API layer (Sprint-1 foundation).

- ``get_current_principal``: extracts and verifies the bearer JWT, returns
  the decoded claims (kept for the JWT-decode-only contract).
- ``get_current_user``: the authenticated USER object — verifies the token,
  requires an access token (refresh tokens are never accepted here), loads
  the account, and 401s when the account no longer exists. Future
  Sprint-1 milestones protect routes with this dependency.
"""
from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.dependencies.db import get_db
from app.application.use_cases.auth.helpers import get_roles
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectType, PermissionAction
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.auth.jwt import decode_token
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.permissions.role_based import RoleBasedPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token")
    try:
        return decode_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001 - normalise to domain error
        raise UnauthorizedError("Invalid or expired token") from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """The authenticated USER object, or 401."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token")
    try:
        claims = decode_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001 - normalise to domain error
        raise UnauthorizedError("Invalid or expired token") from exc

    if claims.get("type") != "access":
        # A refresh token must never satisfy a protected endpoint.
        raise UnauthorizedError("Invalid or expired token")

    subject = claims.get("sub")
    if subject is None:
        # A token signed without a subject is malformed — never a 500.
        raise UnauthorizedError("Invalid or expired token")

    repo = SQLAlchemyObjectRepository(db)
    user = repo.get_by_id(ObjectId(subject))
    if user is None or user.object_type is not ObjectType.USER:
        # The account no longer exists — the token is dead.
        raise UnauthorizedError("Invalid or expired token")
    return user


def require_permission(action: PermissionAction):
    """Dependency factory: 403 unless the authenticated user's roles allow
    ``action`` (Sprint-1 M3 — the single RBAC enforcement seam).

    Usage: ``dependencies=[Depends(require_permission(PermissionAction.MANAGE))]``
    on a router or endpoint. The principal is built from the live USER
    object (roles can never be forged via the token), and the decision
    goes through the R4 ``PermissionEvaluator`` port.
    """

    def _check(user: UniversalObject = Depends(get_current_user)) -> UniversalObject:
        evaluator = RoleBasedPermissionEvaluator()
        principal = {"sub": str(user.id), "roles": get_roles(user)}
        if not evaluator.can(principal=principal, scope=None, action=action):
            raise ForbiddenError(f"Missing permission: {action.value}")
        return user

    return _check


def require_object_access(action: PermissionAction):
    """Dependency factory: object-level ACL enforcement (Sprint-2 M1).

    Reads the object id from the request path (any ``*_id`` path param
    whose value is an object id), loads the object, and evaluates the
    requested action through the R4 ``PermissionEvaluator`` port against
    the object's ACL. 403 on denial; no-op on routes without an object id
    (create/list). One shared factory — no per-route ACL logic.
    """

    def _check(
        request: Request,
        user: UniversalObject = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> UniversalObject | None:
        object_id = _path_object_id(request)
        if object_id is None:
            return None  # no object id in this route (create/list)
        repo = SQLAlchemyObjectRepository(db)
        obj = repo.get_by_id(ObjectId(object_id))
        if obj is None:
            return None  # the handler maps missing to 404
        principal = {"sub": str(user.id), "roles": get_roles(user)}
        evaluator = ObjectPermissionEvaluator()
        scope = _object_acl_scope(obj)
        if not evaluator.can(principal=principal, scope=scope, action=action):
            raise ForbiddenError(f"Missing permission: {action.value}")
        return obj

    return _check


def _path_object_id(request: Request) -> str | None:
    """The value of the first ``*_id`` path param that looks like an ObjectId."""
    for name, value in request.path_params.items():
        if name.endswith("_id") and isinstance(value, str) and value.startswith("obj:"):
            return value
    return None


def _object_acl_scope(obj: UniversalObject) -> str | None:
    import json as _json

    from app.application.dtos.object import (
        ACL_MANAGERS,
        ACL_READERS,
        ACL_WRITERS,
    )

    def _list(key: str) -> list[str]:
        raw = obj.metadata.get_value(key)
        if not raw:
            return []
        try:
            parsed = _json.loads(raw)
        except (ValueError, TypeError):
            return []
        return [str(e) for e in parsed if isinstance(e, str)]

    return _json.dumps(
        {
            "owner": obj.audit.created_by if obj.audit else "",
            "readers": _list(ACL_READERS),
            "writers": _list(ACL_WRITERS),
            "managers": _list(ACL_MANAGERS),
        }
    )
