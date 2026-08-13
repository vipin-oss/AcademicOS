"""L5 tool-registry composition (ADR-037).

Builds the L5 tool registry with the approved deterministic data tools. The
registry is independent of concrete infrastructure; tools wrap existing
services (the ObjectRepository).
"""

from __future__ import annotations

from app.application.services.tool_registry import InMemoryToolRegistry
from app.application.services.tools.data_tools import (
    CountTool,
    InventoryTool,
    ListTool,
    LookupTool,
)
from app.domain.repositories.object_repository import ObjectRepository


def build_tool_registry(repository: ObjectRepository) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()
    registry.register(InventoryTool(repository))
    registry.register(CountTool(repository))
    registry.register(ListTool(repository))
    registry.register(LookupTool(repository))
    return registry


__all__ = ["build_tool_registry"]
