"""Use case: Record attendance for one (class, date) — manual entry (PART I).

One AttendanceSession Object per (class, date): re-recording the same date
updates the same Object (upsert — never duplicates). The records map lives
as L6 human-asserted JSON on the Object; every recorded id must belong to
the roster, so attendance can never name a stranger. QR/biometric capture
is a future ingest channel into this same Object shape.
"""
from __future__ import annotations

from app.application.commands.record_attendance import RecordAttendanceCommand
from app.application.dtos.teaching import (
    KEY_ATTENDANCE_RECORDS,
    KEY_SESSION_DATE,
    AttendanceSessionOutput,
    encode_json,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.teaching.helpers import (
    attendance_sessions_of_class,
    enrolled_students,
)
from app.application.validators.teaching import (
    validate_attendance_records,
    validate_session_date,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry


def find_session(
    sessions: list[UniversalObject], session_date: str
) -> UniversalObject | None:
    for session in sessions:
        if (session.metadata.get_value(KEY_SESSION_DATE) or "") == session_date:
            return session
    return None


class RecordAttendanceUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: RecordAttendanceCommand) -> AttendanceSessionOutput:
        errors = validate_session_date(command.session_date)
        errors += validate_attendance_records(command.records or {})
        if errors:
            raise ValidationError("; ".join(errors))

        cls = self._repository.get_by_id(command.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {command.class_id} not found.")

        session_date = command.session_date.strip()
        actor = (command.actor or "system").strip() or "system"
        roster_ids = {str(s.id) for s in enrolled_students(self._repository, str(cls.id))}
        unknown = [sid for sid in (command.records or {}) if sid not in roster_ids]
        if unknown:
            raise ValidationError(
                f"records reference non-enrolled student ids: {', '.join(sorted(unknown))}."
            )

        sessions = attendance_sessions_of_class(self._repository, str(cls.id))
        session = find_session(sessions, session_date)
        if session is None:
            session = UniversalObject.create(
                object_type=ObjectType.ATTENDANCE_SESSION,
                title=f"Attendance · {cls.title} · {session_date}",
                created_by=actor,
                status=ObjectStatus.ACTIVE,
            )
            session.add_relationship(
                cls.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
            )

        def asserted(key: str, value: str) -> None:
            if session.metadata.get_value(key) != value:
                session.set_metadata(
                    MetadataEntry(
                        key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED
                    ),
                    actor=actor,
                )

        asserted(KEY_SESSION_DATE, session_date)
        canonical = {str(k): v for k, v in (command.records or {}).items()}
        asserted(KEY_ATTENDANCE_RECORDS, encode_json(canonical))

        self._repository.save(session)
        events = session.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return AttendanceSessionOutput.from_domain(session, events)
