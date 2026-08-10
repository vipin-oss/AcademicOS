/**
 * Typed API client for the AI Core (Sprint M11.1 — AI Foundation).
 *
 * Read-only health surface: health summary, provider catalogue, model
 * catalogue. Thin wrappers over the shared `api` client — no business
 * logic here.
 */
import { api, type RequestOptions, DEFAULT_AI_TIMEOUT_MS } from "@/lib/api/client";
import type {
  AiChatResponse,
  AiHealth,
  AiModelsResponse,
  EnrichResponse,
  ListAiProvidersResponse,
  SummarizeResponse,
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

/** `POST /ai/chat` — grounded document chat (M15+M19). */
export function aiChat(
  body: {
    message: string;
    history?: Array<{ role: string; content: string }>;
    conversation_id?: string | null;
  },
  options?: RequestOptions,
): Promise<AiChatResponse> {
  return api.post<AiChatResponse>("/ai/chat", body, {
    timeoutMs: DEFAULT_AI_TIMEOUT_MS,
    ...options,
  });
}

/** `POST /ai/summarize` — on-demand document summary. */
export function summarizeDocument(
  objectId: string,
  options?: RequestOptions,
): Promise<SummarizeResponse> {
  return api.post<SummarizeResponse>("/ai/summarize", { object_id: objectId }, {
    timeoutMs: DEFAULT_AI_TIMEOUT_MS,
    ...options,
  });
}

/** `POST /ai/enrich` — extract metadata from a document. */
export function enrichDocument(
  objectId: string,
  options?: RequestOptions,
): Promise<EnrichResponse> {
  return api.post<EnrichResponse>("/ai/enrich", { object_id: objectId }, {
    timeoutMs: DEFAULT_AI_TIMEOUT_MS,
    ...options,
  });
}
