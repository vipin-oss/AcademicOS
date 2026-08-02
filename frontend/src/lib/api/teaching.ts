/**
 * Teaching API — frontend mirror of the `/teaching` contract.
 *
 * Mirrors `lib/api/publications.ts`: JSON calls reuse the shared {@link api}
 * wrapper; the SUBMISSION file upload (multipart) uses XMLHttpRequest with
 * the exact `attachPublicationPdf` pattern so progress and error handling
 * stay identical across modules.
 *
 * ENCODING CONTRACT (do not break): ids travel decoded; never
 * `encodeURIComponent` them here.
 */
import { API_BASE_URL } from "@/config/env";
import { api, ApiError } from "@/lib/api/client";
import type { RequestOptions } from "@/lib/api/client";
import { DEFAULT_CLASS_PAGE_SIZE } from "@/lib/teaching/constants";
import type {
  AssignmentResponse,
  AssignmentTypeValue,
  AssignmentVisibility,
  AttendanceImportResult,
  AttendanceSessionResponse,
  AttendanceState,
  AttendanceSummary,
  CascadeDeleteResult,
  ClassLinkGroup,
  ClassReport,
  ClassResponse,
  ClassStatus,
  EnrollmentResult,
  Gradebook,
  ListAssignmentsResponse,
  ListClassesResponse,
  ListSubmissionsResponse,
  MarksImportResult,
  RosterEntry,
  RubricCriterion,
  RubricScore,
  SubmissionGrid,
  SubmissionResponse,
  TeachingDashboard,
  WeeklySlot,
} from "@/types";

// ---------------------------------------------------------------------------
// Classes
// ---------------------------------------------------------------------------
export interface ListClassesParams {
  page?: number;
  pageSize?: number;
  q?: string;
  semester?: number | null;
  session?: string | null;
  status?: ClassStatus | null;
  /** The object lens: classes a STUDENT is enrolled in / a FACULTY teaches. */
  objectId?: string | null;
}

export interface CreateClassPayload {
  title: string;
  uploaded_by: string;
  status?: ClassStatus;
  course_code?: string | null;
  programme?: string | null;
  semester?: number | null;
  section?: string | null;
  session?: string | null;
  credits?: number | null;
  weekly_schedule?: WeeklySlot[];
  room?: string | null;
  class_mode?: string | null;
  notes?: string | null;
  tags?: string[];
  links?: Partial<Record<ClassLinkGroup, string[]>>;
  /** Initial enrollment (student Object ids). */
  students?: string[];
}

export type UpdateClassPayload = Partial<CreateClassPayload>;

function classQuery(params: ListClassesParams): Record<string, string | number> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? DEFAULT_CLASS_PAGE_SIZE,
  };
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.semester != null) query.semester = params.semester;
  if (params.session?.trim()) query.session = params.session.trim();
  if (params.status) query.status = params.status;
  if (params.objectId) query.object_id = params.objectId;
  return query;
}

export function listClasses(
  params: ListClassesParams = {},
  options?: RequestOptions,
): Promise<ListClassesResponse> {
  return api.get<ListClassesResponse>("/teaching/classes", {
    ...options,
    query: classQuery(params),
  });
}

export function listClassesByObject(
  objectId: string,
  options?: RequestOptions,
): Promise<ListClassesResponse> {
  return api.get<ListClassesResponse>("/teaching/classes", {
    ...options,
    query: { object_id: objectId, page_size: 100 },
  });
}

export function getClass(id: string, options?: RequestOptions): Promise<ClassResponse> {
  return api.get<ClassResponse>(`/teaching/classes/${id}`, options);
}

export function createClass(
  payload: CreateClassPayload,
  options?: RequestOptions,
): Promise<ClassResponse> {
  return api.post<ClassResponse>("/teaching/classes", payload, options);
}

export function updateClass(
  id: string,
  payload: UpdateClassPayload,
  options?: RequestOptions,
): Promise<ClassResponse> {
  return api.put<ClassResponse>(`/teaching/classes/${id}`, payload, options);
}

/** Cascade-delete: returns WHAT was removed (assignments/submissions/…). */
export function deleteClass(
  id: string,
  options?: RequestOptions,
): Promise<CascadeDeleteResult> {
  return api.delete<CascadeDeleteResult>(`/teaching/classes/${id}`, options);
}

// ---------------------------------------------------------------------------
// Enrollment (PART C)
// ---------------------------------------------------------------------------
export function getRoster(classId: string, options?: RequestOptions): Promise<RosterEntry[]> {
  return api.get<RosterEntry[]>(`/teaching/classes/${classId}/roster`, options);
}

export function enrollStudents(
  classId: string,
  studentIds: string[],
  actor: string,
  options?: RequestOptions,
): Promise<EnrollmentResult> {
  return api.post<EnrollmentResult>(
    `/teaching/classes/${classId}/enroll`,
    { student_ids: studentIds, actor },
    options,
  );
}

export function enrollFromCsv(
  classId: string,
  text: string,
  actor: string,
  options?: RequestOptions,
): Promise<EnrollmentResult> {
  return api.post<EnrollmentResult>(
    `/teaching/classes/${classId}/enroll/csv`,
    { text, actor },
    options,
  );
}

export function unenrollStudent(
  classId: string,
  studentId: string,
  options?: RequestOptions,
): Promise<void> {
  return api.delete<void>(`/teaching/classes/${classId}/enroll/${studentId}`, options);
}

// ---------------------------------------------------------------------------
// Assignments (PART D)
// ---------------------------------------------------------------------------
export interface ListAssignmentsParams {
  page?: number;
  pageSize?: number;
  classId?: string | null;
  q?: string;
  assignmentType?: AssignmentTypeValue | null;
  visibility?: AssignmentVisibility | null;
  status?: ClassStatus | null;
  /** The object lens: assignments of one Class. */
  objectId?: string | null;
}

export interface CreateAssignmentPayload {
  title: string;
  uploaded_by: string;
  class_id?: string | null;
  assignment_type?: AssignmentTypeValue;
  status?: ClassStatus;
  description?: string | null;
  instructions?: string | null;
  max_marks?: number | null;
  deadline?: string | null;
  late_allowed?: boolean;
  rubric?: RubricCriterion[];
  visibility?: AssignmentVisibility;
  weightage?: number | null;
}

export type UpdateAssignmentPayload = Partial<CreateAssignmentPayload>;

export function listAssignments(
  params: ListAssignmentsParams = {},
  options?: RequestOptions,
): Promise<ListAssignmentsResponse> {
  const query: Record<string, string | number> = {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 50,
  };
  if (params.classId) query.class_id = params.classId;
  if (params.q?.trim()) query.q = params.q.trim();
  if (params.assignmentType) query.assignment_type = params.assignmentType;
  if (params.visibility) query.visibility = params.visibility;
  if (params.status) query.status = params.status;
  if (params.objectId) query.object_id = params.objectId;
  return api.get<ListAssignmentsResponse>("/teaching/assignments", {
    ...options,
    query,
  });
}

export function listClassAssignments(
  classId: string,
  options?: RequestOptions,
): Promise<ListAssignmentsResponse> {
  return api.get<ListAssignmentsResponse>(`/teaching/classes/${classId}/assignments`, {
    ...options,
    query: { page_size: 100 },
  });
}

export function getAssignment(
  id: string,
  options?: RequestOptions,
): Promise<AssignmentResponse> {
  return api.get<AssignmentResponse>(`/teaching/assignments/${id}`, options);
}

export function createAssignment(
  payload: CreateAssignmentPayload,
  options?: RequestOptions,
): Promise<AssignmentResponse> {
  return api.post<AssignmentResponse>("/teaching/assignments", payload, options);
}

/** Class-scoped create (PART D: an assignment always belongs to a class). */
export function createClassAssignment(
  classId: string,
  payload: CreateAssignmentPayload,
  options?: RequestOptions,
): Promise<AssignmentResponse> {
  return api.post<AssignmentResponse>(
    `/teaching/classes/${classId}/assignments`,
    payload,
    options,
  );
}

export function updateAssignment(
  id: string,
  payload: UpdateAssignmentPayload,
  options?: RequestOptions,
): Promise<AssignmentResponse> {
  return api.put<AssignmentResponse>(`/teaching/assignments/${id}`, payload, options);
}

/** Cascade-delete (its submissions + blobs); returns what was removed. */
export function deleteAssignment(
  id: string,
  options?: RequestOptions,
): Promise<CascadeDeleteResult> {
  return api.delete<CascadeDeleteResult>(`/teaching/assignments/${id}`, options);
}

/**
 * Shared multipart helper (the `attachPublicationPdf` XHR pattern): the
 * shared JSON client deliberately stays JSON-only, so file uploads report
 * real progress through `XMLHttpRequest` and surface `ApiError`s exactly
 * like every other call.
 */
function uploadFormData<T>(
  method: "POST" | "PUT",
  path: string,
  formData: FormData,
  callbacks: { onProgress?: (progress: { percent: number }) => void; signal?: AbortSignal } = {},
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    if (callbacks.signal?.aborted) {
      reject(new ApiError("Upload cancelled.", { kind: "aborted" }));
      return;
    }
    const xhr = new XMLHttpRequest();
    callbacks.signal?.addEventListener("abort", () => xhr.abort());
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && callbacks.onProgress) {
        callbacks.onProgress({
          percent: Math.round((event.loaded / event.total) * 100),
        });
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
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
      reject(new ApiError(`Cannot reach the API at ${API_BASE_URL}.`, { kind: "network" }));
    xhr.ontimeout = () => reject(new ApiError("The request timed out.", { kind: "timeout" }));
    xhr.open(method, `${API_BASE_URL}${path}`);
    xhr.send(formData);
  });
}

/** Attach (or replace) the assignment's reference file (PART D). */
export function attachAssignmentFile(
  id: string,
  file: File,
  uploadedBy: string,
  callbacks: { onProgress?: (progress: { percent: number }) => void; signal?: AbortSignal } = {},
): Promise<AssignmentResponse> {
  const formData = new FormData();
  formData.append("file", file, file.name);
  return uploadFormData<AssignmentResponse>(
    "PUT",
    `/teaching/assignments/${id}/attachment?uploaded_by=${encodeURIComponent(uploadedBy)}`,
    formData,
    callbacks,
  );
}

// ---------------------------------------------------------------------------
// Submissions (PART E) + the grid (UI Spec C7) + marks CSV (PARTS F/G)
// ---------------------------------------------------------------------------
export function listSubmissions(
  params: { assignmentId?: string; studentId?: string; state?: string } = {},
  options?: RequestOptions,
): Promise<ListSubmissionsResponse> {
  const query: Record<string, string | number> = { page_size: 100 };
  if (params.assignmentId) query.assignment_id = params.assignmentId;
  if (params.studentId) query.student_id = params.studentId;
  if (params.state) query.state = params.state;
  return api.get<ListSubmissionsResponse>("/teaching/submissions", { ...options, query });
}

export function getSubmissionGrid(
  assignmentId: string,
  options?: RequestOptions,
): Promise<SubmissionGrid> {
  return api.get<SubmissionGrid>(`/teaching/assignments/${assignmentId}/grid`, options);
}

/**
 * Student (re)submission — multipart; the file is optional (a submission can
 * be a comment/mark placeholder). Same XHR pattern as `attachPublicationPdf`
 * so real upload progress + ApiError normalisation stay one implementation.
 */
export function submitToAssignment(
  assignmentId: string,
  args: {
    studentId: string;
    comments?: string | null;
    submittedAt?: string | null;
    actor?: string;
    file?: File | null;
  },
  callbacks: { onProgress?: (progress: { percent: number }) => void; signal?: AbortSignal } = {},
): Promise<SubmissionResponse> {
  const formData = new FormData();
  formData.append("student_id", args.studentId);
  if (args.comments) formData.append("comments", args.comments);
  if (args.submittedAt) formData.append("submitted_at", args.submittedAt);
  formData.append("actor", args.actor || "system");
  if (args.file) formData.append("file", args.file, args.file.name);

  return uploadFormData<SubmissionResponse>(
    "POST",
    `/teaching/assignments/${assignmentId}/submit`,
    formData,
    callbacks,
  );
}

export function gradeSubmission(
  submissionId: string,
  payload: {
    marks?: number | null;
    faculty_feedback?: string | null;
    rubric_score?: RubricScore[];
    actor?: string;
  },
  options?: RequestOptions,
): Promise<SubmissionResponse> {
  return api.put<SubmissionResponse>(
    `/teaching/submissions/${submissionId}/grade`,
    payload,
    options,
  );
}

export function deleteSubmission(id: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/teaching/submissions/${id}`, options);
}

/** PART G: the Google-Forms loop — import a response/marks CSV. */
export function importMarksCsv(
  assignmentId: string,
  text: string,
  actor: string,
  options?: RequestOptions,
): Promise<MarksImportResult> {
  return api.post<MarksImportResult>(
    `/teaching/assignments/${assignmentId}/marks/import`,
    { text, actor },
    options,
  );
}

// ---------------------------------------------------------------------------
// Attendance (PART I)
// ---------------------------------------------------------------------------
export function listAttendance(
  classId: string,
  options?: RequestOptions,
): Promise<AttendanceSessionResponse[]> {
  return api.get<AttendanceSessionResponse[]>(
    `/teaching/classes/${classId}/attendance`,
    options,
  );
}

export function recordAttendance(
  classId: string,
  payload: {
    session_date: string;
    records: Record<string, AttendanceState>;
    actor?: string;
  },
  options?: RequestOptions,
): Promise<AttendanceSessionResponse> {
  return api.post<AttendanceSessionResponse>(
    `/teaching/classes/${classId}/attendance`,
    payload,
    options,
  );
}

export function importAttendanceCsv(
  classId: string,
  payload: { session_date: string; text: string; actor?: string },
  options?: RequestOptions,
): Promise<AttendanceImportResult> {
  return api.post<AttendanceImportResult>(
    `/teaching/classes/${classId}/attendance/import`,
    payload,
    options,
  );
}

export function getAttendanceSummary(
  classId: string,
  threshold?: number,
  options?: RequestOptions,
): Promise<AttendanceSummary> {
  return api.get<AttendanceSummary>(`/teaching/classes/${classId}/attendance/summary`, {
    ...options,
    query: threshold != null ? { threshold } : {},
  });
}

// ---------------------------------------------------------------------------
// Gradebook / report / dashboard (PARTS H + J + K)
// ---------------------------------------------------------------------------
export function getGradebook(classId: string, options?: RequestOptions): Promise<Gradebook> {
  return api.get<Gradebook>(`/teaching/classes/${classId}/gradebook`, options);
}

export function getClassReport(classId: string, options?: RequestOptions): Promise<ClassReport> {
  return api.get<ClassReport>(`/teaching/classes/${classId}/report`, options);
}

export function getTeachingDashboard(
  options?: RequestOptions,
): Promise<TeachingDashboard> {
  return api.get<TeachingDashboard>("/teaching/dashboard", options);
}

/** Absolute gradebook CSV URL (university marks-sheet foundation). */
export function gradebookExportUrl(classId: string): string {
  return `${API_BASE_URL}/teaching/classes/${classId}/gradebook/export`;
}
