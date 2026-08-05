"""Unit tests for the Settings & Preferences use cases (no framework deps).

Mirrors ``test_productivity_use_cases.py``: an in-memory ``ObjectRepository``
plus an in-memory ``FileStorage`` stub exercise the whole module surface —
document bootstrap, per-section verbatim merge, validation, backup
(export/import/reset), and the profile-photo lifecycle.
"""
from __future__ import annotations

import pytest

from app.application.commands.delete_profile_photo import DeleteProfilePhotoCommand
from app.application.commands.import_settings import ImportSettingsCommand
from app.application.commands.reset_settings import ResetSettingsCommand
from app.application.commands.set_profile_photo import SetProfilePhotoCommand
from app.application.commands.update_settings_section import UpdateSettingsSectionCommand
from app.application.dtos.settings import (
    ImportSettingsInput,
    ResetSettingsInput,
    SectionUpdateInput,
    SetProfilePhotoInput,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.file_storage import FileStorage
from app.application.queries.get_profile_photo import GetProfilePhotoQuery
from app.application.queries.get_settings import GetSettingsQuery
from app.application.use_cases.settings.delete_profile_photo import DeleteProfilePhotoUseCase
from app.application.use_cases.settings.export_settings import ExportSettingsUseCase
from app.application.use_cases.settings.get_profile_photo import GetProfilePhotoUseCase
from app.application.use_cases.settings.get_settings import GetSettingsUseCase
from app.application.use_cases.settings.import_settings import ImportSettingsUseCase
from app.application.use_cases.settings.reset_settings import ResetSettingsUseCase
from app.application.use_cases.settings.set_profile_photo import SetProfilePhotoUseCase
from app.application.use_cases.settings.update_settings_section import UpdateSettingsSectionUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class InMemoryObjectRepository(ObjectRepository):
    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}

    def save(self, entity: UniversalObject) -> None:
        self._store[str(entity.id)] = entity

    def get_by_id(self, id) -> UniversalObject | None:
        return self._store.get(str(id))

    def find_by_ids(self, ids: list) -> list[UniversalObject]:
        return [self._store[str(i)] for i in ids if str(i) in self._store]

    def exists(self, id) -> bool:
        return str(id) in self._store

    def delete(self, id) -> None:
        self._store.pop(str(id), None)

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status) -> list[UniversalObject]:
        return []

    def find_by_metadata(self, key: str, value) -> list[UniversalObject]:
        return []

    def find_related(self, id, *, relation_type=None, direction="outgoing") -> list:
        return []
    def find(
        self,
        *,
        object_type=None,
        status=None,
        metadata_key=None,
        metadata_value=None,
        page: int = 1,
        page_size: int = 0,
        sort_by: str = "id",
        order: str = "asc",
    ) -> list[UniversalObject]:
        return []

    def count(
        self,
        *,
        object_type=None,
        status=None,
        metadata_key=None,
        metadata_value=None,
    ) -> int:
        return 0



class InMemoryStorage(FileStorage):
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def save(self, key: str, content: bytes) -> None:
        self.blobs[key] = content

    def read(self, key: str) -> bytes:
        if key not in self.blobs:
            raise FileNotFoundError(key)
        return self.blobs[key]

    def exists(self, key: str) -> bool:
        return key in self.blobs

    def delete(self, key: str) -> None:
        self.blobs.pop(key, None)


@pytest.fixture()
def repo() -> InMemoryObjectRepository:
    return InMemoryObjectRepository()


@pytest.fixture()
def storage() -> InMemoryStorage:
    return InMemoryStorage()


def get(repo) -> object:
    return GetSettingsUseCase(repo).execute(GetSettingsQuery())


def put(repo, section: str, values: dict) -> object:
    return UpdateSettingsSectionUseCase(repo).execute(
        UpdateSettingsSectionCommand(input=SectionUpdateInput(section=section, values=values))
    )


# ---------------------------------------------------------------- bootstrap
def test_first_touch_bootstraps_singleton_with_factory_defaults(repo):
    out = get(repo)
    assert out.sections["appearance"]["theme"] == "system"
    assert out.sections["notifications"]["enabled"] is True
    assert out.sections["search"]["recent_searches_limit"] == 10
    assert out.sections["dashboard"]["default_landing_page"] == "/"
    assert out.has_photo is False
    assert repo.find_by_type(ObjectType.SETTINGS).__len__() == 1
    # idempotent: a second read must not create a second object
    get(repo)
    assert len(repo.find_by_type(ObjectType.SETTINGS)) == 1
    # defaults materialise only on write — the object starts minimal
    obj = repo.find_by_type(ObjectType.SETTINGS)[0]
    keys = {entry.key for entry in obj.metadata.entries}
    assert keys == {"settings.scope"}


# -------------------------------------------------------------- section CRUD
def test_profile_update_merge_and_clear(repo):
    put(repo, "profile", {"name": "Dr. N. Rao", "email": "rao@univ.edu", "designation": "Professor"})
    out = put(repo, "profile", {"department": "Mathematics"})
    assert out.values["name"] == "Dr. N. Rao"  # merge: untouched keys survive
    assert out.values["department"] == "Mathematics"
    cleared = put(repo, "profile", {"email": ""}).values
    assert cleared["email"] == ""  # explicit empty clears
    assert get(repo).sections["profile"]["biography"] == ""  # default


def test_appearance_theme_validation(repo):
    assert put(repo, "appearance", {"theme": "dark"}).values["theme"] == "dark"
    with pytest.raises(ValidationError):
        put(repo, "appearance", {"theme": "midnight"})
    with pytest.raises(ValidationError):
        put(repo, "appearance", {"unknown_key": "x"})


def test_email_format_validation(repo):
    with pytest.raises(ValidationError):
        put(repo, "profile", {"email": "not-an-email"})
    assert put(repo, "profile", {"email": "a.b@univ.ac.in"}).values["email"] == "a.b@univ.ac.in"


def test_academic_defaults_and_date_format(repo):
    out = put(repo, "academic", {"default_programme": "MSc Mathematics", "date_format": "dd/mm/yyyy"})
    assert out.values["default_programme"] == "MSc Mathematics"
    assert out.values["date_format"] == "dd/mm/yyyy"
    with pytest.raises(ValidationError):
        put(repo, "academic", {"date_format": "31/12/2026"})


def test_notification_preferences_and_sources(repo):
    out = put(repo, "notifications", {
        "enabled": False,
        "reminder_default": "one_week_before",
        "priority_default": "high",
        "calendar_default_view": "agenda",
        "calendar_default_sources": ["events", "teaching"],
    })
    assert out.values["enabled"] is False
    assert out.values["calendar_default_sources"] == ["events", "teaching"]
    with pytest.raises(ValidationError):
        put(repo, "notifications", {"calendar_default_sources": ["telegram"]})
    with pytest.raises(ValidationError):
        put(repo, "notifications", {"priority_default": "urgent"})


def test_dashboard_preferences(repo):
    out = put(repo, "dashboard", {
        "default_landing_page": "productivity",
        "favorite_modules": ["productivity", "reports"],
        "widget_visibility": {"calendar": True, "tasks": False},
        "default_view": "compact",
    })
    assert out.values["default_landing_page"] == "/productivity"  # normalised
    assert out.values["favorite_modules"] == ["productivity", "reports"]
    assert out.values["widget_visibility"] == {"calendar": True, "tasks": False}
    assert out.values["default_view"] == "compact"
    with pytest.raises(ValidationError):
        put(repo, "dashboard", {"favorite_modules": ["settings"]})  # not a module code
    with pytest.raises(ValidationError):
        put(repo, "dashboard", {"widget_visibility": {"calendar": "yes"}})
    with pytest.raises(ValidationError):
        put(repo, "dashboard", {"default_landing_page": "https://evil.example"})


def test_search_preferences_bounds(repo):
    assert put(repo, "search", {"default_scope": "productivity", "recent_searches_limit": 25}).values["recent_searches_limit"] == 25
    with pytest.raises(ValidationError):
        put(repo, "search", {"recent_searches_limit": 51})
    with pytest.raises(ValidationError):
        put(repo, "search", {"default_scope": "everything"})
    out = put(repo, "search", {"saved_filters": {"finance": {"vendor": "all"}}})
    assert out.values["saved_filters"] == {"finance": {"vendor": "all"}}


def test_privacy_and_ai_sections(repo):
    out = put(repo, "privacy", {"reduce_motion": True, "session_page_size": 50})
    assert out.values["reduce_motion"] is True
    assert out.values["session_page_size"] == 50
    out = put(repo, "ai", {"preferred_writing_style": "concise", "preferred_report_format": "pdf"})
    assert out.values["preferred_writing_style"] == "concise"
    with pytest.raises(ValidationError):
        put(repo, "ai", {"preferred_report_format": "pptx"})


def test_unknown_section_rejected(repo):
    with pytest.raises(ValidationError):
        put(repo, "billing", {"plan": "pro"})


# -------------------------------------------------------------- backup (P6)
def test_export_contains_every_section(repo):
    put(repo, "profile", {"name": "Dr. N. Rao"})
    out = ExportSettingsUseCase(repo).execute(GetSettingsQuery())
    assert out.version == 1 and out.app == "AcademicOS" and out.exported_at
    assert set(out.sections.keys()) == {
        "profile", "appearance", "academic", "notifications",
        "dashboard", "search", "privacy", "ai",
    }
    assert out.sections["profile"]["name"] == "Dr. N. Rao"


def test_import_replaces_provided_sections_keeps_others(repo):
    put(repo, "profile", {"name": "Dr. N. Rao"})
    put(repo, "appearance", {"theme": "dark"})
    out = ImportSettingsUseCase(repo).execute(ImportSettingsCommand(input=ImportSettingsInput(
        sections={"appearance": {"theme": "light"}},
    )))
    assert out.sections["appearance"]["theme"] == "light"
    assert out.sections["profile"]["name"] == "Dr. N. Rao"  # untouched
    with pytest.raises(ValidationError):
        ImportSettingsUseCase(repo).execute(ImportSettingsCommand(input=ImportSettingsInput(
            sections={"appearance": {"theme": "blue"}},
        )))
    with pytest.raises(ValidationError):
        ImportSettingsUseCase(repo).execute(ImportSettingsCommand(input=ImportSettingsInput(
            sections={"unknown_section": {}},
        )))


def test_export_import_round_trip(repo):
    put(repo, "profile", {"name": "Dr. N. Rao", "institution": "IIT Delhi"})
    put(repo, "dashboard", {"favorite_modules": ["reports"]})
    exported = ExportSettingsUseCase(repo).execute(GetSettingsQuery())
    ResetSettingsUseCase(repo).execute(ResetSettingsCommand(input=ResetSettingsInput()))
    assert get(repo).sections["profile"]["name"] == ""
    ImportSettingsUseCase(repo).execute(ImportSettingsCommand(
        input=ImportSettingsInput(sections=exported.sections)))
    restored = get(repo)
    assert restored.sections["profile"]["name"] == "Dr. N. Rao"
    assert restored.sections["dashboard"]["favorite_modules"] == ["reports"]


def test_reset_all_and_partial(repo):
    put(repo, "appearance", {"theme": "dark"})
    put(repo, "search", {"recent_searches_limit": 40})
    out = ResetSettingsUseCase(repo).execute(ResetSettingsCommand(
        input=ResetSettingsInput(sections=["appearance"])))
    assert out.sections["appearance"]["theme"] == "system"  # reset
    assert out.sections["search"]["recent_searches_limit"] == 40  # untouched
    out = ResetSettingsUseCase(repo).execute(ResetSettingsCommand(input=ResetSettingsInput()))
    assert out.sections["search"]["recent_searches_limit"] == 10
    assert out.sections["notifications"]["priority_default"] == "medium"
    with pytest.raises(ValidationError):
        ResetSettingsUseCase(repo).execute(ResetSettingsCommand(
            input=ResetSettingsInput(sections=["nope"])))


def test_reset_materialises_defaults_after_clearing(repo):
    put(repo, "profile", {"name": "X"})
    put(repo, "profile", {"name": ""})
    ResetSettingsUseCase(repo).execute(ResetSettingsCommand(input=ResetSettingsInput(sections=["profile"])))
    assert get(repo).sections["profile"]["name"] == ""


# ------------------------------------------------------------------- photo
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_photo_lifecycle(repo, storage):
    with pytest.raises(ObjectNotFoundError):
        GetProfilePhotoUseCase(repo, storage).execute(GetProfilePhotoQuery())
    out = SetProfilePhotoUseCase(repo, storage).execute(SetProfilePhotoCommand(
        input=SetProfilePhotoInput(file_name="me.png", content=PNG, mime_type="image/png")))
    assert out.size_bytes == len(PNG)
    doc = get(repo)
    assert doc.has_photo is True and doc.photo_name == "me.png"
    got = GetProfilePhotoUseCase(repo, storage).execute(GetProfilePhotoQuery())
    assert got.content == PNG and got.mime_type == "image/png"
    DeleteProfilePhotoUseCase(repo, storage).execute(DeleteProfilePhotoCommand())
    assert get(repo).has_photo is False
    with pytest.raises(ObjectNotFoundError):
        GetProfilePhotoUseCase(repo, storage).execute(GetProfilePhotoQuery())


def test_photo_validation(repo, storage):
    with pytest.raises(ValidationError):
        SetProfilePhotoUseCase(repo, storage).execute(SetProfilePhotoCommand(
            input=SetProfilePhotoInput(file_name="a.txt", content=b"hi", mime_type="text/plain")))
    with pytest.raises(ValidationError):
        SetProfilePhotoUseCase(repo, storage).execute(SetProfilePhotoCommand(
            input=SetProfilePhotoInput(file_name="a.png", content=b"", mime_type="image/png")))
    with pytest.raises(ValidationError):
        SetProfilePhotoUseCase(repo, storage).execute(SetProfilePhotoCommand(
            input=SetProfilePhotoInput(file_name="a.png", content=b"x" * 2_000_001, mime_type="image/png")))


def test_photo_omitted_from_export(repo, storage):
    """Backup is settings-only: the photo blob never enters the JSON export."""
    SetProfilePhotoUseCase(repo, storage).execute(SetProfilePhotoCommand(
        input=SetProfilePhotoInput(file_name="me.png", content=PNG, mime_type="image/png")))
    exported = ExportSettingsUseCase(repo).execute(GetSettingsQuery())
    assert "photo" not in str(exported.sections)
    assert get(repo).has_photo is True


def test_document_reports_updated_at(repo):
    put(repo, "appearance", {"theme": "dark"})
    assert isinstance(get(repo).updated_at, str)
