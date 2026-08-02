"""Use case: List Submissions (assignment inbox / student-history lens).

Read through a lens, never globally: an assignment's submissions for the
faculty, or a student's own submission history for the student dashboard.
``state`` narrows to ``submitted`` | ``late`` | ``graded``
(pending rows are virtual and live in the submission grid instead).
"""
from __future__ import annotations

from app.application.dtos.teaching import ListSubmissionsResult, SubmissionOutput
from app.application.exceptions import ValidationError
from app.application.queries.list_submissions import ListSubmissionsQuery
from app.application.use_cases.teaching.helpers import student_of_submission
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


class ListSubmissionsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListSubmissionsQuery) -> ListSubmissionsResult:
        if query.assignment_id is None and query.student_id is None:
            raise ValidationError(
                "Provide a lens: assignment_id (faculty inbox) or student_id (history)."
            )
        if query.page < 1 or not 1 <= query.page_size <= 100:
            raise ValidationError("page must be >= 1 and page_size between 1 and 100.")
        states = ("submitted", "late", "graded")
        if query.state is not None and query.state not in states:
            raise ValidationError(f"state must be one of: {', '.join(states)}.")

        assignment_id = str(query.assignment_id) if query.assignment_id else None
        student_id = str(query.student_id) if query.student_id else None

        outputs = []
        for submission in self._repository.find_by_type(ObjectType.SUBMISSION):
            if assignment_id is not None and assignment_id not in {
                str(oid) for oid in submission.related_ids(RelationshipKind.BELONGS_TO)
            }:
                continue
            if student_id is not None and student_id not in {
                str(oid) for oid in submission.related_ids(RelationshipKind.AUTHORED_BY)
            }:
                continue
            out = SubmissionOutput.from_domain(submission, [])
            if query.state == "graded" and out.marks is None:
                continue
            if query.state == "late" and not out.is_late:
                continue
            if query.state == "submitted" and (out.submitted_at is None or out.is_late):
                continue
            outputs.append(out)

        total_count = len(outputs)
        outputs.sort(key=lambda out: (out.submitted_at or "", out.id), reverse=True)
        start = (query.page - 1) * query.page_size
        page_items = outputs[start:start + query.page_size]

        # Denormalise students in ONE batch call (no N+1).
        raw_by_id = {str(s.id): s for s in self._repository.find_by_type(ObjectType.SUBMISSION)}
        student_ids = []
        for out in page_items:
            raw = raw_by_id.get(out.id)
            sid = student_of_submission(raw) if raw is not None else None
            if sid is not None:
                student_ids.append(sid)
        student_by_id = {str(s.id): s for s in self._repository.find_by_ids(student_ids)}

        items = []
        for out in page_items:
            raw = raw_by_id[out.id]
            sid = student_of_submission(raw)
            items.append(
                SubmissionOutput.from_domain(
                    raw, [], student=student_by_id.get(str(sid)) if sid is not None else None
                )
            )
        return ListSubmissionsResult(
            items=items, total_count=total_count, page=query.page, page_size=query.page_size
        )
