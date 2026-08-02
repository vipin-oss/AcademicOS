"""Use case: Record a grant installment (release schedule entry).

An installment is a ``grant_installment`` Universal Object (BELONGS_TO →
grant) with no/date/amount/status as L6 metadata — the attendance_session
precedent. Budget integrity (PART 7): the total *released* may never exceed
the sanctioned amount, so a sensibly-typed mistake surfaces as a 422 instead
of corrupting the remaining-balance view.
"""
from __future__ import annotations

from app.application.commands.add_installment import AddInstallmentCommand
from app.application.dtos.research import (
    KEY_AMOUNT,
    KEY_INSTALLMENT_DATE,
    KEY_INSTALLMENT_NO,
    KEY_INSTALLMENT_STATUS,
    KEY_NOTES,
    format_amount,
    parse_amount,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.helpers import (
    grant_totals,
    installment_output,
)
from app.application.validators.research import assert_valid_installment_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


class AddInstallmentUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: AddInstallmentCommand):
        data = command.input
        assert_valid_installment_input(data)

        grant = self._repository.get_by_id(command.grant_id)
        if grant is None or grant.object_type is not ObjectType.GRANT:
            raise ObjectNotFoundError(f"Grant {command.grant_id} not found.")

        actor = (command.actor or "system").strip() or "system"

        # Budget guard: released installments must not exceed the sanction.
        approved = parse_amount(grant.metadata.get_value(KEY_AMOUNT))
        if approved is not None and data.status == "released":
            totals = grant_totals(self._repository, grant)
            if (totals["released"] or 0.0) + float(data.amount) > approved + 1e-9:
                raise ValidationError(
                    f"Released installments would total "
                    f"{(totals['released'] or 0.0) + float(data.amount):g}, exceeding the "
                    f"sanctioned amount {approved:g}."
                )

        entries: list[MetadataEntry] = [
            MetadataEntry(KEY_INSTALLMENT_NO, str(int(data.installment_no)),
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            MetadataEntry(KEY_INSTALLMENT_DATE, data.date.strip(),
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            MetadataEntry(KEY_AMOUNT, format_amount(float(data.amount)) or "0",
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            MetadataEntry(KEY_INSTALLMENT_STATUS, data.status,
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
        ]
        if data.notes:
            entries.append(
                MetadataEntry(KEY_NOTES, data.notes,
                              MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        number = grant.metadata.get_value("grant_number") or grant.title
        installment = UniversalObject.create(
            object_type=ObjectType.GRANT_INSTALLMENT,
            title=f"Installment {int(data.installment_no)} · {number}",
            created_by=actor,
            metadata=Metadata(entries=tuple(entries)),
        )
        installment.add_relationship(
            grant.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
        )
        self._repository.save(installment)

        events = installment.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return installment_output(installment)
