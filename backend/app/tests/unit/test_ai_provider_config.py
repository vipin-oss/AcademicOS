"""Unit tests: provider configuration parsing (Sprint M11.1)."""
from __future__ import annotations

import pytest

from app.application.ai.providers.config import (
    configs_by_kind,
    parse_provider_configs,
)


class TestParseProviderConfigs:
    def test_empty_input_yields_empty_tuple(self):
        assert parse_provider_configs("") == ()
        assert parse_provider_configs("   ") == ()
        assert parse_provider_configs(None) == ()

    def test_valid_entries_keep_declaration_order(self):
        raw = (
            '[{"provider_id": "oa", "kind": "openai", "model": "gpt-4o-mini"},'
            ' {"provider_id": "ol", "kind": "ollama", "model": "qwen2.5:7b",'
            ' "temperature": 0.2, "max_tokens": 512}]'
        )
        configs = parse_provider_configs(raw)
        assert [c.provider_id for c in configs] == ["oa", "ol"]
        assert configs[0].model == "gpt-4o-mini"
        assert configs[1].temperature == 0.2
        assert configs[1].max_tokens == 512

    def test_provider_id_defaults_to_kind(self):
        configs = parse_provider_configs('[{"kind": "local"}]')
        assert configs[0].provider_id == "local"

    def test_non_json_rejected(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_provider_configs("not json")

    def test_non_list_rejected(self):
        with pytest.raises(ValueError, match="JSON list"):
            parse_provider_configs('{"provider_id": "x"}')

    def test_non_object_entry_rejected(self):
        with pytest.raises(ValueError, match="object"):
            parse_provider_configs('["openai"]')

    def test_duplicate_provider_id_rejected(self):
        with pytest.raises(ValueError, match="Duplicate"):
            parse_provider_configs(
                '[{"kind": "openai"}, {"provider_id": "openai", "kind": "openai"}]'
            )

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError, match="Unknown provider kind"):
            parse_provider_configs('[{"kind": "bedrock"}]')


class TestConfigsByKind:
    def test_maps_every_catalogue_kind(self):
        configs = parse_provider_configs('[{"kind": "openai"}, {"kind": "local"}]')
        by_kind = configs_by_kind(configs)
        assert set(by_kind) == {"openai", "anthropic", "google", "ollama", "local"}
        assert by_kind["openai"] is not None
        assert by_kind["anthropic"] is None

    def test_first_occurrence_wins(self):
        configs = parse_provider_configs(
            '[{"provider_id": "a", "kind": "openai"},'
            ' {"provider_id": "b", "kind": "openai"}]'
        )
        by_kind = configs_by_kind(configs)
        assert by_kind["openai"].provider_id == "a"
