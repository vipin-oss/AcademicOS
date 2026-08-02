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

// ---------------------------------------------------------------------------
// Students module (Teaching & Student Management — PART A)
// ---------------------------------------------------------------------------

export type StudentStatus = "draft" | "active" | "archived";

/** The registry taxonomy: undergraduate / postgraduate / doctoral / alumni. */
export type StudentTypeValue = "ug" | "pg" | "phd" | "alumni";

/** The student-side "Linked X" panes (typed relationship edges). */
export type StudentLinkGroup =
  | "supervisors"
  | "co_supervisors"
  | "projects"
  | "grants"
  | "committees"
  | "events";

/** A denormalised linked Object in a student's `links` payload. */
export interface StudentLinkedObject {
  id: string;
  title: string;
  object_type: string;
  /** The typed edge (supervised_by / advised_by / works_in / …). */
  kind: string;
}

/**
 * Frontend mirror of the Students contract (StudentResponseModel):
 *   GET    /students              -> ListStudentsResponse
 *   GET    /students/{id}         -> StudentResponse
 *   POST   /students              -> StudentResponse (409 on duplicate roll/enrollment)
 *   PUT    /students/{id}         -> StudentResponse
 *   DELETE /students/{id}         -> 204
 *   GET    /students?object_id=.. -> ListStudentsResponse (object lens)
 *   GET    /students/export       -> CSV download
 *   POST   /students/import       -> StudentImportResult
 */
export interface StudentResponse {
  id: string;
  name: string;
  student_type: StudentTypeValue;
  status: StudentStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
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
  tags: string[];
  links: Record<StudentLinkGroup, StudentLinkedObject[]>;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListStudentsResponse {
  items: StudentResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface StudentImportResult {
  created: string[];
  skipped_duplicates: { index: number; name?: string; roll_number?: string; message: string }[];
  errors: { index: number; name?: string; message: string }[];
}

// ---------------------------------------------------------------------------
// Teaching module (classes → assignments → submissions → marks → attendance)
// ---------------------------------------------------------------------------

export type ClassStatus = "draft" | "active" | "archived";
export type ClassMode = "offline" | "online" | "blended";
export type ClassLinkGroup = "teachers" | "departments";

export interface WeeklySlot {
  day: "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";
  start?: string;
  end?: string;
}

export interface ClassLinkedObject {
  id: string;
  title: string;
  object_type: string;
  kind: string;
}

export interface ClassResponse {
  id: string;
  title: string;
  status: ClassStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  course_code?: string | null;
  programme?: string | null;
  semester?: number | null;
  section?: string | null;
  session?: string | null;
  credits?: number | null;
  weekly_schedule: WeeklySlot[];
  room?: string | null;
  class_mode?: ClassMode | null;
  notes?: string | null;
  tags: string[];
  student_count: number;
  links: Record<ClassLinkGroup, ClassLinkedObject[]>;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListClassesResponse {
  items: ClassResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface RosterEntry {
  student_id: string;
  name: string;
  roll_number?: string | null;
  email?: string | null;
  programme?: string | null;
  semester?: number | null;
  section?: string | null;
  student_type?: string | null;
}

export interface EnrollmentResult {
  enrolled: string[];
  already_enrolled: string[];
  errors: { student_id?: string; index?: number; roll_number?: string; message: string }[];
}

/** PART D vocabulary: assignment / quiz / internal / mid sem / end sem. */
export type AssignmentTypeValue =
  | "assignment"
  | "quiz"
  | "internal_assessment"
  | "mid_semester"
  | "end_semester";

export type AssignmentVisibility = "visible" | "hidden";

export interface RubricCriterion {
  criterion: string;
  marks?: number;
}

export interface AssignmentResponse {
  id: string;
  title: string;
  class_id: string;
  class_title?: string | null;
  assignment_type: AssignmentTypeValue;
  status: ClassStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  description?: string | null;
  instructions?: string | null;
  max_marks?: number | null;
  deadline?: string | null;
  late_allowed: boolean;
  rubric: RubricCriterion[];
  visibility: AssignmentVisibility;
  weightage?: number | null;
  attachment_file_name?: string | null;
  attachment_file_size: number;
  attachment_mime_type?: string | null;
  attachment_url?: string | null;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListAssignmentsResponse {
  items: AssignmentResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface RubricScore {
  criterion: string;
  marks_awarded?: number;
}

export interface SubmissionResponse {
  id: string;
  assignment_id: string;
  student_id: string;
  student_name?: string | null;
  student_roll?: string | null;
  submitted_at?: string | null;
  is_late: boolean;
  comments?: string | null;
  marks?: number | null;
  faculty_feedback?: string | null;
  rubric_score: RubricScore[];
  graded_at?: string | null;
  graded_by?: string | null;
  file_name?: string | null;
  file_size: number;
  file_mime_type?: string | null;
  file_url?: string | null;
  status: string;
  version: number;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListSubmissionsResponse {
  items: SubmissionResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

/** PART E grid: one row per roster student (pending rows are virtual). */
export type SubmissionGridState = "submitted" | "late" | "pending" | "graded";

export interface SubmissionGridRow {
  student_id: string;
  student_name: string;
  student_roll?: string | null;
  state: SubmissionGridState;
  submission?: SubmissionResponse | null;
}

export interface SubmissionGrid {
  assignment_id: string;
  rows: SubmissionGridRow[];
  submitted_count: number;
  late_count: number;
  pending_count: number;
  graded_count: number;
}

export interface MarksImportResult {
  assignment_id: string;
  graded: string[];
  created_submissions: string[];
  errors: { index: number; roll_number?: string; message: string }[];
}

/** PART I vocabulary. */
export type AttendanceState = "present" | "absent" | "late" | "medical_leave";

export interface AttendanceSessionResponse {
  id: string;
  class_id: string;
  session_date: string;
  records: Record<string, AttendanceState>;
  status: string;
  version: number;
  events?: string[];
}

export interface AttendanceImportResult {
  class_id: string;
  session_date: string;
  applied: string[];
  unknown: { index: number; roll_number?: string; message: string }[];
  errors: { index: number; roll_number?: string; message: string }[];
}

export interface AttendanceSummaryRow {
  student_id: string;
  student_name: string;
  student_roll?: string | null;
  present: number;
  absent: number;
  late: number;
  medical_leave: number;
  effective_present: number;
  total: number;
  percentage: number;
  below_threshold: boolean;
}

export interface AttendanceSummary {
  class_id: string;
  session_count: number;
  threshold: number;
  rows: AttendanceSummaryRow[];
}

/** PART H — the computed gradebook. */
export interface GradebookAssignmentHeader {
  id: string;
  title: string;
  assignment_type: AssignmentTypeValue;
  max_marks?: number | null;
  weightage?: number | null;
}

export interface GradebookCell {
  assignment_id: string;
  title: string;
  assignment_type: AssignmentTypeValue;
  max_marks?: number | null;
  weightage?: number | null;
  marks?: number | null;
  is_late: boolean;
}

export interface GradebookRow {
  student_id: string;
  student_name: string;
  student_roll?: string | null;
  cells: GradebookCell[];
  internal_total: number;
  internal_max: number;
  grade: string;
  average_percent: number;
}

export interface Gradebook {
  class_id: string;
  assignments: GradebookAssignmentHeader[];
  rows: GradebookRow[];
}

export interface AssignmentStat {
  assignment_id: string;
  title: string;
  assignment_type: AssignmentTypeValue;
  max_marks?: number | null;
  deadline?: string | null;
  submitted: number;
  late: number;
  pending: number;
  graded: number;
  average_marks?: number | null;
}

export interface StudentSignal {
  student_id: string;
  name: string;
  roll_number?: string | null;
  average_marks_percent: number;
  attendance_percent?: number | null;
  class_id?: string;
  class_title?: string;
  reasons?: string[];
}

/** PART K — the AI-report-ready class payload. */
export interface ClassReport {
  class_info: ClassResponse;
  roster: RosterEntry[];
  assignment_stats: AssignmentStat[];
  gradebook: Gradebook;
  attendance: AttendanceSummary;
  average_marks_percent?: number | null;
  pending_submissions: number;
  late_submissions: number;
  weak_students: StudentSignal[];
  top_performers: StudentSignal[];
}

/** PART J — the faculty dashboard. */
export interface TeachingDashboard {
  class_count: number;
  student_count: number;
  assignment_count: number;
  pending_submissions: number;
  late_submissions: number;
  graded_submissions: number;
  average_marks_percent?: number | null;
  weak_students: StudentSignal[];
  top_performers: StudentSignal[];
  classes: ClassResponse[];
}

export interface CascadeDeleteResult {
  assignments?: number;
  submissions?: number;
  attendance_sessions?: number;
  unenrolled_students?: number;
}
