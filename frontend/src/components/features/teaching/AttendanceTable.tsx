"use client";

import { CalendarDays, PencilLine } from "lucide-react";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { AttendanceFlagBadge } from "./TeachingBadges";
import { ATTENDANCE_STATES, NO_ATTENDANCE_MARK } from "@/lib/teaching/constants";
import type { AttendanceSessionResponse, AttendanceState, AttendanceSummary } from "@/types";

function sessionCounts(session: AttendanceSessionResponse): Record<AttendanceState, number> {
  const counts: Record<AttendanceState, number> = {
    present: 0,
    absent: 0,
    late: 0,
    medical_leave: 0,
  };
  for (const state of Object.values(session.records ?? {})) {
    if (state in counts) counts[state] += 1;
  }
  return counts;
}

/** The dated register (PART I) — one row per session, newest first. */
export function AttendanceSessionTable({
  sessions,
  loading = false,
  onCorrect,
}: {
  sessions: AttendanceSessionResponse[];
  loading?: boolean;
  onCorrect: (session: AttendanceSessionResponse) => void;
}) {
  if (!loading && sessions.length === 0) {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
        <CalendarDays className="h-4 w-4" aria-hidden="true" />
        No attendance recorded yet — record the first day or import a CSV register.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[620px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Date</th>
            {ATTENDANCE_STATES.map(({ value, label }) => (
              <th key={value} scope="col" className="px-4 py-3 font-medium">
                {label}
              </th>
            ))}
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <TableSkeleton rows={4} cols={6} />
          ) : (
            sessions.map((session) => {
            const counts = sessionCounts(session);
            return (
              <tr
                key={session.id}
                className="border-b border-[var(--border-subtle)] last:border-b-0"
              >
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">
                  {session.session_date}
                </td>
                {ATTENDANCE_STATES.map(({ value }) => (
                  <td key={value} className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                    {counts[value] || NO_ATTENDANCE_MARK}
                  </td>
                ))}
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onCorrect(session)}
                    aria-label={`Correct attendance of ${session.session_date}`}
                    className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                  >
                    <PencilLine className="h-3.5 w-3.5" aria-hidden="true" /> Correct
                  </button>
                </td>
              </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

/**
 * The per-student percentage view (PART I → PARTS J/K): effective presence
 * (present + late + medical leave) over recorded days, flagged below the
 * threshold — exactly the "below-75% attendance" AI question.
 */
export function AttendanceSummaryTable({
  summary,
  loading = false,
}: {
  summary: AttendanceSummary | null;
  loading?: boolean;
}) {
  if (!loading && (!summary || summary.rows.length === 0)) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">
        The summary appears once at least one session is recorded.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {summary ? (
        <p className="text-xs text-[var(--text-tertiary)]" aria-live="polite">
          {summary.session_count} session{summary.session_count === 1 ? "" : "s"} recorded ·
          effective presence = Present + Late + Medical Leave · threshold {summary.threshold}%
        </p>
      ) : null}
      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
        <table className="w-full min-w-[720px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
              <th scope="col" className="px-4 py-3 font-medium">Student</th>
              <th scope="col" className="px-4 py-3 font-medium">P</th>
              <th scope="col" className="px-4 py-3 font-medium">A</th>
              <th scope="col" className="px-4 py-3 font-medium">L</th>
              <th scope="col" className="px-4 py-3 font-medium">ML</th>
              <th scope="col" className="px-4 py-3 font-medium">Attendance</th>
              <th scope="col" className="px-4 py-3 font-medium">Flag</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <TableSkeleton rows={4} cols={7} />
            ) : (
              summary?.rows.map((row) => (
              <tr
                key={row.student_id}
                className="border-b border-[var(--border-subtle)] last:border-b-0"
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-[var(--text-primary)]">{row.student_name}</div>
                  <div className="text-xs text-[var(--text-tertiary)]">
                    {row.student_roll ?? "—"}
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">{row.present}</td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">{row.absent}</td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">{row.late}</td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {row.medical_leave}
                </td>
                <td className="px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
                  {row.percentage}%
                  <span className="ml-1 font-normal text-xs text-[var(--text-tertiary)]">
                    ({row.effective_present}/{row.total})
                  </span>
                </td>
                <td className="px-4 py-3">
                  <AttendanceFlagBadge below={row.below_threshold} />
                </td>
              </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
