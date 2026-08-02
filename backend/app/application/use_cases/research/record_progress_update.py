"""Use case: Append a progress update to a project timeline (PART 8).

The update log rides the ``progress_updates`` JSON metadata key on the
project (list of {date, percent, remark}, date order) — the publications
JSON-list convention (``authors``). The latest percent is the project's
completion %; the full log renders as the timeline's update feed.
"""
from __future__ import annotations

from app.application.commands.record_progress_update import RecordProgressUpdateCommand
from app.application.dtos.publication import encode_json_list
from app.application.dtos.research import (
    KEY_PROGRESS_UPDATES,
    ProjectOutput,
    linked_target_ids,
    parse_json_object_list,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.helpers import (
    deflated_team,
    milestone_output,
    milestones_of_project,
    project_budget,
)
from app.application.validators.research import assert_valid_progress_update_input
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry


class RecordProgressUpdateUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: RecordProgressUpdateCommand) -> ProjectOutput:
        data = command.input
        assert_valid_progress_update_input(data)

        project = self._repository.get_by_id(command.project_id)
        if project is None or project.object_type is not ObjectType.RESEARCH_PROJECT:
            raise ObjectNotFoundError(f"Project {command.project_id} not found.")

        actor = (command.actor or "system").strip() or "system"

        updates = parse_json_object_list(project.metadata.get_value(KEY_PROGRESS_UPDATES))
        updates.append(
            {
                "date": data.date.strip(),
                "percent": float(data.percent),
                "remark": data.remark.strip(),
            }
        )
        updates.sort(key=lambda item: str(item.get("date") or ""))
        project.set_metadata(
            MetadataEntry(
                KEY_PROGRESS_UPDATES,
                encode_json_list(updates),
                MetadataLayer.L6_HUMAN_ASSERTED,
                Provenance.ASSERTED,
            ),
            actor=actor,
        )
        self._repository.save(project)

        events = project.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        # Return the enriched workspace payload (timeline reactivity).
        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(project))
        }
        out = ProjectOutput.from_domain(project, events, linked_by_id=linked_by_id)
        project_id = str(project.id)
        out.team = deflated_team(self._repository, project_id)
        out.milestones = [
            milestone_output(m) for m in milestones_of_project(self._repository, project_id)
        ]
        out.budget = project_budget(self._repository, project)
        return out
