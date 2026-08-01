/** Shared frontend types. Mirrors the API contract, no domain logic. */

export interface ApiHealth {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export type ObjectStatus = "draft" | "active" | "archived" | "superseded";

/**
 * A single metadata field as accepted by the API (`MetadataField` in
 * `app/api/routes/objects.py`). `layer` and `source` are optional — the
 * backend defaults them to L6 / human-asserted, which is what the UI writes.
 */
export interface MetadataFieldPayload {
  key: string;
  value: string;
  layer?: number;
  source?: string;
  confidence?: number | null;
}

export interface ObjectResponse {
  id: string;
  object_type: string;
  title: string;
  status: ObjectStatus;
  version: number;
  created_by: string;
  created_at: string;
  metadata: Record<string, string>;
  events: string[];
}

export interface ListObjectsResponse {
  items: ObjectResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Documents module
// ---------------------------------------------------------------------------

export type DocumentStatus = "draft" | "active" | "archived";

/** Mirrors the file-type taxonomy used by the Documents UI (PDF, DOCX, …). */
export type DocumentTypeValue =
  | "pdf"
  | "docx"
  | "xlsx"
  | "pptx"
  | "txt"
  | "zip"
  | "image"
  | "video"
  | "unknown";

/**
 * Frontend mirror of the (planned) Document contract:
 *   GET    /documents                 -> ListDocumentsResponse
 *   GET    /documents/{id}            -> DocumentResponse
 *   POST   /documents  (multipart)    -> DocumentResponse
 *   PUT    /documents/{id}            -> DocumentResponse
 *   DELETE /documents/{id}            -> 204
 *   GET    /documents?object_id=...   -> ListDocumentsResponse
 */
export interface DocumentResponse {
  id: string;
  title: string;
  /** Linked Object id (`obj:course:…`), or null when unattached. */
  object_id: string | null;
  /** Best-effort denormalised fields returned by the backend for convenience. */
  object_type?: string | null;
  object_title?: string | null;
  document_type: DocumentTypeValue;
  description?: string | null;
  tags: string[];
  file_name: string;
  /** Size in bytes. */
  file_size: number;
  mime_type: string;
  status: DocumentStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  /** Direct download URL, when the file store is wired up. */
  url?: string | null;
  preview_url?: string | null;
  metadata?: Record<string, string>;
  /** Audit/domain events, when the backend exposes them. */
  events?: string[];
}

export interface ListDocumentsResponse {
  items: DocumentResponse[];
  total_count: number;
  page: number;
  page_size: number;
}
