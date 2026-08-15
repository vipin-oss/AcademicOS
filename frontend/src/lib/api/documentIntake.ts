/**
 * Document intelligence (ADR-068) API client.
 *
 * `POST /documents/analyze-upload` and `POST /documents/{id}/analyze` run the
 * upload → classify → extract → route pipeline and return a full analysis.
 */
import { API_BASE_URL } from "@/config/env";
import { api, ApiError, type RequestOptions } from "@/lib/api/client";
import { getAccessToken } from "@/lib/auth/token";

export interface DocumentAnalysisField {
  field_name: string;
  predicate_id: string;
  value: unknown;
  original_text: string;
  confidence: number;
  extractor: string;
}

export interface DocumentAnalysisRecord {
  predicate_id: string;
  value: unknown;
  status: string;
  claim_id: string;
  reason: string;
}

export interface DocumentAnalysisRoute {
  module: string;
  kind: string; // "created" | "duplicate" | "claim_only" | "skipped"
  object_id: string;
  existing_id: string;
  reason: string;
}

export interface DocumentAnalysisResponse {
  document_id: string;
  document_type_id: string | null;
  confidence: number;
  secondary_types: string[];
  target_module: string;
  status: string;
  review_required: boolean;
  fields: DocumentAnalysisField[];
  records: DocumentAnalysisRecord[];
  duplicates: Array<{ predicate_id: string; existing_claim_id: string; value: unknown }>;
  conflicts: Array<{
    predicate_id: string;
    existing_claim_id: string;
    existing_value: unknown;
    extracted_value: unknown;
  }>;
  routing: DocumentAnalysisRoute[];
}

function statusFallback(status: number): string {
  const map: Record<number, string> = {
    400: "The request was invalid.",
    401: "Your session has expired. Please sign in again.",
    403: "You do not have permission to perform this action.",
    404: "The document was not found.",
    422: "Some of the submitted values are invalid.",
    500: "The server encountered an unexpected error.",
    503: "The server is temporarily unavailable.",
  };
  return map[status] ?? `Request failed: ${status}`;
}

/** Upload a document and run the document-intelligence pipeline on it. */
export function analyzeDocumentUpload(
  payload: { title: string; document_type: string; file: File },
  options?: RequestOptions,
): Promise<DocumentAnalysisResponse> {
  const formData = new FormData();
  formData.append("title", payload.title);
  formData.append("document_type", payload.document_type);
  formData.append("file", payload.file, payload.file.name);

  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  // No Content-Type: the browser sets the multipart boundary.

  const controller = new AbortController();
  const external = options?.signal;
  const forwardAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", forwardAbort);
  }

  return fetch(`${API_BASE_URL}/documents/analyze-upload`, {
    method: "POST",
    headers,
    body: formData,
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        let message = statusFallback(res.status);
        try {
          const body = (await res.json()) as { detail?: unknown };
          if (typeof body.detail === "string" && body.detail.trim()) message = body.detail;
        } catch {
          /* non-JSON error body */
        }
        throw new ApiError(message, { kind: "http", status: res.status });
      }
      return (await res.json()) as DocumentAnalysisResponse;
    })
    .catch((err) => {
      if (external?.aborted) throw new ApiError("Upload cancelled.", { kind: "aborted" });
      throw err;
    })
    .finally(() => external?.removeEventListener("abort", forwardAbort));
}

/** Analyze an already-uploaded document (no body). */
export function analyzeDocument(
  documentId: string,
  options?: RequestOptions,
): Promise<DocumentAnalysisResponse> {
  return api.post<DocumentAnalysisResponse>(`/documents/${documentId}/analyze`, undefined, options);
}
