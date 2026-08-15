"""SQL implementation of the user-profile projection store (V3 M16, ADR-063)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.ports.user_profile_store import UserProfile, UserProfileStore
from app.infrastructure.db.models.user_profile_model import UserProfileModel


class SQLUserProfileStore(UserProfileStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, profile: UserProfile) -> UserProfile:
        existing = self._session.execute(
            select(UserProfileModel).where(UserProfileModel.user_id == profile.user_id)
        ).scalars().first()
        if existing is None:
            self._session.add(
                UserProfileModel(
                    user_id=profile.user_id,
                    username=profile.username,
                    display_name=profile.display_name,
                    roles=profile.roles,
                    institution=profile.institution,
                )
            )
        else:
            existing.username = profile.username
            existing.display_name = profile.display_name
            existing.roles = profile.roles
            existing.institution = profile.institution
        return profile

    def get(self, user_id: str) -> UserProfile | None:
        row = self._session.execute(
            select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        ).scalars().first()
        return _from_model(row) if row else None

    def list(self) -> list[UserProfile]:
        rows = self._session.execute(
            select(UserProfileModel).order_by(UserProfileModel.username)
        ).scalars().all()
        return [_from_model(r) for r in rows]

    def clear(self) -> None:
        self._session.execute(delete(UserProfileModel))


def _from_model(row: UserProfileModel) -> UserProfile:
    return UserProfile(
        user_id=row.user_id,
        username=row.username,
        display_name=row.display_name,
        roles=row.roles,
        institution=row.institution,
    )
