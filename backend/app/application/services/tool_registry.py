"""L5 in-memory tool registry (Freeze Contract §18, ADR-037).

Explicit registration, deterministic lookup, duplicate-name protection, schema
validation of the registry entry. Independent of concrete infrastructure —
tools are injected at composition time.
"""

from __future__ import annotations

from app.application.dtos.tool import ToolSpec
from app.application.ports.tool_registry import Tool, ToolRegistry


class RegistryError(Exception):
    """A registry registration/lookup error."""


class InMemoryToolRegistry(ToolRegistry):
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        spec: ToolSpec = tool.spec
        if not spec.name:
            raise RegistryError("Tool name must not be empty.")
        if not isinstance(spec.input_schema, dict) or not spec.input_schema:
            raise RegistryError(f"Tool {spec.name!r} must declare an input_schema.")
        if not isinstance(spec.output_schema, dict) or not spec.output_schema:
            raise RegistryError(f"Tool {spec.name!r} must declare an output_schema.")
        if spec.name in self._tools:
            raise RegistryError(f"Duplicate tool name: {spec.name!r}")
        self._tools[spec.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools.keys()))

    def available(self, name: str) -> bool:
        return name in self._tools


__all__ = ["InMemoryToolRegistry", "RegistryError"]
