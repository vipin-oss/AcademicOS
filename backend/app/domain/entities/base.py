"""Base Entity and Aggregate Root.

Frozen reference: Clean Architecture — the domain layer owns identity and
invariants; the infrastructure layer (repository implementations) lives
elsewhere and is intentionally absent from this module.

Design notes:
- ``Entity`` carries identity (an ``ObjectId``) and defines equality/hash by
  identity, never by attributes.
- ``AggregateRoot`` extends ``Entity`` with a domain-event outbox. Mutators on
  the aggregate call ``add_domain_event``; the application layer later calls
  ``pop_domain_events`` and projects them (graph, timeline, notifications).
- No dataclass field inheritance is used here, so the aggregate stays simple
  and framework-free.
"""
from __future__ import annotations

import abc

from app.domain.events import DomainEvent
from app.domain.value_objects.object_id import ObjectId


class Entity(abc.ABC):
    id: ObjectId

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class AggregateRoot(Entity):
    def __init__(self) -> None:
        self._domain_events: list[DomainEvent] = []

    @property
    def domain_events(self) -> list[DomainEvent]:
        return self._domain_events

    def add_domain_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def pop_domain_events(self) -> list[DomainEvent]:
        events, self._domain_events = self._domain_events, []
        return events
