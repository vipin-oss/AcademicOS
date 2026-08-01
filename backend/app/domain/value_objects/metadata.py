"""Metadata value object — the seven-layer, human-asserted-safe record.

Frozen references:
- AI Architecture F7 (Automatic Metadata) and SRS §16 (metadata layers L1–L7)
- FR-MET-009: "AI must never silently overwrite a human-asserted value"

``Metadata`` is immutable: every write returns a *new* instance via
``with_entry``. ``with_entry`` enforces FR-MET-009 — a human-asserted (L6)
entry can never be overwritten by a non-human source. The AI write is simply
ignored and the human value preserved.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace

from app.domain.value_objects.enums import MetadataLayer, Provenance


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@dataclass(frozen=True)
class MetadataEntry:
    key: str
    value: str
    layer: MetadataLayer
    source: Provenance
    confidence: float | None = None
    recorded_at: dt.datetime = field(default_factory=_utcnow)

    @property
    def is_human_asserted(self) -> bool:
        return self.source is Provenance.ASSERTED

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("Metadata key must not be empty")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class Metadata:
    entries: tuple[MetadataEntry, ...] = field(default_factory=tuple)

    def get(self, key: str) -> MetadataEntry | None:
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None

    def get_value(self, key: str) -> str | None:
        entry = self.get(key)
        return entry.value if entry is not None else None

    def with_entry(self, entry: MetadataEntry) -> "Metadata":
        """Return a new ``Metadata`` with ``entry`` applied.

        Enforces FR-MET-009: if a human-asserted value already exists for the
        key, a non-human (inferred/system) write is ignored and the human
        value is kept untouched.
        """
        existing = self.get(entry.key)
        if (
            existing is not None
            and existing.is_human_asserted
            and entry.source is not Provenance.ASSERTED
        ):
            return self
        new_entries = tuple(e for e in self.entries if e.key != entry.key) + (entry,)
        return replace(self, entries=new_entries)

    def filter(
        self,
        *,
        layer: MetadataLayer | None = None,
        source: Provenance | None = None,
    ) -> "Metadata":
        def keep(e: MetadataEntry) -> bool:
            if layer is not None and e.layer is not layer:
                return False
            if source is not None and e.source is not source:
                return False
            return True

        return replace(self, entries=tuple(e for e in self.entries if keep(e)))

    def human_asserted(self) -> "Metadata":
        return self.filter(source=Provenance.ASSERTED)

    def inferred(self) -> "Metadata":
        return self.filter(source=Provenance.INFERRED)

    def keys(self) -> list[str]:
        return [e.key for e in self.entries]
