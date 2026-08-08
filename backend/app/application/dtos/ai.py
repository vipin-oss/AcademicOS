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

HEALTH_OK = "ok"  # reserved for operationally-verified state (never used without a probe)
HEALTH_CONFIGURED = "configured"  # the strongest honest aggregate status: executable but not verified
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

    Configuration + the single credential seam (M11.2, ADR-001 Q7.5):
    ``api_key`` is the only secret a provider adapter may read, and it is
    read ONLY inside the adapter (never logged, never serialized to the
    API). Empty by default — an unconfigured provider has no key.
    """

    provider_id: str
    kind: str
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = 30.0
    max_tokens: int = 2048
    temperature: float = 0.0
    streaming_enabled: bool = True
    embedding_model: str = ""
    embedding_dimensions: int | None = None

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
    """The provider-independent generation request (system + user).

    ``extra_body`` (M11.2) is a provider-agnostic escape hatch: an optional
    dict of additional request fields the caller asks the gateway to merge
    into its wire body. It keeps the gateway contract provider-independent
    (no first-class assistant concepts leak in) while letting a composed
    feature attach structured request metadata — e.g. the assistant attaches
    its numbered evidence as ``extra_body={"citations": [...]}``. Adapters
    are free to ignore it.
    """

    user: str
    system: str = ""
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    extra_body: dict | None = None

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
    """Per-provider health as reported by the gateway.

    Three distinct runtime states (M11.3.2):
    - ``configured``  — the provider is DECLARED in configuration (an entry exists).
    - ``executable``  — the gateway can actually run (a real adapter + endpoint).
    - ``operational`` — the endpoint is verified reachable (None = not probed;
      AcademicOS performs no live health probe, so this is honestly unknown).
    Readiness (status "ok" / ``executable``) is never claimed merely because a
    configuration entry exists.
    """

    provider_id: str
    display_name: str
    kind: str
    status: str
    configured: bool
    executable: bool = False
    operational: bool | None = None
    models_configured: int = 0
    detail: str = ""
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
    executable: bool = False
    operational: bool | None = None
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



@dataclass(frozen=True)
class SummarizeResult:
    """The result of an on-demand document summarization (M12.1).

    ``available`` is False when the gateway could not produce a summary
    (not configured or provider error) — the ``summary`` field carries an
    honest fallback message. ``truncated`` / ``chars_used`` / ``chars_total``
    disclose whether the source text was truncated before generation.

    M13.3 retrofits the M13.1 provenance contract (provider, model, prompt
    version, tokens, latency) so every summary is observable and auditable,
    mirroring ``QAResult`` / ``EnrichmentResult``. Provenance is sourced from
    the actual ``GenerationResult`` (never fabricated); the fallback path
    records only the prompt identity (no provider/model — none produced one).
    """

    summary: str
    available: bool = True
    truncated: bool = False
    chars_used: int = 0
    chars_total: int = 0
    # Provenance contract (M13.1; retrofitted in M13.3).
    provider_id: str = ""
    model: str = ""
    prompt_id: str = ""
    prompt_version: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_estimated: bool = True
    latency_ms: int = 0

    def __post_init__(self) -> None:
        if self.chars_used < 0 or self.chars_total < 0:
            raise ValueError("SummarizeResult char counts must be >= 0.")
        if self.chars_used > self.chars_total:
            raise ValueError("SummarizeResult chars_used must be <= chars_total.")
        if self.latency_ms < 0:
            raise ValueError("SummarizeResult latency_ms must be >= 0.")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("SummarizeResult token counts must be >= 0.")



@dataclass(frozen=True)
class QAResult:
    """The result of a grounded question-answering call (M13.1).

    Includes provenance metadata (provider, model, prompt version, tokens,
    latency) so every AI answer is observable and auditable. ``available``
    is False when the gateway could not produce an answer — the ``answer``
    field carries an honest fallback.
    """

    answer: str
    available: bool = True
    retrieved_count: int = 0
    truncated: bool = False
    citations: tuple[dict, ...] = ()
    provider_id: str = ""
    model: str = ""
    prompt_id: str = ""
    prompt_version: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_estimated: bool = True
    latency_ms: int = 0

    def __post_init__(self) -> None:
        if self.retrieved_count < 0:
            raise ValueError("QAResult retrieved_count must be >= 0.")
        if self.latency_ms < 0:
            raise ValueError("QAResult latency_ms must be >= 0.")



@dataclass(frozen=True)
class EnrichmentResult:
    """The result of an on-demand document enrichment (M13.2).

    Structured metadata extracted from the document's authoritative text via
    the AI Core's ``structured_generate`` (the first production use of M11
    structured generation). ``available`` is False when the gateway could not
    enrich (not configured or provider error) — the fields then carry honest
    empty/fallback values. ``truncated`` / ``chars_used`` / ``chars_total``
    disclose whether the source text was truncated before generation.
    Includes the provenance contract from M13.1.
    """

    title: str = ""
    summary: str = ""
    tags: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    available: bool = True
    truncated: bool = False
    chars_used: int = 0
    chars_total: int = 0
    # Provenance contract (M13.1).
    provider_id: str = ""
    model: str = ""
    prompt_id: str = ""
    prompt_version: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_estimated: bool = True
    latency_ms: int = 0

    def __post_init__(self) -> None:
        if self.chars_used < 0 or self.chars_total < 0:
            raise ValueError("EnrichmentResult char counts must be >= 0.")
        if self.chars_used > self.chars_total:
            raise ValueError("EnrichmentResult chars_used must be <= chars_total.")
        if self.latency_ms < 0:
            raise ValueError("EnrichmentResult latency_ms must be >= 0.")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("EnrichmentResult token counts must be >= 0.")


@dataclass(frozen=True)
class RelatedDocumentItem:
    """One related document (M13.3) — semantic-similarity nearest neighbour.

    Carries ONLY fields already supported by the existing search/vector result
    contract (object identity, type, title, version) plus a deterministic
    score derived with the existing search scoring convention (reciprocal-rank
    fusion). No content is exposed and no LLM provenance is fabricated
    (related documents is an embedding/search capability, not generation).
    """

    object_id: str
    object_type: str
    title: str
    score: float
    version: int = 0


@dataclass(frozen=True)
class RelatedDocumentsResult:
    """Related documents for one source (M13.3).

    ``items`` is ordered by descending semantic similarity (deterministic,
    ``object_id`` tie-breaks inherited from the vector repository). An empty
    tuple is a valid response (no readable related documents, or the
    embedding/search backend is unavailable).
    """

    items: tuple[RelatedDocumentItem, ...] = ()


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
        "executable": record.executable,
        "operational": record.operational,
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


def summarize_result_dict(result: SummarizeResult) -> dict:
    return {
        "summary": result.summary,
        "available": result.available,
        "truncated": result.truncated,
        "chars_used": result.chars_used,
        "chars_total": result.chars_total,
        "provider_id": result.provider_id,
        "model": result.model,
        "prompt_id": result.prompt_id,
        "prompt_version": result.prompt_version,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "token_usage_estimated": result.token_usage_estimated,
        "latency_ms": result.latency_ms,
    }


def related_documents_result_dict(result: RelatedDocumentsResult) -> dict:
    return {
        "items": [
            {
                "object_id": item.object_id,
                "object_type": item.object_type,
                "title": item.title,
                "score": item.score,
                "version": item.version,
            }
            for item in result.items
        ]
    }


def qa_result_dict(result: QAResult) -> dict:
    return {
        "answer": result.answer,
        "available": result.available,
        "retrieved_count": result.retrieved_count,
        "truncated": result.truncated,
        "citations": list(result.citations),
        "provider_id": result.provider_id,
        "model": result.model,
        "prompt_id": result.prompt_id,
        "prompt_version": result.prompt_version,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "token_usage_estimated": result.token_usage_estimated,
        "latency_ms": result.latency_ms,
    }


def enrichment_result_dict(result: EnrichmentResult) -> dict:
    return {
        "title": result.title,
        "summary": result.summary,
        "tags": list(result.tags),
        "categories": list(result.categories),
        "keywords": list(result.keywords),
        "available": result.available,
        "truncated": result.truncated,
        "chars_used": result.chars_used,
        "chars_total": result.chars_total,
        "provider_id": result.provider_id,
        "model": result.model,
        "prompt_id": result.prompt_id,
        "prompt_version": result.prompt_version,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "token_usage_estimated": result.token_usage_estimated,
        "latency_ms": result.latency_ms,
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
    "EnrichmentResult",
    "RelatedDocumentItem",
    "RelatedDocumentsResult",
    "GenerationEvent",
    "GenerationPrompt",
    "GenerationResult",
    "HEALTH_DISABLED",
    "HEALTH_ERROR",
    "HEALTH_NOT_CONFIGURED",
    "HEALTH_CONFIGURED",
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
    "SummarizeResult",
    "QAResult",
    "TokenUsage",
    "health_summary_dict",
    "model_info_dict",
    "models_summary_dict",
    "summarize_result_dict",
    "qa_result_dict",
    "enrichment_result_dict",
    "related_documents_result_dict",
    "provider_record_dict",
]
