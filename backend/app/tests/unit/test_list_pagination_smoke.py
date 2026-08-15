"""Unit tests: SQL-paginated list fast paths (M26).

The unfiltered directory listings of the major modules must page in SQL
(``count`` + ``find``) instead of loading every row of a type and slicing in
Python. A recording fake repository proves the call pattern — no timing, no
flakiness — and the filtered paths are pinned to the preserved full-scan
behaviour.
"""
from __future__ import annotations

from app.application.queries.list_documents import ListDocumentsQuery
from app.application.queries.list_faculty import ListFacultyQuery
from app.application.use_cases.documents.list_documents import ListDocumentsUseCase
from app.application.use_cases.faculty.list_faculty import ListFacultyUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId


class RecordingRepository(ObjectRepository):
    """Minimal recording fake: counts calls, returns canned objects."""

    def __init__(self, objects: list[UniversalObject]):
        self._objects = objects
        self.calls: list[str] = []

    def _canned(self, object_type, page, page_size, sort_by, order):
        self.calls.append("find")
        self.last_sort_by = sort_by
        rows = [o for o in self._objects if o.object_type is object_type]
        if sort_by in ("title", "title_ci"):
            rows = sorted(rows, key=lambda o: o.title.casefold())
        elif sort_by == "id":
            rows = sorted(rows, key=lambda o: str(o.id))
        start = (page - 1) * page_size
        return rows[start : start + page_size]

    # --- ObjectRepository port (only the paths under test are needed) ---
    def find_by_type(self, object_type):
        self.calls.append(f"find_by_type:{object_type.value}")
        return [o for o in self._objects if o.object_type is object_type]

    def find(self, *, object_type=None, status=None, metadata_key=None,
             metadata_value=None, page=1, page_size=0, sort_by=None, order="asc"):
        return self._canned(object_type, page, page_size, sort_by, order)

    def count(self, *, object_type=None, status=None, metadata_key=None,
              metadata_value=None):
        self.calls.append("count")
        return sum(1 for o in self._objects if o.object_type is object_type)

    def get(self, object_id: ObjectId):
        for o in self._objects:
            if o.id == object_id:
                return o
        return None

    def get_by_id(self, object_id):
        return self.get(object_id)

    def save(self, obj, *, outbox_events=None, expected_version=None):
        raise NotImplementedError

    def delete(self, object_id):
        raise NotImplementedError

    def find_by_status(self, status):
        raise NotImplementedError

    def find_by_metadata(self, key, value=None):
        raise NotImplementedError

    def exists(self, object_id):
        return self.get(object_id) is not None

    def find_by_ids(self, ids):
        self.calls.append("find_by_ids")
        by_id = {str(o.id): o for o in self._objects}
        return [by_id[str(i)] for i in ids if str(i) in by_id]

    def find_related(self, object_id, kind=None):
        return []

    def find_inbound(self, object_id, kind=None):
        return []


def _obj(object_type: ObjectType, title: str, idx: int) -> UniversalObject:
    return UniversalObject.create(
        object_type=object_type,
        title=title,
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId(f"obj:{object_type.value}:{idx:016X}"),
    )


def test_list_documents_plain_query_uses_sql_pagination():
    repo = RecordingRepository(
        [_obj(ObjectType.DOCUMENT, f"Doc {i}", i) for i in range(25)]
    )
    result = ListDocumentsUseCase(repo).execute(
        ListDocumentsQuery(page=2, page_size=10)
    )
    assert repo.calls == ["count", "find", "find_by_ids"]
    assert len(result.items) == 10
    assert result.total_count == 25
    assert result.page == 2
    assert result.page_size == 10


def test_list_documents_linked_object_filter_keeps_full_scan():
    repo = RecordingRepository(
        [_obj(ObjectType.DOCUMENT, "Doc A", 1), _obj(ObjectType.DOCUMENT, "Doc B", 2)]
    )
    ListDocumentsUseCase(repo).execute(
        ListDocumentsQuery(page=1, page_size=10, object_id="obj:project:0000000000000001")
    )
    assert "find_by_type:document" in repo.calls  # slow path preserved for soft filters


def test_list_faculty_plain_query_uses_sql_pagination():
    repo = RecordingRepository(
        [_obj(ObjectType.FACULTY, f"Prof {i}", i) for i in range(12)]
    )
    result = ListFacultyUseCase(repo).execute(
        ListFacultyQuery(page=1, page_size=10)
    )
    assert repo.calls == ["count", "find"]
    assert repo.last_sort_by == "title_ci"  # case-insensitive name order
    assert len(result.items) == 10
    assert result.total_count == 12


def test_list_faculty_filtered_query_keeps_full_scan():
    repo = RecordingRepository(
        [_obj(ObjectType.FACULTY, "Prof A", 1), _obj(ObjectType.FACULTY, "Prof B", 2)]
    )
    ListFacultyUseCase(repo).execute(
        ListFacultyQuery(page=1, page_size=10, q="physics")
    )
    assert "find_by_type:faculty" in repo.calls


# --- M27: research + finance fast paths --------------------------------------

def test_list_projects_plain_query_uses_sql_pagination():
    from app.application.queries.list_projects import ListProjectsQuery
    from app.application.use_cases.research.list_projects import ListProjectsUseCase

    repo = RecordingRepository(
        [_obj(ObjectType.RESEARCH_PROJECT, f"Project {i}", i) for i in range(12)]
    )
    result = ListProjectsUseCase(repo).execute(ListProjectsQuery(page=1, page_size=10))
    assert repo.calls == ["count", "find", "find_by_ids"]
    assert repo.last_sort_by == "title_ci"
    assert len(result.items) == 10
    assert result.total_count == 12


def test_list_projects_filtered_query_keeps_full_scan():
    from app.application.queries.list_projects import ListProjectsQuery
    from app.application.use_cases.research.list_projects import ListProjectsUseCase

    repo = RecordingRepository([_obj(ObjectType.RESEARCH_PROJECT, "P", 1)])
    ListProjectsUseCase(repo).execute(ListProjectsQuery(page=1, page_size=10, q="physics"))
    assert "find_by_type:research_project" in repo.calls


def test_list_agencies_plain_query_uses_sql_pagination():
    from app.application.queries.list_agencies import ListAgenciesQuery
    from app.application.use_cases.research.list_agencies import ListAgenciesUseCase

    repo = RecordingRepository(
        [_obj(ObjectType.FUNDING_AGENCY, f"Agency {i}", i) for i in range(8)]
    )
    result = ListAgenciesUseCase(repo).execute(ListAgenciesQuery(page=1, page_size=5))
    assert repo.calls == ["count", "find"]
    assert repo.last_sort_by == "title_ci"
    assert len(result.items) == 5
    assert result.total_count == 8


def test_list_vendors_plain_query_uses_sql_pagination():
    from app.application.queries.list_vendors import ListVendorsQuery
    from app.application.use_cases.finance.list_vendors import ListVendorsUseCase

    repo = RecordingRepository([_obj(ObjectType.VENDOR, f"Vendor {i}", i) for i in range(6)])
    result = ListVendorsUseCase(repo).execute(ListVendorsQuery(page=1, page_size=10))
    assert repo.calls[0:2] == ["count", "find"]
    assert "find_by_type:vendor" not in repo.calls  # base type never fully loaded
    assert repo.last_sort_by == "title_ci"
    assert len(result.items) == 6


def test_list_proposals_plain_query_uses_sql_pagination():
    from app.application.queries.list_proposals import ListProposalsQuery
    from app.application.use_cases.finance.list_proposals import ListProposalsUseCase

    repo = RecordingRepository(
        [_obj(ObjectType.PURCHASE, f"Proposal {i}", i) for i in range(15)]
    )
    result = ListProposalsUseCase(repo).execute(ListProposalsQuery(page=2, page_size=10))
    assert repo.calls[0:2] == ["count", "find"]
    assert "find_by_type:purchase" not in repo.calls  # base type never fully loaded
    assert repo.last_sort_by == "title_ci"
    assert len(result.items) == 5
    assert result.total_count == 15
