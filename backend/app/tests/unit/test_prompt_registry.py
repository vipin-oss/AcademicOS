"""Unit tests for the prompt registry (Sprint-7 M1, AI doc A7.1).

Versioned prompt assets: registration, latest/pinned lookup, duplicate
rejection, unknown prompt/version errors, and the Prompt Builder's
registry wiring (identifiable versions, backward-compatible constant
fallback).
"""
from __future__ import annotations

import pytest

from app.application.assistant.prompt_builder import (
    SYSTEM_INSTRUCTIONS,
    AssistantPromptBuilder,
)
from app.application.services.prompt_registry import (
    DEFAULT_PROMPT_ID,
    PromptAsset,
    PromptRegistry,
)


def _asset(version: int, label: str = "1.0", text: str = "v1 system") -> PromptAsset:
    return PromptAsset(
        id=DEFAULT_PROMPT_ID, version=version, version_label=label,
        owner="assistant", system_text=text,
    )


def test_register_and_get_latest():
    registry = PromptRegistry()
    registry.register(_asset(1))
    registry.register(_asset(2, "2.0", "v2 system"))
    assert registry.get(DEFAULT_PROMPT_ID).version == 2
    assert registry.get(DEFAULT_PROMPT_ID).system_text == "v2 system"
    assert registry.latest_version(DEFAULT_PROMPT_ID) == 2


def test_get_pinned_version():
    registry = PromptRegistry()
    registry.register(_asset(1))
    registry.register(_asset(2, "2.0", "v2 system"))
    assert registry.get(DEFAULT_PROMPT_ID, version=1).system_text == "v1 system"
    assert registry.get(DEFAULT_PROMPT_ID, version=1).version == 1


def test_duplicate_registration_rejected():
    registry = PromptRegistry()
    registry.register(_asset(1))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_asset(1))


def test_unknown_prompt_and_version_raise():
    registry = PromptRegistry()
    with pytest.raises(KeyError, match="Unknown prompt"):
        registry.get("ghost")
    registry.register(_asset(1))
    with pytest.raises(KeyError, match="no version"):
        registry.get(DEFAULT_PROMPT_ID, version=99)


def test_invalid_asset_rejected():
    with pytest.raises(ValueError):
        PromptAsset(id="", version=1, version_label="1.0", owner="a", system_text="t")
    with pytest.raises(ValueError):
        PromptAsset(id="a", version=0, version_label="1.0", owner="a", system_text="t")
    with pytest.raises(ValueError):
        PromptAsset(id="a", version=1, version_label="1.0", owner="a", system_text=" ")


def test_all_lists_sorted():
    registry = PromptRegistry()
    registry.register(_asset(2, "2.0"))
    registry.register(_asset(1))
    assert [a.version for a in registry.all()] == [1, 2]


def test_builder_with_registry_uses_asset_and_records_version():
    registry = PromptRegistry()
    registry.register(_asset(1))
    registry.register(_asset(2, "2.0", "REGISTERED V2"))
    builder = AssistantPromptBuilder(prompt_registry=registry)

    prompt = builder.build("find quantum", None)
    assert prompt.system == "REGISTERED V2"
    assert prompt.prompt_id == DEFAULT_PROMPT_ID
    assert prompt.prompt_version == 2


def test_builder_with_pinned_version():
    registry = PromptRegistry()
    registry.register(_asset(1))
    registry.register(_asset(2, "2.0", "v2"))
    builder = AssistantPromptBuilder(prompt_registry=registry, prompt_version=1)
    prompt = builder.build("q", None)
    assert prompt.system == "v1 system"
    assert prompt.prompt_version == 1


def test_builder_without_registry_is_backward_compatible():
    builder = AssistantPromptBuilder()
    prompt = builder.build("q", None)
    assert prompt.system == SYSTEM_INSTRUCTIONS
    assert prompt.prompt_id == DEFAULT_PROMPT_ID
    assert prompt.prompt_version == 1
