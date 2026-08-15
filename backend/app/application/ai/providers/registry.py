"""Provider registry — discovery + construction (Sprint M11.1).

The registry is the single place that knows *which provider kinds exist*
(discovery catalogue) and *how to build a gateway for a kind* (factory
registration). Doctrine mirrors ``model_registry.py``:

- factories are registered by kind; duplicate registration is rejected;
- building with an unknown kind raises ``UnknownProviderError``;
- the registry is application-pure: factories are plain callables,
  adapters are injected at composition time (infrastructure layer), so
  tests register fakes without touching infrastructure.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from app.application.ai.errors import UnknownProviderError
from app.application.ai.llm.ports import LanguageModelGateway
from app.application.dtos.ai import ProviderConfig

#: A gateway factory takes the provider's config (``None`` = not
#: configured) and returns a gateway implementing the port.
GatewayFactory = Callable[[ProviderConfig | None], LanguageModelGateway]


class ProviderRegistry:
    """Kind -> factory catalogue with deterministic discovery order."""

    def __init__(self) -> None:
        self._factories: dict[str, GatewayFactory] = {}

    def register_factory(self, kind: str, factory: GatewayFactory) -> None:
        """Register the factory for one provider kind.

        Duplicate kinds are rejected (deterministic configuration errors
        beat silent overrides).
        """
        if not kind or not kind.strip():
            raise ValueError("Provider kind must not be empty.")
        if kind in self._factories:
            raise ValueError(f"Provider factory already registered: {kind}")
        self._factories[kind] = factory

    def known_kinds(self) -> tuple[str, ...]:
        """The discovery catalogue: registered kinds in registration
        order (deterministic)."""
        return tuple(self._factories)

    def has_factory(self, kind: str) -> bool:
        return kind in self._factories

    def build(self, config: ProviderConfig) -> LanguageModelGateway:
        """Build one gateway from a config entry."""
        factory = self._factories.get(config.kind)
        if factory is None:
            raise UnknownProviderError(config.kind)
        return factory(config)

    def build_catalogue(
        self,
        kinds: Sequence[str],
        configs: Mapping[str, ProviderConfig | None],
    ) -> dict[str, LanguageModelGateway]:
        """Build every catalogue gateway: ``kinds`` in order, each with
        its config (or ``None`` when not configured). Unknown kinds raise
        ``UnknownProviderError`` — the catalogue must match the registry.
        """
        gateways: dict[str, LanguageModelGateway] = {}
        for kind in kinds:
            factory = self._factories.get(kind)
            if factory is None:
                raise UnknownProviderError(kind)
            gateways[kind] = factory(configs.get(kind))
        return gateways


__all__ = ["GatewayFactory", "ProviderRegistry"]
