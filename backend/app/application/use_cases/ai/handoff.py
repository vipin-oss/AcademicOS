"""Use case: external-AI handoff (Sprint M16 — the no-provider / no-cost path).

AcademicOS must remain useful with NO AI provider configured (local or paid).
When a user wants an AI task but no gateway is available — or they prefer an
external tool — this use case builds a self-contained, copyable prompt bundle
they can paste into any external AI. AcademicOS makes **no provider call**
(no key, no charge) and the bundle is grounded in exactly the same
authoritative, READ-permission-filtered evidence an internal generation would
use.

Reuse-only: the grounded prompt is built by the existing ``GroundedQAUseCase``
(via its additive ``prepare_prompt`` — retrieve → context → source-text
injection). ``HandoffUseCase`` only maps that prompt + the readable sources
into the handoff bundle. No new retrieval, no new abstraction, no gateway.

Permission: inherited from the permission-filtered retrieval — only documents
the caller may READ appear in the prompt or the source list.
"""
from __future__ import annotations

from app.application.dtos.ai import HandoffBundle, HandoffSource
from app.application.use_cases.ai.grounded_qa import GroundedQAUseCase
from app.domain.entities.object import UniversalObject

#: The only task type supported by the handoff today. Adding more (e.g.
#: "summarize") is a matter of mapping another prompt builder — the bundle
#: shape is task-agnostic.
SUPPORTED_TASKS = ("qa",)

_HANDOFF_NOTE = (
    "No AcademicOS AI provider is required for this. Copy the prompt below "
    "into any AI assistant (e.g. ChatGPT, Claude, Gemini). AcademicOS did not "
    "send your content anywhere and incurred no cost. Only documents you can "
    "READ were included."
)

_QA_EXPECTED_FORMAT = (
    "A concise, factual answer grounded ONLY in the provided sources. "
    "Cite sources by their bracketed numbers [1], [2]. If the sources do not "
    "answer the question, say so plainly."
)

_QA_INSTRUCTIONS = (
    "Paste the SYSTEM PROMPT and USER PROMPT (or the COMBINED PROMPT) into "
    "your external AI. The user prompt already contains the retrieved context "
    "and the source document text."
)


class HandoffUseCase:
    """Build a copyable, grounded prompt bundle for an external AI (no gateway)."""

    def __init__(self, grounded: GroundedQAUseCase) -> None:
        self._grounded = grounded

    def execute(self, task: str, question: str, user: UniversalObject) -> HandoffBundle:
        if task not in SUPPORTED_TASKS:
            raise ValueError(f"Unsupported handoff task: {task!r}")
        question = (question or "").strip()
        if not question:
            raise ValueError("A non-empty question is required for a handoff.")

        gen_prompt, citations, truncated = self._grounded.prepare_prompt(question, user)
        sources = tuple(
            HandoffSource(
                number=c.number,
                object_id=c.object_id,
                object_type=c.object_type,
                title=c.title,
            )
            for c in citations
        )
        return HandoffBundle(
            task=task,
            system_prompt=gen_prompt.system,
            user_prompt=gen_prompt.user,
            combined_prompt=f"{gen_prompt.system}\n\n---\n\n{gen_prompt.user}",
            sources=sources,
            source_count=len(sources),
            truncated=truncated,
            expected_format=_QA_EXPECTED_FORMAT,
            instructions=_QA_INSTRUCTIONS,
            note=_HANDOFF_NOTE,
        )


__all__ = ["HandoffUseCase", "SUPPORTED_TASKS"]
