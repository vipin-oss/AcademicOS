"""Evaluation foundation (Sprint-7 M1).

Reproducible assistant evaluations: an ``EvalCase`` describes one expected
behavior (the question, text that MUST appear in the answer, and whether
verified citations are required); ``run_eval_case`` executes the REAL ask
pipeline (retrieval, context, prompt, provider, citations, verification,
persistence) against an injected provider and records a deterministic
pass/fail ``EvalResult``.

Reproducibility: cases are static data; the provider is injected (an eval
uses a deterministic fake transport, never a live model); the checks are
pure predicates over the produced answer. Running the same case against
the same pipeline always yields the same result.

No benchmark claims, no metrics collection, no telemetry — this is the
correctness/evaluation foundation only.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.application.commands.ask_question import AskQuestionCommand
from app.application.dtos.assistant import AskQuestionInput
from app.application.services.prompt_registry import DEFAULT_PROMPT_ID
from app.application.use_cases.assistant.ask_question import AskQuestionUseCase

if TYPE_CHECKING:  # annotations only — ports/services never import each other at runtime
    from app.application.ports.eval_run_store import EvalRunStore
    from app.application.services.prompt_registry import PromptRegistry


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


@dataclass(frozen=True)
class EvalCase:
    """One reproducible evaluation case."""

    name: str
    question: str
    # Every one of these substrings must appear in the answer summary.
    expected_contains: tuple[str, ...] = ()
    # True: the answer must carry at least one verified citation.
    expect_citations: bool = False
    asked_by: str = "obj:user:eval-0001"


@dataclass(frozen=True)
class EvalResult:
    """The deterministic outcome of running one case."""

    name: str
    passed: bool
    details: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvalRun:
    """One durable evaluation-run record (Sprint-7 M3).

    The benchmark-history unit: everything needed to compare runs and
    detect regressions later — the model that ran (registry id + the
    concrete deployed model name), the prompt asset that was active
    (id + version, resolved from the ``PromptRegistry`` at run time),
    the outcome, the per-case results in suite order, and the run
    timestamp. Records are immutable and append-only: a run's results
    never change after recording.
    """

    run_id: str
    model_id: str
    model_version: str  # the registry spec's deployed model name
    prompt_id: str
    prompt_version: int  # resolved from the PromptRegistry at run time
    passed: int
    total: int
    results: tuple[EvalResult, ...] = field(default_factory=tuple)
    created_at: str = ""  # ISO-8601

    def __post_init__(self) -> None:
        if not self.run_id or not self.model_id or not self.model_version:
            raise ValueError("EvalRun identity fields must not be empty.")
        if not self.prompt_id:
            raise ValueError("EvalRun prompt_id must not be empty.")
        if self.prompt_version < 1:
            raise ValueError("EvalRun prompt_version must be >= 1.")
        if not 0 <= self.passed <= self.total:
            raise ValueError("EvalRun passed must be within [0, total].")
        if len(self.results) != self.total:
            raise ValueError(
                "EvalRun results must contain exactly one entry per case."
            )
        if self.passed != sum(1 for r in self.results if r.passed):
            raise ValueError("EvalRun passed must match the recorded results.")
        if not self.created_at:
            raise ValueError("EvalRun created_at must not be empty.")


def run_eval_case(
    use_case: AskQuestionUseCase,
    case: EvalCase,
) -> EvalResult:
    """Run one case through the real pipeline and judge it deterministically."""
    out = use_case.execute(
        AskQuestionCommand(
            input=AskQuestionInput(
                question=case.question,
                asked_by=case.asked_by,
            )
        )
    )
    summary = out.answer.summary or ""
    details: list[str] = []
    ok = True
    for expected in case.expected_contains:
        if expected not in summary:
            ok = False
            details.append(f"missing {expected!r}")
    if case.expect_citations and not out.answer.citations:
        ok = False
        details.append("expected citations but none were attached")
    if not case.expect_citations and out.answer.citations:
        # Citations are harmless extras; only flag when the case forbids
        # them explicitly.
        pass
    if ok:
        return EvalResult(name=case.name, passed=True)
    return EvalResult(name=case.name, passed=False, details=tuple(details))


def run_eval_suite(
    use_case: AskQuestionUseCase,
    cases: list[EvalCase],
) -> tuple[list[EvalResult], int]:
    """Run every case; returns (results, passed_count)."""
    results = [run_eval_case(use_case, case) for case in cases]
    return results, sum(1 for r in results if r.passed)


__all__ = [
    "EvalCase",
    "EvalResult",
    "EvalRun",
    "run_eval_case",
    "run_eval_suite",
]


def run_eval_suite_across_models(
    registry,
    repository,
    build_use_case,
    cases: list[EvalCase],
) -> dict[str, tuple[list[EvalResult], int]]:
    """Run the SAME evaluation suite against EVERY registered model (S7 M2).

    Deterministic side-by-side comparison: one fresh pipeline per model
    (built by ``build_use_case(model_id)``), the same static cases, the
    same pure predicates — so results are comparable across models and
    reproducible across runs. Returns ``{model_id: (results, passed)}``.
    """
    outcomes: dict[str, tuple[list[EvalResult], int]] = {}
    for spec in registry.all():
        use_case = build_use_case(spec.id)
        outcomes[spec.id] = run_eval_suite(use_case, cases)
    return outcomes
