/**
 * Faculty API — frontend mirror of the `/faculty` contract.
 *
 * Mirrors `lib/api/research.ts` / `lib/api/students.ts` one-to-one: every
 * call reuses the shared {@link api} wrapper (identical error normalisation,
 * timeouts and aborts); the photo upload reuses the publications XHR idiom
 * (real progress events, ApiError-shaped failures). The backend exposes
 * PART 7 server-side search (`q`) + filters (`department`, `designation`,
 * `employment_type`, `status`) with name-ordered pagination.
 *
 * ENCODING CONTRACT (same as every module — do not break): ids travel
 * decoded (`obj:faculty:AB12…`); list links encode exactly once and detail
 * pages decode exactly once. Never `encodeURIComponent` here.
 */
import { api, ApiError } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import { API_BASE_URL } from "@/config/env";
import { DEFAULT_FACULTY_PAGE_SIZE } from "@/lib/faculty/constants";
import type {
  FacultyEmploymentType,
  FacultyResponse,
  FacultySectionEntry,
  ListFacultyResponse,
  ResearchObjectStatus,
} from "@/types";

// ---------------------------------------------------------------------------
// Directory
// ---------------------------------------------------------------------------
export interface ListFacultyParams {
  page?: number;
  pageSize?: number;
  /** Server-side token-AND search (name, codes, designation, specialization, research areas). */
  q?: string;
  department?: string | null;
  designation?: string | null;
  employmentType?: FacultyEmploymentType | null;
  status?: ResearchObjectStatus | null;
}

export interface CreateFacultyPayload {
  name: string;
  employee_id: string;
  uploaded_by: string;
  status?: ResearchObjectStatus;
  faculty_code?: string | null;
  designation?: string | null;
  department?: string | null;
  school?: string | null;
  joining_date?: string | null;
  employment_type?: FacultyEmploymentType | null;
  email?: string | null;
  mobile?: string | null;
  office?: string | null;
  qualification?: string | null;
  specialization?: string | null;
  research_interests?: string[];
  biography?: string | null;
  orcid?: string | null;
  scopus_id?: string | null;
  google_scholar?: string | null;
  researchgate?: string | null;
  website?: string | null;
  notes?: string | null;
  tags?: string[];
  // Academic profile sections (PART 2) — JSON list-of-dicts.
  degrees?: FacultySectionEntry[];
  experience?: FacultySectionEntry[];
  awards?: FacultySectionEntry[];
  memberships?: FacultySectionEntry[];
  certifications?: FacultySectionEntry[];
  admin_positions?: FacultySectionEntry[];
  // Committee memberships (PART 3) — the only edges this module owns.
  links?: Partial<Record<"committees", string[]>>;
}

/** Partial update: every present key replaces; absent keys are untouched. */
export type UpdateFacultyPayload = Partial<CreateFacultyPayload>;

export function listFaculty(
  params: ListFacultyParams = {},
  options?: RequestOptions,
): Promise<ListFacultyResponse> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_FACULTY_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.department?.trim()) query.department = params.department.trim();
  if (params.designation?.trim()) query.designation = params.designation.trim();
  if (params.employmentType) query.employment_type = params.employmentType;
  if (params.status) query.status = params.status;
  return api.get<ListFacultyResponse>("/faculty", { ...options, query });
}

/** `id` must already be decoded (`obj:faculty:…`). */
export function getFaculty(id: string, options?: RequestOptions): Promise<FacultyResponse> {
  return api.get<FacultyResponse>(`/faculty/${id}`, options);
}

export function createFaculty(
  payload: CreateFacultyPayload,
  options?: RequestOptions,
): Promise<FacultyResponse> {
  return api.post<FacultyResponse>("/faculty", payload, options);
}

export function updateFaculty(
  id: string,
  payload: UpdateFacultyPayload,
  options?: RequestOptions,
): Promise<FacultyResponse> {
  return api.put<FacultyResponse>(`/faculty/${id}`, payload, options);
}

export function deleteFaculty(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/faculty/${id}`, options);
}

// ---------------------------------------------------------------------------
// Profile photo (PART 1) — the attach_publication_pdf precedent
// ---------------------------------------------------------------------------
export interface UploadProgress {
  percent: number;
}

/**
 * Attach (or replace) the profile photo. Uses XMLHttpRequest so the UI can
 * show a real upload-progress percentage; errors arrive as {@link ApiError}
 * so the rest of the app handles them exactly like JSON requests.
 */
export function attachFacultyPhoto(
  id: string,
  file: File,
  callbacks: {
    onProgress?: (progress: UploadProgress) => void;
    signal?: AbortSignal;
    uploadedBy?: string;
  } = {},
): Promise<FacultyResponse> {
  const formData = new FormData();
  formData.append("file", file, file.name);

  return new Promise<FacultyResponse>((resolve, reject) => {
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
          resolve(JSON.parse(xhr.responseText) as FacultyResponse);
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
      `${API_BASE_URL}/faculty/${id}/photo?uploaded_by=${encodeURIComponent(uploadedBy)}`,
    );
    xhr.send(formData);
  });
}
