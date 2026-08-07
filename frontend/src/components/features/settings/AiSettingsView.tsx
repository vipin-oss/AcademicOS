"use client";

/**
 * AI Settings view (Sprint M11.1 — AI Foundation).
 *
 * Read-only display of the AI Core health surface: aggregate status,
 * configured provider / current model, the provider catalogue, and the
 * feature-flag state. No chat UI, no prompts, no generation — M11.1 is
 * infrastructure only, and the view says so honestly.
 */
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Cpu, RefreshCw, XCircle } from "lucide-react";
import {
  getAiHealth,
  getAiModels,
  getAiProviders,
} from "@/lib/api/ai";
import { toErrorMessage } from "@/lib/api/client";
import { Spinner } from "@/components/features/objects/Spinner";
import type { AiHealth, AiModelInfo, AiProviderInfo } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  ok: "AI is ready",
  not_configured: "Not configured — no adapter is wired yet",
  disabled: "AI is disabled",
  error: "Configuration error",
};

const PROVIDER_STATUS_LABELS: Record<string, string> = {
  configured: "Configured",
  not_configured: "Not configured",
  error: "Error",
};

const FLAG_LABELS: Record<string, string> = {
  chat: "Chat",
  rag: "RAG retrieval",
  memory: "Memory",
  agents: "Agents",
  document_understanding: "Document understanding",
  streaming: "Streaming",
};

export function AiSettingsView() {
  const [health, setHealth] = useState<AiHealth | null>(null);
  const [providers, setProviders] = useState<AiProviderInfo[]>([]);
  const [models, setModels] = useState<AiModelsInfo>({ default_provider: "", default_model: "", models: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const [healthData, providersData, modelsData] = await Promise.all([
        getAiHealth(),
        getAiProviders(),
        getAiModels(),
      ]);
      setHealth(healthData);
      setProviders(providersData.items);
      setModels(modelsData);
    } catch (err) {
      setError(toErrorMessage(err, "Could not load the AI status."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-[var(--text-tertiary)]" aria-busy="true">
        <Spinner /> Loading AI status…
      </div>
    );
  }

  const statusTone =
    health?.status === "ok"
      ? "border-[var(--success)] bg-[var(--success-subtle)] text-[var(--success)]"
      : health?.status === "error"
        ? "border-[var(--danger)] bg-[var(--danger-subtle)] text-[var(--danger)]"
        : "border-[var(--border-strong)] bg-[var(--bg-surface-2)] text-[var(--text-secondary)]";

  return (
    <div className="space-y-6" data-testid="ai-settings-view">
      {error ? (
        <p role="alert" className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </p>
      ) : null}

      {/* Health banner */}
      {health ? (
        <section aria-label="AI health" className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium ${statusTone}`}>
              {health.status === "ok" ? (
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              ) : (
                <XCircle className="h-4 w-4" aria-hidden="true" />
              )}
              {STATUS_LABELS[health.status] ?? health.status}
            </div>
            <button
              type="button"
              onClick={() => void load(true)}
              disabled={refreshing}
              aria-label="Refresh AI status"
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          </div>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs text-[var(--text-tertiary)]">Status</dt>
              <dd className="mt-0.5 font-medium text-[var(--text-primary)]">
                {health.status === "ok"
                  ? "Ready"
                  : health.status === "not_configured"
                    ? "Not configured"
                    : health.status === "disabled"
                      ? "Disabled"
                      : "Error"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--text-tertiary)]">Default provider</dt>
              <dd className="mt-0.5 font-medium text-[var(--text-primary)]">
                {health.default_provider}
                {!health.default_provider_valid ? (
                  <span className="ml-2 text-xs text-[var(--danger)]">(unknown)</span>
                ) : null}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--text-tertiary)]">Current model</dt>
              <dd className="mt-0.5 font-medium text-[var(--text-primary)]">
                {health.default_model || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--text-tertiary)]">Providers</dt>
              <dd className="mt-0.5 font-medium text-[var(--text-primary)]">
                {health.providers_configured} / {health.providers_total} configured
              </dd>
            </div>
          </dl>
        </section>
      ) : null}

      {/* Feature flags */}
      <section aria-label="AI feature flags" className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <Cpu className="h-4 w-4" aria-hidden="true" /> Capabilities (feature flags)
        </h2>
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
          M11.1 ships the AI foundation only — every capability flag is OFF until its sprint lands.
        </p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {health
            ? Object.entries(FLAG_LABELS).map(([key, label]) => (
                <li
                  key={key}
                  className={`rounded-full border px-3 py-1 text-xs font-medium ${
                    health.feature_flags[key]
                      ? "border-[var(--success)] bg-[var(--success-subtle)] text-[var(--success)]"
                      : "border-[var(--border-subtle)] text-[var(--text-tertiary)]"
                  }`}
                >
                  {label}: {health.feature_flags[key] ? "on" : "off"}
                </li>
              ))
            : null}
        </ul>
      </section>

      {/* Provider catalogue */}
      <section aria-label="AI providers" className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Available providers</h2>
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
          The M11.1 catalogue. Each provider reports &quot;Not configured&quot; until a real adapter lands in a later sprint.
        </p>
        <ul className="mt-3 divide-y divide-[var(--border-subtle)]">
          {providers.map((provider) => (
            <li key={provider.provider_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
              <div className="min-w-0">
                <p className="font-medium text-[var(--text-primary)]">
                  {provider.display_name}
                  <span className="ml-2 font-mono text-xs text-[var(--text-tertiary)]">
                    {provider.provider_id}
                  </span>
                </p>
                {provider.models.length > 0 ? (
                  <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                    {provider.models.map((m) => m.model_id).join(", ")}
                  </p>
                ) : (
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">No model configured</p>
                )}
              </div>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                  provider.configured
                    ? "border-[var(--success)] bg-[var(--success-subtle)] text-[var(--success)]"
                    : "border-[var(--border-subtle)] text-[var(--text-tertiary)]"
                }`}
              >
                {PROVIDER_STATUS_LABELS[provider.status] ?? provider.status}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {/* Model catalogue */}
      <section aria-label="AI models" className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Models</h2>
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
          Declared models across all providers. None are usable until an adapter is wired.
        </p>
        {models.models.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--text-tertiary)]">
            No models configured. Add entries to <code className="font-mono">AI_PROVIDERS_JSON</code> in the backend environment.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-[var(--border-subtle)]">
            {models.models.map((model) => (
              <ModelRow key={`${model.provider_id}:${model.model_id}`} model={model} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

interface AiModelsInfo {
  default_provider: string;
  default_model: string;
  models: AiModelInfo[];
}

function ModelRow({ model }: { model: AiModelInfo }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-2.5">
      <div className="min-w-0">
        <p className="font-mono text-sm text-[var(--text-primary)]">{model.model_id}</p>
        <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
          {model.provider_id}
          {model.context_window ? ` · ${model.context_window.toLocaleString()} tokens` : ""}
          {model.capabilities.length > 0 ? ` · ${model.capabilities.join(", ")}` : ""}
        </p>
      </div>
      <span className="rounded-full border border-[var(--border-subtle)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-tertiary)]">
        {model.configured ? "Usable" : "Declared — not usable yet"}
      </span>
    </li>
  );
}
