"""Unit tests for the Auth use cases (Sprint-1 authentication foundation).

Uses the real BcryptPasswordHasher and JwtTokenService (infrastructure
adapters) so the tests exercise the actual credential and token paths —
no fakes in the security-critical slice.
"""
from __future__ import annotations

import pytest

from app.application.commands.login_user import LoginUserCommand
from app.application.commands.refresh_tokens import RefreshTokensCommand
from app.application.commands.register_user import RegisterUserCommand
from app.application.dtos.auth import LoginInput, RefreshInput, RegisterUserInput
from app.application.exceptions import (
    AuthenticationError,
    ObjectAlreadyExistsError,
    ValidationError,
)
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.refresh_tokens import RefreshTokensUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.auth.jwt_service import JwtTokenService
from app.infrastructure.auth.passwords import BcryptPasswordHasher


class InMemoryObjectRepository(ObjectRepository):
    """Test double implementing the abstract port (auth slice)."""

    def __init__(self) -> None:
        self._store: dict[ObjectId, UniversalObject] = {}

    def save(self, entity: UniversalObject) -> None:
        self._store[entity.id] = entity

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(id)

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[i] for i in ids if i in self._store]

    def exists(self, id: ObjectId) -> bool:
        return id in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(id, None)

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_by_metadata(
        self, key: str, value: str | None = None
    ) -> list[UniversalObject]:
        out: list[UniversalObject] = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
        return out

    def find_related(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        obj = self._store.get(object_id)
        if obj is None:
            return []
        return obj.related_ids(kind)

    def find(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
        page: int = 1,
        page_size: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> list[UniversalObject]:
        return self.find_by_type(object_type) if object_type is not None else self.list()

    def count(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> int:
        return len(
            self.find(
                object_type=object_type,
                status=status,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
            )
        )


@pytest.fixture()
def world():
    repo = InMemoryObjectRepository()
    hasher = BcryptPasswordHasher()
    tokens = JwtTokenService()
    return {
        "repo": repo,
        "hasher": hasher,
        "tokens": tokens,
        "register": RegisterUserUseCase(repo, hasher),
        "login": LoginUserUseCase(repo, tokens, hasher),
        "refresh": RefreshTokensUseCase(repo, tokens),
    }


def _register(world, username="dr.ananya", password="correct-horse-battery"):
    return world["register"].execute(
        RegisterUserCommand(input=RegisterUserInput(username=username, password=password))
    )


def test_register_creates_user_with_hashed_credential(world):
    out = _register(world)
    assert out.username == "dr.ananya"
    assert out.id.startswith("obj:user:")

    obj = world["repo"].get_by_id(ObjectId(out.id))
    assert obj is not None
    assert obj.object_type is ObjectType.USER
    assert obj.status is ObjectStatus.ACTIVE
    stored = obj.metadata.get_value("auth.password_hash")
    assert stored is not None and stored != "correct-horse-battery"
    assert world["hasher"].verify_password("correct-horse-battery", stored) is True


def test_register_duplicate_username_raises(world):
    _register(world)
    with pytest.raises(ObjectAlreadyExistsError):
        _register(world, username="dr.ananya", password="another-password")


def test_register_validation_errors(world):
    # Whitespace-only and over-long usernames are rejected; passwords must
    # be at least 8 characters and at most 72 bytes (bcrypt's hard cap).
    with pytest.raises(ValidationError):
        _register(world, username="   ", password="x" * 8)
    with pytest.raises(ValidationError):
        _register(world, username="x" * 65, password="x" * 8)
    with pytest.raises(ValidationError):
        _register(world, username="dr.ananya", password="short")
    with pytest.raises(ValidationError):
        _register(world, username="dr.ananya", password="x" * 80)


def test_login_issues_tokens_for_valid_credentials(world):
    _register(world)
    out = world["login"].execute(
        LoginUserCommand(input=LoginInput(username="dr.ananya", password="correct-horse-battery"))
    )
    assert out.access_token and out.refresh_token and out.token_type == "bearer"
    claims = world["tokens"].decode_token(out.access_token)
    assert claims["sub"] == world["repo"].list()[0].id.value
    assert claims["type"] == "access"
    refresh_claims = world["tokens"].decode_token(out.refresh_token)
    assert refresh_claims["type"] == "refresh"


def test_login_wrong_password_and_unknown_user_same_error(world):
    _register(world)
    for username, password in (("dr.ananya", "wrong-password"), ("ghost", "correct-horse-battery")):
        with pytest.raises(AuthenticationError) as exc_info:
            world["login"].execute(
                LoginUserCommand(input=LoginInput(username=username, password=password))
            )
        assert str(exc_info.value) == "Invalid username or password."


def test_refresh_issues_fresh_pair(world):
    _register(world)
    login = world["login"].execute(
        LoginUserCommand(input=LoginInput(username="dr.ananya", password="correct-horse-battery"))
    )
    out = world["refresh"].execute(
        RefreshTokensCommand(input=RefreshInput(refresh_token=login.refresh_token))
    )
    assert out.access_token and out.refresh_token
    assert world["tokens"].decode_token(out.access_token)["type"] == "access"


def test_refresh_rejects_access_token(world):
    _register(world)
    login = world["login"].execute(
        LoginUserCommand(input=LoginInput(username="dr.ananya", password="correct-horse-battery"))
    )
    with pytest.raises(AuthenticationError):
        world["refresh"].execute(
            RefreshTokensCommand(input=RefreshInput(refresh_token=login.access_token))
        )


def test_refresh_rejects_garbage_and_deleted_account(world):
    _register(world)
    with pytest.raises(AuthenticationError):
        world["refresh"].execute(
            RefreshTokensCommand(input=RefreshInput(refresh_token="not-a-token"))
        )

    login = world["login"].execute(
        LoginUserCommand(input=LoginInput(username="dr.ananya", password="correct-horse-battery"))
    )
    user = world["repo"].list()[0]
    world["repo"].delete(user.id)
    with pytest.raises(AuthenticationError):
        world["refresh"].execute(
            RefreshTokensCommand(input=RefreshInput(refresh_token=login.refresh_token))
        )


# ------------------------------------------------------------ config guard
# The default JWT secret must never run outside development/test.


def test_default_jwt_secret_rejected_outside_development(monkeypatch):
    import app.core.config as config_module

    # Stale cached settings must not leak across tests.
    config_module.get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValueError, match="JWT_SECRET"):
        config_module.Settings()
    config_module.get_settings.cache_clear()


def test_default_jwt_secret_accepted_in_development(monkeypatch):
    import app.core.config as config_module

    config_module.get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    assert config_module.Settings().jwt_secret == "change-me-in-production"
    config_module.get_settings.cache_clear()
