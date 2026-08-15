"""V3 M16 normalization-wave framework tests (ADR-063)."""

from __future__ import annotations

import pytest

from app.application.services.normalization import (
    NormalizationRunner,
    WaveValidationError,
)
from app.application.services.user_state_wave import UserStateWave, profile_from_object
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.user_profile_model import UserProfileModel  # noqa: F401


class _InMemoryProfileStore:
    def __init__(self):
        self._rows = {}

    def upsert(self, profile):
        self._rows[profile.user_id] = profile
        return profile

    def get(self, user_id):
        return self._rows.get(user_id)

    def list(self):
        return list(self._rows.values())

    def clear(self):
        self._rows.clear()


def _user(obj_id="obj:user:1", title="alice"):
    return UniversalObject.create(
        ObjectType.USER, title, created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId(obj_id),
    )


class _Repo:
    def __init__(self, users):
        self._users = users

    def find(self, **kwargs):
        return list(self._users)


def test_profile_derived_from_object():
    user = _user()
    profile = profile_from_object(user)
    assert profile.user_id == "obj:user:1"
    assert profile.username == "alice"
    assert profile.roles == "[]"


def test_runner_executes_phases_in_order():
    calls = []

    class _Wave:
        wave_id = "t"

        def expand(self):
            calls.append("expand")

        def backfill(self):
            calls.append("backfill")
            return 1

        def validate(self):
            calls.append("validate")
            return []

        def switch_reads(self):
            calls.append("switch_reads")

        def switch_writes(self):
            calls.append("switch_writes")

        def rollback(self):
            calls.append("rollback")

    NormalizationRunner([_Wave()]).run("t")
    assert calls == ["expand", "backfill", "validate", "switch_reads", "switch_writes"]


def test_runner_rolls_back_on_validation_failure():
    class _BadWave:
        wave_id = "bad"

        def expand(self):
            return None

        def backfill(self):
            return 0

        def validate(self):
            return ["integrity violation"]

        def switch_reads(self):
            raise AssertionError("must not switch on failure")

        def switch_writes(self):
            raise AssertionError("must not switch on failure")

        def rollback(self):
            self.rolled_back = True

    wave = _BadWave()
    with pytest.raises(WaveValidationError):
        NormalizationRunner([wave]).run("bad")
    assert wave.rolled_back is True


def test_user_state_wave_end_to_end():
    repo = _Repo([_user("obj:user:1", "alice"), _user("obj:user:2", "bob")])
    store = _InMemoryProfileStore()
    wave = UserStateWave(repo, store)
    runner = NormalizationRunner([wave])

    report = runner.run("user_state")
    assert report.rolled_back is False
    assert len(store.list()) == 2
    assert store.get("obj:user:1").username == "alice"

    # reversible
    runner.rollback("user_state")
    assert store.list() == []
