"""Use case: Update a Research Project (partial — frozen merge contract).

Mirrors ``UpdatePublicationUseCase``/``UpdateStudentUseCase``: ``None`` =
untouched, a provided value replaces; link groups replace per group (present
groups only); team groups replace per group on the person aggregates; the
lifecycle rides the ``lifecycle_status`` metadata key (type-specific state,
§1.4). Duplicate detection on project_code change -> 409.
"""
from __future__ import annotations

from app.application.commands.update_project import UpdateProjectCommand
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
    ProjectOutput,
    format_amount,
    linked_target_ids,
    project_edge_group,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
)
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.create_project import (
    _assert_link_targets,
    _assert_team_targets,
    find_project_duplicates,
)
from app.application.use_cases.research.helpers import (
    deflated_team,
    milestone_output,
    milestones_of_project,
    project_budget,
    replace_team_group,
)
from app.application.validators.research import assert_valid_update_project_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry


class UpdateProjectUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def _assert(self, obj: UniversalObject, key: str, value: str, actor: str) -> None:
        if obj.metadata.get_value(key) != value:
            obj.set_metadata(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )

    def execute(self, command: UpdateProjectCommand) -> ProjectOutput:
        data = command.input
        assert_valid_update_project_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.RESEARCH_PROJECT:
            raise ObjectNotFoundError(f"Project {command.object_id} not found.")

        actor = data.actor.strip()

        # --- duplicate detection when project_code changes --------------
        if data.project_code is not None and (
            data.project_code.strip().casefold()
            != (obj.metadata.get_value(KEY_PROJECT_CODE) or "").strip().casefold()
        ):
            dupes = find_project_duplicates(
                self._repository, project_code=data.project_code, exclude_id=str(obj.id)
            )
            if dupes:
                raise ObjectAlreadyExistsError(
                    f"Duplicate project: {dupes[0].id} ({dupes[0].title!r}) already has "
                    f"this project code."
                )

        # --- link groups (validate first, then merge per group) ---------
        if data.links is not None:
            _assert_link_targets(self._repository, data.links)
            for group, ids in data.links.items():
                kind = PROJECT_GROUP_TO_KIND[group]
                wanted = {str(oid) for oid in ids}
                current = []
                for target in [r.target for r in obj.relationships if r.kind is kind]:
                    linked = self._repository.get_by_id(target)
                    if linked is None or project_edge_group(kind, linked.object_type) == group:
                        current.append(target)
                for target in current:
                    if str(target) not in wanted:
                        obj.remove_relationship(target, kind, Provenance.ASSERTED, actor=actor)
                present = {str(r.target) for r in obj.relationships if r.kind is kind}
                for oid in ids:
                    if str(oid) not in present:
                        obj.add_relationship(oid, kind, Provenance.ASSERTED, actor=actor)

        # --- team groups (replace per group on the person aggregates) ---
        if data.team is not None:
            _assert_team_targets(self._repository, data.team)

        # --- title / universal lifecycle ---------------------------------
        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        # --- human-asserted metadata (L6) --------------------------------
        scalar_fields = (
            (KEY_PROJECT_CODE, data.project_code.strip() if data.project_code else None),
            (KEY_LIFECYCLE_STATUS, data.lifecycle_status),
            (KEY_DEPARTMENT, data.department),
            (KEY_GRANT_NUMBER, data.grant_number),
            (KEY_START_DATE, data.start_date),
            (KEY_END_DATE, data.end_date),
            (KEY_DURATION, data.duration),
            (KEY_OBJECTIVES, data.objectives),
            (KEY_ABSTRACT, data.abstract),
            (KEY_PRIORITY, data.priority),
            (KEY_NOTES, data.notes),
        )
        for key, value in scalar_fields:
            if value is not None:
                self._assert(obj, key, str(value), actor)
        if data.budget_approved is not None:
            self._assert(obj, KEY_BUDGET_APPROVED, format_amount(float(data.budget_approved)) or "0", actor)
        if data.budget_utilized is not None:
            self._assert(obj, KEY_BUDGET_UTILIZED, format_amount(float(data.budget_utilized)) or "0", actor)
        for key, values in (
            (KEY_KEYWORDS, data.keywords),
            (KEY_TAGS, data.tags),
        ):
            if values is not None:
                self._assert(obj, key, encode_json_list(list(values)), actor)

        self._repository.save(obj)

        # --- team edge replacement happens after the project is saved ----
        if data.team is not None:
            for group, ids in data.team.items():
                replace_team_group(self._repository, obj, group, ids, actor=actor)

        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        out = ProjectOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        project_id = str(obj.id)
        out.team = deflated_team(self._repository, project_id)
        out.milestones = [
            milestone_output(m) for m in milestones_of_project(self._repository, project_id)
        ]
        out.budget = project_budget(self._repository, obj)
        return out
