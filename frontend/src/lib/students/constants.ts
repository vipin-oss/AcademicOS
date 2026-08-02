import type { StudentLinkGroup, StudentTypeValue } from "@/types";

/** Every student type the UI knows how to label (PART A taxonomy). */
export const STUDENT_TYPES: { value: StudentTypeValue; label: string }[] = [
  { value: "ug", label: "UG" },
  { value: "pg", label: "PG" },
  { value: "phd", label: "PhD" },
  { value: "alumni", label: "Alumni" },
];

export const DEFAULT_STUDENT_PAGE_SIZE = 20;

/** The 6 student link panes, with human labels (PART A relationships). */
export const STUDENT_LINK_GROUPS: { value: StudentLinkGroup; label: string }[] = [
  { value: "supervisors", label: "Supervisors" },
  { value: "co_supervisors", label: "Co-supervisors" },
  { value: "projects", label: "Projects" },
  { value: "grants", label: "Grants" },
  { value: "committees", label: "Committees" },
  { value: "events", label: "Events" },
];

export function studentTypeLabel(value: string | null | undefined): string {
  const found = STUDENT_TYPES.find((type) => type.value === value);
  return found ? found.label : (value ?? "").toUpperCase() || "—";
}

// ---------------------------------------------------------------------------
// CSV import helpers (PART F — the same headers the backend auto-maps)
// ---------------------------------------------------------------------------

export const STUDENT_IMPORT_HEADERS =
  "Roll No, Name, Email, Phone, Student Type, Programme, Department, " +
  "Semester, Section, Batch, Admission Date, Expected Graduation";

export const STUDENT_IMPORT_SAMPLE =
  "Roll No,Name,Email,Section,Programme,Semester\n" +
  "101,Asha Verma,asha@univ.edu,A,BSc Mathematics,1\n" +
  "102,Ravi Kumar,ravi@univ.edu,A,BSc Mathematics,1\n";

/** Columns the table always needs for a quick registry read. */
function identity(parts: (string | null | undefined)[]): string {
  return parts.filter((part) => part && part.trim()).join(" · ");
}

/** "BSc Mathematics · Sem 1 · Sec A" — programme/semester/section one-liner. */
export function programmeLine(student: {
  programme?: string | null;
  semester?: number | null;
  section?: string | null;
}): string {
  return identity([
    student.programme ?? null,
    student.semester != null ? `Sem ${student.semester}` : null,
    student.section ? `Sec ${student.section}` : null,
  ]);
}
