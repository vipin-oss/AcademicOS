"""Application port: container / package expander (L2, ADR-029).

A safe expander turns a container blob into member blobs with deterministic
member identity and safety enforcement (path traversal, bombs, depth, counts,
duplicates, corrupt members). Corrupt/unsupported members are explicitly
represented via ``ContainerMember.ok`` — never silently dropped.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class ContainerMember:
    path: str
    data: bytes
    sha256: str
    ok: bool = True
    error: str | None = None
    nested: bool = False


class ContainerExpandError(Exception):
    """The container itself could not be safely expanded (bomb/traversal/etc.)."""


class ContainerExpander(abc.ABC):
    @abc.abstractmethod
    def expand(self, data: bytes) -> list[ContainerMember]:
        """Safely expand a container blob into members.

        Raises ``ContainerExpandError`` when the container as a whole is unsafe
        (traversal, bomb, depth, or structural corruption). Individual members
        that are corrupt/unsupported are returned with ``ok=False`` and an
        explicit error — never silently dropped.
        """
