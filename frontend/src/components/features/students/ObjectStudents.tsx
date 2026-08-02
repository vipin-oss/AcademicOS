"use client";

import Link from "next/link";
import { Spinner } from "@/components/features/objects/Spinner";
import { useObjectStudents } from "@/hooks/useObjectStudents";
import { StudentTypeBadge } from "./StudentBadge";
import { programmeLine } from "@/lib/students/constants";

/**
 * The object lens for students (\"students linked to this Object\") — the
 * student counterpart of `ObjectDocuments` / `ObjectPublications`. Rendered
 * on Object detail pages (e.g. a Faculty member's supervisees).
 */
export function ObjectStudents({ objectId }: { objectId: string }) {
  const { students, loading, error } = useObjectStudents(objectId);

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
        <Spinner className="h-4 w-4" /> Loading students…
      </p>
    );
  }
  if (error) {
    return <p className="text-sm text-[var(--danger)]">{error}</p>;
  }
  if (students.length === 0) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">
        No students are linked to this object yet.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-[var(--border-subtle)]">
      {students.map((student) => (
        <li key={student.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
          <div className="min-w-0">
            <Link
              href={`/students/${encodeURIComponent(student.id)}`}
              className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
            >
              {student.name}
            </Link>
            <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
              {[student.roll_number, programmeLine(student)].filter(Boolean).join(" · ")}
            </p>
          </div>
          <StudentTypeBadge type={student.student_type} />
        </li>
      ))}
    </ul>
  );
}
