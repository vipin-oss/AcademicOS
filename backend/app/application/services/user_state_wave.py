"""Normalization wave 1: user_state (V3 M16, ADR-063).

Projects the user object's hot fields (username/display-name/roles/institution)
into the typed ``user_profiles`` table. EXPAND→BACKFILL→VALIDATE→SWITCH READS
→SWITCH WRITES; independently reversible (rollback clears the projection and
reads fall back to the object store).
"""

from __future__ import annotations

import json

from app.application.ports.user_profile_store import UserProfile, UserProfileStore
from app.application.services.normalization import NormalizationWave
from app.application.use_cases.auth.helpers import get_roles
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def profile_from_object(user: UniversalObject) -> UserProfile:
    """Derive a projection row from the authoritative USER object."""
    institution = ""
    raw = user.metadata.get_value("institution") if user.metadata else None
    if raw:
        institution = str(raw)
    return UserProfile(
        user_id=str(user.id),
        username=user.title.strip() or str(user.id),
        display_name=user.title.strip() or str(user.id),
        roles=json.dumps(get_roles(user)),
        institution=institution or None,
    )


class UserStateWave(NormalizationWave):
    """Wave 1: normalize user state into ``user_profiles``."""

    wave_id = "user_state"

    def __init__(
        self,
        objects: ObjectRepository,
        profiles: UserProfileStore,
    ) -> None:
        self._objects = objects
        self._profiles = profiles

    def expand(self) -> None:
        # schema already created by migration 0023; nothing to do at runtime.
        return None

    def backfill(self) -> int:
        users = list(self._objects.find(object_type=ObjectType.USER))
        for user in users:
            self._profiles.upsert(profile_from_object(user))
        return len(users)

    def validate(self) -> list[str]:
        violations: list[str] = []
        for profile in self._profiles.list():
            if not profile.username:
                violations.append(f"{profile.user_id}: empty username")
            if not profile.display_name:
                violations.append(f"{profile.user_id}: empty display_name")
        return violations

    def switch_reads(self) -> None:
        # Reads now consult the projection first (the admin/list-users path);
        # the store's get() returns None on miss so callers fall back.
        return None

    def switch_writes(self) -> None:
        # Writes continue to the USER object; this wave re-backfills on change.
        return None

    def rollback(self) -> None:
        self._profiles.clear()


__all__ = ["UserProfile", "UserStateWave", "profile_from_object"]
