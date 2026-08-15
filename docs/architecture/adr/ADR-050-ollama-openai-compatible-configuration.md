# ADR-050 — Ollama is configured as an OpenAI-compatible provider

- **Status:** Accepted
- **Level:** V3 M1 (Instrumentation & Truthful Baseline)
- **Supersedes:** nothing
- **Related:** ADR-001 (AI Core owns provider authority), V3 audit finding A6

## Context

The V3 architecture audit examined how a free/local model would actually run,
because the product requirement is "use free models, keep paid ones optional."

The repository presents five provider kinds:

```python
# app/application/dtos/ai.py
PROVIDER_KINDS = ("openai", "anthropic", "google", "ollama", "local")
```

This reads as five working integrations. It is not. Only one real adapter
exists:

```python
# app/infrastructure/ai/provider_factory.py
_PROVIDER_CLASSES = {
    "openai":    OpenAIProvider,      # real HTTP adapter
    "anthropic": AnthropicProvider,   # NotConfiguredGateway
    "google":    GoogleProvider,      # NotConfiguredGateway
    "ollama":    OllamaProvider,      # NotConfiguredGateway  ← raises
    "local":     LocalProvider,       # NotConfiguredGateway
}
```

`OllamaProvider` subclasses `NotConfiguredGateway`, whose generation methods
raise `AiNotConfiguredError`. Configuring `kind: "ollama"` therefore produces a
gateway that **fails on every call**. The placeholder is honest by design
(it never fabricates AI output) but the naming invites a configuration that
cannot work, and no document stated this.

## Decision

**Ollama is configured as `kind: "openai"` pointing at Ollama's
OpenAI-compatible endpoint.** The dedicated `ollama` kind remains a reserved,
non-functional placeholder until a native adapter is justified by need.

Canonical configuration:

```jsonc
AI_PROVIDERS_JSON=[
  {
    "provider_id": "local-fast",
    "kind": "openai",                          // NOT "ollama"
    "base_url": "http://localhost:11434/v1",   // Ollama's OpenAI-compatible API
    "model": "qwen2.5:1.5b",
    "api_key": "",                             // empty: no Authorization header
    "keep_alive": "-1",                        // model stays resident in RAM
    "timeout_seconds": 30
  }
]
```

This works because of three properties already present in R1:

1. `OpenAIProvider.executable` is driven by `base_url` being set
   (`openai.py:140`), not by any vendor check.
2. An empty `api_key` sends **no** `Authorization` header
   (`openai.py:146-147`), which is what keyless local servers require.
3. `ProviderConfig.keep_alive` is injected into the request body
   (`openai.py:305-309`), which is Ollama's own residency control.

The same configuration shape serves vLLM, LM Studio, llama.cpp and any other
OpenAI-compatible server. Paid providers are the same object with a real
`base_url` and `api_key`, so free↔paid is configuration, never code.

## Consequences

**Positive**
- The free/local path works today with no new adapter.
- One adapter to maintain, test and harden instead of five.
- Free and paid providers are interchangeable by configuration.
- `keep_alive` + M1 boot pre-warm together remove cold-start latency.

**Negative**
- `PROVIDER_KINDS` advertises kinds that are not executable. Mitigated by:
  this ADR, the readiness probe reporting `executable: false`, and the
  placeholder raising honestly rather than returning fake output.
- Ollama-native features outside the OpenAI-compatible surface are
  unavailable. No current requirement needs them.

**Revisit when:** a required capability is absent from Ollama's
OpenAI-compatible API, or a measurement shows the compatibility layer costs
meaningful latency. Either would justify a native adapter behind the same
`LanguageModelGateway` port — a change of one class, not of the architecture.

## Verification

- `/health/ready` reports `ai.executable` and `ai.model_resident`, so a
  misconfiguration is visible rather than silent.
- `test_m1_telemetry_readiness.py` pins that pre-warm never claims residency
  for a non-executable provider.
