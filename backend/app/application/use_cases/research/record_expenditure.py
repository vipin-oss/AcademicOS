"""Use case: Record a grant expenditure entry (PART 7 budget tracking).

An expenditure is a ``grant_expenditure`` Universal Object (BELONGS_TO →
grant) with date/head/amount/reference as L6 metadata. Budget integrity:
cumulative expenditure may never exceed the sanctioned amount — no
accounting system, just the one guard that keeps "remaining" meaningful.
"""
from __future__ import annotations

from app.application.commands.record_expenditure import RecordExpenditureCommand
from app.application.dtos.research import (
    KEY_AMOUNT,
    KEY_EXPENDITURE_DATE,
    KEY_EXPENDITURE_HEAD,
    KEY_EXPENDITURE_REFERENCE,
    KEY_NOTES,
    format_amount,
    parse_amount,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.helpers import (
    expenditure_output,
    grant_totals,
)
from app.application.validators.research import assert_valid_expenditure_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


class RecordExpenditureUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: RecordExpenditureCommand):
        data = command.input
        assert_valid_expenditure_input(data)

        grant = self._repository.get_by_id(command.grant_id)
        if grant is None or grant.object_type is not ObjectType.GRANT:
            raise ObjectNotFoundError(f"Grant {command.grant_id} not found.")

        actor = (command.actor or "system").strip() or "system"

        # Budget guard: expenditure must not exceed the sanctioned amount.
        approved = parse_amount(grant.metadata.get_value(KEY_AMOUNT))
        if approved is not None:
            totals = grant_totals(self._repository, grant)
            if (totals["utilized"] or 0.0) + float(data.amount) > approved + 1e-9:
                remaining = approved - (totals["utilized"] or 0.0)
                raise ValidationError(
                    f"Expenditure {float(data.amount):g} exceeds the remaining balance "
                    f"{remaining:g} of sanctioned {approved:g}."
                )

        entries: list[MetadataEntry] = [
            MetadataEntry(KEY_EXPENDITURE_DATE, data.date.strip(),
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            MetadataEntry(KEY_EXPENDITURE_HEAD, data.head.strip(),
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            MetadataEntry(KEY_AMOUNT, format_amount(float(data.amount)) or "0",
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
        ]
        if data.reference:
            entries.append(
                MetadataEntry(KEY_EXPENDITURE_REFERENCE, data.reference.strip(),
                              MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )
        if data.notes:
            entries.append(
                MetadataEntry(KEY_NOTES, data.notes,
                              MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        expenditure = UniversalObject.create(
            object_type=ObjectType.GRANT_EXPENDITURE,
            title=f"Expenditure · {data.head.strip()} · {data.date.strip()}",
            created_by=actor,
            metadata=Metadata(entries=tuple(entries)),
        )
        expenditure.add_relationship(
            grant.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
        )
        self._repository.save(expenditure)

        events = expenditure.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return expenditure_output(expenditure)
