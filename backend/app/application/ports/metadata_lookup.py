"""Application port: external bibliographic metadata lookup.

Mirrors ``DomainEventPublisher`` / ``FileStorage``: the Application layer
depends only on this abstraction; infrastructure provides concrete adapters
(the pre-planned ``infrastructure/external`` slot — Crossref first, then
Scopus / Web of Science / PubMed / ORCID per FR-PUB-006). No framework
imports here. The returned record is a plain dict of publication fields
(the same primitive shape the bibliography service produces).
"""
from __future__ import annotations

import abc


class MetadataLookup(abc.ABC):
    @abc.abstractmethod
    def lookup(self, doi: str) -> dict | None:
        """Return the publication record for ``doi``, or ``None`` if unknown."""
