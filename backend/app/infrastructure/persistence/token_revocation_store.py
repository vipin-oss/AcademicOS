"""SQL implementation of the token-revocation denylist (V3 M9, ADR-056)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.ports.token_revocation_store import TokenRevocationStore
from app.infrastructure.db.models.session_revocation_model import SessionRevocationModel


class SQLTokenRevocationStore(TokenRevocationStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, jti: str, expires_at: str) -> None:
        existing = self._session.execute(
            select(SessionRevocationModel).where(SessionRevocationModel.jti == jti)
        ).scalars().first()
        if existing is not None:
            return  # idempotent
        self._session.add(SessionRevocationModel(jti=jti, expires_at=expires_at))

    def is_revoked(self, jti: str, *, now: str) -> bool:
        row = self._session.execute(
            select(SessionRevocationModel).where(SessionRevocationModel.jti == jti)
        ).scalars().first()
        if row is None:
            return False
        # A revocation past the token's absolute expiry is treated as expired
        # (the token is already dead by its own exp).
        return row.expires_at > now

    def prune(self, *, now: str) -> int:
        result = self._session.execute(
            delete(SessionRevocationModel).where(SessionRevocationModel.expires_at <= now)
        )
        return result.rowcount or 0
