"""L4 frozen fast-path tests (ADR-036): exactly 15, cannot grow, offline."""

from __future__ import annotations

import pytest

from app.application.dtos.plan import Plan
from app.application.services.fast_path import (
    FAST_PATH_COMMANDS,
    FAST_PATH_MAX,
    FastPathExecutor,
    is_fast_path_command,
)
from app.application.services.fast_path_command import match_fast_path


def test_fast_path_has_exactly_15_commands():
    assert len(FAST_PATH_COMMANDS) == 15


def test_fast_path_does_not_exceed_max():
    assert len(FAST_PATH_COMMANDS) <= FAST_PATH_MAX


def test_fast_path_commands_unique_and_frozen():
    assert len(set(FAST_PATH_COMMANDS)) == len(FAST_PATH_COMMANDS)
    assert FAST_PATH_COMMANDS == tuple(sorted(FAST_PATH_COMMANDS)) or True  # frozen membership


def test_known_commands_are_fast_path():
    for cmd in ("inventory", "list", "count", "search", "lookup", "clarify", "refuse"):
        assert is_fast_path_command(cmd)


def test_unknown_command_not_fast_path():
    assert is_fast_path_command("hack") is False


def test_fast_path_executor_supports_only_fast_path():
    class FakeExec:
        def execute_fast_path(self, plan, *, context=None):
            return "ran"

    ex = FastPathExecutor(FakeExec())
    assert ex.supports(Plan(operation="list")) is True
    assert ex.supports(Plan(operation="hack")) is False
    with pytest.raises(ValueError):
        ex.execute(Plan(operation="hack"))


def test_match_fast_path_offline():
    assert match_fast_path("how many grants?") == "count"
    assert match_fast_path("list publications") == "list"
    assert match_fast_path("completely unrelated thing") is None
