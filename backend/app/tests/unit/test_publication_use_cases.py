"""Unit tests for the Publication use cases (no framework deps required).

Mirrors ``test_document_use_cases.py``: an in-memory ``ObjectRepository`` plus
a fake ``FileStorage`` exercise the slice without any database, filesystem,
network, or HTTP.
"""
from __future__ import annotations

from app.application.commands.attach_publication_pdf import (
    AttachPublicationPdfCommand,
)
from app.application.commands.create_publication import CreatePublicationCommand
from app.application.commands.delete_publication import DeletePublicationCommand
from app.application.commands.update_publication import UpdatePublicationCommand
from app.application.dtos.publication import (
    CreatePublicationInput,
    UpdatePublicationInput,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.ports.file_storage import FileStorage
from app.application.queries.get_publication import GetPublicationQuery
from app.application.queries.list_publications import ListPublicationsQuery
from app.application.use_cases.publications.attach_publication_pdf import (
    AttachPublicationPdfUseCase,
)
from app.application.use_cases.publications.create_publication import (
    CreatePublicationUseCase,
)
from app.application.use_cases.publications.delete_publication import (
    DeletePublicationUseCase,
)
from app.application.use_cases.publications.get_publication import GetPublicationUseCase
from app.application.use_cases.publications.import_publications import (
    ImportPublicationsCommand,
    ImportPublicationsUseCase,
)
from app.application.use_cases.publications.list_publications import (
    ListPublicationsUseCase,
)
from app.application.use_cases.publications.update_publication import (
    UpdatePublicationUseCase,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
)
from app.domain.value_objects.object_id import ObjectId


class InMemoryObjectRepository(ObjectRepository):
    def __init__(self) -> None:
        self._store: dict[ObjectId, UniversalObject] = {}

    def save(self, entity: UniversalObject, *, outbox_events=()) -> None:
        self._store[entity.id] = entity

    def get_by_id(self, id: ObjectId) -> UniversalObject | None:
        return self._store.get(id)

    def find_by_ids(self, ids: list[ObjectId]) -> list[UniversalObject]:
        return [self._store[i] for i in ids if i in self._store]

    def exists(self, id: ObjectId) -> bool:
        return id in self._store

    def delete(self, id: ObjectId) -> None:
        self._store.pop(id, None)

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_related(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        obj = self._store.get(object_id)
        if obj is None:
            return []
        return obj.related_ids(kind)
    def find_inbound(
        self, object_id: ObjectId, kind=None
    ) -> list[ObjectId]:
        return [
            o.id
            for o in self._store.values()
            if any(r.target == object_id and (kind is None or r.kind == kind) for r in o.relationships)
        ]

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        out: list[UniversalObject] = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
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
        if page < 1:
            raise ValueError("page must be >= 1.")
        if page_size < 0:
            raise ValueError("page_size must be >= 0.")
        if sort_by is not None and sort_by not in (
            "id", "object_type", "title", "title_ci", "status", "version",
        ):
            raise ValueError(f"Unsupported sort_by: {sort_by!r}")
        if order not in ("asc", "desc"):
            raise ValueError(f"Unsupported order: {order!r}")

        items = [
            o
            for o in self._store.values()
            if (object_type is None or o.object_type == object_type)
            and (status is None or o.status == status)
            and (
                metadata_key is None
                or (
                    (value := o.metadata.get_value(metadata_key)) is not None
                    and (metadata_value is None or value == metadata_value)
                )
            )
        ]
        effective_sort = sort_by if sort_by is not None else ("id" if page_size > 0 else None)
        if effective_sort is not None:
            reverse = order == "desc"
            if effective_sort == "id":
                items.sort(key=lambda o: str(o.id), reverse=reverse)
            elif effective_sort == "object_type":
                items.sort(key=lambda o: o.object_type.value, reverse=reverse)
            elif effective_sort in ("title", "title_ci"):
                items.sort(key=lambda o: o.title, reverse=reverse)
            elif effective_sort == "status":
                items.sort(key=lambda o: o.status.value, reverse=reverse)
            elif effective_sort == "version":
                items.sort(key=lambda o: o.version, reverse=reverse)
        if page_size > 0:
            start = (page - 1) * page_size
            items = items[start : start + page_size]
        return items

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


    def list(self) -> list[UniversalObject]:
        return list(self._store.values())


class InMemoryFileStorage(FileStorage):
    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def save(self, key: str, content: bytes) -> None:
        self._blobs[key] = content

    def read(self, key: str) -> bytes:
        return self._blobs[key]

    def exists(self, key: str) -> bool:
        return key in self._blobs

    def delete(self, key: str) -> None:
        self._blobs.pop(key, None)


def _link_target(repo, object_type, title):
    obj = UniversalObject.create(object_type, title, created_by="faculty:1")
    obj.pop_domain_events()
    repo.save(obj)
    return obj


def _input(**overrides) -> CreatePublicationInput:
    data = {
        "title": "Deep Learning for Catalysis",
        "publication_type": "journal_article",
        "uploaded_by": "faculty:1",
        "authors": (
            {"name": "Gupta, Vipin", "orcid": "0000-0002-1825-0097", "corresponding": True},
            {"name": "Sharma, Asha"},
        ),
        "journal": "Nature Catalysis",
        "doi": "10.1038/s41929-024-00001",
        "year": 2025,
        "volume": "7",
        "issue": "3",
        "pages": "201-214",
        "publisher": "Springer Nature",
        "keywords": ("catalysis", "deep learning"),
        "quartile": "Q1",
        "citation_count": 12,
        "impact_factor": 37.8,
        "indexing": ("SCOPUS", "WOS"),
        "publisher_url": "https://doi.org/10.1038/s41929-024-00001",
        "tags": ("ml",),
        "collections": ("Catalysis Papers",),
        "pipeline_stage": "published",
    }
    data.update(overrides)
    return CreatePublicationInput(**data)


def test_create_publication_projects_full_field_set():
    repo = InMemoryObjectRepository()
    out = CreatePublicationUseCase(repo).execute(CreatePublicationCommand(input=_input()))

    assert out.id.startswith("obj:publication:")
    assert out.publication_type == "journal_article"
    assert out.pipeline_stage == "published"
    assert [a["name"] for a in out.authors] == ["Gupta, Vipin", "Sharma, Asha"]
    assert out.authors[0]["corresponding"] is True
    assert out.doi == "10.1038/s41929-024-00001"
    assert out.journal == "Nature Catalysis"
    assert out.year == 2025
    assert out.volume == "7" and out.issue == "3" and out.pages == "201-214"
    assert out.keywords == ["catalysis", "deep learning"]
    assert out.quartile == "Q1"
    assert out.citation_count == 12
    assert out.impact_factor == 37.8
    assert out.indexing == ["SCOPUS", "WOS"]
    assert out.publisher_url == "https://doi.org/10.1038/s41929-024-00001"
    assert out.tags == ["ml"]
    assert out.collections == ["Catalysis Papers"]
    assert out.status == "draft"
    assert "ObjectCreated" in out.events


def test_create_publication_links_denormalised():
    repo = InMemoryObjectRepository()
    project = _link_target(repo, ObjectType.RESEARCH_PROJECT, "Project X")
    grant = _link_target(repo, ObjectType.GRANT, "Grant G1")
    student = _link_target(repo, ObjectType.STUDENT, "Student Y")
    faculty = _link_target(repo, ObjectType.FACULTY, "Dr Gupta")
    committee = _link_target(repo, ObjectType.COMMITTEE, "RDC")
    event = _link_target(repo, ObjectType.EVENT, "ICML 24")
    dept = _link_target(repo, ObjectType.SPACE, "CSE Dept")

    out = CreatePublicationUseCase(repo).execute(
        CreatePublicationCommand(
            input=_input(
                links={
                    "projects": (project.id,),
                    "grants": (grant.id,),
                    "students": (student.id,),
                    "faculty": (faculty.id,),
                    "departments": (dept.id,),
                    "events": (event.id,),
                    "committees": (committee.id,),
                }
            )
        )
    )
    assert out.links["projects"][0]["title"] == "Project X"
    assert out.links["grants"][0]["title"] == "Grant G1"
    assert out.links["students"][0]["title"] == "Student Y"
    assert out.links["faculty"][0]["title"] == "Dr Gupta"
    assert out.links["departments"][0]["title"] == "CSE Dept"
    assert out.links["events"][0]["title"] == "ICML 24"
    assert out.links["committees"][0]["title"] == "RDC"
    assert out.links["grants"][0]["kind"] == "reports"
    assert out.links["students"][0]["kind"] == "authored_by"
    assert out.links["events"][0]["kind"] == "presented_at"


def test_create_rejects_duplicate_doi_and_title():
    repo = InMemoryObjectRepository()
    CreatePublicationUseCase(repo).execute(CreatePublicationCommand(input=_input()))

    for dupe in (
        _input(title="Completely Different Title"),  # same DOI
        _input(doi=None),                            # same title, no DOI
    ):
        try:
            CreatePublicationUseCase(repo).execute(CreatePublicationCommand(input=dupe))
            assert False
        except ObjectAlreadyExistsError:
            pass


def test_create_validates_fields():
    repo = InMemoryObjectRepository()
    for overrides in (
        {"publication_type": "bogus"},
        {"quartile": "Q7"},
        {"doi": "not-a-doi"},
        {"year": 199},
        {"authors": ({"name": "", }, )},
        {"authors": ({"name": "X", "orcid": "123"},)},
        {"links": {"bogus_group": ()}},
    ):
        try:
            CreatePublicationUseCase(repo).execute(
                CreatePublicationCommand(input=_input(**overrides))
            )
            assert False, f"expected ValidationError for {overrides}"
        except ValidationError:
            pass


def test_get_and_non_publication_hidden():
    repo = InMemoryObjectRepository()
    out = CreatePublicationUseCase(repo).execute(CreatePublicationCommand(input=_input()))
    got = GetPublicationUseCase(repo).execute(GetPublicationQuery(object_id=ObjectId(out.id)))
    assert got.title == "Deep Learning for Catalysis"

    course = _link_target(repo, ObjectType.COURSE, "CS101")
    try:
        GetPublicationUseCase(repo).execute(GetPublicationQuery(object_id=course.id))
        assert False
    except ObjectNotFoundError:
        pass


def test_list_search_and_filters():
    repo = InMemoryObjectRepository()
    CreatePublicationUseCase(repo).execute(CreatePublicationCommand(input=_input()))
    CreatePublicationUseCase(repo).execute(
        CreatePublicationCommand(
            input=_input(
                title="Graph Neural Sensors",
                doi=None,
                publication_type="conference_paper",
                journal=None,
                conference="ICML",
                year=2024,
                quartile="Q2",
                pipeline_stage="under_review",
                authors=({"name": "Verma, Rohan"},),
                keywords=("sensors", "graph networks"),
                tags=("edge",),
                collections=(),
            )
        )
    )
    listing = ListPublicationsUseCase(repo)

    assert listing.execute(ListPublicationsQuery()).total_count == 2
    by_q = listing.execute(ListPublicationsQuery(q="catalysis gupta"))
    assert by_q.total_count == 1
    by_doi = listing.execute(ListPublicationsQuery(q="10.1038"))
    assert by_doi.total_count == 1
    by_type = listing.execute(ListPublicationsQuery(publication_type="conference_paper"))
    assert by_type.total_count == 1 and by_type.items[0].conference == "ICML"
    by_year = listing.execute(ListPublicationsQuery(year=2025))
    assert by_year.total_count == 1
    by_quartile = listing.execute(ListPublicationsQuery(quartile="Q2"))
    assert by_quartile.total_count == 1
    by_stage = listing.execute(ListPublicationsQuery(pipeline_stage="under_review"))
    assert by_stage.total_count == 1


def test_list_object_relation_filter():
    repo = InMemoryObjectRepository()
    project = _link_target(repo, ObjectType.RESEARCH_PROJECT, "Project X")
    CreatePublicationUseCase(repo).execute(
        CreatePublicationCommand(input=_input(links={"projects": (project.id,)}))
    )
    CreatePublicationUseCase(repo).execute(
        CreatePublicationCommand(input=_input(title="Unlinked Work", doi=None))
    )
    result = ListPublicationsUseCase(repo).execute(
        ListPublicationsQuery(object_id=project.id)
    )
    assert result.total_count == 1
    assert result.items[0].links["projects"][0]["id"] == str(project.id)


def test_update_metadata_status_and_links():
    repo = InMemoryObjectRepository()
    project_a = _link_target(repo, ObjectType.RESEARCH_PROJECT, "Project A")
    project_b = _link_target(repo, ObjectType.RESEARCH_PROJECT, "Project B")
    out = CreatePublicationUseCase(repo).execute(
        CreatePublicationCommand(input=_input(links={"projects": (project_a.id,)}))
    )

    updated = UpdatePublicationUseCase(repo).execute(
        UpdatePublicationCommand(
            object_id=ObjectId(out.id),
            input=UpdatePublicationInput(
                actor="faculty:1",
                title="Deep Learning for Catalysis — Extended",
                status=ObjectStatus.ACTIVE,
                quartile="Q1",
                citation_count=15,
                keywords=("catalysis", "deep learning", "gcn"),
                links={"projects": (project_b.id,)},
            ),
        )
    )
    assert updated.title == "Deep Learning for Catalysis — Extended"
    assert updated.status == "active"
    assert updated.citation_count == 15
    assert updated.keywords == ["catalysis", "deep learning", "gcn"]
    assert [link["id"] for link in updated.links["projects"]] == [str(project_b.id)]
    assert updated.quartile == "Q1"
    assert updated.version > out.version
    assert updated.updated_at is not None
    assert "ObjectRenamed" in updated.events

    # Absent group stays untouched; present group with empty tuple clears it.
    cleared = UpdatePublicationUseCase(repo).execute(
        UpdatePublicationCommand(
            object_id=ObjectId(out.id),
            input=UpdatePublicationInput(actor="faculty:1", links={"projects": ()}),
        )
    )
    assert cleared.links["projects"] == []
    assert cleared.quartile == "Q1"  # untouched


def test_update_duplicate_conflict():
    repo = InMemoryObjectRepository()
    CreatePublicationUseCase(repo).execute(CreatePublicationCommand(input=_input()))
    second = CreatePublicationUseCase(repo).execute(
        CreatePublicationCommand(
            input=_input(title="Another Work", doi="10.5555/other-1")
        )
    )
    try:
        UpdatePublicationUseCase(repo).execute(
            UpdatePublicationCommand(
                object_id=ObjectId(second.id),
                input=UpdatePublicationInput(
                    actor="faculty:1", doi="10.1038/s41929-024-00001"
                ),
            )
        )
        assert False
    except ObjectAlreadyExistsError:
        pass


def test_attach_pdf_and_replace_then_delete_cleans_up():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    out = CreatePublicationUseCase(repo).execute(CreatePublicationCommand(input=_input()))

    attached = AttachPublicationPdfUseCase(repo, storage).execute(
        AttachPublicationPdfCommand(
            object_id=ObjectId(out.id),
            file_name="paper.pdf",
            content=b"%PDF-one",
            mime_type="application/pdf",
            actor="faculty:1",
        )
    )
    assert attached.pdf_file_name == "paper.pdf"
    assert attached.pdf_file_size == len(b"%PDF-one")
    assert attached.pdf_file_path is not None
    assert storage.read(attached.pdf_file_path) == b"%PDF-one"

    replaced = AttachPublicationPdfUseCase(repo, storage).execute(
        AttachPublicationPdfCommand(
            object_id=ObjectId(out.id),
            file_name="paper-v2.pdf",
            content=b"%PDF-two-longer",
            mime_type="application/pdf",
            actor="faculty:1",
        )
    )
    assert replaced.pdf_file_name == "paper-v2.pdf"
    assert not storage.exists(attached.pdf_file_path)  # old blob removed
    assert storage.exists(replaced.pdf_file_path)

    DeletePublicationUseCase(repo, storage).execute(
        DeletePublicationCommand(object_id=ObjectId(out.id))
    )
    assert not repo.exists(ObjectId(out.id))
    assert not storage.exists(replaced.pdf_file_path)


def test_delete_missing_publication_raises():
    repo, storage = InMemoryObjectRepository(), InMemoryFileStorage()
    try:
        DeletePublicationUseCase(repo, storage).execute(
            DeletePublicationCommand(object_id=ObjectId.generate(ObjectType.PUBLICATION))
        )
        assert False
    except ObjectNotFoundError:
        pass


def test_import_bibtex_with_duplicate_report():
    repo = InMemoryObjectRepository()
    CreatePublicationUseCase(repo).execute(CreatePublicationCommand(input=_input()))
    bib = """
@article{gupta2024,
  title = {Deep Learning for Catalysis},
  author = {Gupta, Vipin and Sharma, Asha},
  journal = {Nature Catalysis},
  doi = {10.1038/s41929-024-00001},
  year = {2025}
}
@inproceedings{sharma2023graph,
  title = {Graph Neural Sensors},
  author = {Sharma, Asha},
  booktitle = {ICML},
  pages = {10--20},
  year = {2024}
}
"""
    result = ImportPublicationsUseCase(repo).execute(
        ImportPublicationsCommand(fmt="bibtex", text=bib, uploaded_by="faculty:1")
    )
    assert len(result.duplicates) == 1
    assert result.duplicates[0]["existing_id"].startswith("obj:publication:")
    assert len(result.created) == 1
    made = GetPublicationUseCase(repo).execute(
        GetPublicationQuery(object_id=ObjectId(result.created[0]))
    )
    assert made.publication_type == "conference_paper"
    assert made.conference == "ICML"
    assert made.pages == "10--20"


def test_import_ris_and_validation():
    repo = InMemoryObjectRepository()
    ris = """TY  - JOUR
TI  - Sensor Networks for Labs
AU  - Verma, Kiran
AU  - Rao, Meena
JO  - Lab Automation
VL  - 5
IS  - 2
SP  - 100
EP  - 112
PY  - 2023
DO  - 10.5555/lab-2023
KW  - sensors
ER  -
"""
    result = ImportPublicationsUseCase(repo).execute(
        ImportPublicationsCommand(fmt="ris", text=ris, uploaded_by="faculty:1")
    )
    assert len(result.created) == 1
    made = GetPublicationUseCase(repo).execute(
        GetPublicationQuery(object_id=ObjectId(result.created[0]))
    )
    assert made.title == "Sensor Networks for Labs"
    assert made.pages == "100-112"
    assert made.authors[0]["name"] == "Verma, Kiran"

    try:
        ImportPublicationsUseCase(repo).execute(
            ImportPublicationsCommand(fmt="yaml", text="x", uploaded_by="faculty:1")
        )
        assert False
    except ValidationError:
        pass
