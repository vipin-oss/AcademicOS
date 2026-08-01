"""Command (CQRS intent) for creating a Universal Object.

The command is the immutable intent the use case executes. It simply wraps the
boundary ``CreateObjectInput`` DTO, making the command/query separation explicit
without duplicating fields.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.object import CreateObjectInput


@dataclass
class CreateObjectCommand:
    """Intent to create a Universal Object."""

    input: CreateObjectInput
