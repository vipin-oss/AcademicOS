"""V3 M17 transliteration + identity resolution tests (ADR-064)."""

from __future__ import annotations

from app.application.services.identity_resolution import IdentityResolutionService
from app.application.services.transliteration import match_key, to_latin
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import MetadataLayer, ObjectStatus, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


def test_transliteration_matches_vipin_both_scripts():
    assert match_key("Vipin") == match_key("विपिन")


def test_transliteration_is_case_and_whitespace_insensitive():
    assert match_key("VIPIN") == match_key("vipin")
    assert match_key("Vipin Kumar") == match_key("vipin  kumar")
    assert to_latin("विपिन") == "vipin"


class _Repo:
    def __init__(self, users):
        self._users = {str(u.id): u for u in users}

    def get_by_id(self, oid):
        return self._users.get(str(oid))

    def find(self, **kwargs):
        return list(self._users.values())


def _user(obj_id, title, *, orcid=None):
    entries = []
    if orcid:
        entries.append(MetadataEntry("orcid", orcid, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM))
    return UniversalObject.create(
        ObjectType.USER, title, created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId(obj_id), metadata=Metadata(entries=tuple(entries)),
    )


def test_finds_transliteration_candidate():
    repo = _Repo([
        _user("obj:user:1", "Vipin"),
        _user("obj:user:2", "विपिन"),
    ])
    report = IdentityResolutionService(repo).find_candidates("obj:user:1")
    reasons = {c.reason for c in report.candidates}
    assert "transliteration" in reasons
    assert any(c.match_id == "obj:user:2" for c in report.candidates)


def test_finds_identifier_candidate():
    repo = _Repo([
        _user("obj:user:1", "Vipin Kumar", orcid="0000-0001-2345"),
        _user("obj:user:2", "V. Kumar", orcid="0000-0001-2345"),
    ])
    report = IdentityResolutionService(repo).find_candidates(
        "obj:user:1", identifier="0000-0001-2345"
    )
    assert any(c.reason == "identifier" and c.match_id == "obj:user:2" for c in report.candidates)


def test_never_auto_merges():
    # resolution only PROPOSES candidates; it never mutates the graph.
    repo = _Repo([_user("obj:user:1", "Vipin"), _user("obj:user:2", "विपिन")])
    report = IdentityResolutionService(repo).find_candidates("obj:user:1")
    assert isinstance(report.candidates, tuple)  # read-only proposal


def test_missing_subject_returns_empty():
    repo = _Repo([])
    report = IdentityResolutionService(repo).find_candidates("obj:user:missing")
    assert report.candidates == ()
