/**
 * Typed API client for the Academic Intelligence Assistant (module 13).
 *
 * Mirrors `lib/api/settings.ts` one-to-one: thin wrappers over the shared
 * `api` client; updates go through PUT (the events/productivity precedent —
 * the backend also accepts PATCH twins). No business logic here: intent
 * parsing and answering live entirely in the backend provider.
 */
import { api, type RequestOptions } from "@/lib/api/client";
import type {
  AskResult,
  AssistantConversation,
  AssistantHome,
  ConversationDetail,
  ConversationListResult,
  SuggestedCatalogue,
} from "@/types";

const DEFAULT_ACTOR = "faculty:ui";

/** `GET /assistant/home` — suggested prompts + recent + pinned threads. */
export function getAssistantHome(options?: RequestOptions): Promise<AssistantHome> {
  return api.get<AssistantHome>("/assistant/home", options);
}

/** `GET /assistant/suggested` — prompts plus the full intent taxonomy. */
export function getSuggested(options?: RequestOptions): Promise<SuggestedCatalogue> {
  return api.get<SuggestedCatalogue>("/assistant/suggested", options);
}

/**
 * `POST /assistant/ask` — one question. Omitting `conversationId` starts a
 * new conversation (auto-titled from the question on the server).
 */
export function askQuestion(
  question: string,
  conversationId?: string | null,
  options?: RequestOptions,
): Promise<AskResult> {
  return api.post<AskResult>(
    "/assistant/ask",
    { question, conversation_id: conversationId ?? undefined, asked_by: DEFAULT_ACTOR },
    options,
  );
}

/** `GET /assistant/conversations` — pinned first, then most recent. */
export function listConversations(
  page = 1,
  pageSize = 50,
  options?: RequestOptions,
): Promise<ConversationListResult> {
  return api.get<ConversationListResult>(
    `/assistant/conversations?page=${page}&page_size=${pageSize}`,
    options,
  );
}

/** `POST /assistant/conversations` — start an empty thread. */
export function createConversation(
  title?: string,
  options?: RequestOptions,
): Promise<AssistantConversation> {
  return api.post<AssistantConversation>(
    "/assistant/conversations",
    { title: title ?? undefined, created_by: DEFAULT_ACTOR },
    options,
  );
}

/** `GET /assistant/conversations/{id}` — the full message thread. */
export function getConversation(
  id: string,
  options?: RequestOptions,
): Promise<ConversationDetail> {
  return api.get<ConversationDetail>(`/assistant/conversations/${id}`, options);
}

/** `PUT /assistant/conversations/{id}` — rename / pin / unpin (strict body). */
export function updateConversation(
  id: string,
  values: { title?: string; pinned?: boolean },
  options?: RequestOptions,
): Promise<AssistantConversation> {
  return api.put<AssistantConversation>(
    `/assistant/conversations/${id}`,
    { ...values, updated_by: DEFAULT_ACTOR },
    options,
  );
}

/** `DELETE /assistant/conversations/{id}` — remove the thread (204). */
export function deleteConversation(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/assistant/conversations/${id}`, options);
}

// ---------------------------------------------------------------------------
// Memory, review & evaluation (final release — previously unwired routes)
// ---------------------------------------------------------------------------

export interface MemoryItem {
  conversation_id: string;
  title: string;
  question: string;
  answer: string;
  citations: unknown[];
  review_status: string;
  score: number;
  review_score: number;
  sources: string[];
  version: number;
  last_message_at: string | null;
}

export interface MemoryRecall {
  conversations: MemoryItem[];
  knowledge: { object_id: string; object_type: string; title: string }[];
  search_count: number;
  graph_count: number;
}

/** `GET /assistant/memory/recall?q=&limit=` — recalled conversations. */
export function recallMemory(
  q: string,
  limit = 10,
  options?: RequestOptions,
): Promise<MemoryRecall> {
  return api.get<MemoryRecall>(
    `/assistant/memory/recall?q=${encodeURIComponent(q)}&limit=${limit}`,
    options,
  );
}

/** `POST /assistant/memory/consolidate` — one consolidation pass. */
export function consolidateMemory(
  options?: RequestOptions,
): Promise<{ scanned: number; consolidated: number; superseded: unknown[] }> {
  return api.post<{ scanned: number; consolidated: number; superseded: unknown[] }>(
    "/assistant/memory/consolidate",
    undefined,
    options,
  );
}

export interface ReviewQueueItem {
  conversation: { id: string; title: string };
  question: string;
  answer: string;
  message_seq: number;
}

/** `GET /assistant/review/pending` — conversations awaiting review. */
export function listPendingReviews(options?: RequestOptions): Promise<{ items: ReviewQueueItem[] }> {
  return api.get<{ items: ReviewQueueItem[] }>("/assistant/review/pending", options);
}

/** `POST /assistant/review/approve` — approve with optional feedback. */
export function approveReview(
  conversationId: string,
  feedback?: { notes?: string; rating?: number; confidence?: number; eval_run_id?: string },
  options?: RequestOptions,
): Promise<unknown> {
  return api.post(
    "/assistant/review/approve",
    { conversation_id: conversationId, ...feedback },
    options,
  );
}

/** `POST /assistant/review/reject` — reject with optional feedback. */
export function rejectReview(
  conversationId: string,
  feedback?: { notes?: string; rating?: number; confidence?: number; eval_run_id?: string },
  options?: RequestOptions,
): Promise<unknown> {
  return api.post(
    "/assistant/review/reject",
    { conversation_id: conversationId, ...feedback },
    options,
  );
}

/** `GET /assistant/eval/runs` — recorded evaluation runs (history). */
export function listEvalRuns(
  modelId?: string,
  limit = 20,
  options?: RequestOptions,
): Promise<{ items: unknown[] }> {
  const query = modelId
    ? `/assistant/eval/runs?model_id=${encodeURIComponent(modelId)}&limit=${limit}`
    : `/assistant/eval/runs?limit=${limit}`;
  return api.get<{ items: unknown[] }>(query, options);
}
