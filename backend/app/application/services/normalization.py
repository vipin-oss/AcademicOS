"""Normalization-wave framework (V3 M16, ADR-063).

Operational Data Normalization: retire full-table scans over the object store
by projecting hot operational data into typed, indexed tables — one reversible
WAVE at a time. Each wave follows the frozen doctrine, in order:

    EXPAND        add the typed projection (additive schema)
    BACKFILL      idempotently populate it from the authoritative objects
    VALIDATE      assert integrity (no nulls / no orphans / counts match)
    SWITCH READS  route reads to the projection (fallback to objects on miss)
    SWITCH WRITES keep the object the source of truth; the projection is
                  derived and rebuildable

Every wave is independently reversible (drop the projection; reads fall back
to the object store). The UniversalObject remains the identity/graph anchor —
its correct role; the projection is derived data, never the source of truth.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

#: Phase names, in canonical order.
PHASE_EXPAND = "expand"
PHASE_BACKFILL = "backfill"
PHASE_VALIDATE = "validate"
PHASE_SWITCH_READS = "switch_reads"
PHASE_SWITCH_WRITES = "switch_writes"

PHASES: tuple[str, ...] = (
    PHASE_EXPAND,
    PHASE_BACKFILL,
    PHASE_VALIDATE,
    PHASE_SWITCH_READS,
    PHASE_SWITCH_WRITES,
)


@dataclass(frozen=True)
class WaveReport:
    wave_id: str
    phases: tuple[str, ...] = PHASES
    rolled_back: bool = False


class NormalizationWave(ABC):
    """One reversible normalization wave (EXPAND→…→SWITCH WRITES)."""

    wave_id: str = "unnamed"

    @abstractmethod
    def expand(self) -> None:  # pragma: no cover - per-wave
        """Add the typed projection (schema)."""

    @abstractmethod
    def backfill(self) -> int:
        """Populate the projection idempotently; return rows written."""

    @abstractmethod
    def validate(self) -> list[str]:
        """Return a list of integrity violations (empty = valid)."""

    @abstractmethod
    def switch_reads(self) -> None:  # pragma: no cover - per-wave
        """Route reads to the projection (fallback to objects on miss)."""

    @abstractmethod
    def switch_writes(self) -> None:  # pragma: no cover - per-wave
        """Writes continue to the object (source of truth); projection derived."""

    @abstractmethod
    def rollback(self) -> None:  # pragma: no cover - per-wave
        """Reverse the wave (drop projection; reads fall back to objects)."""


class NormalizationRunner:
    """Runs a wave through its phases, halting (and reporting) on validation
    failure so a half-migrated projection never serves reads."""

    def __init__(self, waves: list[NormalizationWave]) -> None:
        self._waves = waves

    def run(self, wave_id: str) -> WaveReport:
        wave = next((w for w in self._waves if w.wave_id == wave_id), None)
        if wave is None:
            raise KeyError(f"Unknown wave: {wave_id}")
        wave.expand()
        wave.backfill()
        violations = wave.validate()
        if violations:
            wave.rollback()
            raise WaveValidationError(wave_id, violations)
        wave.switch_reads()
        wave.switch_writes()
        return WaveReport(wave_id=wave_id)

    def rollback(self, wave_id: str) -> None:
        wave = next((w for w in self._waves if w.wave_id == wave_id), None)
        if wave is None:
            raise KeyError(f"Unknown wave: {wave_id}")
        wave.rollback()


class WaveValidationError(Exception):
    """A wave failed VALIDATE; it was rolled back (never left half-migrated)."""

    def __init__(self, wave_id: str, violations: list[str]) -> None:
        self.wave_id = wave_id
        self.violations = violations
        super().__init__(f"Wave {wave_id} failed validation: {violations}")


__all__ = [
    "PHASE_BACKFILL",
    "PHASE_EXPAND",
    "PHASE_SWITCH_READS",
    "PHASE_SWITCH_WRITES",
    "PHASE_VALIDATE",
    "PHASES",
    "NormalizationRunner",
    "NormalizationWave",
    "WaveReport",
    "WaveValidationError",
]
