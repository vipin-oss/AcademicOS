"""REST routes for authentication (Sprint-1 authentication foundation).

Surface:
    POST   /auth/register   create a user account (201; 409 duplicate)
    POST   /auth/login      verify credentials -> access + refresh tokens
    POST   /auth/refresh    exchange a refresh token for a fresh pair
    GET    /auth/me         the authenticated user (401 without a valid
                            access token) — the protected-endpoint proof
                            for this milestone.

Scope guard: authentication only. Roles/authorisation/permission
enforcement are later Sprint-1 milestones; existing routes remain
unprotected until then.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_permission
from app.api.dependencies.db import get_db
from app.api.mappers.auth_mapper import (
    to_login_input,
    to_refresh_input,
    to_register_input,
    to_tokens_response,
    to_user_response,
)
from app.application.commands.assign_roles import AssignRolesCommand
from app.application.commands.login_user import LoginUserCommand
from app.application.commands.refresh_tokens import RefreshTokensCommand
from app.application.commands.register_user import RegisterUserCommand
from app.application.dtos.auth import AssignRolesInput
from app.application.exceptions import (
    AuthenticationError,
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.token_service import TokenService
from app.application.use_cases.auth.assign_roles import AssignRolesUseCase
from app.application.use_cases.auth.helpers import user_output
from app.application.use_cases.auth.list_users import ListUsersUseCase
from app.application.use_cases.auth.login_user import LoginUserUseCase
from app.application.use_cases.auth.refresh_tokens import RefreshTokensUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import PermissionAction
from app.infrastructure.auth.jwt_service import JwtTokenService
from app.infrastructure.auth.passwords import BcryptPasswordHasher
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    created_at: str
    roles: list[str] = []


def _token_service() -> TokenService:
    return JwtTokenService()


def _password_hasher() -> PasswordHasher:
    return BcryptPasswordHasher()


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    body: RegisterRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    hasher: PasswordHasher = Depends(_password_hasher),
) -> UserResponse:
    try:
        out = RegisterUserUseCase(repo, hasher).execute(
            RegisterUserCommand(
                input=to_register_input(username=body.username, password=body.password)
            )
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserResponse(**to_user_response(out))


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    tokens: TokenService = Depends(_token_service),
    hasher: PasswordHasher = Depends(_password_hasher),
) -> TokenResponse:
    try:
        out = LoginUserUseCase(repo, tokens, hasher).execute(
            LoginUserCommand(input=to_login_input(username=body.username, password=body.password))
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenResponse(**to_tokens_response(out))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    tokens: TokenService = Depends(_token_service),
) -> TokenResponse:
    try:
        out = RefreshTokensUseCase(repo, tokens).execute(
            RefreshTokensCommand(input=to_refresh_input(refresh_token=body.refresh_token))
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenResponse(**to_tokens_response(out))


@router.get("/me", response_model=UserResponse)
def me(user: UniversalObject = Depends(get_current_user)) -> UserResponse:
    return UserResponse(**to_user_response(user_output(user)))


class AssignRolesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[str] = []


@router.get("/users", response_model=list[UserResponse])
def list_users(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    _admin: UniversalObject = Depends(require_permission(PermissionAction.MANAGE)),
) -> list[UserResponse]:
    users = ListUsersUseCase(repo).execute()
    return [UserResponse(**to_user_response(u)) for u in users]


@router.put("/users/{user_id}/roles", response_model=UserResponse)
def assign_user_roles(
    user_id: str,
    body: AssignRolesRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    _admin: UniversalObject = Depends(require_permission(PermissionAction.MANAGE)),
) -> UserResponse:
    try:
        out = AssignRolesUseCase(repo).execute(
            AssignRolesCommand(input=AssignRolesInput(user_id=user_id, roles=body.roles))
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UserResponse(**to_user_response(out))
