import Link from "next/link";
import { Badge } from "@/components/features/documents/DocumentBadge";
import { roleLabel, StudentTypeBadge } from "./FacultyBadges";
import type { FacultySupervisionEntry } from "@/types";

function StudentList({ entries }: { entries: FacultySupervisionEntry[] }) {
  return (
    <ul className="space-y-1.5">
      {entries.map((student) => (
        <li
          key={`${student.id}-${student.kind}`}
          className="flex flex-wrap items-center gap-2 text-sm"
        >
          <Link
            href={`/students/${encodeURIComponent(student.id)}`}
            className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
          >
            {student.title}
          </Link>
          <Badge className="bg-[var(--bg-hover)] text-[var(--text-secondary)]">
            {roleLabel(student.kind)}
          </Badge>
          {student.student_type ? <StudentTypeBadge type={student.student_type} /> : null}
        </li>
      ))}
    </ul>
  );
}

/**
 * PART 4 student supervision: current students (UG/PG/PhD — typed
 * supervisor/co-supervisor edges) and completed students (alumni lens).
 */
export function SupervisionPanel({
  current,
  completed,
}: {
  current: FacultySupervisionEntry[];
  completed: FacultySupervisionEntry[];
}) {
  const empty = current.length === 0 && completed.length === 0;
  return (
    <section
      aria-label="Student supervision"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Student Supervision</h2>
      {empty ? (
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">
          No students linked yet — assign this faculty as supervisor or co-supervisor from the
          Students module.
        </p>
      ) : (
        <dl className="mt-2 space-y-3">
          {current.length > 0 ? (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                Current Students ({current.length})
              </dt>
              <dd className="mt-1">
                <StudentList entries={current} />
              </dd>
            </div>
          ) : null}
          {completed.length > 0 ? (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                Completed Students ({completed.length})
              </dt>
              <dd className="mt-1">
                <StudentList entries={completed} />
              </dd>
            </div>
          ) : null}
        </dl>
      )}
    </section>
  );
}
