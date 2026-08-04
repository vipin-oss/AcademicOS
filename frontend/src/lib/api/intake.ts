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
import { api } from "@/lib/api/client";
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

export function resumeIntakeSession(sessionId: string): Promise<IntakeSession> {
  return api.post<IntakeSession>(`/intake/sessions/${sessionId}/resume`);
}

export function cancelIntakeSession(sessionId: string): Promise<IntakeSession> {
  return api.post<IntakeSession>(`/intake/sessions/${sessionId}/cancel`);
}

export function deleteIntakeSession(sessionId: string): Promise<void> {
  return api.delete<void>(`/intake/sessions/${sessionId}`);
}
