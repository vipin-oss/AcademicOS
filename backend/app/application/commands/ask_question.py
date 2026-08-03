"""Command: Ask the assistant a question (answer + persisted message pair)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.assistant import AskQuestionInput


@dataclass
class AskQuestionCommand:
    input: AskQuestionInput
