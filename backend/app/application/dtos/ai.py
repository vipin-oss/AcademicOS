"""AI Core DTOs (Sprint M11.1 — AI Foundation).

The shared vocabulary of the AI capability layer. Everything the
``LanguageModelGateway`` port exchanges lives here as frozen dataclasses,
mirroring the ``dtos/assistant.py`` doctrine: strict validation in
``__post_init__``, tuples for ordered/immutable collections, no provider-
specific fields anywhere.

M11.1 is infrastructure-only: the five provider kinds are a *catalogue*,
generation operations are defined but never executed (gateways report
``not_configured``), and token/cost values are deterministic estimates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Provider catalogue (M11.1: discovery surface; adapters arrive in M11.2+)
# ---------------------------------------------------------------------------
PROVIDER_KIND_OPENAI = "openai"
PROVIDER_KIND_ANTHROPIC = "anthropic"
PROVIDER_KIND_GOOGLE = "google"
PROVIDER_KIND_OLLAMA = "ollama"
PROVIDER_KIND_LOCAL = "local"

PROVIDER_KINDS: tuple[str, ...] = (
    PROVIDER_KIND_OPENAI,
    PROVIDER_KIND_ANTHROPIC,
    PROVIDER_KIND_GOOGLE,
    PROVIDER_KIND_OLLAMA,
    PROVIDER_KIND_LOCAL,
)

#: Human-facing catalogue labels, in the same order as ``PROVIDER_KINDS``.
PROVIDER_LABELS: dict[str, str] = {
    PROVIDER_KIND_OPENAI: "OpenAI",
    PROVIDER_KIND_ANTHROPIC: "Anthropic",
    PROVIDER_KIND_GOOGLE: "Google",
    PROVIDER_KIND_OLLAMA: "Ollama",
    PROVIDER_KIND_LOCAL: "Local",
}

#: Capabilities a provider *kind* will support once a real adapter exists.
#: Informational only in M11.1 — no adapter implements them yet.
KIND_CAPABILITIES: dict[str, tuple[str, ...]] = {
    PROVIDER_KIND_OPENAI: ("chat", "stream", "structured_output", "tools"),
    PROVIDER_KIND_ANTHROPIC: ("chat", "stream", "structured_output", "tools"),
    PROVIDER_KIND_GOOGLE: ("chat", "stream", "structured_output", "tools"),
    PROVIDER_KIND_OLLAMA: ("chat", "stream"),
    PROVIDER_KIND_LOCAL: ("chat", "stream"),
}

# ---------------------------------------------------------------------------
# Health / status vocabulary
# ---------------------------------------------------------------------------
STATUS_CONFIGURED = "configured"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_DISABLED = "disabled"
STATUS_ERROR = "error"

HEALTH_OK = "ok"
HEALTH_NOT_CONFIGURED = "not_configured"
HEALTH_DISABLED = "disabled"
HEALTH_ERROR = "error"

NOT_CONFIGURED_DETAIL = (
    "Provider '{provider_id}' is not configured: no adapter is wired for "
    "kind '{kind}' yet. Adapters land in a later M11 sprint; until then all "
    "generation operations raise AiNotConfiguredError."
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProviderConfig:
    """One configured provider entry (from ``AI_PROVIDERS_JSON``).

    Configuration data only — never credentials (M11.1 stores no API keys
    anywhere). Fields are consumed by future adapters; placeholders only
    report them.
    """

    provider_id: str
    kind: str
    model: str = ""
    base_url: str = ""
    timeout_seconds: float = 30.0
    max_tokens: int = 2048
    temperature: float = 0.0
    streaming_enabled: bool = True

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("ProviderConfig provider_id must not be empty.")
        if self.kind not in PROVIDER_KINDS:
            raise ValueError(f"Unknown provider kind: {self.kind!r}")
        if self.timeout_seconds <= 0:
            raise ValueError("ProviderConfig timeout_seconds must be positive.")
        if self.max_tokens < 1:
            raise ValueError("ProviderConfig max_tokens must be >= 1.")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("ProviderConfig temperature must be in [0.0, 2.0].")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ModelInfo:
    """One model exposed by a provider.

    ``configured=False`` marks models that are *declared* in configuration
    but not usable yet (no adapter) — the settings surface shows them
    honestly instead of pretending they work.
    """

    provider_id: str
    model_id: str
    display_name: str = ""
    context_window: int | None = None
    capabilities: tuple[str, ...] = ()
    configured: bool = True

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("ModelInfo provider_id must not be empty.")
        if not self.model_id.strip():
            raise ValueError("ModelInfo model_id must not be empty.")
        if self.context_window is not None and self.context_window < 1:
            raise ValueError("ModelInfo context_window must be >= 1 or None.")


# ---------------------------------------------------------------------------
# Generation contracts
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TokenUsage:
    """Token counts for one call. ``estimated`` is True when the provider
    reported no native counts (always true in M11.1)."""

    input_tokens: int = 0
    output_tokens: int = 0
    estimated: bool = True

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("TokenUsage counts must be >= 0.")


@dataclass(frozen=True)
class GenerationPrompt:
    """The provider-independent generation request (system + user)."""

    user: str
    system: str = ""
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.user:
            raise ValueError("GenerationPrompt user must not be empty.")
        if self.temperature is not None and not 0.0 <= self.temperature <= 2.0:
            raise ValueError("GenerationPrompt temperature must be in [0.0, 2.0].")
        if self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError("GenerationPrompt max_tokens must be >= 1.")


@dataclass(frozen=True)
class GenerationResult:
    """One complete generation (non-streaming)."""

    text: str
    model: str
    finish_reason: str = "stop"
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("GenerationResult model must not be empty.")
        if self.latency_ms < 0:
            raise ValueError("GenerationResult latency_ms must be >= 0.")


@dataclass(frozen=True)
class GenerationEvent:
    """One streaming event: ``kind`` is ``token`` | ``complete`` | ``error``."""

    kind: str
    delta: str = ""
    result: GenerationResult | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("token", "complete", "error"):
            raise ValueError(f"Unknown GenerationEvent kind: {self.kind!r}")


@dataclass(frozen=True)
class StructuredGenerationPrompt:
    """Structured-output request: the caller supplies a JSON Schema."""

    user: str
    schema: dict
    system: str = ""
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.user:
            raise ValueError("StructuredGenerationPrompt user must not be empty.")
        if not isinstance(self.schema, dict) or not self.schema:
            raise ValueError("StructuredGenerationPrompt schema must be a non-empty object.")
        if self.temperature is not None and not 0.0 <= self.temperature <= 2.0:
            raise ValueError("StructuredGenerationPrompt temperature must be in [0.0, 2.0].")


@dataclass(frozen=True)
class StructuredGenerationResult:
    """One structured generation: the validated value plus the raw text."""

    value: dict
    raw_text: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.value, dict):
            raise ValueError("StructuredGenerationResult value must be an object.")
        if not self.model:
            raise ValueError("StructuredGenerationResult model must not be empty.")


# ---------------------------------------------------------------------------
# Health / registry views
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProviderHealth:
    """Per-provider health as reported by the gateway."""

    provider_id: str
    display_name: str
    kind: str
    status: str
    configured: bool
    models_configured: int
    detail: str
    checked_at: str = ""

    def __post_init__(self) -> None:
        if self.status not in (STATUS_CONFIGURED, STATUS_NOT_CONFIGURED, STATUS_ERROR):
            raise ValueError(f"Unknown ProviderHealth status: {self.status!r}")
        if self.models_configured < 0:
            raise ValueError("ProviderHealth models_configured must be >= 0.")


@dataclass(frozen=True)
class ProviderRecord:
    """One provider row for the settings/health surface."""

    provider_id: str
    display_name: str
    kind: str
    status: str
    configured: bool
    models: tuple[ModelInfo, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class AiHealthSummary:
    """Aggregate AI health (GET /ai/health)."""

    status: str
    ai_enabled: bool
    default_provider: str
    default_model: str
    default_provider_valid: bool
    providers_total: int
    providers_configured: int
    feature_flags: dict[str, bool]
    checked_at: str = ""


@dataclass(frozen=True)
class AiModelsSummary:
    """Aggregate model catalogue (GET /ai/models)."""

    default_provider: str
    default_model: str
    models: tuple[ModelInfo, ...] = ()


# ---------------------------------------------------------------------------
# Serialization helpers (deterministic, shared by routes and tests)
# ---------------------------------------------------------------------------
def provider_record_dict(record: ProviderRecord) -> dict:
    return {
        "provider_id": record.provider_id,
        "display_name": record.display_name,
        "kind": record.kind,
        "status": record.status,
        "configured": record.configured,
        "models": [model_info_dict(m) for m in record.models],
        "detail": record.detail,
    }


def model_info_dict(info: ModelInfo) -> dict:
    return {
        "provider_id": info.provider_id,
        "model_id": info.model_id,
        "display_name": info.display_name,
        "context_window": info.context_window,
        "capabilities": list(info.capabilities),
        "configured": info.configured,
    }


def health_summary_dict(summary: AiHealthSummary) -> dict:
    return {
        "status": summary.status,
        "ai_enabled": summary.ai_enabled,
        "default_provider": summary.default_provider,
        "default_model": summary.default_model,
        "default_provider_valid": summary.default_provider_valid,
        "providers_total": summary.providers_total,
        "providers_configured": summary.providers_configured,
        "feature_flags": dict(summary.feature_flags),
        "checked_at": summary.checked_at,
    }


def models_summary_dict(summary: AiModelsSummary) -> dict:
    return {
        "default_provider": summary.default_provider,
        "default_model": summary.default_model,
        "models": [model_info_dict(m) for m in summary.models],
    }


__all__ = [
    "AiHealthSummary",
    "AiModelsSummary",
    "GenerationEvent",
    "GenerationPrompt",
    "GenerationResult",
    "HEALTH_DISABLED",
    "HEALTH_ERROR",
    "HEALTH_NOT_CONFIGURED",
    "HEALTH_OK",
    "KIND_CAPABILITIES",
    "ModelInfo",
    "NOT_CONFIGURED_DETAIL",
    "PROVIDER_KINDS",
    "PROVIDER_KIND_ANTHROPIC",
    "PROVIDER_KIND_GOOGLE",
    "PROVIDER_KIND_LOCAL",
    "PROVIDER_KIND_OLLAMA",
    "PROVIDER_KIND_OPENAI",
    "PROVIDER_LABELS",
    "ProviderConfig",
    "ProviderHealth",
    "ProviderRecord",
    "STATUS_CONFIGURED",
    "STATUS_DISABLED",
    "STATUS_ERROR",
    "STATUS_NOT_CONFIGURED",
    "StructuredGenerationPrompt",
    "StructuredGenerationResult",
    "TokenUsage",
    "health_summary_dict",
    "model_info_dict",
    "models_summary_dict",
    "provider_record_dict",
]
