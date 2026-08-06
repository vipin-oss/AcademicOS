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


@dataclass(frozen=True)
class RunComparison:
    """Deterministic diff between two runs of the SAME suite (Sprint-7 M3).

    Regression detection over benchmark history: every case of the base
    run is classified by how its pass/fail changed in the candidate run.
    Case identity is the case NAME; comparing runs whose suites differ is
    rejected (the diff would be meaningless).
    """

    base_run_id: str
    candidate_run_id: str
    regressions: tuple[str, ...]  # passed in base, failed in candidate
    fixes: tuple[str, ...]  # failed in base, passed in candidate
    stable_passes: tuple[str, ...]  # passed in both
    stable_failures: tuple[str, ...]  # failed in both
    base_passed: int
    candidate_passed: int
    total: int

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)


class EvaluationHistory:
    """Benchmark history + quality tracking (Sprint-7 M3).

    The single application seam that records evaluation runs and answers
    history questions: latest/recent runs per model and deterministic
    run-to-run comparison (historical regression detection). Records are
    append-only — history never goes stale; the injected ``EvalRunStore``
    is the only persistence the service touches.
    """

    def __init__(self, store: EvalRunStore) -> None:
        self._store = store

    # ------------------------------------------------------------- record
    def record_run(
        self,
        *,
        model_id: str,
        model_version: str,
        prompt_id: str,
        prompt_version: int,
        results: list[EvalResult] | tuple[EvalResult, ...],
    ) -> EvalRun:
        """Persist one evaluation run and return its durable record.

        ``run_id`` (UUID) and ``created_at`` are generated here — the run
        record's identity is the service's concern, the store only
        persists it. Passed/total are derived from ``results``, so the
        record is internally consistent by construction.
        """
        run = EvalRun(
            run_id=str(uuid.uuid4()),
            model_id=model_id,
            model_version=model_version,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            passed=sum(1 for r in results if r.passed),
            total=len(results),
            results=tuple(results),
            created_at=_utcnow_iso(),
        )
        self._store.add(run)
        return run

    # ------------------------------------------------------------ history
    def get(self, run_id: str) -> EvalRun | None:
        return self._store.get(run_id)

    def latest(self, model_id: str) -> EvalRun | None:
        return self._store.latest_by_model(model_id)

    def recent(self, model_id: str, limit: int = 20) -> list[EvalRun]:
        return self._store.recent_by_model(model_id, limit)

    # --------------------------------------------------------- comparison
    def compare(self, base: EvalRun, candidate: EvalRun) -> RunComparison:
        """Classify every case of ``base`` by its change in ``candidate``.

        Deterministic: cases are walked in base suite order. Runs that do
        not cover the same case names are rejected — a regression report
        across different suites would be meaningless.
        """
        base_by_name = {r.name: r.passed for r in base.results}
        candidate_by_name = {r.name: r.passed for r in candidate.results}
        if set(base_by_name) != set(candidate_by_name):
            raise ValueError(
                "Runs cover different case sets; comparison is meaningless."
            )
        regressions: list[str] = []
        fixes: list[str] = []
        stable_passes: list[str] = []
        stable_failures: list[str] = []
        for name, before in base_by_name.items():
            after = candidate_by_name[name]
            if before and not after:
                regressions.append(name)
            elif not before and after:
                fixes.append(name)
            elif before:
                stable_passes.append(name)
            else:
                stable_failures.append(name)
        return RunComparison(
            base_run_id=base.run_id,
            candidate_run_id=candidate.run_id,
            regressions=tuple(regressions),
            fixes=tuple(fixes),
            stable_passes=tuple(stable_passes),
            stable_failures=tuple(stable_failures),
            base_passed=base.passed,
            candidate_passed=candidate.passed,
            total=base.total,
        )

    def compare_latest(self, model_id: str) -> RunComparison | None:
        """Historical regression detection: the two most recent runs.

        ``None`` when the model has fewer than two recorded runs. The
        candidate is the newest run, the base the one before it.
        """
        recent = self._store.recent_by_model(model_id, 2)
        if len(recent) < 2:
            return None
        return self.compare(recent[1], recent[0])


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
    "EvaluationHistory",
    "RunComparison",
    "run_eval_case",
    "run_eval_suite",
]


def run_eval_suite_across_models(
    registry,
    repository,
    build_use_case,
    cases: list[EvalCase],
    *,
    history: EvaluationHistory | None = None,
    prompt_registry: PromptRegistry | None = None,
    prompt_id: str = DEFAULT_PROMPT_ID,
) -> dict[str, tuple[list[EvalResult], int]]:
    """Run the SAME evaluation suite against EVERY registered model (S7 M2).

    Deterministic side-by-side comparison: one fresh pipeline per model
    (built by ``build_use_case(model_id)``), the same static cases, the
    same pure predicates — so results are comparable across models and
    reproducible across runs. Returns ``{model_id: (results, passed)}``.

    Sprint-7 M3 — evaluation persistence: when ``history`` is wired, every
    model's run is recorded IMMEDIATELY after its suite completes (model
    id, the deployed model name from the registry spec, the prompt id +
    version resolved from ``prompt_registry`` at run time, the per-case
    results, and the run timestamp). ``prompt_registry`` is REQUIRED when
    ``history`` is enabled — the recorded prompt version must come from
    the registry (the single source of truth), never from a loose number;
    callers must wire the same registry into the prompt builders of the
    use cases produced by ``build_use_case`` so the recorded version is
    the version that actually ran. Without a history the runner behaves
    exactly as before (backward compatible).

    Partial-failure semantics: recording is per model and immediate, so a
    later model raising propagates the exception but every completed
    model's record is already persisted.
    """
    if history is not None and prompt_registry is None:
        raise ValueError("prompt_registry is required when history is enabled.")
    outcomes: dict[str, tuple[list[EvalResult], int]] = {}
    for spec in registry.all():
        use_case = build_use_case(spec.id)
        results, passed = run_eval_suite(use_case, cases)
        if history is not None:
            history.record_run(
                model_id=spec.id,
                model_version=spec.model,
                prompt_id=prompt_id,
                prompt_version=prompt_registry.latest_version(prompt_id),
                results=results,
            )
        outcomes[spec.id] = (results, passed)
    return outcomes
