import type { ReactNode } from "react";
import Link from "next/link";
import { CalendarClock, ClipboardList, Percent, Scale, Upload } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { formatDeadline } from "@/lib/teaching/constants";
import { DocumentVersionBadge } from "@/components/features/documents/DocumentBadge";
import { AssignmentTypeBadge, ClassStatusBadge } from "./TeachingBadges";
import type { AssignmentResponse } from "@/types";

/** Assignment workspace header (mirrors StudentHeader, ClipboardList icon). */
export function AssignmentHeader({
  assignment,
  actions,
}: {
  assignment: AssignmentResponse;
  actions?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          <ClipboardList
            className="mt-1 h-11 w-11 shrink-0 rounded-lg bg-[var(--accent-subtle)] p-2.5 text-[var(--accent)]"
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <h1 className="break-words text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">
              {assignment.title}
            </h1>
            <p className="mt-1.5 text-sm text-[var(--text-secondary)]">
              {assignment.class_title ? (
                <Link
                  href={`/teaching/classes/${encodeURIComponent(assignment.class_id)}`}
                  className="text-[var(--accent)] hover:underline"
                >
                  {assignment.class_title}
                </Link>
              ) : (
                "Assignment"
              )}
              {assignment.visibility === "hidden" ? " · hidden from students" : ""}
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <AssignmentTypeBadge type={assignment.assignment_type} />
              <ClassStatusBadge status={assignment.status} />
              <DocumentVersionBadge version={assignment.version} />
            </div>

            <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-[var(--text-secondary)]">
              <div className="flex items-center gap-1.5">
                <CalendarClock
                  className="h-4 w-4 text-[var(--text-tertiary)]"
                  aria-hidden="true"
                />
                <dt className="sr-only">Deadline</dt>
                <dd>
                  {formatDeadline(assignment.deadline)}
                  {assignment.late_allowed && assignment.deadline ? " (late allowed)" : ""}
                </dd>
              </div>
              {assignment.max_marks != null ? (
                <div className="flex items-center gap-1.5">
                  <Scale className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                  <dt className="sr-only">Maximum marks</dt>
                  <dd>{assignment.max_marks} marks</dd>
                </div>
              ) : null}
              {assignment.weightage != null ? (
                <div className="flex items-center gap-1.5">
                  <Percent className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                  <dt className="sr-only">Weightage</dt>
                  <dd>{assignment.weightage}% of total</dd>
                </div>
              ) : null}
              <div className="flex items-center gap-1.5">
                <Upload className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                <dt className="sr-only">Created by / at</dt>
                <dd>
                  {assignment.uploaded_by || "—"} · {formatDate(assignment.created_at)}
                </dd>
              </div>
            </dl>

            <p className="mt-2 break-all font-mono text-xs text-[var(--text-tertiary)]">
              {assignment.id}
            </p>
          </div>
        </div>

        {actions ? <div className="flex flex-wrap gap-2 lg:justify-end">{actions}</div> : null}
      </div>
    </div>
  );
}
