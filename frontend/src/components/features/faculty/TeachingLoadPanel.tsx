import Link from "next/link";
import type { FacultyResponse } from "@/types";

function formatHours(hours: number): string {
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)}h`;
}

/**
 * PART 5 teaching load: every class this faculty teaches (course code,
 * programme, semester, credits, weekly hours derived from the class schedule)
 * plus the total weekly contact hours.
 */
export function TeachingLoadPanel({ faculty }: { faculty: FacultyResponse }) {
  const classes = faculty.teaching?.classes ?? [];
  const total = faculty.teaching?.total_weekly_hours ?? 0;
  return (
    <section
      aria-label="Teaching load"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Teaching Load</h2>
        {classes.length > 0 ? (
          <p className="text-xs font-medium text-[var(--text-tertiary)]">
            Total: <span className="text-[var(--text-primary)]">{formatHours(total)}/week</span>
          </p>
        ) : null}
      </div>
      {classes.length === 0 ? (
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">
          No classes this term — assign this faculty as a teacher from the Teaching module.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th scope="col" className="py-2 pr-3 font-medium">Class</th>
                <th scope="col" className="py-2 pr-3 font-medium">Course</th>
                <th scope="col" className="py-2 pr-3 font-medium">Programme</th>
                <th scope="col" className="py-2 pr-3 font-medium">Sem</th>
                <th scope="col" className="py-2 pr-3 font-medium">Credits</th>
                <th scope="col" className="py-2 font-medium text-right">Weekly hrs</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((cls) => (
                <tr
                  key={cls.id}
                  className="border-b border-[var(--border-subtle)] align-top last:border-0"
                >
                  <td className="py-2 pr-3 text-sm">
                    <Link
                      href={`/teaching/classes/${encodeURIComponent(cls.id)}`}
                      className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                    >
                      {cls.title}
                    </Link>
                  </td>
                  <td className="py-2 pr-3 text-sm text-[var(--text-secondary)]">
                    {cls.course_code ?? "—"}
                  </td>
                  <td className="py-2 pr-3 text-sm text-[var(--text-secondary)]">
                    {cls.programme ?? "—"}
                  </td>
                  <td className="py-2 pr-3 text-sm text-[var(--text-secondary)]">
                    {cls.semester ?? "—"}
                  </td>
                  <td className="py-2 pr-3 text-sm text-[var(--text-secondary)]">
                    {cls.credits ?? "—"}
                  </td>
                  <td className="py-2 text-right text-sm font-medium text-[var(--text-primary)]">
                    {formatHours(cls.weekly_hours)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
