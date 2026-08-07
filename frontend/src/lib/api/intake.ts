/**
 * Intake Foundations API — frontend mirror of the `/intake/sessions` contract.
 *
 * Reuses the shared {@link api} wrapper so error normalisation, timeouts and
 * abort handling are identical to every other module.
 *
 * ENCODING CONTRACT (same as Objects/Documents — do not break): ids travel
 * decoded (`obj:intake_session:AB12…`); colons are legal in path segments and
 * are never percent-encoded here.
 */
import { api, type RequestOptions } from "@/lib/api/client";
import type {
  CreateIntakeSessionPayload,
  IntakeProgressUpdate,
  IntakeSession,
  IntakeItem,
  ListIntakeItemsResponse,
  ListIntakeSessionsResponse,
} from "@/types";

export interface ListSessionsParams {
  page?: number;
  pageSize?: number;
}

export interface ListItemsParams {
  page?: number;
  pageSize?: number;
}

export function createIntakeSession(
  payload: CreateIntakeSessionPayload,
): Promise<IntakeSession> {
  return api.post<IntakeSession>("/intake/sessions", payload);
}

export function listIntakeSessions(
  params: ListSessionsParams = {},
): Promise<ListIntakeSessionsResponse> {
  return api.get<ListIntakeSessionsResponse>("/intake/sessions", {
    query: { page: params.page ?? 1, page_size: params.pageSize ?? 20 },
  });
}

export function getIntakeSession(sessionId: string): Promise<IntakeSession> {
  return api.get<IntakeSession>(`/intake/sessions/${sessionId}`);
}

export function getIntakeProgress(sessionId: string): Promise<IntakeProgressUpdate> {
  return api.get<IntakeProgressUpdate>(`/intake/sessions/${sessionId}/progress`);
}

export function listIntakeItems(
  sessionId: string,
  params: ListItemsParams = {},
): Promise<ListIntakeItemsResponse> {
  return api.get<ListIntakeItemsResponse>(`/intake/sessions/${sessionId}/items`, {
    query: { page: params.page ?? 1, page_size: params.pageSize ?? 50 },
  });
}

export function pauseIntakeSession(sessionId: string): Promise<IntakeSession> {
  return api.post<IntakeSession>(`/intake/sessions/${sessionId}/pause`);
}

/**
 * M2: the raw extracted text of one item. Resolves to the exact bytes the
 * extraction engine produced (never assembled client-side); a 404 `ApiError`
 * is the honest answer for unsupported/unextracted items — callers render
 * that as an empty state, never as fabricated text.
 */
export function getIntakeExtractedText(
  sessionId: string,
  itemId: string,
  options?: { signal?: AbortSignal },
): Promise<string> {
  return api.getText(`/intake/sessions/${sessionId}/items/${itemId}/extraction/text`, options);
}

export function resumeIntakeSession(sessionId: string): Promise<IntakeSession> {
  return api.post<IntakeSession>(`/intake/sessions/${sessionId}/resume`);
}

/**
 * M2.3: re-run ONLY the failed items that still own retry attempts (max 3
 * attempts each). A 422 is the honest answer when nothing is retryable.
 */
export function retryIntakeSession(sessionId: string): Promise<IntakeSession> {
  return api.post<IntakeSession>(`/intake/sessions/${sessionId}/retry`);
}

export function cancelIntakeSession(sessionId: string): Promise<IntakeSession> {
  return api.post<IntakeSession>(`/intake/sessions/${sessionId}/cancel`);
}

export function deleteIntakeSession(sessionId: string): Promise<void> {
  return api.delete<void>(`/intake/sessions/${sessionId}`);
}

// ---------------------------------------------------------------------------
// Item proposal & commit (final release — previously unwired routes)
// ---------------------------------------------------------------------------

/** `GET /intake/items/{id}/proposal` — the proposal for one item. */
export function getItemProposal(
  itemId: string,
  options?: RequestOptions,
): Promise<{ proposal: unknown }> {
  return api.get<{ proposal: unknown }>(`/intake/items/${itemId}/proposal`, options);
}

/** `POST /intake/items/{id}/proposal/regenerate` — rebuild the proposal. */
export function regenerateItemProposal(
  itemId: string,
  options?: RequestOptions,
): Promise<{ proposal: unknown }> {
  return api.post<{ proposal: unknown }>(
    `/intake/items/${itemId}/proposal/regenerate`,
    undefined,
    options,
  );
}

/** `POST /intake/items/{id}/commit` — commit the item into the graph. */
export function commitIntakeItem(itemId: string, options?: RequestOptions): Promise<unknown> {
  return api.post(`/intake/items/${itemId}/commit`, undefined, options);
}

/** `POST /intake/items/{id}/commit-preview` — dry-run commit. */
export function previewCommitIntakeItem(
  itemId: string,
  options?: RequestOptions,
): Promise<unknown> {
  return api.post(`/intake/items/${itemId}/commit-preview`, undefined, options);
}

// ---------------------------------------------------------------------------
// M9 — review workflow (approve / reject / bulk)
// ---------------------------------------------------------------------------

export interface ReviewItemResult {
  item_id: string;
  status: string;
  document_id: string | null;
}

export interface BulkReviewItemResult {
  item_id: string;
  status: string;
  document_id: string | null;
  error: string | null;
}

export interface BulkReviewResult {
  items: BulkReviewItemResult[];
  succeeded: number;
}

/** `POST /intake/items/{id}/review` — approve (commit) or reject one item. */
export function reviewIntakeItem(
  itemId: string,
  decision: "approve" | "reject",
  options?: RequestOptions,
): Promise<ReviewItemResult> {
  return api.post<ReviewItemResult>(
    `/intake/items/${itemId}/review`,
    { decision },
    options,
  );
}

/** `POST /intake/sessions/{id}/review` — bulk approve/reject. */
export function bulkReviewIntakeItems(
  sessionId: string,
  decision: "approve" | "reject",
  itemIds?: string[],
  options?: RequestOptions,
): Promise<BulkReviewResult> {
  return api.post<BulkReviewResult>(
    `/intake/sessions/${sessionId}/review`,
    { decision, item_ids: itemIds ?? null },
    options,
  );
}
