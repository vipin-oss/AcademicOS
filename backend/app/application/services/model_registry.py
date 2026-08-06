"""Model registry — the single source of truth for assistant models (Sprint-7 M1).

Models are DEPLOYMENT CONFIGURATION (endpoint, model name, credentials),
not runtime data, so the registry is config-driven rather than persisted:

- ``ModelSpec`` — one registered model (id, endpoint, model name, api key,
  timeout, provider kind). Nothing about prompts or evaluation lives here.
- ``ModelRegistry`` — register / lookup / default selection. Duplicate ids
  are rejected; unknown lookups raise ``KeyError``.
- ``build_provider`` — the ONE provider factory: turns a ``ModelSpec`` into
  the existing ``AssistantProvider`` adapter (LLM transport or rules).
  Provider construction previously lived inline in the route — centralizing
  it here removes duplicated provider logic and keeps routes orchestration-free.

Backward compatibility: an empty registry synthesizes a single ``default``
spec from the legacy ``assistant_llm_*`` settings, so existing deployments
keep working with zero configuration change.
"""
from __future__ import annotations

DEFAULT_MODEL_ID = "default"
PROVIDER_KIND_LLM = "llm"
PROVIDER_KIND_RULES = "rules"


class ModelSpec:
    """One registered model. Immutable configuration value."""

    __slots__ = (
        "id",
        "base_url",
        "model",
        "api_key",
        "timeout_seconds",
        "provider_kind",
    )

    def __init__(
        self,
        *,
        id: str,
        base_url: str | None = None,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 30.0,
        provider_kind: str = PROVIDER_KIND_LLM,
    ) -> None:
        if not id or not id.strip():
            raise ValueError("Model id must not be empty.")
        if not model or not model.strip():
            raise ValueError("Model name must not be empty.")
        if provider_kind not in (PROVIDER_KIND_LLM, PROVIDER_KIND_RULES):
            raise ValueError(f"Unknown provider kind: {provider_kind!r}")
        self.id = id.strip()
        self.base_url = (base_url or "").strip() or None
        self.model = model.strip()
        self.api_key = api_key or ""
        self.timeout_seconds = timeout_seconds
        self.provider_kind = provider_kind

    @property
    def is_llm(self) -> bool:
        return self.provider_kind == PROVIDER_KIND_LLM and self.base_url is not None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "base_url": self.base_url,
            "model": self.model,
            "provider_kind": self.provider_kind,
        }


class ModelRegistry:
    """Named model collection with deterministic default selection."""

    def __init__(self, default_id: str = DEFAULT_MODEL_ID) -> None:
        self._default_id = default_id
        self._specs: dict[str, ModelSpec] = {}

    def register(self, spec: ModelSpec) -> ModelSpec:
        """Register a model; duplicate ids are rejected."""
        if spec.id in self._specs:
            raise ValueError(f"Model already registered: {spec.id}")
        self._specs[spec.id] = spec
        return spec

    def get(self, model_id: str) -> ModelSpec:
        if model_id not in self._specs:
            raise KeyError(f"Unknown model: {model_id}")
        return self._specs[model_id]

    def default(self) -> ModelSpec:
        if self._default_id not in self._specs:
            # Deterministic fallback: the first registered model.
            if not self._specs:
                raise KeyError("No models registered.")
            return next(iter(self._specs.values()))
        return self._specs[self._default_id]

    def all(self) -> list[ModelSpec]:
        return [self._specs[model_id] for model_id in sorted(self._specs)]

    @property
    def default_id(self) -> str:
        return self._default_id


def registry_from_settings(settings) -> ModelRegistry:
    """Build the model registry from application settings.

    The registry is the single source of truth for model names. When no
    models are configured, a single ``default`` spec is synthesized from
    the legacy ``assistant_llm_*`` settings so existing deployments keep
    working unchanged (and the rules provider is always registered as a
    fallback candidate).
    """
    import json

    registry = ModelRegistry(default_id=settings.assistant_default_model)
    # The rules provider is always available.
    registry.register(
        ModelSpec(
            id="rules",
            model="rules-v1",
            provider_kind=PROVIDER_KIND_RULES,
        )
    )
    raw = (settings.assistant_models_json or "").strip()
    if raw:
        try:
            specs = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f"assistant_models_json is not valid JSON: {exc}") from exc
        if not isinstance(specs, list):
            raise ValueError("assistant_models_json must be a JSON list.")
        for entry in specs:
            if not isinstance(entry, dict):
                raise ValueError("Each model spec must be an object.")
            registry.register(
                ModelSpec(
                    id=str(entry["id"]),
                    base_url=entry.get("base_url"),
                    model=str(entry["model"]),
                    api_key=str(entry.get("api_key") or ""),
                    timeout_seconds=float(entry.get("timeout_seconds") or 30.0),
                    provider_kind=str(entry.get("provider_kind") or PROVIDER_KIND_LLM),
                )
            )
    else:
        # Legacy single-model fallback (S6 M2 settings).
        if settings.assistant_llm_base_url:
            registry.register(
                ModelSpec(
                    id=DEFAULT_MODEL_ID,
                    base_url=settings.assistant_llm_base_url,
                    model=settings.assistant_llm_model,
                    api_key=settings.assistant_llm_api_key,
                    timeout_seconds=settings.assistant_llm_timeout_seconds,
                )
            )
        else:
            registry.register(
                ModelSpec(
                    id=DEFAULT_MODEL_ID,
                    model=settings.assistant_llm_model or "rules-v1",
                    provider_kind=PROVIDER_KIND_RULES,
                )
            )
    return registry
