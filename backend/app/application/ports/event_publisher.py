"""Application port: domain-event projection.

Infrastructure (message bus, timeline, graph projector) implements this. The
Application layer depends only on the abstraction, never on a concrete adapter.
No framework imports here.
"""
from __future__ import annotations

import abc

from app.domain.events import DomainEvent


class DomainEventPublisher(abc.ABC):
    @abc.abstractmethod
    def publish(self, events: list[DomainEvent]) -> None:
        """Project the given domain events to the outside world."""
