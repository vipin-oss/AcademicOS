"""The Intake Commit Engine (Sprint-3 M1).

The single entry point for committing processed intake items. Coordination
only: every business step lives in the existing use cases
(``CommitItemUseCase`` for eligibility + idempotency, ``CreateDocumentUseCase``
for document creation). This facade owns the wiring so the API layer and
future consumers (proposal engine M8, search S5, outbox S5) depend on one
stable seam — and no other code path transitions an item to COMMITTED.
"""
from __future__ import annotations

from app.application.commands.commit_intake_item import CommitIntakeItemCommand
from app.application.dtos.intake import CommitItemOutput
from app.application.ports.document_content_store import DocumentContentStore
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.use_cases.intake.commit_item import CommitItemUseCase
from app.domain.repositories.object_repository import ObjectRepository


class CommitEngineService:
    def __init__(
        self,
        repository: ObjectRepository,
        storage: FileStorage,
        content_store: DocumentContentStore | None = None,
    ) -> None:
        self._repository = repository
        self._document_creator = CreateDocumentUseCase(repository, storage)
        self._commit_item = CommitItemUseCase(
            repository, storage, self._document_creator, content_store=content_store
        )

    def commit_item(self, item_id: str, actor: str, dry_run: bool = False) -> CommitItemOutput:
        """Commit one processed intake item to a Document (idempotent).

        ``dry_run=True`` runs the same eligibility checks without creating
        anything — the preview endpoint's single source of truth.
        """
        return self._commit_item.execute(
            CommitIntakeItemCommand(item_id=item_id, actor=actor, dry_run=dry_run)
        )
