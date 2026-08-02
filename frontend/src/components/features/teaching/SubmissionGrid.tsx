"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { gradeSubmission } from "@/lib/api/teaching";
import { GRID_STATE_LABELS } from "@/lib/teaching/constants";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { GridStateBadge } from "./TeachingBadges";
import type { AssignmentResponse, SubmissionGrid, SubmissionGridRow } from "@/types";

const INPUT_CLASS =
  "w-20 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-sm text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * The student × assignment matrix (UI Spec §2.5 C7) with INLINE marks:
 * every roster student gets a row — pending rows are virtual — and grading
 * happens in place (marks + feedback saved per row, rubric totals computed
 * server-side when a rubric breakdown is used).
 */
export function SubmissionGridTable({
  grid,
  assignment,
  loading = false,
  onGraded,
  onError,
}: {
  grid: SubmissionGrid | null;
  assignment: AssignmentResponse | null;
  loading?: boolean;
  onGraded: (submissionId: string, marks: number) => void;
  onError: (message: string) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [feedbackDrafts, setFeedbackDrafts] = useState<Record<string, string>>({});
  const [savingRow, setSavingRow] = useState<string | null>(null);

  const maxMarks = assignment?.max_marks ?? null;

  if (loading || !grid) {
    // TableSkeleton emits bare <tr>s — valid only inside a table body.
    return (
      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
        <table className="w-full min-w-[860px] border-collapse text-left" aria-busy={loading}>
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
              <th scope="col" className="px-4 py-3 font-medium">Student</th>
              <th scope="col" className="px-4 py-3 font-medium">State</th>
              <th scope="col" className="px-4 py-3 font-medium">Submission</th>
              <th scope="col" className="px-4 py-3 font-medium">
                Marks{maxMarks != null ? ` (of ${maxMarks})` : ""}
              </th>
              <th scope="col" className="px-4 py-3 font-medium">Faculty feedback</th>
              <th scope="col" className="px-4 py-3 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <TableSkeleton rows={6} cols={5} />
          </tbody>
        </table>
      </div>
    );
  }



  const handleSave = async (row: SubmissionGridRow) => {
    const submissionId = row.submission?.id;
    if (!submissionId) return;
    const raw = (drafts[row.student_id] ?? "").trim();
    const marks = raw ? Number(raw) : NaN;
    if (!raw || Number.isNaN(marks)) {
      onError(`Enter numeric marks for ${row.student_name} first.`);
      return;
    }
    setSavingRow(row.student_id);
    try {
      await gradeSubmission(submissionId, {
        marks,
        faculty_feedback: (feedbackDrafts[row.student_id] ?? "").trim() || null,
        actor: "faculty:ui",
      });
      onGraded(submissionId, marks);
      setDrafts((current) => ({ ...current, [row.student_id]: "" }));
      setFeedbackDrafts((current) => ({ ...current, [row.student_id]: "" }));
    } catch (err) {
      onError(toErrorMessage(err));
    } finally {
      setSavingRow(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-tertiary)]" aria-live="polite">
        <span className="rounded-full bg-[var(--bg-hover)] px-2.5 py-1">
          {GRID_STATE_LABELS.submitted}: {grid.submitted_count}
        </span>
        <span className="rounded-full bg-[var(--bg-hover)] px-2.5 py-1">
          {GRID_STATE_LABELS.late}: {grid.late_count}
        </span>
        <span className="rounded-full bg-[var(--bg-hover)] px-2.5 py-1">
          {GRID_STATE_LABELS.pending}: {grid.pending_count}
        </span>
        <span className="rounded-full bg-[var(--bg-hover)] px-2.5 py-1">
          {GRID_STATE_LABELS.graded}: {grid.graded_count}
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
        <table className="w-full min-w-[860px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
              <th scope="col" className="px-4 py-3 font-medium">Student</th>
              <th scope="col" className="px-4 py-3 font-medium">State</th>
              <th scope="col" className="px-4 py-3 font-medium">Submission</th>
              <th scope="col" className="px-4 py-3 font-medium">
                Marks{maxMarks != null ? ` (of ${maxMarks})` : ""}
              </th>
              <th scope="col" className="px-4 py-3 font-medium">Faculty feedback</th>
              <th scope="col" className="px-4 py-3 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {grid.rows.map((row) => {
              const submission = row.submission;
              const existingMarks = submission?.marks;
              const draft = drafts[row.student_id] ?? "";
              const feedbackDraft = feedbackDrafts[row.student_id] ?? "";
              return (
                <tr key={row.student_id} className="border-b border-[var(--border-subtle)] last:border-b-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-[var(--text-primary)]">{row.student_name}</div>
                    <div className="text-xs text-[var(--text-tertiary)]">{row.student_roll ?? "—"}</div>
                  </td>
                  <td className="px-4 py-3">
                    <GridStateBadge state={row.state} />
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                    {submission?.file_url ? (
                      <a
                        href={submission.file_url}
                        download
                        className="inline-flex items-center gap-1.5 text-[var(--accent)] hover:underline"
                      >
                        <Download className="h-3.5 w-3.5" aria-hidden="true" />
                        {submission.file_name ?? "Download"}
                      </a>
                    ) : submission?.submitted_at ? (
                      "No file"
                    ) : (
                      "—"
                    )}
                    {submission?.is_late ? (
                      <span className="ml-1.5 text-xs text-[var(--warning)]">late</span>
                    ) : null}
                    {submission?.comments ? (
                      <div className="mt-0.5 line-clamp-1 text-xs text-[var(--text-tertiary)]">
                        “{submission.comments}”
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    {row.state === "pending" ? (
                      <span className="text-sm text-[var(--text-tertiary)]">—</span>
                    ) : row.state === "graded" && !draft ? (
                      <span className="text-sm font-semibold text-[var(--text-primary)]">
                        {existingMarks}
                        {maxMarks != null ? (
                          <span className="font-normal text-[var(--text-tertiary)]"> / {maxMarks}</span>
                        ) : null}
                      </span>
                    ) : (
                      <input
                        type="number"
                        min={0}
                        max={maxMarks ?? undefined}
                        step="0.5"
                        value={draft || String(existingMarks ?? "")}
                        onChange={(event) =>
                          setDrafts((current) => ({ ...current, [row.student_id]: event.target.value }))
                        }
                        aria-label={`Marks for ${row.student_name}`}
                        className={INPUT_CLASS}
                      />
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {row.state === "pending" ? (
                      <span className="text-sm text-[var(--text-tertiary)]">—</span>
                    ) : (
                      <input
                        type="text"
                        value={feedbackDraft || (submission?.faculty_feedback ?? "")}
                        onChange={(event) =>
                          setFeedbackDrafts((current) => ({
                            ...current,
                            [row.student_id]: event.target.value,
                          }))
                        }
                        aria-label={`Feedback for ${row.student_name}`}
                        placeholder="Feedback…"
                        className="w-44 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
                      />
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {row.state !== "pending" && (draft || feedbackDraft) ? (
                      <button
                        type="button"
                        onClick={() => handleSave(row)}
                        disabled={savingRow === row.student_id}
                        className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
                      >
                        {savingRow === row.student_id ? "Saving…" : "Save marks"}
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
