/**
 * Typed API client for the AI Core (Sprint M11.1 — AI Foundation).
 *
 * Read-only health surface: health summary, provider catalogue, model
 * catalogue. Thin wrappers over the shared `api` client — no business
 * logic here.
 */
import { API_BASE_URL } from "@/config/env";
import { getAccessToken } from "@/lib/auth/token";
import { api, ApiError, type RequestOptions, DEFAULT_AI_TIMEOUT_MS } from "@/lib/api/client";
import type {
  AiChatResponse,
  AiHealth,
  AiModelsResponse,
  AssistantResponse,
  AssistantRole,
  EnrichResponse,
  ListAiProvidersResponse,
  ListAssistantRolesResponse,
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

/**
 * `GET /ai/assistants` - the domain-assistant catalogue (Group D, F18-F21).
 * Static and configuration-derived (requires auth).
 */
export function getAssistantRoles(options?: RequestOptions): Promise<AssistantRole[]> {
  return api
    .get<ListAssistantRolesResponse>("/ai/assistants", options)
    .then((res) => res.items);
}

/** `POST /ai/assistants/{role}` - role-specialized grounded generation. */
export function queryAssistant(
  role: string,
  body: {
    message: string;
    history?: Array<{ role: string; content: string }>;
  },
  options?: RequestOptions,
): Promise<AssistantResponse> {
  return api.post<AssistantResponse>(`/ai/assistants/${encodeURIComponent(role)}`, body, {
    timeoutMs: DEFAULT_AI_TIMEOUT_MS,
    ...options,
  });
}

// ---------------------------------------------------------------------------
// Streaming (SSE) — one shared implementation for /ai/chat/stream and
// /ai/assistants/{role}/stream. Both endpoints emit the same event contract:
//   event: token       data: {"delta": "..."}
//   event: completion  data: {answer, citations, ...}   (qa_result_dict shape)
// The server buffers tokens until generation is confirmed, so a stream that
// ends without a completion event is a failure — callers surface the honest
// fallback, never a partial answer.
// ---------------------------------------------------------------------------

export interface StreamHandlers {
  onToken?: (delta: string) => void;
  onCompletion?: (data: Record<string, unknown>) => void;
}

/** One SSE frame: {event, data} parsed from a `\n\n`-delimited chunk. */
interface SseFrame {
  event: string;
  data: string;
}

function parseSseFrame(raw: string): SseFrame | null {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  return { event, data };
}

/**
 * POST an SSE stream to `path` with the bearer token attached, dispatching
 * `token` / `completion` events to the handlers. Rejects with the same
 * `ApiError` taxonomy as the shared client (401/404/network/timeout), so the
 * unified AI workspace renders one error surface.
 */
export async function streamAi(
  path: string,
  body: unknown,
  handlers: StreamHandlers,
  options?: { signal?: AbortSignal },
): Promise<void> {
  const controller = new AbortController();
  const external = options?.signal;
  const onExternalAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", onExternalAbort, { once: true });
  }

  const headers: Record<string, string> = {
    Accept: "text/event-stream",
    "Content-Type": "application/json",
  };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    if (external?.aborted) {
      throw new ApiError("Request cancelled.", { kind: "aborted" });
    }
    throw new ApiError(
      `Cannot reach the API at ${API_BASE_URL}. Make sure the backend is running.`,
      { kind: "network", details: error },
    );
  }

  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") message = payload.detail;
      else if (Array.isArray(payload.detail) && payload.detail.length > 0) {
        const first = payload.detail[0] as { msg?: string };
        if (first?.msg) message = first.msg;
      }
    } catch {
      /* non-JSON error body — keep the status fallback */
    }
    throw new ApiError(message, { kind: "http", status: response.status });
  }

  if (!response.body) {
    throw new ApiError("The server returned no stream.", { kind: "http", status: 200 });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = parseSseFrame(buffer.slice(0, boundary));
        if (frame) {
          if (frame.event === "token") {
            const payload = JSON.parse(frame.data) as { delta?: string };
            handlers.onToken?.(payload.delta ?? "");
          } else if (frame.event === "completion") {
            handlers.onCompletion?.(JSON.parse(frame.data) as Record<string, unknown>);
          }
        }
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }
    }
  } finally {
    if (external) external.removeEventListener("abort", onExternalAbort);
  }
}
