# AcademicOS — AI Developer Guide (extended through M11.3.1)

How the AI Core works and how to extend it. The core contract:
**adding a new provider (or a new AI capability) requires implementing an
adapter — nothing else in the system changes.**

## L0 — frozen architecture (read this first)

The architectural contract lives in
[`docs/architecture/`](docs/architecture/) (Freeze Contract Part 13).

- A failed user question is diagnosed at the **capability** level.
  Add a phrasing under `backend/app/tests/eval/capabilities/golden/`.
- **Do not** add a regex, `INTENT_*`, `_answer_*` builder, or
  `retrieval_plan` special case.
- `rules-v1` is legacy: frozen, not the target, deleted at L4 (ADR-020).
- Run `python scripts/eval_capabilities.py --check` from `backend/` to
  validate the capability catalog (no model required).

---

## 1. The architecture in one picture

```
 application/ai/          pure: ports, DTOs, registry, config, core, use cases
 infrastructure/ai/       adapters (placeholders today, real adapters later)
 api/dependencies/ai.py   the DI seam (get_ai_core — overridable in tests)
 api/routes/ai.py         /ai/health · /ai/providers · /ai/models
```

Layering rules (enforced by `tests/architecture/test_ai_guardrails.py`):

1. `application/ai` imports **no** infrastructure, no API, no frameworks,
   no other AI feature modules (assistant/intake).
2. `infrastructure/ai` adapters never import each other — the only
   composition crossing is `infrastructure/ai/provider_factory.py`.
3. Routes never construct anything — they receive the composed `AiCore`
   through `get_ai_core`.



## 1a. Provider identity & selection contract (M11.3.1)

Three distinct identifiers — never conflated:

| Concept | Meaning | Example |
|---|---|---|
| `provider_id` | The configured **catalogue identity** of one provider (from `AI_PROVIDERS_JSON` `provider_id`). Unique; selection key. | `"oa"`, `"main"` |
| `kind` | The provider **family/adapter** (one of `PROVIDER_KINDS`). | `"openai"` |
| `model` / `model_id` | The **model name** configured on a provider (`ProviderConfig.model`). A property of a provider, not a selection key. | `"gpt-4o-mini"` |

- A gateway reports `provider_id` = its configured catalogue identity (NOT the
  kind), so multiple providers of the same kind stay distinguishable. When no
  config is present (discovery), `provider_id` falls back to `kind`.
- Selection resolves a `provider_id` via `AiCore.select_provider(requested, pinned)`
  with precedence **override > conversation pin > configured default**.
- The assistant's selection key is `provider_id` (API field `provider_id`;
  `model_id` is a deprecated alias). The conversation pin is stored under
  metadata key `assistant.provider_id` (legacy `assistant.model_id` still read).
- `AI_DEFAULT_MODEL`, when set, makes the default provider the one whose model
  matches — so it genuinely influences runtime selection.
- Health (`/ai/health`) reports the **runtime-effective** default provider and
  `default_provider_valid` = the default is actually executable; it never claims
  "ok" when the selected provider cannot run.
- `AiCore.build_gateway(config)` is **disabled** — gateways come only from the
  catalogue via `select_provider` / `gateway`.

## 2. The LanguageModelGateway port

`backend/app/application/ai/llm/ports.py` defines the six operations
every provider implements (snake_case; the M11.1 brief's names in
parentheses):

| Operation | Purpose | M11.1 placeholder behavior |
|---|---|---|
| `health()` | provider status | reports `not_configured` |
| `list_models()` | declared model catalogue | returns configured entries marked `configured=False` |
| `generate(prompt)` | one completion | raises `AiNotConfiguredError` |
| `stream(prompt)` | token stream | raises `AiNotConfiguredError` |
| `structured_generate(prompt)` | JSON-Schema output | raises `AiNotConfiguredError` |
| `count_tokens(text)` | token estimate | deterministic `ceil(len/4)` |
| `estimate_cost(...)` | USD estimate | `0.0` (no price tables) |

**Doctrine:** no fake AI responses, no network in tests, temperature-0
determinism, prompts are built by the prompt layer (future sprint), not
by adapters.

## 3. How to add a real provider (the "implement only an adapter" path)

> **M11.2 status:** the OpenAI adapter described below is **already real** —
> `infrastructure/ai/llm/openai.py::OpenAIProvider` is the reference
> `LanguageModelGateway` implementation and the single owner of generative
> transport. Use it as the template for the next provider.

Say you want to wire **OpenAI** for real:

1. **Implement the adapter.** Create
   `backend/app/infrastructure/ai/llm/openai.py` with a class
   `OpenAIProvider` implementing `LanguageModelGateway` (the Protocol).
   Keep the existing `placeholders.py` class as the fallback path or
   replace it — the rest of the system only sees the protocol.
   - Use the repository's HTTP doctrine: `httpx`, bounded retries with
     fixed backoff, `_NO_RETRY_STATUS`-style non-retryable statuses,
     `LlmProviderError`-style domain errors (see
     `infrastructure/llm/llm_provider.py` for the pattern).
   - `count_tokens` / `estimate_cost` may switch to vendor-reported
     values, but keep the deterministic fallback.
2. **Register the factory.** In
   `backend/app/infrastructure/ai/provider_factory.py`, register the
   real class for the `"openai"` kind (or add a new kind to
   `PROVIDER_KINDS` in `application/dtos/ai.py`).
3. **Configure it.** Add an entry to `AI_PROVIDERS_JSON` in the backend
   environment (`.env.example` documents the schema). The entry's model
   appears in `/ai/models`; when the adapter is genuinely usable, its
   `health()` returns `configured` and `/ai/health` flips to `ok`.
4. **Add credentials deliberately.** M11.1 stores no API keys anywhere.
   When your adapter needs one, add the field to `ProviderConfig` +
   `AI_PROVIDERS_JSON` and read it only inside the adapter. Never log it.
5. **Contract tests.** Mirror
   `backend/app/tests/unit/test_ai_placeholders.py` and the assistant's
   `LlmAssistantProvider` tests: fake transport (`httpx.MockTransport`),
   golden request/response fixtures, error paths, retry behavior.
6. **Eval before ship.** Run the golden eval set (chat/classify cases)
   through the new adapter and record the run (the eval harness persists
   to `eval_runs`); a candidate provider must not regress the golden set.

**That's it.** Routes, use cases, the core, the frontend settings page
and the health API require zero changes — they all speak the port.

## 4. Configuration reference (M11.1)

| Setting | Default | Meaning |
|---|---|---|
| `AI_ENABLED` | `true` | master switch (health reports `disabled` when off) |
| `AI_DEFAULT_PROVIDER` | `local` | default provider (a provider_id, or a kind resolved to its first provider) |
| `AI_DEFAULT_MODEL` | `` | default model name; when set, the default provider is the one whose model matches (influences runtime) |
| `AI_TEMPERATURE` | `0.0` | generation default for future adapters |
| `AI_MAX_TOKENS` | `2048` | generation default for future adapters |
| `AI_TIMEOUT_SECONDS` | `30.0` | transport timeout default |
| `AI_STREAMING_ENABLED` | `true` | streaming default |
| `AI_CHAT_ENABLED` … `AI_DOCUMENT_UNDERSTANDING_ENABLED` | `false` | capability feature flags (all OFF in M11.1) |
| `AI_PROVIDERS_JSON` | `` | JSON list of provider entries (see `.env.example`) |

## 5. The health surface

- `GET /api/v1/ai/health` — public liveness: aggregate status
  (`ok` / `not_configured` / `disabled` / `error`). `default_provider` is the
  runtime-effective default; `default_provider_valid` is True only when that
  default is actually executable (no misleading "healthy" state).
- `GET /api/v1/ai/providers` — authenticated: one row per **provider**
  (keyed by `provider_id`, with its `kind`), so multiple providers of a kind
  stay distinguishable; plus a not-configured discovery row per unconfigured kind.
- `GET /api/v1/ai/models` — authenticated: aggregated model list plus
  the configured defaults.

## 6. Testing

- Unit: DTO validation, estimates, config parsing, registry, config view,
  core aggregation, use cases, placeholders (`tests/unit/test_ai_*.py`).
- Integration: full DI chain through the API
  (`tests/integration/test_ai_health_api.py`), including auth gates and
  the `/api/v1/health` regression.
- Architecture guardrails (16 tests): AI purity + adapter independence,
  transport ownership (no feature imports httpx), composition authority
  (no feature imports a concrete provider; one `build_gateway`), config
  authority (only the AI Core constructs `ProviderConfig`), production
  isolation (api/application never import the bypass constructors).
- Runtime contract (`tests/unit/test_ai_runtime_contract.py`): provider
  identity, multi-provider distinguishability, selection precedence,
  `AI_DEFAULT_MODEL` influence, health/runtime default consistency.
- Frontend: `AiSettingsView.test.tsx` (mocked API client).

## 7. Local / Free AI (no paid key required)

The core product never requires a paid cloud subscription. Any
OpenAI-compatible **local** model works through the same `LanguageModelGateway`
boundary — set `AI_PROVIDERS_JSON` to a local endpoint with an **empty**
`api_key` and the adapter sends **no** `Authorization` header (local servers
such as Ollama, vLLM and LM Studio do not need one). Application use cases are
provider-neutral, so local → cloud (or cloud → local) is a configuration
change, never a code change.

### Example: Ollama (free, local)
```bash
# 1. Run a local model (one-time)
ollama pull llama3.1
ollama serve                      # serves OpenAI-compatible API at :11434/v1
```
```dotenv
# .env — point AcademicOS at the local model (NO API key)
AI_ENABLED=true
AI_PROVIDERS_JSON=[{"provider_id":"local-llama","kind":"openai","model":"llama3.1","base_url":"http://localhost:11434/v1","api_key":"","temperature":0.0,"max_tokens":2048,"streaming_enabled":true}]
AI_DEFAULT_PROVIDER=local-llama
# Then enable the capabilities you want, e.g.:
AI_SUMMARIZATION_ENABLED=true
AI_QA_ENABLED=true
AI_ENRICHMENT_ENABLED=true
```

### No provider at all
With no provider configured (or `AI_ENABLED=false`), every AI endpoint
degrades honestly to an `available=false` fallback and **`POST /ai/handoff`**
returns a self-contained, grounded prompt bundle the user can paste into any
external AI — AcademicOS makes no provider call and incurs no charge.
