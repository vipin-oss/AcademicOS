"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { formatDeadline } from "@/lib/teaching/constants";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { AssignmentTypeBadge } from "./TeachingBadges";
import type { AssignmentResponse } from "@/types";

function AssignmentRow({ assignment }: { assignment: AssignmentResponse }) {
  const router = useRouter();
  const href = `/teaching/assignments/${encodeURIComponent(assignment.id)}`;

  return (
    <tr
      onClick={() => router.push(href)}
      className="cursor-pointer border-b border-[var(--border-subtle)] transition-colors last:border-b-0 hover:bg-[var(--bg-hover)]"
    >
      <td className="px-4 py-3">
        <Link
          href={href}
          onClick={(event) => event.stopPropagation()}
          className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
        >
          {assignment.title}
        </Link>
        {assignment.description ? (
          <div className="mt-0.5 line-clamp-1 text-xs text-[var(--text-tertiary)]">
            {assignment.description}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-3">
        <AssignmentTypeBadge type={assignment.assignment_type} />
      </td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        {assignment.max_marks != null ? assignment.max_marks : "—"}
      </td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        {formatDeadline(assignment.deadline)}
        {assignment.late_allowed ? (
          <span className="ml-1.5 text-xs text-[var(--text-tertiary)]">(late ok)</span>
        ) : null}
      </td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        {assignment.weightage != null ? `${assignment.weightage}%` : "—"}
      </td>
    </tr>
  );
}

/** Assignments of a class, deadline-ordered by the backend (PART D). */
export function AssignmentTable({
  assignments,
  loading = false,
}: {
  assignments: AssignmentResponse[];
  loading?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[720px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Title</th>
            <th scope="col" className="px-4 py-3 font-medium">Type</th>
            <th scope="col" className="px-4 py-3 font-medium">Max marks</th>
            <th scope="col" className="px-4 py-3 font-medium">Deadline</th>
            <th scope="col" className="px-4 py-3 font-medium">Weightage</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <TableSkeleton rows={4} cols={5} />
          ) : (
            assignments.map((assignment) => (
              <AssignmentRow key={assignment.id} assignment={assignment} />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
