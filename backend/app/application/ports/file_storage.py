"""Application port: binary file storage.

Mirrors ``DomainEventPublisher``: the Application layer depends only on this
abstraction; infrastructure provides the concrete adapters (the pre-planned
``infrastructure/storage/local`` adapter first, Google Drive / OneDrive later).
No framework imports here.
"""
from __future__ import annotations

import abc


class FileStorage(abc.ABC):
    @abc.abstractmethod
    def save(self, key: str, content: bytes) -> None:
        """Store ``content`` under ``key`` (overwrites any existing blob)."""

    @abc.abstractmethod
    def read(self, key: str) -> bytes:
        """Return the blob stored under ``key`` (raises if it does not exist)."""

    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        """True if a blob is stored under ``key``."""

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        """Remove the blob stored under ``key`` (missing keys are ignored)."""
