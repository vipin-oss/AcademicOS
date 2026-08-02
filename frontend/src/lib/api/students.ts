/**
 * Students API — frontend mirror of the `/students` contract.
 *
 * Mirrors `lib/api/publications.ts` one-to-one: every call reuses the shared
 * {@link api} wrapper (identical error normalisation, timeouts and aborts).
 * The backend exposes server-side search + filters (`q`, `student_type`,
 * `programme`, `semester`, `section`, `status`, `object_id`) — each parameter
 * below maps 1:1 onto the API.
 *
 * ENCODING CONTRACT (same as every module — do not break): ids travel
 * decoded (`obj:student:AB12…`); the list Link encodes exactly once and the
 * detail page decodes exactly once. Never `encodeURIComponent` here.
 */
import { API_BASE_URL } from "@/config/env";
import { api } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import { DEFAULT_STUDENT_PAGE_SIZE } from "@/lib/students/constants";
import type {
  ListStudentsResponse,
  StudentImportResult,
  StudentLinkGroup,
  StudentResponse,
  StudentStatus,
  StudentTypeValue,
} from "@/types";

export interface ListStudentsParams {
  page?: number;
  pageSize?: number;
  /** Server-side token-AND search (name/roll/registration/enrollment/email/…). */
  q?: string;
  studentType?: StudentTypeValue | null;
  programme?: string | null;
  semester?: number | null;
  section?: string | null;
  status?: StudentStatus | null;
  /** The object lens: "students linked to Object X" (e.g. scholars of a supervisor). */
  objectId?: string | null;
}

export interface CreateStudentPayload {
  name: string;
  student_type: StudentTypeValue;
  uploaded_by: string;
  status?: StudentStatus;
  roll_number?: string | null;
  registration_number?: string | null;
  university_enrollment?: string | null;
  email?: string | null;
  phone?: string | null;
  programme?: string | null;
  department?: string | null;
  semester?: number | null;
  section?: string | null;
  batch?: string | null;
  admission_date?: string | null;
  expected_graduation?: string | null;
  research_area?: string | null;
  orcid?: string | null;
  google_scholar?: string | null;
  notes?: string | null;
  tags?: string[];
  /** {group: [object ids]} — present groups replace, absent groups untouched. */
  links?: Partial<Record<StudentLinkGroup, string[]>>;
}

/** Partial update: every present key replaces; absent keys are untouched. */
export type UpdateStudentPayload = Partial<CreateStudentPayload>;

function listQuery(params: ListStudentsParams): Record<string, string | number> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_STUDENT_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.studentType) query.student_type = params.studentType;
  if (params.programme?.trim()) query.programme = params.programme.trim();
  if (params.semester != null) query.semester = params.semester;
  if (params.section?.trim()) query.section = params.section.trim();
  if (params.status) query.status = params.status;
  if (params.objectId) query.object_id = params.objectId;
  return query;
}

export function listStudents(
  params: ListStudentsParams = {},
  options?: RequestOptions,
): Promise<ListStudentsResponse> {
  return api.get<ListStudentsResponse>("/students", {
    ...options,
    query: listQuery(params),
  });
}

/** Students linked to a single Object (`GET /students?object_id=`). */
export function listStudentsByObject(
  objectId: string,
  options?: RequestOptions,
): Promise<ListStudentsResponse> {
  return api.get<ListStudentsResponse>("/students", {
    ...options,
    query: { object_id: objectId, page_size: 100 },
  });
}

/** `id` must already be decoded (`obj:student:…`) — never encode it here. */
export function getStudent(
  id: string,
  options?: RequestOptions,
): Promise<StudentResponse> {
  return api.get<StudentResponse>(`/students/${id}`, options);
}

export function createStudent(
  payload: CreateStudentPayload,
  options?: RequestOptions,
): Promise<StudentResponse> {
  return api.post<StudentResponse>("/students", payload, options);
}

/** `id` must already be decoded (`obj:student:…`) — never encode it here. */
export function updateStudent(
  id: string,
  payload: UpdateStudentPayload,
  options?: RequestOptions,
): Promise<StudentResponse> {
  return api.put<StudentResponse>(`/students/${id}`, payload, options);
}

/** `id` must already be decoded (`obj:student:…`) — never encode it here. */
export function deleteStudent(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/students/${id}`, options);
}

/** Bulk roster CSV import (PARTS C + F) — headers auto-map server-side. */
export function importStudentsCsv(
  text: string,
  uploadedBy: string,
  options?: RequestOptions,
): Promise<StudentImportResult> {
  return api.post<StudentImportResult>(
    "/students/import",
    { text, uploaded_by: uploadedBy },
    options,
  );
}

/** Absolute CSV-export URL preserving the current filters (used as href). */
export function studentsExportUrl(params: ListStudentsParams = {}): string {
  const query = listQuery({ ...params, page: 1, pageSize: 100 });
  delete query.page;
  delete query.page_size;
  const search = new URLSearchParams(
    Object.entries(query).map(([key, value]) => [key, String(value)]),
  ).toString();
  return `${API_BASE_URL}/students/export${search ? `?${search}` : ""}`;
}
