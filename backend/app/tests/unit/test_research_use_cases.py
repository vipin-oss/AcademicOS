"""Unit tests for the Research use cases (no framework deps required).

Mirrors ``test_student_use_cases.py``: an in-memory ``ObjectRepository``
exercises the slice without any database, filesystem, network, or HTTP.
"""
from __future__ import annotations

import pytest

from app.application.commands.add_installment import AddInstallmentCommand
from app.application.commands.add_milestone import AddMilestoneCommand
from app.application.commands.create_agency import CreateAgencyCommand
from app.application.commands.create_grant import CreateGrantCommand
from app.application.commands.create_project import CreateProjectCommand
from app.application.commands.delete_agency import DeleteAgencyCommand
from app.application.commands.delete_grant import DeleteGrantCommand
from app.application.commands.delete_milestone import DeleteMilestoneCommand
from app.application.commands.delete_project import DeleteProjectCommand
from app.application.commands.record_expenditure import RecordExpenditureCommand
from app.application.commands.record_progress_update import RecordProgressUpdateCommand
from app.application.commands.update_agency import UpdateAgencyCommand
from app.application.commands.update_grant import UpdateGrantCommand
from app.application.commands.update_milestone import UpdateMilestoneCommand
from app.application.commands.update_project import UpdateProjectCommand
from app.application.dtos.research import (
    CreateAgencyInput,
    CreateGrantInput,
    CreateProjectInput,
    ExpenditureInput,
    InstallmentInput,
    MilestoneInput,
    ProgressUpdateInput,
    UpdateAgencyInput,
    UpdateGrantInput,
    UpdateMilestoneInput,
    UpdateProjectInput,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_agency import GetAgencyQuery
from app.application.queries.get_grant import GetGrantQuery
from app.application.queries.get_project import GetProjectQuery
from app.application.queries.get_research_dashboard import GetResearchDashboardQuery
from app.application.queries.list_agencies import ListAgenciesQuery
from app.application.queries.list_grants import ListGrantsQuery
from app.application.queries.list_projects import ListProjectsQuery
from app.application.use_cases.research.add_installment import AddInstallmentUseCase
from app.application.use_cases.research.add_milestone import AddMilestoneUseCase
from app.application.use_cases.research.create_agency import CreateAgencyUseCase
from app.application.use_cases.research.create_grant import CreateGrantUseCase
from app.application.use_cases.research.create_project import CreateProjectUseCase
from app.application.use_cases.research.delete_agency import DeleteAgencyUseCase
from app.application.use_cases.research.delete_grant import DeleteGrantUseCase
from app.application.use_cases.research.delete_milestone import DeleteMilestoneUseCase
from app.application.use_cases.research.delete_project import DeleteProjectUseCase
from app.application.use_cases.research.get_agency import GetAgencyUseCase
from app.application.use_cases.research.get_grant import GetGrantUseCase
from app.application.use_cases.research.get_project import GetProjectUseCase
from app.application.use_cases.research.get_research_dashboard import (
    GetResearchDashboardUseCase,
)
from app.application.use_cases.research.list_agencies import ListAgenciesUseCase
from app.application.use_cases.research.list_grants import ListGrantsUseCase
from app.application.use_cases.research.list_projects import ListProjectsUseCase
from app.application.use_cases.research.record_expenditure import RecordExpenditureUseCase
from app.application.use_cases.research.record_progress_update import (
    RecordProgressUpdateUseCase,
)
from app.application.use_cases.research.update_agency import UpdateAgencyUseCase
from app.application.use_cases.research.update_grant import UpdateGrantUseCase
from app.application.use_cases.research.update_milestone import UpdateMilestoneUseCase
from app.application.use_cases.research.update_project import UpdateProjectUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId


class InMemoryObjectRepository(ObjectRepository):
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

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_related(self, object_id: ObjectId, kind=None) -> list[ObjectId]:
        obj = self._store.get(object_id)
        return [] if obj is None else obj.related_ids(kind)

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        out: list[UniversalObject] = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
        return out

    def list(self) -> list[UniversalObject]:
        return list(self._store.values())


def _target(repo, object_type, title):
    obj = UniversalObject.create(object_type, title, created_by="faculty:1")
    obj.pop_domain_events()
    repo.save(obj)
    return obj


def _agency(repo, name="DST", **overrides):
    body = {"name": name, "created_by": "faculty:1", "scheme": "Core Research Grant",
            "website": "https://dst.gov.in", "contact_email": "help@dst.gov.in"}
    body.update(overrides)
    return CreateAgencyUseCase(repo).execute(CreateAgencyCommand(input=CreateAgencyInput(**body)))


def _project_input(**overrides):
    data = {
        "title": "Quantum Materials Discovery",
        "created_by": "faculty:1",
        "lifecycle_status": "draft",
        "project_code": "DST-2026-0137",
        "department": "Physics",
        "start_date": "2026-04-01",
        "end_date": "2029-03-31",
        "duration": "36 months",
        "budget_approved": 4500000.0,
        "budget_utilized": 0.0,
        "objectives": "Discover qubit-grade materials",
        "keywords": ("quantum", "materials"),
        "abstract": "A materials informatics study.",
        "priority": "high",
        "tags": ("flagship",),
    }
    data.update(overrides)
    return CreateProjectInput(**data)


def _project(repo, **overrides):
    return CreateProjectUseCase(repo).execute(
        CreateProjectCommand(input=_project_input(**overrides))
    )


# ---------------------------------------------------------------------------
# Agencies
# ---------------------------------------------------------------------------
def test_create_agency_stores_registry_fields():
    repo = InMemoryObjectRepository()
    out = _agency(repo)
    assert out.name == "DST"
    assert out.scheme == "Core Research Grant"
    assert out.website == "https://dst.gov.in"
    stored = repo.get_by_id(ObjectId(out.id))
    assert stored is not None and stored.object_type is ObjectType.FUNDING_AGENCY
    assert stored.metadata.get_value("contact_email") == "help@dst.gov.in"


def test_create_agency_duplicate_name_is_409():
    repo = InMemoryObjectRepository()
    _agency(repo, name="CSIR")
    with pytest.raises(ObjectAlreadyExistsError):
        _agency(repo, name="csir")  # case-insensitive registry identity


def test_list_agencies_searches_tokens():
    repo = InMemoryObjectRepository()
    _agency(repo, name="DST")
    _agency(repo, name="Haryana HSRF", scheme="State research fellowship")
    result = ListAgenciesUseCase(repo).execute(ListAgenciesQuery(q="fellowship"))
    assert result.total_count == 1
    assert result.items[0].name == "Haryana HSRF"


def test_update_agency_merge_semantics_and_duplicate_guard():
    repo = InMemoryObjectRepository()
    first = _agency(repo, name="DST")
    _agency(repo, name="UGC")
    updated = UpdateAgencyUseCase(repo).execute(
        UpdateAgencyCommand(
            object_id=ObjectId(first.id),
            input=UpdateAgencyInput(actor="faculty:2", scheme="TARE"),
        )
    )
    assert updated.scheme == "TARE"
    assert updated.website == "https://dst.gov.in"  # untouched
    with pytest.raises(ObjectAlreadyExistsError):
        UpdateAgencyUseCase(repo).execute(
            UpdateAgencyCommand(
                object_id=ObjectId(first.id),
                input=UpdateAgencyInput(actor="faculty:2", name="ugc"),
            )
        )


def test_delete_agency_and_not_found():
    repo = InMemoryObjectRepository()
    agency = _agency(repo)
    DeleteAgencyUseCase(repo).execute(DeleteAgencyCommand(object_id=ObjectId(agency.id)))
    with pytest.raises(ObjectNotFoundError):
        GetAgencyUseCase(repo).execute(GetAgencyQuery(object_id=ObjectId(agency.id)))


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
def test_create_project_stores_metadata_and_budget():
    repo = InMemoryObjectRepository()
    out = _project(repo)
    assert out.lifecycle_status == "draft"
    assert out.budget_approved == 4500000.0
    assert out.keywords == ["quantum", "materials"]
    stored = repo.get_by_id(ObjectId(out.id))
    assert stored.object_type is ObjectType.RESEARCH_PROJECT
    assert stored.metadata.get_value("project_code") == "DST-2026-0137"
    assert stored.metadata.get_value("priority") == "high"


def test_create_project_duplicate_code_is_409():
    repo = InMemoryObjectRepository()
    _project(repo, title="One", project_code="SERB-101")
    with pytest.raises(ObjectAlreadyExistsError):
        _project(repo, title="Two", project_code="serb-101")


def test_create_project_links_agency_with_type_guard():
    repo = InMemoryObjectRepository()
    agency = _agency(repo)
    stranger = _target(repo, ObjectType.COURSE, "CS-101")
    out = _project(repo, links={"agencies": (ObjectId(agency.id),)})
    assert out.links["agencies"][0]["id"] == agency.id
    assert out.links["agencies"][0]["object_type"] == "funding_agency"
    with pytest.raises(ValidationError):
        _project(repo, title="Bad", project_code="BAD-1", links={"agencies": (stranger.id,)})


def test_create_project_writes_team_edges_on_people():
    repo = InMemoryObjectRepository()
    pi = _target(repo, ObjectType.FACULTY, "Dr Meera Krishnan")
    co_pi = _target(repo, ObjectType.FACULTY, "Dr Arjun Rao")
    member = _target(repo, ObjectType.STUDENT, "Asha Verma")
    out = _project(
        repo,
        team={
            "principal_investigators": (pi.id,),
            "co_investigators": (co_pi.id,),
            "team_members": (member.id,),
        },
    )
    assert out.team["principal_investigators"][0]["title"] == "Dr Meera Krishnan"
    assert out.team["co_investigators"][0]["title"] == "Dr Arjun Rao"
    assert out.team["team_members"][0]["title"] == "Asha Verma"
    # The edges live on the person aggregates (enroll_students precedent).
    assert RelationshipKind.LEADS in {r.kind for r in repo.get_by_id(pi.id).relationships}
    assert RelationshipKind.CO_LEADS in {r.kind for r in repo.get_by_id(co_pi.id).relationships}
    assert RelationshipKind.WORKS_IN in {r.kind for r in repo.get_by_id(member.id).relationships}


def test_create_project_rejects_student_as_pi():
    repo = InMemoryObjectRepository()
    student = _target(repo, ObjectType.STUDENT, "Asha Verma")
    with pytest.raises(ValidationError):
        _project(repo, team={"principal_investigators": (student.id,)})


def test_update_project_lifecycle_and_budget():
    repo = InMemoryObjectRepository()
    project = _project(repo)
    updated = UpdateProjectUseCase(repo).execute(
        UpdateProjectCommand(
            object_id=ObjectId(project.id),
            input=UpdateProjectInput(
                actor="faculty:1",
                lifecycle_status="funded",
                budget_utilized=125000.0,
            ),
        )
    )
    assert updated.lifecycle_status == "funded"
    assert updated.budget_utilized == 125000.0
    assert updated.project_code == "DST-2026-0137"  # untouched
    assert updated.budget["remaining"] == 4500000.0 - 125000.0


def test_update_project_duplicate_code_change_is_409():
    repo = InMemoryObjectRepository()
    first = _project(repo, title="One", project_code="A-1")
    _project(repo, title="Two", project_code="B-2")
    with pytest.raises(ObjectAlreadyExistsError):
        UpdateProjectUseCase(repo).execute(
            UpdateProjectCommand(
                object_id=ObjectId(first.id),
                input=UpdateProjectInput(actor="faculty:1", project_code="b-2"),
            )
        )


def test_update_project_replaces_team_group_only_that_group():
    repo = InMemoryObjectRepository()
    pi_a = _target(repo, ObjectType.FACULTY, "PI A")
    pi_b = _target(repo, ObjectType.FACULTY, "PI B")
    member = _target(repo, ObjectType.STUDENT, "Asha Verma")
    project = _project(
        repo,
        team={"principal_investigators": (pi_a.id,), "team_members": (member.id,)},
    )
    updated = UpdateProjectUseCase(repo).execute(
        UpdateProjectCommand(
            object_id=ObjectId(project.id),
            input=UpdateProjectInput(
                actor="faculty:1",
                team={"principal_investigators": (pi_b.id,)},
            ),
        )
    )
    assert [p["title"] for p in updated.team["principal_investigators"]] == ["PI B"]
    assert [p["title"] for p in updated.team["team_members"]] == ["Asha Verma"]  # untouched
    assert RelationshipKind.LEADS not in {r.kind for r in repo.get_by_id(pi_a.id).relationships}
    assert RelationshipKind.LEADS in {r.kind for r in repo.get_by_id(pi_b.id).relationships}


def test_list_projects_part9_filters():
    repo = InMemoryObjectRepository()
    agency = _agency(repo, name="SERB")
    pi = _target(repo, ObjectType.FACULTY, "Dr Meera Krishnan")
    _project(
        repo,
        title="Quantum Materials Discovery",
        links={"agencies": (ObjectId(agency.id),)},
        team={"principal_investigators": (pi.id,)},
        lifecycle_status="active",
        department="Physics",
        start_date="2026-01-15",
    )
    _project(repo, title="Wetland Ecology Survey", project_code="UGC-9",
             lifecycle_status="completed", department="Botany", start_date="2024-06-01",
             objectives="Map wetland diversity", keywords=("ecology", "wetland"))

    by_status = ListProjectsUseCase(repo).execute(ListProjectsQuery(status="active"))
    assert [o.title for o in by_status.items] == ["Quantum Materials Discovery"]
    by_year = ListProjectsUseCase(repo).execute(ListProjectsQuery(year=2024))
    assert [o.title for o in by_year.items] == ["Wetland Ecology Survey"]
    by_dept = ListProjectsUseCase(repo).execute(ListProjectsQuery(department="physics"))
    assert by_dept.total_count == 1
    by_pi = ListProjectsUseCase(repo).execute(ListProjectsQuery(pi="meera"))
    assert by_pi.total_count == 1
    by_agency = ListProjectsUseCase(repo).execute(ListProjectsQuery(agency="serb"))
    assert by_agency.total_count == 1
    by_q = ListProjectsUseCase(repo).execute(ListProjectsQuery(q="quantum materials"))
    assert by_q.total_count == 1


def test_milestones_add_update_order_and_delete():
    repo = InMemoryObjectRepository()
    project = _project(repo)
    first = AddMilestoneUseCase(repo).execute(
        AddMilestoneCommand(
            project_id=ObjectId(project.id),
            input=MilestoneInput(title="Literature review", date="2026-06-30"),
        )
    )
    AddMilestoneUseCase(repo).execute(
        AddMilestoneCommand(
            project_id=ObjectId(project.id),
            input=MilestoneInput(title="Pilot experiments", date="2026-03-15"),
        )
    )
    fetched = GetProjectUseCase(repo).execute(GetProjectQuery(object_id=ObjectId(project.id)))
    assert [m.title for m in fetched.milestones] == ["Pilot experiments", "Literature review"]

    done = UpdateMilestoneUseCase(repo).execute(
        UpdateMilestoneCommand(
            milestone_id=ObjectId(first.id),
            input=UpdateMilestoneInput(actor="faculty:1", status="done"),
        )
    )
    assert done.status == "done"

    DeleteMilestoneUseCase(repo).execute(DeleteMilestoneCommand(milestone_id=ObjectId(first.id)))
    fetched = GetProjectUseCase(repo).execute(GetProjectQuery(object_id=ObjectId(project.id)))
    assert [m.title for m in fetched.milestones] == ["Pilot experiments"]


def test_progress_updates_append_sorted_and_validated():
    repo = InMemoryObjectRepository()
    project = _project(repo)
    RecordProgressUpdateUseCase(repo).execute(
        RecordProgressUpdateCommand(
            project_id=ObjectId(project.id),
            input=ProgressUpdateInput(date="2026-07-01", percent=40, remark="Setup complete"),
        )
    )
    out = RecordProgressUpdateUseCase(repo).execute(
        RecordProgressUpdateCommand(
            project_id=ObjectId(project.id),
            input=ProgressUpdateInput(date="2026-05-01", percent=15, remark="Kickoff"),
        )
    )
    assert [u["percent"] for u in out.progress_updates] == [15.0, 40.0]
    assert out.progress_updates[-1]["remark"] == "Setup complete"
    with pytest.raises(ValidationError):
        RecordProgressUpdateUseCase(repo).execute(
            RecordProgressUpdateCommand(
                project_id=ObjectId(project.id),
                input=ProgressUpdateInput(date="2026-08-01", percent=140, remark="X"),
            )
        )


def test_delete_project_cascades_milestones_only():
    repo = InMemoryObjectRepository()
    project = _project(repo)
    milestone = AddMilestoneUseCase(repo).execute(
        AddMilestoneCommand(
            project_id=ObjectId(project.id),
            input=MilestoneInput(title="Mid-term review", date="2027-01-15"),
        )
    )
    DeleteProjectUseCase(repo).execute(DeleteProjectCommand(object_id=ObjectId(project.id)))
    with pytest.raises(ObjectNotFoundError):
        GetProjectUseCase(repo).execute(GetProjectQuery(object_id=ObjectId(project.id)))
    # The milestone child is gone with its project (documented cascade).
    assert repo.get_by_id(ObjectId(milestone.id)) is None


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------
def _grant(repo, project_id=None, agency_id=None, **overrides):
    links = {}
    if project_id:
        links["projects"] = (ObjectId(project_id),)
    if agency_id:
        links["funding_agencies"] = (ObjectId(agency_id),)
    body = {
        "title": "Core Research Grant",
        "grant_number": "CRG/2026/004501",
        "created_by": "faculty:1",
        "amount": 2400000.0,
        "release_schedule": "annual",
        "links": links or None,
    }
    body.update(overrides)
    return CreateGrantUseCase(repo).execute(CreateGrantCommand(input=CreateGrantInput(**body)))


def test_create_grant_links_and_duplicate_guard():
    repo = InMemoryObjectRepository()
    project = _project(repo)
    agency = _agency(repo, name="SERB")
    out = _grant(repo, project_id=project.id, agency_id=agency.id)
    assert out.links["projects"][0]["id"] == project.id
    assert out.links["funding_agencies"][0]["object_type"] == "funding_agency"
    with pytest.raises(ObjectAlreadyExistsError):
        _grant(repo, grant_number="crg/2026/004501")


def test_grant_budget_math_and_guards():
    repo = InMemoryObjectRepository()
    grant = _grant(repo, amount=1000.0)
    gid = ObjectId(grant.id)
    AddInstallmentUseCase(repo).execute(
        AddInstallmentCommand(
            grant_id=gid, input=InstallmentInput(installment_no=1, date="2026-04-10", amount=400.0)
        )
    )
    AddInstallmentUseCase(repo).execute(
        AddInstallmentCommand(
            grant_id=gid,
            input=InstallmentInput(installment_no=2, date="2026-10-10", amount=600.0, status="scheduled"),
        )
    )
    RecordExpenditureUseCase(repo).execute(
        RecordExpenditureCommand(
            grant_id=gid,
            input=ExpenditureInput(date="2026-05-01", head="Equipment", amount=250.0, reference="PO-17"),
        )
    )
    fetched = GetGrantUseCase(repo).execute(GetGrantQuery(object_id=gid))
    assert fetched.budget == {"approved": 1000.0, "released": 400.0, "utilized": 250.0, "remaining": 750.0}
    assert [i.installment_no for i in fetched.installments] == [1, 2]
    assert fetched.expenditures[0].head == "Equipment"

    # Over-release is rejected (released installments must not exceed sanction)
    with pytest.raises(ValidationError):
        AddInstallmentUseCase(repo).execute(
            AddInstallmentCommand(
                grant_id=gid,
                input=InstallmentInput(installment_no=3, date="2026-11-01", amount=601.0),
            )
        )
    # Over-expenditure is rejected (utilized must not exceed sanction)
    with pytest.raises(ValidationError):
        RecordExpenditureUseCase(repo).execute(
            RecordExpenditureCommand(
                grant_id=gid,
                input=ExpenditureInput(date="2026-06-01", head="Travel", amount=800.0),
            )
        )


def test_list_grants_filters_and_delete_cascade():
    repo = InMemoryObjectRepository()
    project = _project(repo)
    agency = _agency(repo, name="ICMR")
    grant = _grant(repo, project_id=project.id, agency_id=agency.id, grant_number="ICMR-77")
    _grant(repo, grant_number="OTHER-1", title="Unrelated")

    by_project = ListGrantsUseCase(repo).execute(ListGrantsQuery(project_id=ObjectId(project.id)))
    assert [g.grant_number for g in by_project.items] == ["ICMR-77"]
    by_agency = ListGrantsUseCase(repo).execute(ListGrantsQuery(agency_id=ObjectId(agency.id)))
    assert by_agency.total_count == 1
    by_q = ListGrantsUseCase(repo).execute(ListGrantsQuery(q="unrelated"))
    assert [g.grant_number for g in by_q.items] == ["OTHER-1"]

    gid = ObjectId(grant.id)
    inst = AddInstallmentUseCase(repo).execute(
        AddInstallmentCommand(
            grant_id=gid, input=InstallmentInput(installment_no=1, date="2026-04-10", amount=100.0)
        )
    )
    DeleteGrantUseCase(repo).execute(DeleteGrantCommand(object_id=gid))
    assert repo.get_by_id(gid) is None
    assert repo.get_by_id(ObjectId(inst.id)) is None  # children cascade


def test_update_grant_merge_and_number_guard():
    repo = InMemoryObjectRepository()
    first = _grant(repo, title="A", grant_number="G-1")
    _grant(repo, title="B", grant_number="G-2")
    updated = UpdateGrantUseCase(repo).execute(
        UpdateGrantCommand(
            object_id=ObjectId(first.id),
            input=UpdateGrantInput(actor="faculty:1", release_schedule="milestone-based"),
        )
    )
    assert updated.release_schedule == "milestone-based"
    assert updated.grant_number == "G-1"
    with pytest.raises(ObjectAlreadyExistsError):
        UpdateGrantUseCase(repo).execute(
            UpdateGrantCommand(
                object_id=ObjectId(first.id),
                input=UpdateGrantInput(actor="faculty:1", grant_number="g-2"),
            )
        )


# ---------------------------------------------------------------------------
# Dashboard (PART 10)
# ---------------------------------------------------------------------------
def test_dashboard_cards_and_upcoming_deadlines():
    repo = InMemoryObjectRepository()
    _project(repo, title="P1", lifecycle_status="active", budget_approved=1000.0, budget_utilized=100.0)
    _project(repo, title="P2", lifecycle_status="funded", project_code="C-2", budget_approved=500.0)
    _project(repo, title="P3", lifecycle_status="completed", project_code="C-3", budget_approved=None, budget_utilized=None)
    _project(repo, title="P4", lifecycle_status="draft", project_code="C-4", budget_approved=None, budget_utilized=None)
    _grant(repo, grant_number="G-1")

    p5 = CreateProjectUseCase(repo).execute(
        CreateProjectCommand(input=_project_input(title="P5", project_code="C-5", budget_approved=None, budget_utilized=None))
    )
    AddMilestoneUseCase(repo).execute(
        AddMilestoneCommand(
            project_id=ObjectId(p5.id),
            input=MilestoneInput(title="Progress report due", date="2026-09-30", status="pending"),
        )
    )
    AddMilestoneUseCase(repo).execute(
        AddMilestoneCommand(
            project_id=ObjectId(p5.id),
            input=MilestoneInput(title="Old milestone", date="2026-01-15", status="in_progress"),
        )
    )
    AddMilestoneUseCase(repo).execute(
        AddMilestoneCommand(
            project_id=ObjectId(p5.id),
            input=MilestoneInput(title="Finished", date="2026-02-01", status="done"),
        )
    )

    dash = GetResearchDashboardUseCase(repo).execute(GetResearchDashboardQuery())
    assert dash.total_projects == 5
    assert dash.active_projects == 2  # active + funded (in-flight semantics)
    assert dash.completed_projects == 1
    assert dash.total_grants == 1
    assert dash.budget_approved == 1500.0
    assert dash.budget_utilized == 100.0
    # pending + in_progress, date order (overdue first), done excluded
    assert [d.title for d in dash.upcoming_deadlines] == ["Old milestone", "Progress report due"]
    assert dash.upcoming_deadlines[0].project_title == "P5"
