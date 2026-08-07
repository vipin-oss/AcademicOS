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
  | "png"
  | "jpg"
  | "jpeg"
  | "tiff"
  | "svg"
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

// ---------------------------------------------------------------------------
// Research module (Projects & Grants management)
// ---------------------------------------------------------------------------

/** The 9-state research lifecycle (a type-specific state — metadata, §1.4). */
export type ProjectLifecycleStatus =
  | "draft"
  | "proposal_submitted"
  | "under_review"
  | "approved"
  | "funded"
  | "active"
  | "on_hold"
  | "completed"
  | "closed";

export type ProjectPriority = "high" | "medium" | "low";
export type MilestoneStatus = "pending" | "in_progress" | "done";
export type InstallmentStatus = "scheduled" | "released";
export type ResearchObjectStatus = "draft" | "active" | "archived";

/** A denormalised linked Object in a research payload (typed edge). */
export interface ResearchLinkedObject {
  id: string;
  title: string;
  object_type: string;
  kind: string;
}

/** Outgoing edges that live on the project aggregate. */
export type ProjectLinkGroup = "agencies" | "committees";
/** Outgoing edges that live on the grant aggregate. */
export type GrantLinkGroup = "projects" | "funding_agencies";
/** Team edges are written on the faculty/student aggregates. */
export type ProjectTeamGroup =
  | "principal_investigators"
  | "co_investigators"
  | "team_members";

export interface ProjectMilestone {
  id: string;
  title: string;
  date?: string | null;
  status: MilestoneStatus;
  notes?: string | null;
}

/** PART 8 progress log entry ({date, percent, remark}). */
export interface ProjectProgressUpdate {
  date: string;
  percent: number;
  remark: string;
}

/** PART 7 project-level MVP budget view. */
export interface ProjectBudget {
  approved: number | null;
  utilized: number | null;
  remaining: number | null;
  /** Sum of released installments across the project's grant objects. */
  grants_released: number | null;
}

/**
 * Frontend mirror of the Research projects contract:
 *   GET    /research/projects              -> ListProjectsResponse (PART 9 filters)
 *   GET    /research/projects/{id}         -> ProjectResponse (enriched workspace)
 *   POST   /research/projects              -> ProjectResponse (409 duplicate code)
 *   PUT    /research/projects/{id}         -> ProjectResponse (merge + lifecycle)
 *   DELETE /research/projects/{id}         -> 204 (milestones cascade)
 *   POST   /research/projects/{id}/milestones / .../updates
 *   GET    /research/projects?object_id=.. -> object lens
 */
export interface ProjectResponse {
  id: string;
  title: string;
  status: ResearchObjectStatus;
  lifecycle_status: ProjectLifecycleStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  project_code?: string | null;
  department?: string | null;
  grant_number?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  duration?: string | null;
  budget_approved?: number | null;
  budget_utilized?: number | null;
  objectives?: string | null;
  keywords: string[];
  abstract?: string | null;
  priority?: string | null;
  notes?: string | null;
  tags: string[];
  progress_updates: ProjectProgressUpdate[];
  links: Record<ProjectLinkGroup, ResearchLinkedObject[]>;
  team: Record<ProjectTeamGroup, ResearchLinkedObject[]>;
  milestones: ProjectMilestone[];
  budget?: ProjectBudget | null;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListProjectsResponse {
  items: ProjectResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface GrantInstallment {
  id: string;
  installment_no?: number | null;
  date?: string | null;
  amount?: number | null;
  status: InstallmentStatus;
  notes?: string | null;
}

export interface GrantExpenditure {
  id: string;
  date?: string | null;
  head?: string | null;
  amount?: number | null;
  reference?: string | null;
  notes?: string | null;
}

/** PART 7 grant budget view (approved/released/utilized/remaining). */
export interface GrantBudget {
  approved: number | null;
  released: number | null;
  utilized: number | null;
  remaining: number | null;
}

/**
 * Frontend mirror of the Research grants contract:
 *   GET    /research/grants                -> ListGrantsResponse (q + lenses)
 *   GET    /research/grants/{id}           -> GrantResponse (enriched)
 *   POST   /research/grants                -> GrantResponse (409 duplicate number)
 *   PUT    /research/grants/{id}           -> GrantResponse (merge)
 *   DELETE /research/grants/{id}           -> 204 (children cascade)
 *   POST   /research/grants/{id}/installments / .../expenditures
 *   DELETE /research/installments/{id} / /expenditures/{id}
 */
export interface GrantResponse {
  id: string;
  title: string;
  grant_number: string;
  status: ResearchObjectStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  amount?: number | null;
  release_schedule?: string | null;
  notes?: string | null;
  links: Record<GrantLinkGroup, ResearchLinkedObject[]>;
  installments: GrantInstallment[];
  expenditures: GrantExpenditure[];
  budget?: GrantBudget | null;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListGrantsResponse {
  items: GrantResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

/**
 * Frontend mirror of the Funding Agency contract (registry — name unique):
 *   GET/POST /research/agencies, GET/PUT/DELETE /research/agencies/{id}
 */
export interface AgencyResponse {
  id: string;
  name: string;
  status: ResearchObjectStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  website?: string | null;
  scheme?: string | null;
  contact_person?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  address?: string | null;
  notes?: string | null;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListAgenciesResponse {
  items: AgencyResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

/** PART 10 dashboard card: one upcoming milestone with its project. */
export interface ResearchUpcomingDeadline {
  milestone_id: string;
  title: string;
  date?: string | null;
  status: MilestoneStatus;
  project_id: string;
  project_title: string;
}

export interface ResearchDashboard {
  total_projects: number;
  active_projects: number;
  completed_projects: number;
  total_grants: number;
  budget_approved: number;
  budget_utilized: number;
  upcoming_deadlines: ResearchUpcomingDeadline[];
}

// ---------------------------------------------------------------------------
// Faculty module (Faculty Management)
// ---------------------------------------------------------------------------

/** Employment type vocabulary (PART 1 — guidance, not a closed enum). */
export type FacultyEmploymentType = "regular" | "contract" | "visiting" | "adjunct";

/** A denormalised linked Object in a faculty payload (typed edge). */
export interface FacultyLinkedObject {
  id: string;
  title: string;
  object_type: string;
  kind: string;
}

/** One row of an academic profile section (PART 2 — {degree, institution, year} etc.). */
export type FacultySectionEntry = Record<string, string>;

/** A supervised student: the linked object + the student-type lens (PART 4). */
export interface FacultySupervisionEntry extends FacultyLinkedObject {
  student_type?: string | null;
}

/** A taught class: the linked object + the teaching-load fields (PART 5). */
export interface FacultyTeachingClass extends FacultyLinkedObject {
  course_code?: string | null;
  programme?: string | null;
  semester?: number | null;
  credits?: number | null;
  weekly_hours: number;
}

/** PART 6 dashboard cards (computed by the backend, never client-side). */
export interface FacultyStats {
  publications: number;
  active_projects: number;
  grants: number;
  students_supervised: number;
  courses: number;
  committees: number;
}

/**
 * Frontend mirror of the Faculty contract:
 *   GET    /faculty              -> ListFacultyResponse (PART 7 search + filters)
 *   GET    /faculty/{id}         -> FacultyResponse (enriched workspace)
 *   POST   /faculty              -> FacultyResponse (409 duplicate employee id/code)
 *   PUT    /faculty/{id}         -> FacultyResponse (merge — provided keys replace)
 *   DELETE /faculty/{id}         -> 204
 *   PUT    /faculty/{id}/photo   -> FacultyResponse (profile photo, image/*)
 *   GET    /faculty/{id}/photo   -> the photo blob
 */
export interface FacultyResponse {
  id: string;
  name: string;
  status: ResearchObjectStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  employee_id?: string | null;
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
  research_interests: string[];
  biography?: string | null;
  orcid?: string | null;
  scopus_id?: string | null;
  google_scholar?: string | null;
  researchgate?: string | null;
  website?: string | null;
  notes?: string | null;
  tags: string[];
  // Academic profile sections (PART 2)
  degrees: FacultySectionEntry[];
  experience: FacultySectionEntry[];
  awards: FacultySectionEntry[];
  memberships: FacultySectionEntry[];
  certifications: FacultySectionEntry[];
  admin_positions: FacultySectionEntry[];
  // Profile photo facts (L2)
  photo_file_name?: string | null;
  photo_file_size: number;
  photo_mime_type?: string | null;
  photo_url?: string | null;
  // Edges the module owns
  links: Record<"committees", FacultyLinkedObject[]>;
  // Derived lenses (PART 3/4/5)
  research: {
    projects: FacultyLinkedObject[];
    grants: FacultyLinkedObject[];
  };
  supervision: {
    current: FacultySupervisionEntry[];
    completed: FacultySupervisionEntry[];
  };
  teaching: {
    classes: FacultyTeachingClass[];
    total_weekly_hours: number;
  };
  stats: FacultyStats;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListFacultyResponse {
  items: FacultyResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Committees & Meetings module (governance)
// ---------------------------------------------------------------------------

/** Member roles (PART 2 — the closed vocabulary from the spec). */
export type CommitteeRole =
  | "chairperson"
  | "convener"
  | "coordinator"
  | "member"
  | "external_expert"
  | "student_member"
  | "observer"
  | "nominee";

export type MeetingMode = "offline" | "online" | "hybrid";
export type AgendaItemPriority = "high" | "medium" | "low";
export type AgendaItemStatus = "pending" | "discussed" | "decided" | "deferred";
export type AttendanceStatus = "present" | "absent" | "leave";
export type ActionPriority = "high" | "medium" | "low";
export type ActionStatus = "pending" | "in_progress" | "done";

/** A denormalised linked Object in a committee payload (related_to edges). */
export interface CommitteeLinkedObject {
  id: string;
  title: string;
  object_type: string;
  kind: string;
}

/** PART 7 link groups written on the committee aggregate. */
export type CommitteeLinkGroup = "projects" | "grants" | "students" | "publications";

/** One resolved committee member (faculty/student backlink + role, PART 2). */
export interface CommitteeMember {
  id: string;
  name: string;
  object_type: string;
  role: CommitteeRole;
  start_date?: string | null;
  end_date?: string | null;
  remarks?: string | null;
}

/** A meeting row embedded in the committee workspace. */
export interface CommitteeMeetingSummary {
  id: string;
  title: string;
  meeting_number?: string | null;
  meeting_date?: string | null;
  venue?: string | null;
  mode?: MeetingMode | null;
  status: string;
}

export interface CommitteeStats {
  meetings: number;
  pending_actions: number;
  completed_actions: number;
}

/**
 * Frontend mirror of the Committees contract:
 *   GET    /committees            -> ListCommitteesResponse (PART 9 search + filters)
 *   GET    /committees/{id}       -> CommitteeResponse (enriched workspace)
 *   POST   /committees            -> 201 (409 duplicate code / name+type+dept)
 *   PUT    /committees/{id}       -> merge (members + links group-replace)
 *   DELETE /committees/{id}       -> 204 (meetings + actions cascade)
 */
export interface CommitteeResponse {
  id: string;
  name: string;
  status: ResearchObjectStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  committee_code?: string | null;
  committee_type?: string | null;
  department?: string | null;
  school?: string | null;
  description?: string | null;
  constitution_date?: string | null;
  expiry_date?: string | null;
  notes?: string | null;
  tags: string[];
  members: CommitteeMember[];
  meetings: CommitteeMeetingSummary[];
  links: Record<CommitteeLinkGroup, CommitteeLinkedObject[]>;
  stats: CommitteeStats;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListCommitteesResponse {
  items: CommitteeResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

/** PART 4 agenda item ({title, priority?, presenter?, discussion?, decision?, status?, document_ids?}). */
export interface AgendaItem {
  title: string;
  priority?: AgendaItemPriority | null;
  presenter?: string | null;
  discussion?: string | null;
  decision?: string | null;
  status?: AgendaItemStatus | null;
  document_ids?: string[];
  /** Resolved on read (GET): [{id, title}]. */
  supporting_documents?: { id: string; title: string }[];
}

/** Meeting attendance entry ({object_id | name, status}) — denormalised on read. */
export interface AttendanceEntry {
  object_id?: string | null;
  name: string;
  object_type?: string;
  status: AttendanceStatus;
}

/** PART 5 action item (a task child of the meeting). */
export interface ActionItem {
  id: string;
  title: string;
  status: ActionStatus;
  assigned_to?: string | null;
  assigned_name?: string | null;
  due_date?: string | null;
  priority?: ActionPriority | null;
  progress: number;
  completion_date?: string | null;
  remarks?: string | null;
  meeting?: CommitteeLinkedObject | null;
  committee?: CommitteeLinkedObject | null;
}

export interface MeetingStats {
  agenda_items: number;
  pending_actions: number;
  completed_actions: number;
}

/**
 * Frontend mirror of the Meetings contract:
 *   POST   /committees/{id}/meetings        -> 201 (409 number per committee)
 *   GET    /committees/meetings/{id}        -> MeetingResponse (workspace)
 *   PUT    /committees/meetings/{id}        -> MeetingResponse (merge)
 *   DELETE /committees/meetings/{id}        -> 204 (actions cascade)
 *   POST   /committees/meetings/{id}/actions / PUT/DELETE /committees/actions/{id}
 */
export interface MeetingResponse {
  id: string;
  title: string;
  status: string;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  meeting_number?: string | null;
  meeting_date?: string | null;
  venue?: string | null;
  mode?: MeetingMode | null;
  agenda_items: AgendaItem[];
  minutes?: string | null;
  attendance: AttendanceEntry[];
  decisions: string[];
  remarks?: string | null;
  committee?: CommitteeLinkedObject | null;
  action_items: ActionItem[];
  stats: MeetingStats;
  metadata?: Record<string, string>;
  events?: string[];
}

/** A dashboard upcoming-meeting row (with the committee denormalised). */
export interface UpcomingMeeting {
  meeting_id: string;
  committee_id: string;
  committee_title: string;
  title: string;
  meeting_number?: string | null;
  date: string;
  venue?: string | null;
  mode?: string | null;
}

/** PART 8 dashboard payload. */
export interface CommitteesDashboard {
  total_committees: number;
  active_committees: number;
  meetings_this_month: number;
  pending_actions: number;
  completed_actions: number;
  upcoming_meetings: UpcomingMeeting[];
}

// ---------------------------------------------------------------------------
// Finance & Procurement module (procurement governance)
// ---------------------------------------------------------------------------

export type ProposalStatus =
  | "draft"
  | "submitted"
  | "under_review"
  | "approved"
  | "rejected"
  | "ordered"
  | "completed"
  | "cancelled";

export type ProposalPriority = "high" | "medium" | "low";
export type PurchaseOrderStatus =
  | "issued"
  | "acknowledged"
  | "partially_received"
  | "delivered"
  | "closed"
  | "cancelled";
export type PaymentStatus = "pending" | "partial" | "paid";
export type ComplianceValue = "compliant" | "non_compliant" | "conditional";
export type AssetStatus = "in_service" | "in_store" | "under_maintenance" | "retired";
export type AssetCategory =
  | "equipment"
  | "furniture"
  | "computer"
  | "laboratory"
  | "library"
  | "vehicle"
  | "software"
  | "other";

/** One linked document resolved on a section row (documents integration). */
export interface SupportingDocumentRef {
  id: string;
  title: string;
}

/** PART 4 quotation row (vendor resolved server-side). */
export interface QuotationRow {
  vendor_id?: string;
  vendor_name?: string;
  quotation_date?: string;
  amount?: string;
  validity_date?: string;
  document_ids?: string[];
  supporting_documents?: SupportingDocumentRef[];
  remarks?: string;
}

/** PART 5 comparative-statement row. */
export interface ComparativeRow {
  vendor_id?: string;
  vendor_name?: string;
  amount?: string;
  technical_compliance?: ComplianceValue;
  financial_compliance?: ComplianceValue;
  recommended?: boolean;
  remarks?: string;
}

/** PART 6 purchase-order row. */
export interface PurchaseOrderRow {
  po_number?: string;
  po_date?: string;
  vendor_id?: string;
  vendor_name?: string;
  amount?: string;
  status?: PurchaseOrderStatus;
  delivery_date?: string;
  document_ids?: string[];
  supporting_documents?: SupportingDocumentRef[];
  remarks?: string;
}

/** PART 7 bill/invoice row. */
export interface BillRow {
  bill_number?: string;
  invoice_number?: string;
  vendor_id?: string;
  vendor_name?: string;
  bill_date?: string;
  amount?: string;
  gst_amount?: string;
  payment_status?: PaymentStatus;
  paid_date?: string;
  po_number?: string;
  document_ids?: string[];
  supporting_documents?: SupportingDocumentRef[];
  remarks?: string;
}

/** PART 8 asset row (also surfaced via the register lens). */
export interface AssetRow {
  asset_id?: string;
  category?: AssetCategory;
  item_name?: string;
  serial_number?: string;
  location?: string;
  assigned_to?: string;
  warranty_expiry?: string;
  purchase_date?: string;
  cost?: string;
  status?: AssetStatus;
  po_number?: string;
  vendor_name?: string;
  remarks?: string;
}

export interface BankDetails {
  bank_name?: string;
  account_number?: string;
  ifsc?: string;
  branch?: string;
}

export interface VendorStats {
  proposals: number;
  purchase_orders: number;
  pending_bills: number;
  spent: number;
}

/** A denormalised linked Object in a proposal payload (related_to edges). */
export interface ProposalLinkedObject {
  id: string;
  title: string;
  object_type: string;
  kind: string;
}

export type ProposalLinkGroup = "projects" | "grants" | "committees";

/** The resolved PART 2 approval meeting pointer. */
export interface ApprovalMeetingRef {
  id: string;
  title: string;
  meeting_number?: string | null;
  meeting_date?: string | null;
  mode?: string | null;
  venue?: string | null;
}

export interface ProposalStats {
  quotations: number;
  purchase_orders: number;
  bills: number;
  pending_bills: number;
  committed: number;
  spent: number;
  assets: number;
}

export interface ProposalResponse {
  id: string;
  title: string;
  status: ResearchObjectStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  proposal_number?: string | null;
  department?: string | null;
  requested_by?: string | null;
  requested_name?: string | null;
  proposal_date?: string | null;
  purpose?: string | null;
  budget_head?: string | null;
  estimated_cost?: number | null;
  proposal_status: ProposalStatus;
  priority?: ProposalPriority | null;
  notes?: string | null;
  tags: string[];
  approval_meeting_id?: string | null;
  approval_meeting?: ApprovalMeetingRef | null;
  minutes?: string | null;
  recommendations?: string | null;
  quotations: QuotationRow[];
  comparative: ComparativeRow[];
  purchase_orders: PurchaseOrderRow[];
  bills: BillRow[];
  assets: AssetRow[];
  links: Record<ProposalLinkGroup, ProposalLinkedObject[]>;
  stats: ProposalStats;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListProposalsResponse {
  items: ProposalResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface VendorResponse {
  id: string;
  name: string;
  status: ResearchObjectStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  gst_number?: string | null;
  pan?: string | null;
  contact_person?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  bank_details: BankDetails;
  notes?: string | null;
  tags: string[];
  stats: VendorStats;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListVendorsResponse {
  items: VendorResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

/** PART 11 dashboard cards (computed server-side). */
export interface FinanceDashboard {
  active_procurements: number;
  pending_approvals: number;
  total_vendors: number;
  total_purchase_orders: number;
  budget_utilized: number;
  budget_remaining?: number | null;
  pending_bills: number;
}

/** PART 9 per-project budget tracking line (computed read). */
export interface BudgetLine {
  project_id: string;
  title: string;
  approved?: number | null;
  released: number;
  utilized: number;
  remaining?: number | null;
  proposals: number;
  spent: number;
}

export interface ListBudgetsResponse {
  items: BudgetLine[];
}

export interface AssetRegisterRow {
  proposal_id: string;
  proposal_number?: string | null;
  proposal_title: string;
  row: AssetRow;
}

export interface ListAssetRegisterResponse {
  items: AssetRegisterRow[];
  total_count: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// Events & Academic Activities module (personal academic activity registry)
// ---------------------------------------------------------------------------

export type EventType =
  | "conference"
  | "workshop"
  | "seminar"
  | "webinar"
  | "fdp"
  | "sttp"
  | "expert_lecture"
  | "guest_lecture"
  | "invited_talk"
  | "mathematics_day"
  | "science_day"
  | "orientation_programme"
  | "training_programme"
  | "industry_visit"
  | "club_activity"
  | "research_colloquium"
  | "outreach_activity"
  | "competition"
  | "custom";

export type EventStatus =
  | "planned"
  | "ongoing"
  | "postponed"
  | "completed"
  | "cancelled";
export type EventMode = "online" | "offline" | "hybrid";
export type EventPriority = "high" | "medium" | "low";

/** PART 2 "My Participation" role vocabulary. */
export type ParticipationRole =
  | "organizer"
  | "coordinator"
  | "convener"
  | "speaker"
  | "session_chair"
  | "participant"
  | "volunteer"
  | "resource_person"
  | "chief_guest"
  | "judge"
  | "attendee";

/** PART 8 event ↔ publication link relation vocabulary. */
export type PresentationRelation =
  | "presented_paper"
  | "published_proceedings"
  | "best_paper_award"
  | "poster_presentation";

/** One linked document resolved on a section row (documents integration). */
export interface EventDocumentRef {
  id: string;
  title: string;
}

/** PART 2 participation row (certificate resolved server-side). */
export interface ParticipationRow {
  role?: ParticipationRole;
  contribution?: string;
  certificate_document_id?: string;
  certificate?: EventDocumentRef;
  remarks?: string;
}

/** PART 3 speaker directory row (`row_id` is server-minted when absent). */
export interface SpeakerRow {
  row_id?: string;
  name?: string;
  affiliation?: string;
  designation?: string;
  email?: string;
  phone?: string;
  biography?: string;
  photo_document_id?: string;
  photo?: EventDocumentRef;
  document_ids?: string[];
  supporting_documents?: EventDocumentRef[];
}

/** PART 4 schedule session row (speaker resolved from the speakers list). */
export interface ScheduleRow {
  title?: string;
  session_date?: string;
  start_time?: string;
  end_time?: string;
  speaker_id?: string;
  speaker_name?: string;
  venue?: string;
  chairperson?: string;
  remarks?: string;
}

/** PART 5 registration counters. */
export interface EventRegistration {
  expected_participants: number;
  registered: number;
  present: number;
  certificates_issued: number;
}

/** PART 8 publication link row (title resolved server-side). */
export interface PresentationRow {
  publication_id?: string;
  publication_title?: string;
  relation?: PresentationRelation;
  remarks?: string;
}

/** A denormalised linked Object in an event payload (related_to edges). */
export interface EventLinkedObject {
  id: string;
  title: string;
  object_type: string;
  kind: string;
}

export type EventLinkGroup =
  | "faculty"
  | "students"
  | "projects"
  | "grants"
  | "committees"
  | "publications";
/** Groups accepted on the wire (`presentations` rows drive publications). */
export type EventInputLinkGroup = Exclude<EventLinkGroup, "publications">;

export interface EventStats {
  participation: number;
  speakers: number;
  sessions: number;
  presentations: number;
  certificates: number;
}

export interface EventResponse {
  id: string;
  title: string;
  status: ResearchObjectStatus;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at?: string | null;
  event_code?: string | null;
  event_type?: EventType | null;
  organizer?: string | null;
  co_organizer?: string | null;
  venue?: string | null;
  mode?: EventMode | null;
  start_date?: string | null;
  end_date?: string | null;
  department?: string | null;
  school?: string | null;
  description?: string | null;
  objectives?: string | null;
  outcome?: string | null;
  event_status: EventStatus;
  priority?: EventPriority | null;
  notes?: string | null;
  tags: string[];
  participation: ParticipationRow[];
  speakers: SpeakerRow[];
  schedule: ScheduleRow[];
  registration: EventRegistration;
  presentations: PresentationRow[];
  links: Record<EventLinkGroup, EventLinkedObject[]>;
  stats: EventStats;
  metadata?: Record<string, string>;
  events?: string[];
}

export interface ListEventsResponse {
  items: EventResponse[];
  total_count: number;
  page: number;
  page_size: number;
}

/** PART 9 dashboard cards (computed server-side). */
export interface EventsDashboard {
  upcoming_events: number;
  completed_events: number;
  events_organized: number;
  events_attended: number;
  certificates: number;
  presentations: number;
  invited_talks: number;
}

// ---------------------------------------------------------------------------
// Reports & Analytics (read-only; everything computed server-side)
// ---------------------------------------------------------------------------

/** PART 1 dashboard cards (computed read over every module). */
export interface ReportsDashboard {
  total_publications: number;
  total_projects: number;
  total_grants: number;
  total_students: number;
  total_classes: number;
  total_faculty: number;
  total_committees: number;
  total_events: number;
  budget_approved: number;
  budget_utilized: number;
  budget_remaining: number;
}

/** PART 12 filters (all optional; each report kind honours a documented
 * subset — see `REPORT_KINDS` in `lib/reports/constants`). */
export interface ReportFilters {
  year?: string;          // e.g. "2026" (string on the wire; server narrows)
  date_from?: string;     // ISO YYYY-MM-DD, inclusive
  date_to?: string;       // ISO YYYY-MM-DD, inclusive
  faculty_id?: string;
  student_id?: string;
  project_id?: string;
  grant_id?: string;
  department?: string;
  event_id?: string;
  committee_id?: string;
}

export interface ReportKpi {
  label: string;
  value: string;
}

export interface ReportTable {
  key: string;
  title: string;
  columns: string[];
  rows: string[][];
  /** Optional per-cell module hrefs; `null` = plain text cell (frontend only). */
  hrefs?: (string | null)[][] | null;
}

export interface ReportChartSeries {
  name: string;
  data: number[];
}

export interface ReportChart {
  key: string;
  title: string;
  kind: "bar" | "line";
  labels: string[];
  series: ReportChartSeries[];
}

/** The computed report — the workspace payload and the export source. */
export interface ReportView {
  kind: string;
  title: string;
  generated_at: string;
  applied_filters: Record<string, string>;
  kpis: ReportKpi[];
  tables: ReportTable[];
  charts: ReportChart[];
}

/** The module catalogue: report kinds + which PART 12 filters each honours. */
export interface ReportsCatalogue {
  kinds: { key: string; title: string; filters: string[] }[];
}

// ---------------------------------------------------------------------------
// Productivity Hub (Calendar + Notifications) — module 11
// Mirrors the backend dtos/productivity.py outputs one-to-one.
// ---------------------------------------------------------------------------

export type ProductivityPriority = "high" | "medium" | "low";
export type TaskCategory =
  | "research"
  | "teaching"
  | "committees"
  | "finance"
  | "events"
  | "publications"
  | "personal"
  | "admin"
  | "other";
export type NotificationCategory =
  | "task"
  | "deadline"
  | "meeting"
  | "finance"
  | "milestone"
  | "system";

export interface ProductivityTask {
  id: string;
  title: string;
  status: string;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at: string | null;
  description: string | null;
  priority: string | null;
  category: string | null;
  start_date: string | null;
  due_date: string | null;
  completed: boolean;
  completion_date: string | null;
  pinned: boolean;
  reminder: string | null;
  tags: string[];
  remarks: string | null;
  overdue: boolean;
  metadata: Record<string, string>;
}

export interface TaskListResult {
  items: ProductivityTask[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface CalendarEntry {
  id: string;
  title: string;
  status: string;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at: string | null;
  description: string | null;
  start_date: string;
  end_date: string | null;
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  category: string | null;
  tags: string[];
  metadata: Record<string, string>;
}

export interface CalendarEntryListResult {
  items: CalendarEntry[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface ProductivityNotification {
  id: string;
  title: string;
  status: string;
  version: number;
  uploaded_by: string;
  created_at: string;
  updated_at: string | null;
  body: string | null;
  category: string | null;
  priority: string | null;
  link: string | null;
  source_module: string | null;
  source_ref: string | null;
  generated_by: string;
  is_read: boolean;
  read_at: string | null;
  pinned: boolean;
  archived: boolean;
  snoozed_until: string | null;
  snoozed: boolean;
  metadata: Record<string, string>;
}

export interface NotificationListResult {
  items: ProductivityNotification[];
  total_count: number;
  page: number;
  page_size: number;
  unread_count: number;
}

export interface RefreshNotificationsResult {
  created: number;
  skipped_existing: number;
  considered: number;
}

export type CalendarSource =
  | "events"
  | "committee_meetings"
  | "research_projects"
  | "grant_milestones"
  | "teaching"
  | "assignments"
  | "attendance_sessions"
  | "finance_due"
  | "reports_due"
  | "personal";

export interface CalendarItem {
  id: string;
  source: string;
  source_id: string;
  title: string;
  date: string;
  date_end: string | null;
  start_time: string | null;
  end_time: string | null;
  all_day: boolean;
  kind: string;
  subtitle: string | null;
  status: string | null;
  priority: string | null;
  href: string;
}

export interface CalendarFeed {
  items: CalendarItem[];
  date_from: string;
  date_to: string;
  sources: string[];
}

export interface ReminderItem {
  id: string;
  source: string;
  title: string;
  date: string;
  subtitle: string | null;
  priority: string | null;
  href: string;
}

export interface RemindersFeed {
  overdue: ReminderItem[];
  due_today: ReminderItem[];
  upcoming_today: ReminderItem[];
  tomorrow: ReminderItem[];
  this_week: ReminderItem[];
  generated_at: string;
}

export interface ProductivityDashboard {
  todays_tasks: number;
  upcoming_deadlines: number;
  upcoming_meetings: number;
  unread_notifications: number;
  overdue_items: number;
  completed_today: number;
}

export interface ProductivitySearchHit {
  id: string;
  source: string;
  kind: string;
  title: string;
  date: string | null;
  priority: string | null;
  category: string | null;
  snippet: string | null;
  href: string;
}

export interface ProductivitySearchResult {
  items: ProductivitySearchHit[];
  total_count: number;
}

export type CalendarView = "day" | "week" | "month" | "agenda";
export type NotificationState = "all" | "unread" | "read" | "pinned" | "snoozed" | "archived";

// ---------------------------------------------------------------------------
// Settings & Preferences (module 12) — mirrors application/dtos/settings.py
// ---------------------------------------------------------------------------

export type SettingsSectionCode =
  | "profile"
  | "appearance"
  | "academic"
  | "notifications"
  | "dashboard"
  | "search"
  | "privacy"
  | "ai";

export interface ProfileSection {
  name: string;
  email: string;
  designation: string;
  department: string;
  institution: string;
  biography: string;
}

export interface AppearanceSection {
  theme: string; // "light" | "dark" | "system"
  custom_theme: string; // stored for future custom themes — inactive
}

export interface AcademicSection {
  default_session: string;
  default_department: string;
  default_programme: string;
  default_semester: string;
  default_timezone: string;
  date_format: string;
}

export interface NotificationPrefsSection {
  enabled: boolean;
  reminder_default: string;
  priority_default: string;
  calendar_default_view: string;
  calendar_default_sources: string[];
}

export interface DashboardPrefsSection {
  default_landing_page: string;
  favorite_modules: string[];
  widget_visibility: Record<string, boolean>;
  default_view: string;
}

export interface SearchPrefsSection {
  default_scope: string;
  recent_searches_limit: number;
  saved_filters: Record<string, unknown>;
}

export interface PrivacySection {
  remember_last_module: boolean;
  reduce_motion: boolean;
  session_filter_memory: boolean;
  session_page_size: number;
}

export interface AiPrefsSection {
  preferred_writing_style: string;
  preferred_report_format: string;
  preferred_dashboard_layout: string;
}

export interface SettingsSections {
  profile: ProfileSection;
  appearance: AppearanceSection;
  academic: AcademicSection;
  notifications: NotificationPrefsSection;
  dashboard: DashboardPrefsSection;
  search: SearchPrefsSection;
  privacy: PrivacySection;
  ai: AiPrefsSection;
}

export interface SettingsDocument {
  sections: SettingsSections;
  has_photo: boolean;
  photo_name: string | null;
  photo_url: string | null;
  updated_at: string | null;
}

/** Response of `PUT /settings/{section}` (verbatim-merge result). */
export interface SettingsSectionResult<K extends SettingsSectionCode = SettingsSectionCode> {
  section: K;
  values: SettingsSections[K];
}

/** Response of `GET /settings/export` (settings only — not a DB backup). */
export interface SettingsExport {
  version: number;
  app: string;
  exported_at: string;
  sections: SettingsSections;
}

/** Response of `POST /settings/profile/photo` (metadata only, never bytes). */
export interface ProfilePhotoInfo {
  file_name: string;
  mime_type: string;
  size_bytes: number;
}

/* --------------------------------------------------------------------------
 * Module 13 — Academic Intelligence Assistant
 *
 * Mirrors `application/dtos/assistant.py` field-for-field. Conversations are
 * universal objects; answers are the deterministic contract the rule-based
 * provider produces — a future sanctioned LLM adapter must honour the same
 * shape (application/ports/assistant_provider.py).
 * ----------------------------------------------------------------------- */

/** Suggested next step under an answer (module buttons vs plain links). */
export interface AssistantAction {
  label: string;
  href: string;
  kind: "link" | "module";
}

/** Linked context card (PART 4): Publication → Project → Grant → Faculty … */
export interface AssistantCard {
  object_id: string;
  object_type: string;
  title: string;
  subtitle: string | null;
  href: string;
  badge: string | null;
  stats: Record<string, string>;
}

/** One raw list row inside an answer (used for flat lists like decisions). */
export interface AssistantAnswerItem {
  title: string;
  subtitle?: string | null;
  href?: string | null;
}

/** The deterministic answer contract (PARTS 3..5 surface). */
export interface AssistantAnswer {
  intent: string;
  intent_label: string;
  question: string;
  summary: string;
  metrics: Record<string, string>;
  items: AssistantAnswerItem[];
  cards: AssistantCard[];
  actions: AssistantAction[];
  sources: string[];
}

export interface AssistantMessage {
  seq: number;
  role: "user" | "assistant" | string;
  content: string;
  created_at: string;
  answer: AssistantAnswer | null;
}

export interface AssistantConversation {
  id: string;
  title: string;
  pinned: boolean;
  message_count: number;
  last_message_at: string | null;
  created_at: string | null;
  version: number;
}

export interface ConversationDetail {
  conversation: AssistantConversation;
  messages: AssistantMessage[];
}

export interface ConversationListResult {
  items: AssistantConversation[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface SuggestedPrompt {
  group: string;
  question: string;
  intent: string;
}

/** `GET /assistant/home` — AI Home payload (PART 1). */
export interface AssistantHome {
  suggested: SuggestedPrompt[];
  recent: AssistantConversation[];
  pinned: AssistantConversation[];
  conversation_count: number;
}

/** `POST /assistant/ask` — the whole exchange, persisted. */
export interface AskResult {
  conversation: AssistantConversation;
  user_message: AssistantMessage;
  assistant_message: AssistantMessage;
  answer: AssistantAnswer;
}

/** `GET /assistant/suggested` — prompts + the full intent taxonomy. */
export interface SuggestedCatalogue {
  suggested: SuggestedPrompt[];
  intents: { group: string; codes: { code: string; label: string }[] }[];
}
// --------------------------------------------------------------------------
// Intake Foundations (v2) — mirrors backend dtos/intake.py field-for-field
// --------------------------------------------------------------------------

export type IntakeSourceKind = "folder" | "files";
export type IntakeSessionStatus =
  | "queued"
  | "running"
  | "paused"
  | "cancelled"
  | "completed"
  | "failed";
export type IntakeItemStatus =
  | "pending"
  | "staged"
  /** M2.3: an extraction attempt is actively running on this item. */
  | "extracting"
  /** M2.3: attempt 2..N running after a failure (retry budget: 3). */
  | "retrying"
  | "awaiting_review"
  | "error"
  /** M9: rejected by a human reviewer — terminal, never committed. */
  | "rejected"
  /** M9: committed — promoted to a Document (see document_id). */
  | "committed";
export type IntakeStageName =
  | "enumerate"
  | "stage"
  | "hash"
  | "extract"
  | "classify"
  | "match"
  | "propose"
  | "review"
  | "commit";

export interface IntakeSource {
  kind: IntakeSourceKind;
  path?: string;
  paths?: string[];
  display: string;
}

export interface IntakeSessionProgress {
  total: number;
  processed: number;
  percent: number;
  pending: number;
  staged: number;
  hashed: number;
  awaiting_review: number;
  errors: number;
  /** M2.3 — queue counters (live, recomputed from items every read). */
  extracting: number;
  retrying: number;
  retryable_items: number;
  remaining_items: number;
  extracted_items: number;
  unsupported_items: number;
  needs_ocr_items: number;
  /** M2.3 — live foreground: current filename/stage, measured speed, ETA. */
  current_item: string | null;
  current_stage: string;
  avg_seconds_per_item: number | null;
  items_per_minute: number | null;
  eta_seconds: number | null;
}

export interface IntakeStatistics {
  total_items: number;
  processed_items: number;
  percent: number;
  pending: number;
  staged: number;
  hashed: number;
  staged_items: number;
  awaiting_review: number;
  errors: number;
  /** M2: items whose extraction engine produced a text record. */
  extracted_items: number;
  /** M2: items recorded as UNSUPPORTED (format outside the engine table). */
  unsupported_items: number;
  /** M2.3: items in an active attempt (first run / later attempts). */
  extracting: number;
  retrying: number;
  /** M2.3: pdf-derived items whose text layer is empty (need OCR later). */
  needs_ocr_items: number;
  /** M2.3: failed items still owning retry attempts (< 3 attempts). */
  retryable_items: number;
  total_bytes: number;
  by_extension: Record<string, number>;
  by_mime: Record<string, number>;
  skipped_junk: number;
  skipped_junk_samples: string[];
}

export interface IntakeError {
  stage: string;
  message: string;
}

export interface IntakeSession {
  id: string;
  title: string;
  source: IntakeSource;
  status: IntakeSessionStatus;
  current_stage: string;
  progress: IntakeSessionProgress;
  statistics: IntakeStatistics;
  summary: string | null;
  error: IntakeError | null;
  created_at: string | null;
  updated_at: string | null;
  version: number;
}

export interface IntakeProgressCounts {
  pending: number;
  staged: number;
  hashed: number;
  awaiting_review: number;
  errors: number;
  /** M2.3 — queue counters (all live, all additive). */
  extracting: number;
  retrying: number;
  retryable: number;
  extracted: number;
  unsupported: number;
  needs_ocr: number;
}

export interface IntakeProgressUpdate {
  session_id: string;
  status: IntakeSessionStatus;
  current_stage: string;
  total_items: number;
  processed_items: number;
  percent: number;
  counts: IntakeProgressCounts;
  updated_at: string | null;
  /** M2.3 — live foreground: current filename, remaining work, speed, ETA. */
  current_item: string | null;
  remaining_items: number;
  avg_seconds_per_item: number | null;
  items_per_minute: number | null;
  eta_seconds: number | null;
}

export interface IntakeStageRecord {
  stage: string;
  entered_at: string;
  exited_at: string;
  result: Record<string, unknown>;
}

/** M2 extraction outcome for one staged file (backend `ExtractionStatus`). */
export type IntakeExtractionStatus = "extracted" | "unsupported";

/**
 * M2 extraction descriptor — mirrors the backend `ExtractionDescriptor.to_dict()`
 * contract field-for-field. `null` on fields the file honestly does not carry;
 * `null` on the whole `extraction` field until the extract stage has run.
 * Nothing here is inferred client-side.
 */
export interface IntakeExtractionDescriptor {
  status: IntakeExtractionStatus;
  engine: string | null;
  format: "pdf" | "docx" | "text" | "markdown" | "csv" | "json" | null;
  sha256: string | null;
  page_count: number | null;
  word_count: number | null;
  character_count: number | null;
  document_title: string | null;
  author: string | null;
  created_at: string | null;
  modified_at: string | null;
  embedded_metadata: Record<string, string>;
  text_key: string | null;
  text_bytes: number | null;
  preview_text: string | null;
  warnings: string[];
  extracted_at: string | null;
}

export interface IntakeItem {
  id: string;
  session_id: string;
  title: string;
  original_path: string;
  relative_path: string;
  extension: string;
  size_bytes: number;
  mime_type: string | null;
  sha256: string | null;
  staged_key: string | null;
  status: IntakeItemStatus;
  stage: string;
  attempts: number;
  stage_history: IntakeStageRecord[];
  error: IntakeError | null;
  /** M2 extraction descriptor; `null` until the extract stage has run. */
  extraction: IntakeExtractionDescriptor | null;
  /** M9: the human review decision (approved | rejected | null). */
  review_decision: string | null;
  /** M9: the committed Document id once the item is committed. */
  document_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ListIntakeSessionsResponse {
  items: IntakeSession[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface ListIntakeItemsResponse {
  items: IntakeItem[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface CreateIntakeSessionPayload {
  source_kind: IntakeSourceKind;
  path?: string;
  paths?: string[];
  actor?: string;
  title?: string;
}

// ---------------------------------------------------------------------------
// Authentication (final release)
// ---------------------------------------------------------------------------
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthUser {
  id: string;
  username: string;
  created_at: string;
  roles: string[];
}

export interface ForgotPasswordResult {
  reset_token: string;
  expires_in_seconds: number;
}

// ---------------------------------------------------------------------------
// Document viewer & annotations (Sprint M10)
// ---------------------------------------------------------------------------
export type AnnotationType = "highlight" | "note" | "bookmark";

export interface AnnotationRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface HighlightPayload {
  rects: AnnotationRect[];
  text?: string;
}

export interface NotePayload {
  text: string;
  x?: number;
  y?: number;
}

export interface BookmarkPayload {
  label?: string;
}

export type AnnotationPayload = HighlightPayload | NotePayload | BookmarkPayload;

export interface DocumentAnnotation {
  annotation_id: string;
  document_id: string;
  annotation_type: AnnotationType;
  page: number;
  payload: AnnotationPayload;
  created_by: string;
  created_at: string;
  updated_at: string | null;
}

export interface ExtractedTextResponse {
  text: string;
  session_id: string;
  item_id: string;
}

// ---------------------------------------------------------------------------
// AI Core (Sprint M11.1) — mirrors `backend/app/api/routes/ai.py`
// ---------------------------------------------------------------------------

/** Aggregate AI health (`GET /ai/health`). */
export interface AiHealth {
  status: "ok" | "not_configured" | "disabled" | "error";
  ai_enabled: boolean;
  default_provider: string;
  default_model: string;
  default_provider_valid: boolean;
  providers_total: number;
  providers_configured: number;
  feature_flags: Record<string, boolean>;
  checked_at: string;
}

/** One model in the aggregated catalogue (`GET /ai/models`). */
export interface AiModelInfo {
  provider_id: string;
  model_id: string;
  display_name: string;
  context_window: number | null;
  capabilities: string[];
  configured: boolean;
}

/** `GET /ai/models` response. */
export interface AiModelsResponse {
  default_provider: string;
  default_model: string;
  models: AiModelInfo[];
}

/** One provider row (`GET /ai/providers`). */
export interface AiProviderInfo {
  provider_id: string;
  display_name: string;
  kind: string;
  status: "configured" | "not_configured" | "error";
  configured: boolean;
  executable: boolean;
  operational: boolean | null;
  models: AiModelInfo[];
  detail: string;
}

/** `GET /ai/providers` response. */
export interface ListAiProvidersResponse {
  items: AiProviderInfo[];
}
