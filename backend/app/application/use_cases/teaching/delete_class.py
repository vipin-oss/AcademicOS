"""Use case: Delete a Class (cascade — evidence is never silently orphaned).

Deleting a Class cascade-deletes, and reports, everything the class owns:
  - its Assignment Objects (with their attachment blobs),
  - every Submission Object of those assignments (with file blobs),
  - its AttendanceSession Objects,
  - the ENROLLED_IN edges written on the Student Objects (the roster dies
    with the class; the Students themselves are untouched).

Mirrors ``DeletePublicationUseCase``: hard delete via the frozen repository;
blob removal through the ``FileStorage`` port is best-effort.
"""
from __future__ import annotations

from app.application.commands.delete_class import DeleteClassCommand
from app.application.dtos.teaching import KEY_ATTACHMENT_PATH, KEY_FILE_PATH
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.file_storage import FileStorage
from app.application.services.graph_integrity import assert_no_inbound_edges
from app.application.use_cases.teaching.helpers import (
    assignments_of_class,
    attendance_sessions_of_class,
    enrolled_students,
    submissions_of_assignment,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, Provenance, RelationshipKind


class DeleteClassUseCase:
    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, command: DeleteClassCommand) -> dict:
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {command.object_id} not found.")

        class_id = str(obj.id)
        deleted = {
            "class_id": class_id,
            "assignments": 0,
            "submissions": 0,
            "attendance_sessions": 0,
            "unenrolled_students": 0,
        }

        # --- cascade: assignments -> their submissions (+ blobs) ---------
        for assignment in assignments_of_class(self._repository, class_id):
            for submission in submissions_of_assignment(self._repository, str(assignment.id)):
                file_key = submission.metadata.get_value(KEY_FILE_PATH)
                if file_key:
                    self._storage.delete(file_key)
                self._repository.delete(submission.id)
                deleted["submissions"] += 1
            attachment_key = assignment.metadata.get_value(KEY_ATTACHMENT_PATH)
            if attachment_key:
                self._storage.delete(attachment_key)
            self._repository.delete(assignment.id)
            deleted["assignments"] += 1

        # --- cascade: attendance sessions ---------------------------------
        for session in attendance_sessions_of_class(self._repository, class_id):
            self._repository.delete(session.id)
            deleted["attendance_sessions"] += 1

        # --- roster: ENROLLED_IN edges on the Student Objects -------------
        for student in enrolled_students(self._repository, class_id):
            student.remove_relationship(
                obj.id, RelationshipKind.ENROLLED_IN, Provenance.ASSERTED
            )
            self._repository.save(student)
            student.pop_domain_events()
            deleted["unenrolled_students"] += 1

        assert_no_inbound_edges(self._repository, command.object_id)
        self._repository.delete(command.object_id)
        return deleted
