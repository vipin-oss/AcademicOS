"""Command (CQRS intent) for registering a Publication.

Mirrors ``CreateObjectCommand``: the immutable intent wraps the boundary DTO.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.publication import CreatePublicationInput


@dataclass
class CreatePublicationCommand:
    """Intent to register a Publication (metadata + optional links)."""

    input: CreatePublicationInput
