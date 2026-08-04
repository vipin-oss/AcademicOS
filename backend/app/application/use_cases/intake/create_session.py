"""Use case: Create an Intake Session (one import operation).

Vertical slice flow (mirrors ``CreateDocumentUseCase``):
  Input DTO -> shape validation -> filesystem validation (part of the
  business action) -> Universal Object creation (``intake_session``,
  ACTIVE, QUEUED) -> Repository.

The session is created *queued*; the route layer then enqueues it with the
job manager. Storage-root overlap is rejected up-front so an import can
never recursively stage its own staging area.
"""
from __future__ import annotations

import os
from pathlib import Path

from app.application.commands.create_intake_session import CreateIntakeSessionCommand
from app.application.dtos.intake import (
    INTAKE_ACTOR,
    KEY_CONTROL,
    KEY_CURRENT_STAGE,
    KEY_INTAKE_STATUS,
    KEY_PROGRESS,
    KEY_SOURCE,
    KEY_STATISTICS,
    IntakeSessionOutput,
    IntakeSessionStatus,
    IntakeSourceKind,
    IntakeStage,
    intake_session_output,
    json_encode,
)
from app.application.exceptions import ValidationError
from app.application.validators.intake import assert_valid_create_intake_session_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


def _entry(key: str, value: str) -> MetadataEntry:
    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


class CreateIntakeSessionUseCase:
    def __init__(self, repository: ObjectRepository, storage_root: str) -> None:
        self._repository = repository
        self._storage_root = storage_root

    def execute(self, command: CreateIntakeSessionCommand) -> IntakeSessionOutput:
        data = command.input
        assert_valid_create_intake_session_input(data)
        actor = data.actor.strip() or INTAKE_ACTOR

        if data.source_kind is IntakeSourceKind.FOLDER:
            assert data.path is not None
            root = Path(data.path.strip()).expanduser()
            if not root.is_dir():
                raise ValidationError(
                    f"Source folder does not exist or is not a directory: {data.path}"
                )
            if not os.access(root, os.R_OK):
                raise ValidationError(f"Source folder is not readable: {root}")
            resolved = root.resolve()
            storage_root = Path(self._storage_root).expanduser().resolve()
            if (
                resolved == storage_root
                or storage_root in resolved.parents
                or resolved in storage_root.parents
            ):
                raise ValidationError(
                    "The source folder must not overlap the intake storage area."
                )
            source = {"kind": "folder", "path": str(root), "display": str(root)}
            title = (data.title or "").strip() or f"Folder import — {root.name or str(root)}"
        else:
            accepted: list[str] = []
            for raw in data.paths:
                candidate = Path(str(raw).strip()).expanduser()
                if not candidate.is_file():
                    raise ValidationError(
                        f"File does not exist or is not a regular file: {raw}"
                    )
                accepted.append(str(candidate))
            source = {
                "kind": "files",
                "paths": accepted,
                "display": f"{len(accepted)} dropped file(s)",
            }
            title = (data.title or "").strip() or f"File drop — {len(accepted)} files"

        entries = [
            _entry(KEY_INTAKE_STATUS, IntakeSessionStatus.QUEUED.value),
            _entry(KEY_SOURCE, json_encode(source)),
            _entry(KEY_PROGRESS, json_encode({"enumerated": False})),
            _entry(
                KEY_STATISTICS,
                json_encode({"skipped_junk": 0, "skipped_junk_samples": []}),
            ),
            _entry(KEY_CONTROL, json_encode({"pause": False, "cancel": False})),
            _entry(KEY_CURRENT_STAGE, IntakeStage.ENUMERATE.value),
        ]
        obj = UniversalObject.create(
            object_type=ObjectType.INTAKE_SESSION,
            title=title,
            created_by=actor,
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=tuple(entries)),
        )
        self._repository.save(obj)
        return intake_session_output(obj, [])
