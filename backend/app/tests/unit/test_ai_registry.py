"""Unit tests: provider registry (Sprint M11.1)."""
from __future__ import annotations

import pytest

from app.application.ai.errors import UnknownProviderError
from app.application.ai.providers.registry import ProviderRegistry
from app.application.dtos.ai import ProviderConfig


def _fake_factory(marker: str):
    def factory(config: ProviderConfig | None):
        return {"marker": marker, "config": config}

    return factory


class TestProviderRegistry:
    def test_empty_registry_has_empty_catalogue(self):
        registry = ProviderRegistry()
        assert registry.known_kinds() == ()

    def test_registration_order_is_discovery_order(self):
        registry = ProviderRegistry()
        registry.register_factory("openai", _fake_factory("oa"))
        registry.register_factory("local", _fake_factory("lc"))
        assert registry.known_kinds() == ("openai", "local")
        assert registry.has_factory("openai")
        assert not registry.has_factory("anthropic")

    def test_duplicate_registration_rejected(self):
        registry = ProviderRegistry()
        registry.register_factory("openai", _fake_factory("a"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register_factory("openai", _fake_factory("b"))

    def test_empty_kind_rejected(self):
        registry = ProviderRegistry()
        with pytest.raises(ValueError):
            registry.register_factory("  ", _fake_factory("x"))

    def test_build_uses_the_kinds_factory(self):
        registry = ProviderRegistry()
        registry.register_factory("openai", _fake_factory("oa"))
        gateway = registry.build(ProviderConfig(provider_id="main", kind="openai"))
        assert gateway["marker"] == "oa"
        assert gateway["config"].model == ""

    def test_build_unknown_kind_raises(self):
        # "local" is a valid catalogue kind, but no factory is registered —
        # the registry (not the config validator) reports the unknown kind.
        registry = ProviderRegistry()
        registry.register_factory("openai", _fake_factory("oa"))
        with pytest.raises(UnknownProviderError):
            registry.build(ProviderConfig(provider_id="x", kind="local"))

    def test_build_catalogue_maps_configs_to_kinds(self):
        registry = ProviderRegistry()
        registry.register_factory("openai", _fake_factory("oa"))
        registry.register_factory("local", _fake_factory("lc"))
        configs = {
            "openai": ProviderConfig(provider_id="oa", kind="openai", model="m1"),
            "local": None,
        }
        gateways = registry.build_catalogue(("openai", "local"), configs)
        assert gateways["openai"]["config"].model == "m1"
        assert gateways["local"]["config"] is None

    def test_build_catalogue_unknown_kind_raises(self):
        registry = ProviderRegistry()
        registry.register_factory("openai", _fake_factory("oa"))
        with pytest.raises(UnknownProviderError):
            registry.build_catalogue(("openai", "bedrock"), {})
