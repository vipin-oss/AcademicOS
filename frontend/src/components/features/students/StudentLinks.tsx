import Link from "next/link";
import { Link2 } from "lucide-react";
import { STUDENT_LINK_GROUPS } from "@/lib/students/constants";
import type { StudentResponse } from "@/types";

/**
 * The student-side "Linked X" panes (PART A — relationships): Supervisors /
 * Co-supervisors / Projects / Grants / Committees / Events. Each entry links
 * into the Objects explorer (the Object is the single source of truth — the
 * student only carries typed edges to it). Mirrors `PublicationLinks`.
 */
export function StudentLinks({ student }: { student: StudentResponse }) {
  const anyLinks = STUDENT_LINK_GROUPS.some(
    ({ value }) => (student.links?.[value] ?? []).length > 0,
  );

  if (!anyLinks) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">
        Not linked to any supervisors, projects, grants, committees, or events
        yet. Link them via Edit to power object-centric lenses (“scholars of
        Professor X”, “students on Grant Y”).
      </p>
    );
  }

  return (
    <dl className="space-y-3 text-sm">
      {STUDENT_LINK_GROUPS.map(({ value, label }) => {
        const entries = student.links?.[value] ?? [];
        if (entries.length === 0) return null;
        return (
          <div
            key={value}
            className="flex flex-col gap-1 border-b border-[var(--border-subtle)] py-2 last:border-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4"
          >
            <dt className="shrink-0 text-[var(--text-tertiary)]">{label}</dt>
            <dd className="flex flex-wrap justify-start gap-1.5 sm:justify-end">
              {entries.map((entry) => (
                <Link
                  key={entry.id}
                  href={`/objects/${encodeURIComponent(entry.id)}`}
                  title={`${entry.title} (${entry.kind})`}
                  className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-hover)] px-2.5 py-0.5 text-xs text-[var(--accent)] transition-colors hover:bg-[var(--accent-subtle)]"
                >
                  <Link2 className="h-3 w-3" aria-hidden="true" />
                  {entry.title}
                </Link>
              ))}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
