"""Accreditation frameworks as DATA (V3 M18, ADR-065).

NAAC · NBA · NIRF · IQAC/AQAR are configurable frameworks: each is a list of
criteria, each criterion a list of indicators with an evidence requirement.
This is data, not code (the same additive-registry doctrine as the predicate
catalogue and document types): a new framework / criterion / indicator is an
additive row, never a schema or code change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Indicator:
    indicator_id: str
    name: str
    evidence_requirement: str


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    name: str
    indicators: tuple[Indicator, ...]


@dataclass(frozen=True)
class AccreditationFramework:
    framework_id: str
    name: str
    criteria: tuple[Criterion, ...]


#: Wave-1 seed frameworks (the four the blueprint names + IQAC/AQAR).
FRAMEWORKS: tuple[AccreditationFramework, ...] = (
    AccreditationFramework(
        "naac",
        "NAAC",
        (
            Criterion("naac-c1", "Curricular Aspects",
                      (Indicator("naac-c1-i1", "Curriculum design & development", "Syllabus + BoS minutes"),)),
            Criterion("naac-c2", "Teaching-Learning & Evaluation",
                      (Indicator("naac-c2-i1", "Student-centric methods", "Pedagogy records"),)),
        ),
    ),
    AccreditationFramework(
        "nba",
        "NBA",
        (
            Criterion("nba-c1", "Vision, Mission & PEOs",
                      (Indicator("nba-c1-i1", "PEO definition & review", "PEO statements + review minutes"),)),
        ),
    ),
    AccreditationFramework(
        "nirf",
        "NIRF",
        (
            Criterion("nirf-c1", "Teaching, Learning & Resources",
                      (Indicator("nirf-c1-i1", "Faculty-student ratio", "Sanctioned/actual strength"),)),
        ),
    ),
    AccreditationFramework(
        "iqac",
        "IQAC/AQAR",
        (
            Criterion("iqac-c1", "Curricular Planning & Implementation",
                      (Indicator("iqac-c1-i1", "AQAR submission", "AQAR reports"),)),
        ),
    ),
)

_BY_ID: dict[str, AccreditationFramework] = {f.framework_id: f for f in FRAMEWORKS}


def get_framework(framework_id: str) -> AccreditationFramework | None:
    return _BY_ID.get(framework_id)


__all__ = [
    "AccreditationFramework",
    "Criterion",
    "FRAMEWORKS",
    "Indicator",
    "get_framework",
]
