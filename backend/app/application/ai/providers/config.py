"""Provider configuration parsing (Sprint M11.1).

Turns the ``AI_PROVIDERS_JSON`` setting into validated
:class:`ProviderConfig` records. Doctrine mirrors ``model_registry``:
strict parsing (a malformed configuration is a server fault, surfaced
loudly) and deterministic ordering (declaration order preserved).
"""
from __future__ import annotations

import json

from app.application.dtos.ai import PROVIDER_KINDS, ProviderConfig


def parse_provider_configs(raw: str) -> tuple[ProviderConfig, ...]:
    """Parse the JSON list of provider configs.

    Raises ``ValueError`` with a factual message when the payload is not a
    JSON list of objects, when an entry is invalid, or when two entries
    target the same provider id. Empty input yields an empty tuple.
    """
    text = (raw or "").strip()
    if not text:
        return ()
    try:
        entries = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"ai_providers_json is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise ValueError("ai_providers_json must be a JSON list.")
    configs: list[ProviderConfig] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each provider entry must be an object.")
        provider_id = str(entry.get("provider_id") or entry.get("kind") or "")
        kind = str(entry.get("kind") or provider_id)
        if provider_id in seen:
            raise ValueError(f"Duplicate provider entry: {provider_id}")
        config = ProviderConfig(
            provider_id=provider_id,
            kind=kind,
            model=str(entry.get("model") or ""),
            base_url=str(entry.get("base_url") or ""),
            timeout_seconds=float(entry.get("timeout_seconds") or 30.0),
            max_tokens=int(entry.get("max_tokens") or 2048),
            temperature=float(entry.get("temperature") or 0.0),
            streaming_enabled=bool(entry.get("streaming_enabled", True)),
        )
        seen.add(provider_id)
        configs.append(config)
    return tuple(configs)


def configs_by_kind(
    configs: tuple[ProviderConfig, ...],
) -> dict[str, ProviderConfig | None]:
    """Map kind -> config for the catalogue kinds.

    One config per kind is allowed; the first occurrence wins. Kinds
    without an entry map to ``None`` (not configured).
    """
    by_kind: dict[str, ProviderConfig | None] = {kind: None for kind in PROVIDER_KINDS}
    for config in configs:
        if by_kind.get(config.kind) is None:
            by_kind[config.kind] = config
    return by_kind


__all__ = ["configs_by_kind", "parse_provider_configs"]
