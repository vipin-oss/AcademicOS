"""REST routes for the Settings & Preferences module.

Mirrors ``routes/productivity.py`` one-to-one: thin request models
(extra=forbid), ``_unprocessable``/``_not_found`` mapping, and dual
PUT+PATCH decorators on every update endpoint (the events/productivity
precedent — the shared web client only has a PUT verb). Static paths are
declared before any parameterized ones (none here — all literal).

Surface:
    GET    /settings                         full document (defaults on first touch)
    PUT|PATCH /settings/{section}            profile | appearance | academic |
                                             notifications | dashboard | search |
                                             privacy | ai  (verbatim merge)
    POST   /settings/profile/photo           multipart upload (-> FileStorage port)
    GET    /settings/profile/photo           binary (404 when unset)
    DELETE /settings/profile/photo           remove (204)
    GET    /settings/export                  portable JSON (settings only)
    POST   /settings/import                  replace provided sections
    POST   /settings/reset                   factory defaults (all or listed sections)
"""
from __future__ import annotations

import mimetypes
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.mappers.settings_mapper import (
    output_dict,
    to_import_input,
    to_reset_input,
    to_section_update_input,
)
from app.application.commands.delete_profile_photo import DeleteProfilePhotoCommand
from app.application.commands.import_settings import ImportSettingsCommand
from app.application.commands.reset_settings import ResetSettingsCommand
from app.application.commands.set_profile_photo import SetProfilePhotoCommand
from app.application.commands.update_settings_section import UpdateSettingsSectionCommand
from app.application.dtos.settings import SetProfilePhotoInput
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.queries.get_profile_photo import GetProfilePhotoQuery
from app.application.queries.get_settings import GetSettingsQuery
from app.application.use_cases.settings.delete_profile_photo import DeleteProfilePhotoUseCase
from app.application.use_cases.settings.export_settings import ExportSettingsUseCase
from app.application.use_cases.settings.get_profile_photo import GetProfilePhotoUseCase
from app.application.use_cases.settings.get_settings import GetSettingsUseCase
from app.application.use_cases.settings.import_settings import ImportSettingsUseCase
from app.application.use_cases.settings.reset_settings import ResetSettingsUseCase
from app.application.use_cases.settings.set_profile_photo import SetProfilePhotoUseCase
from app.application.use_cases.settings.update_settings_section import (
    UpdateSettingsSectionUseCase,
)
from app.core.config import settings
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(prefix="/settings", tags=["Settings"], dependencies=[Depends(get_current_user)])


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def get_storage() -> LocalFileStorage:
    return LocalFileStorage(settings.storage_dir)


def _not_found(exc: ObjectNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


# ---------------------------------------------------------------------------
# Request models (extra=forbid, module doctrine)
# ---------------------------------------------------------------------------
class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileBody(StrictBody):
    name: str | None = None
    email: str | None = None
    designation: str | None = None
    department: str | None = None
    institution: str | None = None
    biography: str | None = None
    updated_by: str | None = None


class AppearanceBody(StrictBody):
    theme: str | None = None
    custom_theme: str | None = None
    updated_by: str | None = None


class AcademicBody(StrictBody):
    default_session: str | None = None
    default_department: str | None = None
    default_programme: str | None = None
    default_semester: str | None = None
    default_timezone: str | None = None
    date_format: str | None = None
    updated_by: str | None = None


class NotificationPrefsBody(StrictBody):
    enabled: bool | None = None
    reminder_default: str | None = None
    priority_default: str | None = None
    calendar_default_view: str | None = None
    calendar_default_sources: list[str] | None = None
    updated_by: str | None = None


class DashboardPrefsBody(StrictBody):
    default_landing_page: str | None = None
    favorite_modules: list[str] | None = None
    widget_visibility: dict[str, bool] | None = None
    default_view: str | None = None
    updated_by: str | None = None


class SearchPrefsBody(StrictBody):
    default_scope: str | None = None
    recent_searches_limit: int | None = None
    saved_filters: dict[str, Any] | None = None
    updated_by: str | None = None


class PrivacyBody(StrictBody):
    remember_last_module: bool | None = None
    reduce_motion: bool | None = None
    session_filter_memory: bool | None = None
    session_page_size: int | None = None
    updated_by: str | None = None


class AiPrefsBody(StrictBody):
    preferred_writing_style: str | None = None
    preferred_report_format: str | None = None
    preferred_dashboard_layout: str | None = None
    updated_by: str | None = None


class ImportBody(StrictBody):
    sections: dict[str, dict[str, Any]]
    updated_by: str | None = None


class ResetBody(StrictBody):
    sections: list[str] | None = None
    updated_by: str | None = None


SECTION_BODY_TYPES: dict[str, type[StrictBody]] = {
    "profile": ProfileBody,
    "appearance": AppearanceBody,
    "academic": AcademicBody,
    "notifications": NotificationPrefsBody,
    "dashboard": DashboardPrefsBody,
    "search": SearchPrefsBody,
    "privacy": PrivacyBody,
    "ai": AiPrefsBody,
}

# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------
@router.get("")
def get_settings_document(repo: SQLAlchemyObjectRepository = Depends(_repository)):
    out = GetSettingsUseCase(repo).execute(GetSettingsQuery())
    return output_dict(out)


def _update_section(
    section: str,
    body: StrictBody,
    repo: SQLAlchemyObjectRepository,
):
    try:
        out = UpdateSettingsSectionUseCase(repo).execute(
            UpdateSettingsSectionCommand(
                input=to_section_update_input(section, body.model_dump())
            )
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.put("/profile")
@router.patch("/profile")
def update_profile(body: ProfileBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return _update_section("profile", body, repo)


@router.put("/appearance")
@router.patch("/appearance")
def update_appearance(body: AppearanceBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return _update_section("appearance", body, repo)


@router.put("/academic")
@router.patch("/academic")
def update_academic(body: AcademicBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return _update_section("academic", body, repo)


@router.put("/notifications")
@router.patch("/notifications")
def update_notification_prefs(body: NotificationPrefsBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return _update_section("notifications", body, repo)


@router.put("/dashboard")
@router.patch("/dashboard")
def update_dashboard_prefs(body: DashboardPrefsBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return _update_section("dashboard", body, repo)


@router.put("/search")
@router.patch("/search")
def update_search_prefs(body: SearchPrefsBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return _update_section("search", body, repo)


@router.put("/privacy")
@router.patch("/privacy")
def update_privacy(body: PrivacyBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return _update_section("privacy", body, repo)


@router.put("/ai")
@router.patch("/ai")
def update_ai_prefs(body: AiPrefsBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    return _update_section("ai", body, repo)


# ---------------------------------------------------------------------------
# Profile photo (FileStorage port — local adapter first)
# ---------------------------------------------------------------------------
@router.post("/profile/photo", status_code=status.HTTP_201_CREATED)
def upload_profile_photo(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    *,
    file: UploadFile = File(...),
):
    content = file.file.read()
    file_name = file.filename or "profile-photo"
    mime_type = (
        file.content_type
        or mimetypes.guess_type(file_name)[0]
        or "application/octet-stream"
    )
    try:
        out = SetProfilePhotoUseCase(repo, storage).execute(
            SetProfilePhotoCommand(
                input=SetProfilePhotoInput(
                    file_name=file_name,
                    content=content,
                    mime_type=mime_type,
                )
            )
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.get("/profile/photo")
def get_profile_photo(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
):
    try:
        out = GetProfilePhotoUseCase(repo, storage).execute(GetProfilePhotoQuery())
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return Response(
        content=out.content,
        media_type=out.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{out.file_name}"',
            "Cache-Control": "private, max-age=60",
        },
    )


@router.delete("/profile/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile_photo(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
):
    DeleteProfilePhotoUseCase(repo, storage).execute(DeleteProfilePhotoCommand())


# ---------------------------------------------------------------------------
# Backup & restore (settings only — NOT a database backup)
# ---------------------------------------------------------------------------
@router.get("/export")
def export_settings(repo: SQLAlchemyObjectRepository = Depends(_repository)):
    out = ExportSettingsUseCase(repo).execute(GetSettingsQuery())
    return output_dict(out)


@router.post("/import")
def import_settings(body: ImportBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        out = ImportSettingsUseCase(repo).execute(
            ImportSettingsCommand(input=to_import_input(body.model_dump()))
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.post("/reset")
def reset_settings(body: ResetBody, repo: SQLAlchemyObjectRepository = Depends(_repository)):
    try:
        out = ResetSettingsUseCase(repo).execute(
            ResetSettingsCommand(input=to_reset_input(body.model_dump()))
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)
