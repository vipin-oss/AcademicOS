"""Third-party client adapters (Crossref today; Scopus/WoS/PubMed/ORCID later)."""

from app.infrastructure.external.crossref import CrossrefMetadataLookup

__all__ = ["CrossrefMetadataLookup"]
