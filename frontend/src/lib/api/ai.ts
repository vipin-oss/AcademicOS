/**
 * Typed API client for the AI Core (Sprint M11.1 — AI Foundation).
 *
 * Read-only health surface: health summary, provider catalogue, model
 * catalogue. Thin wrappers over the shared `api` client — no business
 * logic here. No generation endpoints exist yet (M11.2+).
 */
import { api, type RequestOptions } from "@/lib/api/client";
import type {
  AiHealth,
  AiModelsResponse,
  ListAiProvidersResponse,
} from "@/types";

/** `GET /ai/health` — aggregate AI health (public). */
export function getAiHealth(options?: RequestOptions): Promise<AiHealth> {
  return api.get<AiHealth>("/ai/health", options);
}

/** `GET /ai/providers` — provider catalogue with configuration status. */
export function getAiProviders(
  options?: RequestOptions,
): Promise<ListAiProvidersResponse> {
  return api.get<ListAiProvidersResponse>("/ai/providers", options);
}

/** `GET /ai/models` — aggregated model catalogue plus defaults. */
export function getAiModels(options?: RequestOptions): Promise<AiModelsResponse> {
  return api.get<AiModelsResponse>("/ai/models", options);
}
