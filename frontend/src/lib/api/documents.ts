/**
 * Documents API — frontend mirror of the (planned) `/documents` contract.
 *
 * GET/PUT/DELETE reuse the shared {@link api} wrapper so error normalisation,
 * timeouts, offline detection and abort handling are identical to the Objects
 * module. The upload is the one exception: file uploads need a *real* progress
 * signal, which `fetch` cannot report, so `uploadDocument` uses XMLHttpRequest.
 *
 * ENCODING CONTRACT (same as Objects — do not break):
 *   ids travel decoded (`doc:pdf:AB12…`); the list Link encodes exactly once
 *   and the detail page decodes exactly once. Never `encodeURIComponent` here.
 */
import { API_BASE_URL } from "@/config/env";
import { api, ApiError } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import { getAccessToken } from "@/lib/auth/token";
import { DEFAULT_DOC_PAGE_SIZE } from "@/lib/documents/constants";
import type {
  DocumentResponse,
  DocumentStatus,
  DocumentTypeValue,
  ListDocumentsResponse,
} from "@/types";

export interface ListDocumentsParams {
  page?: number;
  pageSize?: number;
  /** Filter to a single linked object. */
  objectId?: string | null;
}

export interface DocumentFilters {
  type?: DocumentTypeValue | "all";
  status?: DocumentStatus | "all";
}

export interface CreateDocumentPayload {
  title?: string;
  object_id?: string | null;
  document_type?: DocumentTypeValue;
  description?: string;
  tags?: string[];
  uploaded_by?: string;
  /** The selected file (sent as multipart/form-data). */
  file: File;
}

export interface UpdateDocumentPayload {
  title?: string;
  object_id?: string | null;
  document_type?: DocumentTypeValue;
  description?: string;
  tags?: string[];
  status?: DocumentStatus;
  uploaded_by?: string;
}

export interface UploadProgress {
  /** 0–100 once the request is in flight. */
  percent: number;
}

function statusFallback(status: number): string {
  const map: Record<number, string> = {
    400: "The request was invalid.",
    401: "Your session has expired. Please sign in again.",
    403: "You do not have permission to perform this action.",
    404: "The requested document was not found.",
    409: "This conflicts with the current state of the resource.",
    422: "Some of the submitted values are invalid.",
    500: "The server encountered an unexpected error.",
    502: "The server is temporarily unavailable.",
    503: "The server is temporarily unavailable.",
    504: "The server took too long to respond.",
  };
  return map[status] ?? `Request failed: ${status}`;
}

export function listDocuments(
  params: ListDocumentsParams = {},
  options?: RequestOptions,
): Promise<ListDocumentsResponse> {
  const { page = 1, pageSize = DEFAULT_DOC_PAGE_SIZE, objectId } = params;
  return api.get<ListDocumentsResponse>("/documents", {
    ...options,
    query: { page, page_size: pageSize, ...(objectId ? { object_id: objectId } : {}) },
  });
}

/** Documents belonging to a single object (`GET /documents?object_id=`). */
export function listDocumentsByObject(
  objectId: string,
  options?: RequestOptions,
): Promise<ListDocumentsResponse> {
  return api.get<ListDocumentsResponse>("/documents", {
    ...options,
    query: { object_id: objectId, page_size: 100 },
  });
}

/** `id` must already be decoded (`doc:pdf:…`) — never encode it here. */
export function getDocument(id: string, options?: RequestOptions): Promise<DocumentResponse> {
  return api.get<DocumentResponse>(`/documents/${id}`, options);
}

/**
 * Upload a document (multipart). Uses XMLHttpRequest so the UI can show a real
 * upload-progress percentage; errors are surfaced as {@link ApiError} so the
 * rest of the app handles them identically to JSON requests.
 */
export function uploadDocument(
  payload: CreateDocumentPayload,
  callbacks: {
    onProgress?: (progress: UploadProgress) => void;
    signal?: AbortSignal;
  } = {},
): Promise<DocumentResponse> {
  const formData = new FormData();
  if (payload.title) formData.append("title", payload.title);
  if (payload.object_id) formData.append("object_id", payload.object_id);
  if (payload.document_type) formData.append("document_type", payload.document_type);
  if (payload.description) formData.append("description", payload.description);
  if (payload.tags) formData.append("tags", JSON.stringify(payload.tags));
  if (payload.uploaded_by) formData.append("uploaded_by", payload.uploaded_by);
  formData.append("file", payload.file, payload.file.name);

  return new Promise<DocumentResponse>((resolve, reject) => {
    if (callbacks.signal?.aborted) {
      reject(new ApiError("Upload cancelled.", { kind: "aborted" }));
      return;
    }

    const xhr = new XMLHttpRequest();
    callbacks.signal?.addEventListener("abort", () => xhr.abort());

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && callbacks.onProgress) {
        callbacks.onProgress({ percent: Math.round((event.loaded / event.total) * 100) });
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as DocumentResponse);
        } catch {
          resolve(undefined as unknown as DocumentResponse);
        }
        return;
      }
      let message = statusFallback(xhr.status);
      try {
        const body = JSON.parse(xhr.responseText) as { detail?: unknown; message?: unknown };
        const detail = body.detail ?? body.message;
        if (typeof detail === "string" && detail.trim()) message = detail.trim();
        else if (Array.isArray(detail)) {
          const parts = detail
            .map((entry) => (typeof entry === "string" ? entry : (entry as { msg?: string })?.msg))
            .filter(Boolean);
          if (parts.length) message = parts.join("; ");
        }
      } catch {
        /* non-JSON error body — fall back to the status message */
      }
      reject(new ApiError(message, { kind: "http", status: xhr.status }));
    };

    xhr.onerror = () =>
      reject(
        new ApiError(`Cannot reach the API at ${API_BASE_URL}. Make sure the backend is running.`, {
          kind: "http",
          status: null,
        }),
      );
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", { kind: "aborted" }));

    xhr.open("POST", `${API_BASE_URL}/documents`);
    // Upload auth (P0): the raw XHR bypasses the shared client's
    // attachAuthorization(), so attach the bearer token here — the SAME
    // token the shared client sends (getAccessToken is the single source
    // of truth). No token -> no header (public endpoints stay
    // unauthenticated, matching the shared client). Content-Type is NOT
    // set manually — the browser must generate the multipart boundary.
    const token = getAccessToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send(formData);
  });
}

/** `id` must already be decoded (`doc:pdf:…`) — never encode it here. */
export function updateDocument(
  id: string,
  payload: UpdateDocumentPayload,
  options?: RequestOptions,
): Promise<DocumentResponse> {
  return api.put<DocumentResponse>(`/documents/${id}`, payload, options);
}

/** `id` must already be decoded (`doc:pdf:…`) — never encode it here. */
export function deleteDocument(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/documents/${id}`, options);
}
