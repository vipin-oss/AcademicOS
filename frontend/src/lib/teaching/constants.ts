import type {
  AssignmentTypeValue,
  AttendanceState,
  ClassLinkGroup,
  ClassMode,
  ClassResponse,
  SubmissionGridState,
} from "@/types";

export const DEFAULT_CLASS_PAGE_SIZE = 20;

/** PART D vocabulary, with human labels. */
export const ASSIGNMENT_TYPES: { value: AssignmentTypeValue; label: string }[] = [
  { value: "assignment", label: "Assignment" },
  { value: "quiz", label: "Quiz" },
  { value: "internal_assessment", label: "Internal Assessment" },
  { value: "mid_semester", label: "Mid Semester" },
  { value: "end_semester", label: "End Semester" },
];

export const CLASS_MODES: { value: ClassMode; label: string }[] = [
  { value: "offline", label: "Offline" },
  { value: "online", label: "Online" },
  { value: "blended", label: "Blended" },
];

export const CLASS_LINK_GROUPS: { value: ClassLinkGroup; label: string }[] = [
  { value: "teachers", label: "Teachers" },
  { value: "departments", label: "Departments" },
];

export const WEEKDAYS: { value: string; label: string }[] = [
  { value: "mon", label: "Mon" },
  { value: "tue", label: "Tue" },
  { value: "wed", label: "Wed" },
  { value: "thu", label: "Thu" },
  { value: "fri", label: "Fri" },
  { value: "sat", label: "Sat" },
  { value: "sun", label: "Sun" },
];

/** PART I vocabulary, in register order. */
export const ATTENDANCE_STATES: { value: AttendanceState; label: string }[] = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "late", label: "Late" },
  { value: "medical_leave", label: "Medical Leave" },
];

export const ATTENDANCE_THRESHOLD_DEFAULT = 75;

export function assignmentTypeLabel(value: string | null | undefined): string {
  const found = ASSIGNMENT_TYPES.find((type) => type.value === value);
  return found ? found.label : "Assignment";
}

/** "CS-101 · BSc Mathematics · Sem 1 · Sec A · 2026-27" class subtitle. */
export function classLine(cls: ClassResponse): string {
  return [
    cls.course_code,
    cls.programme,
    cls.semester != null ? `Sem ${cls.semester}` : null,
    cls.section ? `Sec ${cls.section}` : null,
    cls.session,
  ]
    .filter((part) => part && String(part).trim())
    .join(" · ");
}

/**
 * Human-readable deadline: a bare date shows as-is (register style), an ISO
 * datetime shortens to "10 Jan 2026, 11:59 pm"; `null` means "no deadline".
 */
export function formatDeadline(raw: string | null | undefined): string {
  if (!raw) return "No deadline";
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

/** Submission grid state vocabulary (UI Spec §2.5 C7). */
export const GRID_STATE_LABELS: Record<SubmissionGridState, string> = {
  submitted: "Submitted",
  late: "Late",
  pending: "Pending",
  graded: "Graded",
};

export const GRID_STATE_ORDER: SubmissionGridState[] = [
  "pending",
  "submitted",
  "late",
  "graded",
];

export const STUDENT_CSV_SAMPLE =
  "Roll No,Email\n101,\n102,ravi@univ.edu\n";

export const MARKS_CSV_SAMPLE = "Roll No,Marks,Feedback\n101,18,Well done\n102,16,\n";

export const ATTENDANCE_CSV_SAMPLE = "Roll No,Status\n101,P\n102,A\n103,ML\n";

/** Attendance "no entry" marker shown per unrecorded student/date. */
export const NO_ATTENDANCE_MARK = "—";
