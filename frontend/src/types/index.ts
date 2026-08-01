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

// ---------------------------------------------------------------------------
// Publications module
// ---------------------------------------------------------------------------

export type PublicationStatus = "draft" | "active" | "archived";

/** The scholarly-output taxonomy (FR-PUB; mirrors the backend vocabulary). */
export type PublicationTypeValue =
  | "journal_article"
  | "conference_paper"
  | "book_chapter"
  | "book"
  | "patent"
  | "technical_report"
  | "thesis"
  | "preprint"
  | "other";

/** FR-PUB-001 lifecycle, idea -> post_publication. */
export type PipelineStage =
  | "idea"
  | "draft"
  | "internal_review"
  | "submitted"
  | "under_review"
  | "revision"
  | "accepted"
  | "published"
  | "post_publication";

export type Quartile = "Q1" | "Q2" | "Q3" | "Q4";

export type CitationStyle =
  | "apa"
  | "ieee"
  | "vancouver"
  | "chicago"
  | "harvard"
  | "bibtex";

export type BibliographyFormat = "bibtex" | "ris" | "csv";

/** The reference-manager "Linked X" panes (typed relationship edges). */
export type PublicationLinkGroup =
  | "projects"
  | "grants"
  | "students"
  | "faculty"
  | "departments"
  | "events"
  | "committees";

export interface PublicationAuthor {
  name: string;
  orcid?: string | null;
  affiliation?: string | null;
  corresponding?: boolean;
}

/** A denormalised linked Object in a publication's `links` payload. */
export interface PublicationLinkedObject {
  id: string;
  title: string;
  object_type: string;
  /** The typed edge (reports / authored_by / presented_at / belongs_to). */
  kind: string;
}

/**
 * Frontend mirror of the Publications contract (PublicationResponseModel):
 *   GET    /publications                    -> ListPublicationsResponse
 *   GET    /publications/{id}               -> PublicationResponse
 *   POST   /publications                    -> PublicationResponse
 *   PUT    /publications/{id}               -> PublicationResponse
 *   DELETE /publications/{id}               -> 204
 *   GET    /publications?object_id=...      -> ListPublicationsResponse
 *   PUT    /publications/{id}/pdf           -> PublicationResponse
 *   GET    /publications/{id}/pdf           -> blob
 *   GET    /publications/{id}/citation      -> PublicationCitation
 *   GET    /publications/export?fmt=...     -> BibTeX / RIS / CSV download
 *   POST   /publications/import             -> PublicationImportResult
 *   GET    /publications/doi-lookup/{doi}   -> DoiLookupRecord
 */
export interface PublicationResponse {
  id: string;
  title: string;
  publication_type: PublicationTypeValue;
  pipeline_stage?: PipelineStage | null;
  authors: PublicationAuthor[];
  affiliations: string[];
  abstract?: string | null;
  keywords: string[];
  doi?: string | null;
  isbn?: string | null;
  issn?: string | null;
  publisher?: string | null;
  journal?: string | null;
  conference?: string | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  year?: number | null;
  date?: string | null;
  language?: string | null;
  citation_count: number;
  impact_factor?: number | null;
  quartile?: Quartile | null;
  indexing: string[];
  publisher_url?: string | null;
  notes?: string | null;
  tags: string[];
  collections: string[];
  status: PublicationStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  pdf_file_name?: string | null;
  pdf_file_size: number;
  pdf_mime_type?: string | null;
  /** Direct PDF download URL, when a PDF is attached. */
  pdf_url?: string | null;
  links: Record<PublicationLinkGroup, PublicationLinkedObject[]>;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListPublicationsResponse {
  items: PublicationResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

/** A record skipped during import because it already exists (409-semantics). */
export interface PublicationImportDuplicate {
  index: number;
  title: string;
  doi?: string | null;
  existing_id: string;
}

export interface PublicationImportError {
  index: number;
  title?: string;
  message: string;
}

export interface PublicationImportResult {
  created: string[];
  duplicates: PublicationImportDuplicate[];
  errors: PublicationImportError[];
}

export interface PublicationCitation {
  style: string;
  citation: string;
}

/** Mapped external metadata record (Crossref adapter), pre-fills the form. */
export interface DoiLookupRecord {
  title?: string | null;
  publication_type?: string | null;
  authors?: (string | PublicationAuthor)[];
  affiliations?: string[];
  journal?: string | null;
  conference?: string | null;
  publisher?: string | null;
  doi?: string | null;
  issn?: string | null;
  isbn?: string | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  year?: number | null;
  date?: string | null;
  abstract?: string | null;
  publisher_url?: string | null;
}
