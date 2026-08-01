/**
 * Publications API — frontend mirror of the `/publications` contract.
 *
 * All calls reuse the shared {@link api} wrapper so error normalisation,
 * timeouts, offline detection and abort handling are identical to the Objects
 * and Documents modules. The PDF attachment is the one exception: like
 * `uploadDocument`, it uses XMLHttpRequest to report real upload progress.
 *
 * Unlike Documents, the Publications backend exposes server-side search and
 * filters (`q`, `publication_type`, `year`, `quartile`, `pipeline_stage`,
 * `status`, `object_id`) — every parameter below maps 1:1 onto the API.
 *
 * ENCODING CONTRACT (same as Objects/Documents — do not break): ids travel
 * decoded (`obj:publication:AB12…`); the list Link encodes exactly once and
 * the detail page decodes exactly once. Never `encodeURIComponent` here.
 */
import { API_BASE_URL } from "@/config/env";
import { api, ApiError } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import { DEFAULT_PUB_PAGE_SIZE } from "@/lib/publications/constants";
import type {
  BibliographyFormat,
  CitationStyle,
  DoiLookupRecord,
  ListPublicationsResponse,
  PipelineStage,
  PublicationAuthor,
  PublicationCitation,
  PublicationImportResult,
  PublicationLinkGroup,
  PublicationResponse,
  PublicationStatus,
  PublicationTypeValue,
  Quartile,
} from "@/types";

export interface ListPublicationsParams {
  page?: number;
  pageSize?: number;
  /** Server-side token-AND search (title/authors/DOI/venue/keywords/publisher). */
  q?: string;
  publicationType?: PublicationTypeValue | null;
  year?: number | null;
  quartile?: Quartile | null;
  pipelineStage?: PipelineStage | null;
  status?: PublicationStatus | null;
  /** The object lens: "papers linked to Object X" (e.g. funded by Grant X). */
  objectId?: string | null;
}

export interface CreatePublicationPayload {
  title: string;
  publication_type: PublicationTypeValue;
  uploaded_by: string;
  status?: PublicationStatus;
  pipeline_stage?: PipelineStage | null;
  authors?: PublicationAuthor[];
  affiliations?: string[];
  abstract?: string | null;
  keywords?: string[];
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
  citation_count?: number | null;
  impact_factor?: number | null;
  quartile?: Quartile | null;
  indexing?: string[];
  publisher_url?: string | null;
  notes?: string | null;
  tags?: string[];
  collections?: string[];
  /** {group: [object ids]} — present groups replace, absent groups untouched. */
  links?: Partial<Record<PublicationLinkGroup, string[]>>;
}

/** Partial update: every present key replaces; absent keys are untouched. */
export type UpdatePublicationPayload = Partial<CreatePublicationPayload>;

function listQuery(params: ListPublicationsParams): Record<string, string | number> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_PUB_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.publicationType) query.publication_type = params.publicationType;
  if (params.year != null) query.year = params.year;
  if (params.quartile) query.quartile = params.quartile;
  if (params.pipelineStage) query.pipeline_stage = params.pipelineStage;
  if (params.status) query.status = params.status;
  if (params.objectId) query.object_id = params.objectId;
  return query;
}

export function listPublications(
  params: ListPublicationsParams = {},
  options?: RequestOptions,
): Promise<ListPublicationsResponse> {
  return api.get<ListPublicationsResponse>("/publications", {
    ...options,
    query: listQuery(params),
  });
}

/** Publications linked to a single Object (`GET /publications?object_id=`). */
export function listPublicationsByObject(
  objectId: string,
  options?: RequestOptions,
): Promise<ListPublicationsResponse> {
  return api.get<ListPublicationsResponse>("/publications", {
    ...options,
    query: { object_id: objectId, page_size: 100 },
  });
}

/** `id` must already be decoded (`obj:publication:…`) — never encode it here. */
export function getPublication(
  id: string,
  options?: RequestOptions,
): Promise<PublicationResponse> {
  return api.get<PublicationResponse>(`/publications/${id}`, options);
}

export function createPublication(
  payload: CreatePublicationPayload,
  options?: RequestOptions,
): Promise<PublicationResponse> {
  return api.post<PublicationResponse>("/publications", payload, options);
}

/** `id` must already be decoded (`obj:publication:…`) — never encode it here. */
export function updatePublication(
  id: string,
  payload: UpdatePublicationPayload,
  options?: RequestOptions,
): Promise<PublicationResponse> {
  return api.put<PublicationResponse>(`/publications/${id}`, payload, options);
}

/** `id` must already be decoded (`obj:publication:…`) — never encode it here. */
export function deletePublication(
  id: string,
  options?: RequestOptions,
): Promise<void> {
  return api.delete<void>(`/publications/${id}`, options);
}

export interface UploadProgress {
  /** 0–100 once the request is in flight. */
  percent: number;
}

/**
 * Attach (or replace) the primary PDF. Uses XMLHttpRequest so the UI can show
 * a real upload-progress percentage; errors arrive as {@link ApiError} so the
 * rest of the app handles them exactly like JSON requests ({@link uploadDocument}).
 */
export function attachPublicationPdf(
  id: string,
  file: File,
  callbacks: {
    onProgress?: (progress: UploadProgress) => void;
    signal?: AbortSignal;
    uploadedBy?: string;
  } = {},
): Promise<PublicationResponse> {
  const formData = new FormData();
  formData.append("file", file, file.name);

  return new Promise<PublicationResponse>((resolve, reject) => {
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
          resolve(JSON.parse(xhr.responseText) as PublicationResponse);
        } catch {
          reject(
            new ApiError("The server returned a malformed response.", {
              kind: "http",
              status: xhr.status,
            }),
          );
        }
        return;
      }
      let message = `Request failed: ${xhr.status}`;
      try {
        const body = JSON.parse(xhr.responseText) as { detail?: unknown };
        if (typeof body.detail === "string" && body.detail.trim()) {
          message = body.detail.trim();
        }
      } catch {
        /* non-JSON error body — keep the status message */
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

    const uploadedBy = callbacks.uploadedBy?.trim() || "system";
    xhr.open(
      "PUT",
      `${API_BASE_URL}/publications/${id}/pdf?uploaded_by=${encodeURIComponent(uploadedBy)}`,
    );
    xhr.send(formData);
  });
}

/** Formatted citation (APA/IEEE/Vancouver/Chicago/Harvard/BibTeX). */
export function getCitation(
  id: string,
  style: CitationStyle,
  options?: RequestOptions,
): Promise<PublicationCitation> {
  return api.get<PublicationCitation>(`/publications/${id}/citation`, {
    ...options,
    query: { style },
  });
}

/**
 * Direct export download URL (BibTeX / RIS / CSV). The current list filters
 * ride along, so "export what I see" is a plain link — no client fetch, no
 * blob juggling, the browser handles the attachment.
 */
export function exportPublicationsUrl(
  fmt: BibliographyFormat,
  params: Omit<ListPublicationsParams, "page" | "pageSize"> = {},
): string {
  const query = listQuery({ ...params, page: 1, pageSize: 100 });
  delete query.page;
  delete query.page_size;
  const search = new URLSearchParams({ fmt });
  for (const [key, value] of Object.entries(query)) {
    search.append(key, String(value));
  }
  return `${API_BASE_URL}/publications/export?${search.toString()}`;
}

/** Bulk import (BibTeX / RIS / CSV text) with a duplicate/error report. */
export function importPublications(
  payload: { fmt: BibliographyFormat; text: string; uploaded_by: string },
  options?: RequestOptions,
): Promise<PublicationImportResult> {
  return api.post<PublicationImportResult>("/publications/import", payload, options);
}

/**
 * External metadata lookup (Crossref) by DOI. The DOI travels verbatim — the
 * route uses a `:path` converter precisely so slashes inside the identifier
 * keep working (mirrors the "never encode ids here" contract).
 */
export function lookupDoi(doi: string, options?: RequestOptions): Promise<DoiLookupRecord> {
  const clean = doi.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "");
  return api.get<DoiLookupRecord>(`/publications/doi-lookup/${clean}`, options);
}
