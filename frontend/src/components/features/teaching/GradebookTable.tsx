"use client";

import { FileDown } from "lucide-react";
import { gradebookExportUrl } from "@/lib/api/teaching";
import { assignmentTypeLabel } from "@/lib/teaching/constants";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { GradeBadge } from "./TeachingBadges";
import type { Gradebook } from "@/types";


/**
 * The computed marks matrix (PART H — UI Spec §2.5 C7's grade view):
 * students × assessments, with weighted internal total (0–100), overall
 * average and the letter grade appended. Cells show raw marks; late
 * submissions are marked. The export anchor downloads the same matrix as
 * CSV (the university-format marks sheet of PART K).
 */
export function GradebookTable({
  gradebook,
  loading = false,
}: {
  gradebook: Gradebook | null;
  loading?: boolean;
}) {
  if (loading || !gradebook) {
    // TableSkeleton emits bare <tr>s — valid only inside a table body.
    return (
      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
        <table className="w-full min-w-[860px] border-collapse text-left" aria-busy={loading}>
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
              <th scope="col" className="px-4 py-3 font-medium">Student</th>
              <th scope="col" className="px-4 py-3 font-medium">Assessments</th>
              <th scope="col" className="px-4 py-3 font-medium">Internal</th>
              <th scope="col" className="px-4 py-3 font-medium">Average</th>
              <th scope="col" className="px-4 py-3 font-medium">Grade</th>
            </tr>
          </thead>
          <tbody>
            <TableSkeleton rows={6} cols={5} />
          </tbody>
        </table>
      </div>
    );
  }
  if (gradebook.assignments.length === 0) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">
        The gradebook appears once the class has at least one assessment.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-[var(--text-tertiary)]" aria-live="polite">
          {gradebook.rows.length} student{gradebook.rows.length === 1 ? "" : "s"} ×{" "}
          {gradebook.assignments.length} assessment
          {gradebook.assignments.length === 1 ? "" : "s"} · totals are weightage-weighted
        </p>
        <a
          href={gradebookExportUrl(gradebook.class_id)}
          download
          aria-label="Export gradebook as CSV"
          title="University-format marks sheet (CSV)"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <FileDown className="h-3.5 w-3.5" aria-hidden="true" /> Export CSV
        </a>
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
        <table className="w-full min-w-[860px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
              <th
                scope="col"
                className="sticky left-0 z-10 bg-[var(--bg-surface)] px-4 py-3 font-medium"
              >
                Student
              </th>
              {gradebook.assignments.map((header) => (
                <th key={header.id} scope="col" className="px-4 py-3 font-medium">
                  <span className="block max-w-40 truncate" title={header.title}>
                    {header.title}
                  </span>
                  <span className="block font-normal normal-case text-[var(--text-tertiary)]">
                    {assignmentTypeLabel(header.assignment_type)}
                    {header.max_marks != null ? ` · /${header.max_marks}` : ""}
                    {header.weightage != null ? ` · w${header.weightage}%` : ""}
                  </span>
                </th>
              ))}
              <th scope="col" className="px-4 py-3 font-medium">
                Internal
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Average
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Grade
              </th>
            </tr>
          </thead>
          <tbody>
            {gradebook.rows.map((row) => (
              <tr
                key={row.student_id}
                className="border-b border-[var(--border-subtle)] last:border-b-0"
              >
                <td className="sticky left-0 z-10 bg-[var(--bg-surface)] px-4 py-3">
                  <div className="font-medium text-[var(--text-primary)]">{row.student_name}</div>
                  <div className="text-xs text-[var(--text-tertiary)]">
                    {row.student_roll ?? "—"}
                  </div>
                </td>
                {row.cells.map((cell) => (
                  <td key={cell.assignment_id} className="px-4 py-3 text-sm">
                    {cell.marks != null ? (
                      <span className="font-medium text-[var(--text-primary)]">
                        {cell.marks}
                        {cell.max_marks != null ? (
                          <span className="font-normal text-xs text-[var(--text-tertiary)]">
                            {" "}
                            /{cell.max_marks}
                          </span>
                        ) : null}
                      </span>
                    ) : (
                      <span className="text-[var(--text-tertiary)]">—</span>
                    )}
                    {cell.is_late ? (
                      <span className="ml-1 text-xs text-[var(--warning)]" title="Submitted late">
                        L
                      </span>
                    ) : null}
                  </td>
                ))}
                <td className="px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
                  {row.internal_total}%
                </td>
                <td className="px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
                  {row.average_percent}%
                </td>
                <td className="px-4 py-3">
                  <GradeBadge grade={row.grade} />
                </td>
              </tr>
            ))}
            {gradebook.rows.length === 0 ? (
              <tr>
                <td
                  colSpan={gradebook.assignments.length + 4}
                  className="px-4 py-6 text-center text-sm text-[var(--text-tertiary)]"
                >
                  No students enrolled yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
