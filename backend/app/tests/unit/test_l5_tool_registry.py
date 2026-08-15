"""L5 tool registry + executor tests (ADR-037)."""

from __future__ import annotations

import pytest

from app.application.dtos.tool import ToolResult, ToolSpec
from app.application.ports.tool_registry import Tool
from app.application.services.tool_executor import ToolExecutor
from app.application.services.tool_registry import InMemoryToolRegistry, RegistryError
from app.domain.value_objects.enums import PermissionAction


class _FakePermission:
    def __init__(self, allowed: bool = True):
        self._allowed = allowed

    def can(self, *, principal, scope, action):
        return self._allowed and action is PermissionAction.READ


class _NoAudit:
    def add(self, record):
        return record

    def recent(self, limit=50):
        return []


class _EchoTool(Tool):
    spec = ToolSpec(
        name="echo", input_schema={"properties": {"v": {"type": "string"}}},
        output_schema={"properties": {"v": {"type": "string"}}}, acl_scope="echo",
    )

    def execute(self, *, principal, args):
        return ToolResult(tool_name="echo", principal=principal, ok=True, value=args)


def test_registry_register_and_lookup():
    reg = InMemoryToolRegistry()
    reg.register(_EchoTool())
    assert reg.names() == ("echo",)
    assert reg.available("echo") is True
    assert reg.get("echo") is not None


def test_registry_rejects_duplicate():
    reg = InMemoryToolRegistry()
    reg.register(_EchoTool())
    with pytest.raises(RegistryError):
        reg.register(_EchoTool())


def test_registry_rejects_empty_name():
    class _Bad(Tool):
        spec = ToolSpec(name="", input_schema={"properties": {}},
                        output_schema={"properties": {}}, acl_scope="x")
        def execute(self, *, principal, args):
            return ToolResult(tool_name="", principal=principal, ok=True, value={})

    with pytest.raises(RegistryError):
        InMemoryToolRegistry().register(_Bad())


def test_executor_unknown_tool_returns_error():
    ex = ToolExecutor(InMemoryToolRegistry(), permissions=_FakePermission(), audit=_NoAudit())
    r = ex.execute(principal="u:1", tool_name="nope", args={})
    assert r.ok is False
    assert "Unknown tool" in (r.error or "")


def test_executor_acl_deny():
    reg = InMemoryToolRegistry()
    reg.register(_EchoTool())
    ex = ToolExecutor(reg, permissions=_FakePermission(allowed=False), audit=_NoAudit())
    r = ex.execute(principal="u:1", tool_name="echo", args={"v": "x"})
    assert r.ok is False
    assert r.error == "Access denied"


def test_executor_validates_input_schema():
    reg = InMemoryToolRegistry()
    reg.register(_EchoTool())
    ex = ToolExecutor(reg, permissions=_FakePermission(), audit=_NoAudit())
    r = ex.execute(principal="u:1", tool_name="echo", args={"v": 123})
    assert r.ok is False
    assert "must be a string" in (r.error or "")


def test_executor_principal_propagates_and_succeeds():
    reg = InMemoryToolRegistry()
    reg.register(_EchoTool())
    ex = ToolExecutor(reg, permissions=_FakePermission(), audit=_NoAudit())
    r = ex.execute(principal="u:7", tool_name="echo", args={"v": "hi"})
    assert r.ok is True
    assert r.principal == "u:7"
    assert r.value == {"v": "hi"}


def test_executor_is_deterministic():
    reg = InMemoryToolRegistry()
    reg.register(_EchoTool())
    ex = ToolExecutor(reg, permissions=_FakePermission(), audit=_NoAudit())
    a = ex.execute(principal="u:1", tool_name="echo", args={"v": "x"}).value
    b = ex.execute(principal="u:1", tool_name="echo", args={"v": "x"}).value
    assert a == b
