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
from app.application.services.tools.memory_recall_tool import MemoryRecallTool
from app.domain.repositories.object_repository import ObjectRepository


def build_tool_registry(
    repository: ObjectRepository,
    *,
    memory=None,
) -> InMemoryToolRegistry:
    """Build the L5 tool registry.

    ``memory`` is an optional ``PersistentMemoryService`` (L7). When supplied,
    the ``memory-recall`` tool (Freeze Contract §18) is registered; without it
    the registry is the pre-L7 set (backward compatible).
    """
    registry = InMemoryToolRegistry()
    registry.register(InventoryTool(repository))
    registry.register(CountTool(repository))
    registry.register(ListTool(repository))
    registry.register(LookupTool(repository))
    if memory is not None:
        registry.register(MemoryRecallTool(repository, memory))
    return registry


__all__ = ["build_tool_registry"]
