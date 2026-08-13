"""L5 tool-registry port (Freeze Contract §18, ADR-037).

A tool is a deterministic operation registered under a ``ToolSpec``. The
registry is explicit and independent of concrete infrastructure. Tools carry
the user's principal and are ACL-gated by the executor.
"""

from __future__ import annotations

import abc

from app.application.dtos.tool import ToolResult, ToolSpec


class Tool(abc.ABC):
    """One registered L5 tool (the execution unit)."""

    @property
    @abc.abstractmethod
    def spec(self) -> ToolSpec:
        """The frozen registry entry for this tool."""

    @abc.abstractmethod
    def execute(self, *, principal: str, args: dict) -> ToolResult:
        """Deterministically execute the tool for a principal.

        Implementations MUST perform their own data access through existing
        ACL-gated services; the executor additionally enforces the tool's
        ``acl_scope`` before dispatch.
        """


class ToolRegistry(abc.ABC):
    @abc.abstractmethod
    def register(self, tool: Tool) -> None:
        """Register a tool (rejects duplicate names)."""

    @abc.abstractmethod
    def get(self, name: str) -> Tool | None:
        """Resolve a tool by name (deterministic)."""

    @abc.abstractmethod
    def names(self) -> tuple[str, ...]:
        """All registered tool names, deterministic order."""

    @abc.abstractmethod
    def available(self, name: str) -> bool:
        """Whether a tool is registered and usable."""
