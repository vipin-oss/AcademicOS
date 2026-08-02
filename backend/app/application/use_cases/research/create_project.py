"""Use case: Register a Research Project (manual entry).

Mirrors ``CreateStudentUseCase``: validate -> duplicate check (project_code,
portable across engines) -> build the L6 human-asserted metadata record ->
outgoing asserted edges (agencies / committees) -> team edges on the person
aggregates (the multi-aggregate ``enroll_students`` precedent) -> persist ->
events -> enriched output.
"""
from __future__ import annotations

from app.application.commands.create_project import CreateProjectCommand
from app.application.dtos.publication import encode_json_list
from app.application.dtos.research import (
    KEY_ABSTRACT,
    KEY_BUDGET_APPROVED,
    KEY_BUDGET_UTILIZED,
    KEY_DEPARTMENT,
    KEY_DURATION,
    KEY_END_DATE,
    KEY_GRANT_NUMBER,
    KEY_KEYWORDS,
    KEY_LIFECYCLE_STATUS,
    KEY_NOTES,
    KEY_OBJECTIVES,
    KEY_PRIORITY,
    KEY_PROJECT_CODE,
    KEY_START_DATE,
    KEY_TAGS,
    PROJECT_GROUP_TO_KIND,
    TEAM_GROUP_TO_KIND,
    ProjectOutput,
    format_amount,
)
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.helpers import (
    deflated_team,
    project_budget,
    replace_team_group,
)
from app.application.validators.research import assert_valid_create_project_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId

_GROUP_TARGET_TYPES = {
    "agencies": (ObjectType.FUNDING_AGENCY,),
    "committees": (ObjectType.COMMITTEE,),
}
_PI_TYPES = (ObjectType.FACULTY,)
_MEMBER_TYPES = (ObjectType.FACULTY, ObjectType.STUDENT)


def find_project_duplicates(
    repository: ObjectRepository,
    *,
    project_code: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: project_code (case-insensitive).

    Evaluated in Python over ``find_by_type`` (frozen interface), identical
    on PostgreSQL, SQLite and in-memory repositories — no JSONB dependency.
    """
    code = (project_code or "").strip().casefold()
    if not code:
        return []
    matches: list[UniversalObject] = []
    for project in repository.find_by_type(ObjectType.RESEARCH_PROJECT):
        if exclude_id is not None and str(project.id) == exclude_id:
            continue
        if (project.metadata.get_value(KEY_PROJECT_CODE) or "").strip().casefold() == code:
            matches.append(project)
    return matches


def _assert_link_targets(
    repository: ObjectRepository, links: dict[str, tuple[ObjectId, ...]] | None
) -> None:
    """Outgoing edge targets must exist and carry the group's object type."""
    for group, ids in (links or {}).items():
        for target_id in ids:
            target = repository.get_by_id(target_id)
            if target_id == ObjectId("") or target is None:
                raise ValidationError(f"Linked object {target_id} not found.")
            if target.object_type not in _GROUP_TARGET_TYPES[group]:
                raise ValidationError(
                    f"links.{group} expects {', '.join(t.value for t in _GROUP_TARGET_TYPES[group])} "
                    f"targets; {target_id} is a {target.object_type.value}."
                )


def _assert_team_targets(
    repository: ObjectRepository, team: dict[str, tuple[ObjectId, ...]] | None
) -> None:
    for group, ids in (team or {}).items():
        allowed = _PI_TYPES if group != "team_members" else _MEMBER_TYPES
        for target_id in ids:
            target = repository.get_by_id(target_id)
            if target_id == ObjectId("") or target is None:
                raise ValidationError(f"Team member {target_id} not found.")
            if target.object_type not in allowed:
                raise ValidationError(
                    f"team.{group} expects {', '.join(t.value for t in allowed)} targets; "
                    f"{target_id} is a {target.object_type.value}."
                )


class CreateProjectUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateProjectCommand) -> ProjectOutput:
        data = command.input

        # 1. Validate boundary input
        assert_valid_create_project_input(data)

        # 2. Registry duplicate detection (project_code) -> 409
        duplicates = find_project_duplicates(self._repository, project_code=data.project_code)
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate project: {existing.id} ({existing.title!r}) already has this "
                f"project code."
            )

        # 3. Link + team targets must exist and be of the right type
        _assert_link_targets(self._repository, data.links)
        _assert_team_targets(self._repository, data.team)

        # 4. Assemble the L6 human-asserted metadata record
        entries: list[MetadataEntry] = [
            MetadataEntry(
                KEY_LIFECYCLE_STATUS,
                data.lifecycle_status,
                MetadataLayer.L6_HUMAN_ASSERTED,
                Provenance.ASSERTED,
            )
        ]

        def asserted(key: str, value: str) -> None:
            entries.append(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        for key, value in (
            (KEY_PROJECT_CODE, (data.project_code or "").strip()),
            (KEY_DEPARTMENT, data.department),
            (KEY_GRANT_NUMBER, data.grant_number),
            (KEY_START_DATE, data.start_date),
            (KEY_END_DATE, data.end_date),
            (KEY_DURATION, data.duration),
            (KEY_OBJECTIVES, data.objectives),
            (KEY_ABSTRACT, data.abstract),
            (KEY_PRIORITY, data.priority),
            (KEY_NOTES, data.notes),
        ):
            if value is not None and str(value) != "":
                asserted(key, str(value))
        if data.budget_approved is not None:
            asserted(KEY_BUDGET_APPROVED, format_amount(float(data.budget_approved)) or "0")
        if data.budget_utilized is not None:
            asserted(KEY_BUDGET_UTILIZED, format_amount(float(data.budget_utilized)) or "0")
        if data.keywords:
            asserted(KEY_KEYWORDS, encode_json_list(list(data.keywords)))
        if data.tags:
            asserted(KEY_TAGS, encode_json_list(list(data.tags)))

        # 5. Create the domain aggregate (emits ObjectCreated)
        obj = UniversalObject.create(
            object_type=ObjectType.RESEARCH_PROJECT,
            title=data.title.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )

        # 6. Outgoing asserted edges (agencies / committees)
        for group, ids in (data.links or {}).items():
            for target_id in ids:
                obj.add_relationship(
                    target_id,
                    PROJECT_GROUP_TO_KIND[group],
                    Provenance.ASSERTED,
                    actor=data.created_by,
                )

        # 7. Persist, then write team edges on the person aggregates
        self._repository.save(obj)
        for group, ids in (data.team or {}).items():
            _ = TEAM_GROUP_TO_KIND[group]
            replace_team_group(
                self._repository, obj, group, ids, actor=data.created_by.strip()
            )

        # 8. Collect + project domain events
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        # 9. Enriched output (team + budget resolved in one pass each)
        all_ids = [oid for ids in (data.links or {}).values() for oid in ids]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}
        out = ProjectOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        out.team = deflated_team(self._repository, str(obj.id))
        out.budget = project_budget(self._repository, obj)
        return out
