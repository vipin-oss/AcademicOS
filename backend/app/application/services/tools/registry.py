"""L5 tool-registry composition (ADR-037).

Builds the L5 tool registry with the approved deterministic data tools. The
registry is independent of concrete infrastructure; tools wrap existing
services (the ObjectRepository).
"""

from __future__ import annotations

from app.application.services.tool_registry import InMemoryToolRegistry
from app.application.services.tools.absence_tool import AbsenceTool
from app.application.services.tools.compare_tool import CompareTool
from app.application.services.tools.cross_domain_tool import CrossDomainTool
from app.application.services.tools.data_tools import (
    CountTool,
    InventoryTool,
    ListTool,
    LookupTool,
)
from app.application.services.tools.memory_recall_tool import MemoryRecallTool
from app.application.services.tools.temporal_tool import TemporalTool
from app.domain.repositories.object_repository import ObjectRepository


def build_tool_registry(
    repository: ObjectRepository,
    *,
    memory=None,
    cross_domain=None,
) -> InMemoryToolRegistry:
    """Build the L5 tool registry.

    Additive options:
    - ``memory`` (L7 ``PersistentMemoryService``): registers ``memory-recall``.
    - ``cross_domain`` (L8 ``CrossDomainService``): registers ``cross-domain``,
      ``absence``, ``temporal``, ``compare`` (Freeze Contract §18).
    Without them the registry is the base data-tool set (backward compatible).
    """
    registry = InMemoryToolRegistry()
    registry.register(InventoryTool(repository))
    registry.register(CountTool(repository))
    registry.register(ListTool(repository))
    registry.register(LookupTool(repository))
    if memory is not None:
        registry.register(MemoryRecallTool(repository, memory))
    if cross_domain is not None:
        registry.register(CrossDomainTool(repository, cross_domain))
        registry.register(AbsenceTool(repository, cross_domain))
        registry.register(TemporalTool(repository, cross_domain))
        registry.register(CompareTool(repository, cross_domain))
    return registry


__all__ = ["build_tool_registry"]
