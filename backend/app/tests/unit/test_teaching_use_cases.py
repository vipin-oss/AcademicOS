"""Unit tests for the Teaching use cases (no framework deps required).

Mirrors ``test_publication_use_cases.py``: an in-memory ``ObjectRepository``
plus a fake ``FileStorage`` exercise the whole slice — classes, enrollment,
assignments, submissions, marks CSV, attendance, gradebook, report and
dashboard — without any database, filesystem, network, or HTTP.
"""
from __future__ import annotations

import pytest

from app.application.commands.attach_assignment_file import AttachAssignmentFileCommand
from app.application.commands.create_assignment import CreateAssignmentCommand
from app.application.commands.create_class import CreateClassCommand
from app.application.commands.create_student import CreateStudentCommand
from app.application.commands.delete_assignment import DeleteAssignmentCommand
from app.application.commands.delete_class import DeleteClassCommand
from app.application.commands.delete_submission import DeleteSubmissionCommand
from app.application.commands.enroll_from_csv import EnrollFromCsvCommand
from app.application.commands.enroll_students import EnrollStudentsCommand
from app.application.commands.grade_submission import GradeSubmissionCommand
from app.application.commands.import_attendance_csv import ImportAttendanceCsvCommand
from app.application.commands.import_marks_csv import ImportMarksCsvCommand
from app.application.commands.record_attendance import RecordAttendanceCommand
from app.application.commands.submit_to_assignment import SubmitToAssignmentCommand
from app.application.commands.unenroll_student import UnenrollStudentCommand
from app.application.commands.update_assignment import UpdateAssignmentCommand
from app.application.commands.update_class import UpdateClassCommand
from app.application.dtos.student import CreateStudentInput
from app.application.dtos.teaching import (
    CreateAssignmentInput,
    CreateClassInput,
    UpdateAssignmentInput,
    UpdateClassInput,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.file_storage import FileStorage
from app.application.queries.get_attendance_summary import GetAttendanceSummaryQuery
from app.application.queries.get_class import GetClassQuery
from app.application.queries.get_class_report import GetClassReportQuery
from app.application.queries.get_gradebook import GetGradebookQuery
from app.application.queries.get_roster import GetRosterQuery
from app.application.queries.get_submission_grid import GetSubmissionGridQuery
from app.application.queries.get_teaching_dashboard import GetTeachingDashboardQuery
from app.application.queries.list_assignments import ListAssignmentsQuery
from app.application.queries.list_attendance import ListAttendanceQuery
from app.application.queries.list_classes import ListClassesQuery
from app.application.queries.list_submissions import ListSubmissionsQuery
from app.application.use_cases.students.create_student import CreateStudentUseCase
from app.application.use_cases.teaching.attach_assignment_file import (
    AttachAssignmentFileUseCase,
)
from app.application.use_cases.teaching.attendance_summary import (
    GetAttendanceSummaryUseCase,
)
from app.application.use_cases.teaching.create_assignment import CreateAssignmentUseCase
from app.application.use_cases.teaching.create_class import CreateClassUseCase
from app.application.use_cases.teaching.delete_assignment import DeleteAssignmentUseCase
from app.application.use_cases.teaching.delete_class import DeleteClassUseCase
from app.application.use_cases.teaching.delete_submission import DeleteSubmissionUseCase
from app.application.use_cases.teaching.enroll_from_csv import EnrollFromCsvUseCase
from app.application.use_cases.teaching.enroll_students import EnrollStudentsUseCase
from app.application.use_cases.teaching.get_class import GetClassUseCase
from app.application.use_cases.teaching.get_class_report import GetClassReportUseCase
from app.application.use_cases.teaching.get_gradebook import GetGradebookUseCase
from app.application.use_cases.teaching.get_submission_grid import (
    GetSubmissionGridUseCase,
)
from app.application.use_cases.teaching.get_teaching_dashboard import (
    GetTeachingDashboardUseCase,
)
from app.application.use_cases.teaching.grade_submission import GradeSubmissionUseCase
from app.application.use_cases.teaching.import_attendance_csv import (
    ImportAttendanceCsvUseCase,
)
from app.application.use_cases.teaching.import_marks_csv import ImportMarksCsvUseCase
from app.application.use_cases.teaching.list_assignments import ListAssignmentsUseCase
from app.application.use_cases.teaching.list_attendance import ListAttendanceUseCase
from app.application.use_cases.teaching.list_classes import ListClassesUseCase
from app.application.use_cases.teaching.list_submissions import ListSubmissionsUseCase
from app.application.use_cases.teaching.record_attendance import RecordAttendanceUseCase
from app.application.use_cases.teaching.roster import GetRosterUseCase
from app.application.use_cases.teaching.submit_to_assignment import (
    SubmitToAssignmentUseCase,
)
from app.application.use_cases.teaching.unenroll_student import UnenrollStudentUseCase
from app.application.use_cases.teaching.update_assignment import UpdateAssignmentUseCase
from app.application.use_cases.teaching.update_class import UpdateClassUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    ObjectStatus,
    ObjectType,
    RelationshipKind,
)
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
        if obj is None:
            return []
        return obj.related_ids(kind)

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
            "id", "object_type", "title", "status", "version",
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
            elif effective_sort == "title":
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


# --------------------------------------------------------------------------- factories
@pytest.fixture()
def repo():
    return InMemoryObjectRepository()


@pytest.fixture()
def storage():
    return InMemoryFileStorage()


def _faculty(repo, title="Dr. Rao"):
    obj = UniversalObject.create(ObjectType.FACULTY, title, created_by="admin")
    obj.pop_domain_events()
    repo.save(obj)
    return obj


def _student(repo, name, roll):
    return CreateStudentUseCase(repo).execute(
        CreateStudentCommand(
            input=CreateStudentInput(
                name=name,
                created_by="faculty:1",
                student_type="ug",
                roll_number=roll,
                status=ObjectStatus.ACTIVE,
            )
        )
    )


def _class(repo, title="Computer Fundamentals", **overrides):
    data = {
        "title": title,
        "created_by": "faculty:1",
        "status": ObjectStatus.ACTIVE,
        "programme": "BSc Mathematics with Data Science",
        "semester": 1,
        "section": "A",
        "session": "2026-27",
        "credits": 4.0,
    }
    data.update(overrides)
    return CreateClassUseCase(repo).execute(CreateClassCommand(input=CreateClassInput(**data)))


def _assignment(repo, class_id, title="Assignment 1", **overrides):
    data = {
        "title": title,
        "class_id": ObjectId.parse(class_id),
        "created_by": "faculty:1",
        "status": ObjectStatus.ACTIVE,
        "max_marks": 20.0,
    }
    data.update(overrides)
    return CreateAssignmentUseCase(repo).execute(
        CreateAssignmentCommand(input=CreateAssignmentInput(**data))
    )


# --------------------------------------------------------------------------- classes
def test_create_class_with_links_and_initial_enrollment(repo):
    teacher = _faculty(repo)
    s1 = _student(repo, "Asha Verma", "101")
    out = _class(
        repo,
        links={"teachers": (teacher.id,)},
        students=(ObjectId.parse(s1.id),),
        weekly_schedule=({"day": "mon", "start": "09:00", "end": "10:00"},),
        room="LH-2",
        class_mode="offline",
    )
    assert out.title == "Computer Fundamentals"
    assert out.student_count == 1
    assert [link["id"] for link in out.links["teachers"]] == [str(teacher.id)]
    assert out.weekly_schedule == [{"day": "mon", "start": "09:00", "end": "10:00"}]

    # enrollment edge lives ON the student object
    student = repo.get_by_id(ObjectId.parse(s1.id))
    assert str(out.id) in {
        str(oid) for oid in student.related_ids(RelationshipKind.ENROLLED_IN)
    }
    roster = GetRosterUseCase(repo).execute(GetRosterQuery(class_id=ObjectId.parse(out.id)))
    assert [r.name for r in roster] == ["Asha Verma"]


def test_get_class_rejects_non_class(repo):
    teacher = _faculty(repo)
    with pytest.raises(ObjectNotFoundError):
        GetClassUseCase(repo).execute(GetClassQuery(object_id=teacher.id))


def test_update_class_partial_and_teacher_merge(repo):
    t1, t2 = _faculty(repo, "Dr. Rao"), _faculty(repo, "Dr. Bose")
    out = _class(repo, links={"teachers": (t1.id,)})
    updated = UpdateClassUseCase(repo).execute(
        UpdateClassCommand(
            object_id=ObjectId.parse(out.id),
            input=UpdateClassInput(
                actor="faculty:1", room="LH-9", links={"teachers": (t2.id,)}
            ),
        )
    )
    assert updated.room == "LH-9"
    assert updated.programme == "BSc Mathematics with Data Science"  # untouched
    assert [link["id"] for link in updated.links["teachers"]] == [str(t2.id)]


def test_list_classes_filters_q_session_and_lenses(repo):
    c1 = _class(repo, "Computer Fundamentals")
    _class(repo, "Linear Algebra", session="2025-26")
    s1 = _student(repo, "Asha", "101")
    EnrollStudentsUseCase(repo).execute(
        EnrollStudentsCommand(class_id=ObjectId.parse(c1.id), student_ids=(ObjectId.parse(s1.id),))
    )
    listing = ListClassesUseCase(repo)
    assert listing.execute(ListClassesQuery()).total_count == 2
    assert listing.execute(ListClassesQuery(session="2025-26")).total_count == 1
    assert listing.execute(ListClassesQuery(q="computer")).total_count == 1
    lens = listing.execute(ListClassesQuery(object_id=ObjectId.parse(s1.id)))
    assert lens.total_count == 1 and lens.items[0].title == "Computer Fundamentals"
    assert lens.items[0].student_count == 1


# --------------------------------------------------------------------------- enrollment
def test_enroll_is_idempotent_and_reports_unknown(repo):
    cls = _class(repo)
    s1 = _student(repo, "Asha", "101")
    use_case = EnrollStudentsUseCase(repo)
    first = use_case.execute(
        EnrollStudentsCommand(class_id=ObjectId.parse(cls.id), student_ids=(ObjectId.parse(s1.id),))
    )
    assert first.enrolled == [s1.id]
    second = use_case.execute(
        EnrollStudentsCommand(
            class_id=ObjectId.parse(cls.id),
            student_ids=(ObjectId.parse(s1.id), ObjectId.generate(ObjectType.STUDENT)),
        )
    )
    assert second.already_enrolled == [s1.id]
    assert len(second.errors) == 1  # the ghost id


def test_unenroll_removes_edge_and_validates(repo):
    cls = _class(repo)
    s1 = _student(repo, "Asha", "101")
    enroll = EnrollStudentsUseCase(repo)
    enroll.execute(
        EnrollStudentsCommand(class_id=ObjectId.parse(cls.id), student_ids=(ObjectId.parse(s1.id),))
    )
    UnenrollStudentUseCase(repo).execute(
        UnenrollStudentCommand(
            class_id=ObjectId.parse(cls.id), student_id=ObjectId.parse(s1.id)
        )
    )
    assert GetRosterUseCase(repo).execute(GetRosterQuery(class_id=ObjectId.parse(cls.id))) == []
    with pytest.raises(ValidationError):
        UnenrollStudentUseCase(repo).execute(
            UnenrollStudentCommand(
                class_id=ObjectId.parse(cls.id), student_id=ObjectId.parse(s1.id)
            )
        )


def test_enroll_csv_resolves_roll_and_email_with_row_errors(repo):
    cls = _class(repo)
    _student(repo, "Asha Verma", "101")
    s2 = CreateStudentUseCase(repo).execute(
        CreateStudentCommand(
            input=CreateStudentInput(
                name="Ravi Kumar", created_by="f:1", student_type="ug",
                roll_number="102", email="ravi@u.edu",
            )
        )
    )
    result = EnrollFromCsvUseCase(repo).execute(
        EnrollFromCsvCommand(
            class_id=ObjectId.parse(cls.id),
            text="Roll No,Email\n101,\n,ravi@u.edu\n999,ghost@u.edu\n",
        )
    )
    assert len(result.enrolled) == 2
    assert len(result.errors) == 1 and result.errors[0]["roll_number"] == "999"
    roster = GetRosterUseCase(repo).execute(GetRosterQuery(class_id=ObjectId.parse(cls.id)))
    assert {r.name for r in roster} == {"Asha Verma", "Ravi Kumar"}
    assert s2.id in {r.student_id for r in roster}


# --------------------------------------------------------------------------- assignments
def test_create_assignment_metadata_and_edges(repo):
    cls = _class(repo)
    out = _assignment(
        repo,
        cls.id,
        description="Week 1 worksheet",
        deadline="2026-09-15",
        late_allowed=True,
        assignment_type="quiz",
        weightage=25.0,
        rubric=({"criterion": "Correctness", "marks": 15}, {"criterion": "Style", "marks": 5}),
    )
    assert out.class_id == cls.id
    assert out.class_title == "Computer Fundamentals"
    assert out.assignment_type == "quiz"
    assert out.max_marks == 20.0
    assert out.late_allowed is True
    assert [r["criterion"] for r in out.rubric] == ["Correctness", "Style"]
    stored = repo.get_by_id(ObjectId.parse(out.id))
    assert cls.id in {str(oid) for oid in stored.related_ids(RelationshipKind.BELONGS_TO)}


def test_assignment_validation_rejects_bad_input(repo):
    cls = _class(repo)
    with pytest.raises(ValidationError):  # unknown type
        _assignment(repo, cls.id, assignment_type="homework")
    with pytest.raises(ValidationError):  # weightage out of range
        _assignment(repo, cls.id, weightage=250.0)
    with pytest.raises(ValidationError):  # bad deadline format
        _assignment(repo, cls.id, deadline="15-09-2026")
    with pytest.raises(ObjectNotFoundError):  # ghost class
        _assignment(repo, str(ObjectId.generate(ObjectType.COURSE)))


def test_update_assignment_partial(repo):
    cls = _class(repo)
    out = _assignment(repo, cls.id)
    updated = UpdateAssignmentUseCase(repo).execute(
        UpdateAssignmentCommand(
            object_id=ObjectId.parse(out.id),
            input=UpdateAssignmentInput(
                actor="faculty:1", max_marks=30.0, late_allowed=True, visibility="hidden"
            ),
        )
    )
    assert updated.max_marks == 30.0
    assert updated.late_allowed is True
    assert updated.visibility == "hidden"
    assert updated.title == "Assignment 1"  # untouched


def test_list_assignments_class_lens_and_filters(repo):
    c1, c2 = _class(repo, "CF"), _class(repo, "Linear Algebra")
    _assignment(repo, c1.id, "Worksheet 1")
    _assignment(repo, c1.id, "Quiz 1", assignment_type="quiz")
    _assignment(repo, c2.id, "Other Class Work")
    listing = ListAssignmentsUseCase(repo)
    assert listing.execute(ListAssignmentsQuery()).total_count == 3
    assert listing.execute(
        ListAssignmentsQuery(class_id=ObjectId.parse(c1.id))
    ).total_count == 2
    assert listing.execute(
        ListAssignmentsQuery(object_id=ObjectId.parse(c2.id))
    ).total_count == 1
    assert listing.execute(
        ListAssignmentsQuery(class_id=ObjectId.parse(c1.id), assignment_type="quiz")
    ).total_count == 1


def test_attach_assignment_file_and_replace(repo, storage):
    cls = _class(repo)
    out = _assignment(repo, cls.id)
    use_case = AttachAssignmentFileUseCase(repo, storage)
    first = use_case.execute(
        AttachAssignmentFileCommand(
            object_id=ObjectId.parse(out.id),
            file_name="questions.pdf",
            content=b"pdf-1",
            mime_type="application/pdf",
        )
    )
    assert first.attachment_file_name == "questions.pdf"
    assert first.attachment_file_size == 5
    assert storage.exists(first.attachment_file_path)
    second = use_case.execute(
        AttachAssignmentFileCommand(
            object_id=ObjectId.parse(out.id),
            file_name="questions-v2.pdf",
            content=b"pdf-2",
            mime_type="application/pdf",
        )
    )
    assert not storage.exists(first.attachment_file_path)  # old blob removed
    assert storage.exists(second.attachment_file_path)
    with pytest.raises(ValidationError):
        use_case.execute(
            AttachAssignmentFileCommand(
                object_id=ObjectId.parse(out.id),
                file_name="x.pdf", content=b"", mime_type="application/pdf",
            )
        )


# --------------------------------------------------------------------------- submissions
def _enrolled_class_with_students(repo, rolls):
    cls = _class(repo)
    students = [_student(repo, f"Student {roll}", roll) for roll in rolls]
    EnrollStudentsUseCase(repo).execute(
        EnrollStudentsCommand(
            class_id=ObjectId.parse(cls.id),
            student_ids=tuple(ObjectId.parse(s.id) for s in students),
        )
    )
    return cls, students


def test_submit_creates_single_submission_with_system_facts(repo, storage):
    cls, (s1, _) = _enrolled_class_with_students(repo, ["101", "102"])
    assignment = _assignment(repo, cls.id, deadline="2999-01-01")
    out = SubmitToAssignmentUseCase(repo, storage).execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
            file_name="answer.pdf",
            content=b"work",
            mime_type="application/pdf",
            comments="Please review Q3.",
        )
    )
    assert out.assignment_id == assignment.id
    assert out.student_id == s1.id
    assert out.student_roll == "101"
    assert out.submitted_at is not None
    assert out.is_late is False
    assert out.file_size == 4
    assert out.comments == "Please review Q3."
    stored = repo.get_by_id(ObjectId.parse(out.id))
    assert assignment.id in {str(oid) for oid in stored.related_ids(RelationshipKind.BELONGS_TO)}
    assert s1.id in {str(oid) for oid in stored.related_ids(RelationshipKind.AUTHORED_BY)}


def test_submit_late_marked_when_allowed(repo, storage):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    assignment = _assignment(repo, cls.id, deadline="2020-01-01", late_allowed=True)
    out = SubmitToAssignmentUseCase(repo, storage).execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
            comments="sorry, late",
        )
    )
    assert out.is_late is True


def test_submit_late_rejected_when_not_allowed(repo, storage):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    assignment = _assignment(repo, cls.id, deadline="2020-01-01", late_allowed=False)
    with pytest.raises(ValidationError):
        SubmitToAssignmentUseCase(repo, storage).execute(
            SubmitToAssignmentCommand(
                assignment_id=ObjectId.parse(assignment.id),
                student_id=ObjectId.parse(s1.id),
            )
        )


def test_resubmit_keeps_one_object_and_bumps_version(repo, storage):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    assignment = _assignment(repo, cls.id, deadline="2999-01-01")
    use_case = SubmitToAssignmentUseCase(repo, storage)
    first = use_case.execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
            file_name="v1.pdf", content=b"v1",
        )
    )
    second = use_case.execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
            file_name="v2.pdf", content=b"v2!",
        )
    )
    assert second.id == first.id
    assert second.version > first.version
    assert not storage.exists(first.file_path)  # replaced blob removed
    assert storage.read(second.file_path) == b"v2!"
    # still exactly ONE submission for the pair
    listing = ListSubmissionsUseCase(repo).execute(
        ListSubmissionsQuery(assignment_id=ObjectId.parse(assignment.id))
    )
    assert listing.total_count == 1


def test_grade_submission_marks_feedback_and_rubric_total(repo, storage):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    assignment = _assignment(repo, cls.id, deadline="2999-01-01")
    submission = SubmitToAssignmentUseCase(repo, storage).execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
        )
    )
    graded = GradeSubmissionUseCase(repo).execute(
        GradeSubmissionCommand(
            object_id=ObjectId.parse(submission.id),
            marks=17.5,
            faculty_feedback="Good work",
            actor="faculty:1",
        )
    )
    assert graded.marks == 17.5
    assert graded.faculty_feedback == "Good work"
    assert graded.graded_at is not None
    assert graded.graded_by == "faculty:1"

    rubric_graded = GradeSubmissionUseCase(repo).execute(
        GradeSubmissionCommand(
            object_id=ObjectId.parse(submission.id),
            rubric_score=(
                {"criterion": "Correctness", "marks_awarded": 12},
                {"criterion": "Style", "marks_awarded": 4},
            ),
            actor="faculty:1",
        )
    )
    assert rubric_graded.marks == 16.0  # rubric total becomes marks
    assert len(rubric_graded.rubric_score) == 2


def test_grade_rejects_marks_above_assignment_max(repo, storage):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    assignment = _assignment(repo, cls.id, max_marks=20.0)
    submission = SubmitToAssignmentUseCase(repo, storage).execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
        )
    )
    with pytest.raises(ValidationError):
        GradeSubmissionUseCase(repo).execute(
            GradeSubmissionCommand(object_id=ObjectId.parse(submission.id), marks=25.0)
        )


def test_delete_submission_removes_blob(repo, storage):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    assignment = _assignment(repo, cls.id)
    submission = SubmitToAssignmentUseCase(repo, storage).execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
            file_name="a.pdf", content=b"x",
        )
    )
    path = submission.file_path
    DeleteSubmissionUseCase(repo, storage).execute(
        DeleteSubmissionCommand(object_id=ObjectId.parse(submission.id))
    )
    assert repo.get_by_id(ObjectId.parse(submission.id)) is None
    assert not storage.exists(path)


def test_submission_grid_states_and_counts(repo, storage):
    cls, (s1, s2, s3) = _enrolled_class_with_students(repo, ["101", "102", "103"])
    assignment = _assignment(repo, cls.id, deadline="2999-01-01", late_allowed=True)
    submit = SubmitToAssignmentUseCase(repo, storage)
    sub1 = submit.execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id), student_id=ObjectId.parse(s1.id)
        )
    )
    late_assignment = _assignment(
        repo, cls.id, "Late One", deadline="2020-01-01", late_allowed=True
    )
    submit.execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(late_assignment.id),
            student_id=ObjectId.parse(s2.id),
        )
    )
    grid = GetSubmissionGridUseCase(repo).execute(
        GetSubmissionGridQuery(assignment_id=ObjectId.parse(assignment.id))
    )
    states = {row.student_roll: row.state for row in grid.rows}
    assert states == {"101": "submitted", "102": "pending", "103": "pending"}
    assert (grid.submitted_count, grid.pending_count, grid.graded_count) == (1, 2, 0)

    GradeSubmissionUseCase(repo).execute(
        GradeSubmissionCommand(object_id=ObjectId.parse(sub1.id), marks=18.0)
    )
    grid = GetSubmissionGridUseCase(repo).execute(
        GetSubmissionGridQuery(assignment_id=ObjectId.parse(assignment.id))
    )
    states = {row.student_roll: row.state for row in grid.rows}
    assert states["101"] == "graded"
    assert grid.graded_count == 1

    late_grid = GetSubmissionGridUseCase(repo).execute(
        GetSubmissionGridQuery(assignment_id=ObjectId.parse(late_assignment.id))
    )
    assert {r.student_roll: r.state for r in late_grid.rows}["102"] == "late"
    assert late_grid.late_count == 1
    _ = s3


# --------------------------------------------------------------------------- marks CSV
def test_import_marks_csv_creates_and_grades_submissions(repo):
    cls, (s1, s2) = _enrolled_class_with_students(repo, ["101", "102"])
    assignment = _assignment(repo, cls.id, max_marks=20.0)
    result = ImportMarksCsvUseCase(repo).execute(
        ImportMarksCsvCommand(
            assignment_id=ObjectId.parse(assignment.id),
            text="Roll No,Marks,Feedback\n101,18,Great\n102,n/a,\n999,10,\n",
        )
    )
    assert len(result.graded) == 1
    assert len(result.created_submissions) == 1  # created on the fly
    assert len(result.errors) == 2  # non-numeric marks + unknown roll
    listing = ListSubmissionsUseCase(repo).execute(
        ListSubmissionsQuery(assignment_id=ObjectId.parse(assignment.id))
    )
    assert listing.total_count == 1
    assert listing.items[0].marks == 18.0
    assert listing.items[0].faculty_feedback == "Great"
    _ = (s1, s2)


def test_import_marks_csv_enforces_max_marks_per_row(repo):
    cls, _ = _enrolled_class_with_students(repo, ["101"])
    assignment = _assignment(repo, cls.id, max_marks=10.0)
    result = ImportMarksCsvUseCase(repo).execute(
        ImportMarksCsvCommand(
            assignment_id=ObjectId.parse(assignment.id),
            text="Roll No,Marks\n101,15\n",
        )
    )
    assert result.graded == []
    assert "maximum" in result.errors[0]["message"]


# --------------------------------------------------------------------------- attendance
def test_record_attendance_upserts_one_session_per_class_date(repo):
    cls, (s1, s2) = _enrolled_class_with_students(repo, ["101", "102"])
    use_case = RecordAttendanceUseCase(repo)
    first = use_case.execute(
        RecordAttendanceCommand(
            class_id=ObjectId.parse(cls.id),
            session_date="2026-08-03",
            records={s1.id: "present", s2.id: "absent"},
        )
    )
    second = use_case.execute(
        RecordAttendanceCommand(
            class_id=ObjectId.parse(cls.id),
            session_date="2026-08-03",
            records={s1.id: "late", s2.id: "present"},
        )
    )
    assert second.id == first.id  # upsert — no duplicate session
    sessions = ListAttendanceUseCase(repo).execute(
        ListAttendanceQuery(class_id=ObjectId.parse(cls.id))
    )
    assert len(sessions) == 1
    assert sessions[0].records == {s1.id: "late", s2.id: "present"}


def test_record_attendance_rejects_non_enrolled_ids(repo):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    ghost = ObjectId.generate(ObjectType.STUDENT)
    with pytest.raises(ValidationError):
        RecordAttendanceUseCase(repo).execute(
            RecordAttendanceCommand(
                class_id=ObjectId.parse(cls.id),
                session_date="2026-08-03",
                records={s1.id: "present", str(ghost): "present"},
            )
        )


def test_record_attendance_validates_date_and_states(repo):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    use_case = RecordAttendanceUseCase(repo)
    with pytest.raises(ValidationError):
        use_case.execute(
            RecordAttendanceCommand(
                class_id=ObjectId.parse(cls.id),
                session_date="03-08-2026",
                records={s1.id: "present"},
            )
        )
    with pytest.raises(ValidationError):
        use_case.execute(
            RecordAttendanceCommand(
                class_id=ObjectId.parse(cls.id),
                session_date="2026-08-03",
                records={s1.id: "sleeping"},
            )
        )


def test_attendance_summary_counts_and_threshold(repo):
    cls, (s1, s2) = _enrolled_class_with_students(repo, ["101", "102"])
    record = RecordAttendanceUseCase(repo)
    record.execute(
        RecordAttendanceCommand(
            class_id=ObjectId.parse(cls.id),
            session_date="2026-08-03",
            records={s1.id: "present", s2.id: "absent"},
        )
    )
    record.execute(
        RecordAttendanceCommand(
            class_id=ObjectId.parse(cls.id),
            session_date="2026-08-04",
            records={s1.id: "late"},  # s2 has NO record -> counted absent
        )
    )
    summary = GetAttendanceSummaryUseCase(repo).execute(
        GetAttendanceSummaryQuery(class_id=ObjectId.parse(cls.id), threshold=75.0)
    )
    assert summary.session_count == 2
    rows = {r.student_roll: r for r in summary.rows}
    assert rows["101"].effective_present == 2
    assert rows["101"].percentage == 100.0
    assert rows["101"].below_threshold is False
    assert rows["102"].present == 0
    assert rows["102"].absent == 2
    assert rows["102"].percentage == 0.0
    assert rows["102"].below_threshold is True


def test_import_attendance_csv_applies_and_reports(repo):
    cls, (s1, _) = _enrolled_class_with_students(repo, ["101", "102"])
    result = ImportAttendanceCsvUseCase(repo).execute(
        ImportAttendanceCsvCommand(
            class_id=ObjectId.parse(cls.id),
            session_date="2026-08-03",
            text="Roll No,Status\n101,P\n102,ML\n999,A\n",
        )
    )
    assert sorted(result.applied) == sorted([s1.id, _enroll_roll(repo, "102")])
    assert len(result.unknown) == 1
    summary = GetAttendanceSummaryUseCase(repo).execute(
        GetAttendanceSummaryQuery(class_id=ObjectId.parse(cls.id))
    )
    rows = {r.student_roll: r for r in summary.rows}
    assert rows["101"].present == 1
    assert rows["102"].medical_leave == 1


def _enroll_roll(repo, roll):
    for student in repo.find_by_type(ObjectType.STUDENT):
        if student.metadata.get_value("roll_number") == roll:
            return str(student.id)
    raise AssertionError("roll not found")


# --------------------------------------------------------------------------- gradebook
def test_gradebook_weighted_totals_and_grade(repo):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    a1 = _assignment(repo, cls.id, "A1", max_marks=20.0, weightage=50.0)
    q1 = _assignment(repo, cls.id, "Quiz", assignment_type="quiz", max_marks=10.0,
                     weightage=50.0)
    end = _assignment(repo, cls.id, "End Sem", assignment_type="end_semester",
                      max_marks=100.0, weightage=100.0)
    def grade(sub_id, marks):
        return GradeSubmissionUseCase(repo).execute(
            GradeSubmissionCommand(object_id=sub_id, marks=marks)
        )
    for assignment, marks in ((a1, 18.0), (q1, 8.0), (end, 70.0)):
        submission = SubmitToAssignmentUseCase(repo, InMemoryFileStorage()).execute(
            SubmitToAssignmentCommand(
                assignment_id=ObjectId.parse(assignment.id),
                student_id=ObjectId.parse(s1.id),
            )
        )
        grade(ObjectId.parse(submission.id), marks)

    book = GetGradebookUseCase(repo).execute(GetGradebookQuery(class_id=ObjectId.parse(cls.id)))
    assert [h["title"] for h in book.assignments] == ["A1", "End Sem", "Quiz"]
    (row,) = book.rows
    assert row.internal_total == 85.0  # (90*50 + 80*50) / 100
    assert row.average_percent == 77.5  # (90*50 + 80*50 + 70*100) / 200
    assert row.grade == "B+"
    assert [c.marks for c in row.cells] == [18.0, 70.0, 8.0]


def test_gradebook_falls_back_to_max_marks_weighting(repo):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    a1 = _assignment(repo, cls.id, "A1", max_marks=100.0)
    a2 = _assignment(repo, cls.id, "A2", max_marks=50.0)
    submit = SubmitToAssignmentUseCase(repo, InMemoryFileStorage())
    for assignment, marks in ((a1, 80.0), (a2, 40.0)):
        sub = submit.execute(
            SubmitToAssignmentCommand(
                assignment_id=ObjectId.parse(assignment.id), student_id=ObjectId.parse(s1.id)
            )
        )
        GradeSubmissionUseCase(repo).execute(
            GradeSubmissionCommand(object_id=ObjectId.parse(sub.id), marks=marks)
        )
    book = GetGradebookUseCase(repo).execute(GetGradebookQuery(class_id=ObjectId.parse(cls.id)))
    (row,) = book.rows
    assert row.average_percent == 80.0  # marks-weighted: (80*100 + 80*50)/150
    assert row.grade == "A"


# --------------------------------------------------------------------------- report + dashboard
def test_class_report_composes_everything(repo):
    cls, (s1, s2) = _enrolled_class_with_students(repo, ["101", "102"])
    assignment = _assignment(repo, cls.id, max_marks=100.0, weightage=100.0)
    submit = SubmitToAssignmentUseCase(repo, InMemoryFileStorage())
    grade = GradeSubmissionUseCase(repo)
    for student, marks in ((s1, 92.0), (s2, 25.0)):
        sub = submit.execute(
            SubmitToAssignmentCommand(
                assignment_id=ObjectId.parse(assignment.id),
                student_id=ObjectId.parse(student.id),
            )
        )
        grade.execute(GradeSubmissionCommand(object_id=ObjectId.parse(sub.id), marks=marks))
    RecordAttendanceUseCase(repo).execute(
        RecordAttendanceCommand(
            class_id=ObjectId.parse(cls.id),
            session_date="2026-08-03",
            records={s1.id: "present", s2.id: "absent"},
        )
    )
    report = GetClassReportUseCase(repo).execute(
        GetClassReportQuery(class_id=ObjectId.parse(cls.id))
    )
    assert report.class_info.title == "Computer Fundamentals"
    assert len(report.roster) == 2
    assert len(report.assignment_stats) == 1
    stat = report.assignment_stats[0]
    assert (stat.submitted, stat.graded, stat.pending) == (2, 2, 0)
    assert report.average_marks_percent == 58.5
    assert {w["roll_number"] for w in report.weak_students} == {"102"}
    assert "average marks below 40%" in report.weak_students[0]["reasons"][0]
    assert {t["roll_number"] for t in report.top_performers} == {"101"}
    assert len(report.gradebook.rows) == 2
    assert report.attendance.session_count == 1


def test_teaching_dashboard_aggregates_across_classes(repo):
    c1, (s1,) = _enrolled_class_with_students(repo, ["101"])
    c2, (s2,) = _enrolled_class_with_students(repo, ["201"])
    _assignment(repo, c1.id, "A1", max_marks=100.0)
    submit = SubmitToAssignmentUseCase(repo, InMemoryFileStorage())
    a1 = ListAssignmentsUseCase(repo).execute(
        ListAssignmentsQuery(class_id=ObjectId.parse(c1.id))
    ).items[0]
    sub = submit.execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(a1.id), student_id=ObjectId.parse(s1.id)
        )
    )
    GradeSubmissionUseCase(repo).execute(
        GradeSubmissionCommand(object_id=ObjectId.parse(sub.id), marks=95.0)
    )
    dashboard = GetTeachingDashboardUseCase(repo).execute(GetTeachingDashboardQuery())
    assert dashboard.class_count == 2
    assert dashboard.student_count == 2
    assert dashboard.assignment_count == 1
    assert dashboard.graded_submissions == 1
    assert dashboard.pending_submissions == 0  # the one assignment is submitted
    assert dashboard.average_marks_percent == 95.0
    assert [t["roll_number"] for t in dashboard.top_performers] == ["101"]
    assert len(dashboard.classes) == 2
    _ = (c2, s2)


# --------------------------------------------------------------------------- cascades
def test_delete_assignment_cascades_submissions_and_blobs(repo, storage):
    cls, (s1,) = _enrolled_class_with_students(repo, ["101"])
    assignment = _assignment(repo, cls.id)
    AttachAssignmentFileUseCase(repo, storage).execute(
        AttachAssignmentFileCommand(
            object_id=ObjectId.parse(assignment.id),
            file_name="q.pdf", content=b"q", mime_type="application/pdf",
        )
    )
    sub = SubmitToAssignmentUseCase(repo, storage).execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
            file_name="s.pdf", content=b"s",
        )
    )
    sub_path = sub.file_path
    result = DeleteAssignmentUseCase(repo, storage).execute(
        DeleteAssignmentCommand(object_id=ObjectId.parse(assignment.id))
    )
    assert result["submissions"] == 1
    assert repo.get_by_id(ObjectId.parse(assignment.id)) is None
    assert repo.get_by_id(ObjectId.parse(sub.id)) is None
    assert not storage.exists(sub_path)


def test_delete_class_cascades_and_unenrolls(repo, storage):
    cls = _class(repo)
    s1 = _student(repo, "Asha", "101")
    EnrollStudentsUseCase(repo).execute(
        EnrollStudentsCommand(class_id=ObjectId.parse(cls.id), student_ids=(ObjectId.parse(s1.id),))
    )
    assignment = _assignment(repo, cls.id)
    sub = SubmitToAssignmentUseCase(repo, storage).execute(
        SubmitToAssignmentCommand(
            assignment_id=ObjectId.parse(assignment.id),
            student_id=ObjectId.parse(s1.id),
            file_name="s.pdf", content=b"s",
        )
    )
    RecordAttendanceUseCase(repo).execute(
        RecordAttendanceCommand(
            class_id=ObjectId.parse(cls.id),
            session_date="2026-08-03",
            records={s1.id: "present"},
        )
    )
    sub_path = sub.file_path
    result = DeleteClassUseCase(repo, storage).execute(
        DeleteClassCommand(object_id=ObjectId.parse(cls.id))
    )
    assert result["assignments"] == 1
    assert result["submissions"] == 1
    assert result["attendance_sessions"] == 1
    assert result["unenrolled_students"] == 1
    assert repo.get_by_id(ObjectId.parse(cls.id)) is None
    assert repo.get_by_id(ObjectId.parse(assignment.id)) is None
    assert not storage.exists(sub_path)
    # student survives, roster edge gone
    student = repo.get_by_id(ObjectId.parse(s1.id))
    assert student is not None
    assert student.related_ids(RelationshipKind.ENROLLED_IN) == []
