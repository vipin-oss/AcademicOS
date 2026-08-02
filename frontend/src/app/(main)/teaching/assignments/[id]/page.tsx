"use client";

import { useCallback, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  Clock,
  Download,
  FileSpreadsheet,
  FileUp,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { AssignmentHeader } from "@/components/features/teaching/AssignmentHeader";
import {
  AssignmentModal,
  type AssignmentSaveResult,
} from "@/components/features/teaching/AssignmentModal";
import { SubmissionGridTable } from "@/components/features/teaching/SubmissionGrid";
import { MarksCsvModal } from "@/components/features/teaching/MarksCsvModal";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useAssignment } from "@/hooks/useAssignment";
import { useSubmissionGrid } from "@/hooks/useSubmissionGrid";
import { attachAssignmentFile, deleteAssignment } from "@/lib/api/teaching";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDateTime, titleCase } from "@/lib/utils";
import { formatDeadline } from "@/lib/teaching/constants";
import { formatFileSize } from "@/lib/documents/constants";
import type { MarksImportResult } from "@/types";

/**
 * Next.js hands the dynamic segment back percent-encoded. This is the ONE and
 * ONLY decode in the whole flow — the hooks and the API layer forward the
 * decoded id untouched (mirrors the Publications detail page).
 */
function decodeRouteId(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value; // malformed escape sequence — use the raw segment
  }
}

export default function AssignmentWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const assignmentId = decodeRouteId(params?.id);

  const {
    assignment,
    loading,
    refreshing,
    error,
    notFound,
    refresh,
  } = useAssignment(assignmentId);
  const gridState = useSubmissionGrid(assignmentId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [marksOpen, setMarksOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [fileProgress, setFileProgress] = useState<number | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const attaching = fileProgress !== null;

  const handleSaved = useCallback(
    (result: AssignmentSaveResult) => {
      setEditOpen(false);
      refresh();
      show("success", "Assignment updated successfully.");
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!assignment || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const result = await deleteAssignment(assignment.id);
      const cascaded = result.submissions
        ? ` (with ${result.submissions} submission${result.submissions === 1 ? "" : "s"})`
        : "";
      setFlash({
        kind: "success",
        message: `“${assignment.title}” was deleted${cascaded}.`,
      });
      setConfirmOpen(false);
      router.push(`/teaching/classes/${encodeURIComponent(assignment.class_id)}`);
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this assignment."));
      setDeleting(false);
    }
  }, [assignment, deleting, router]);

  const handleFileChosen = useCallback(
    async (file: File | undefined) => {
      if (!assignment || !file) return;
      setFileError(null);
      setFileProgress(0);
      try {
        await attachAssignmentFile(assignment.id, file, assignment.uploaded_by, {
          onProgress: ({ percent }) => setFileProgress(percent),
        });
        refresh();
        show("success", `“${file.name}” attached as the assignment file.`);
      } catch (err) {
        setFileError(toErrorMessage(err, "Failed to attach the file."));
      } finally {
        setFileProgress(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [assignment, refresh, show],
  );

  const handleMarksImported = useCallback(
    (result: MarksImportResult) => {
      // Keep the modal OPEN: it shows the per-row import report (unknown
      // rolls, out-of-range marks) — the faculty clicks Done when reviewed.
      gridState.refresh();
      const parts = [`Graded ${result.graded.length} submission${result.graded.length === 1 ? "" : "s"}`];
      if (result.created_submissions.length) {
        parts.push(`${result.created_submissions.length} created from the CSV`);
      }
      if (result.errors.length) parts.push(`${result.errors.length} failed`);
      show(result.errors.length ? "warning" : "success", `${parts.join(" · ")}.`);
    },
    [gridState, show],
  );

  const actions = assignment ? (
    <>
      {assignment.attachment_url ? (
        <a
          href={assignment.attachment_url}
          download={assignment.attachment_file_name || assignment.title}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <Download className="h-4 w-4" aria-hidden="true" /> Download file
        </a>
      ) : null}
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        disabled={attaching || deleting}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {attaching ? <Spinner /> : <FileUp className="h-4 w-4" aria-hidden="true" />}
        {attaching
          ? `Uploading ${fileProgress ?? 0}%`
          : assignment.attachment_url
            ? "Replace file"
            : "Attach file"}
      </button>
      <button
        type="button"
        onClick={() => setMarksOpen(true)}
        disabled={deleting || attaching}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <FileSpreadsheet className="h-4 w-4" aria-hidden="true" /> Import marks CSV
      </button>
      <button
        type="button"
        onClick={() => setEditOpen(true)}
        disabled={deleting || attaching}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Pencil className="h-4 w-4" aria-hidden="true" /> Edit
      </button>
      <button
        type="button"
        onClick={() => {
          setDeleteError(null);
          setConfirmOpen(true);
        }}
        disabled={deleting || attaching}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger)] px-3 py-2 text-sm font-medium text-[var(--danger)] transition-colors hover:bg-[var(--danger-subtle)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {deleting ? <Spinner /> : <Trash2 className="h-4 w-4" aria-hidden="true" />}
        {deleting ? "Deleting…" : "Delete"}
      </button>
    </>
  ) : null;

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => router.back()}
              className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--accent)]"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back
            </button>
            {assignment ? (
              <button
                type="button"
                onClick={() => {
                  refresh();
                  gridState.refresh();
                }}
                disabled={refreshing || gridState.refreshing}
                aria-label="Refresh assignment"
                title="Refresh"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${refreshing || gridState.refreshing ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
                {refreshing || gridState.refreshing ? "Refreshing…" : "Refresh"}
              </button>
            ) : null}
          </div>

          <Breadcrumbs
            items={[
              { label: "Dashboard", href: "/" },
              { label: "Teaching", href: "/teaching" },
              ...(assignment?.class_title
                ? [
                    {
                      label: assignment.class_title,
                      href: `/teaching/classes/${encodeURIComponent(assignment.class_id)}`,
                    },
                  ]
                : []),
              { label: assignment?.title ?? (notFound ? "Not found" : "Assignment") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Assignment not found"
                description="This assignment may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/teaching")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Teaching
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this assignment"
                description={error}
                action={
                  <button
                    type="button"
                    onClick={refresh}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" /> Try again
                  </button>
                }
              />
            ) : assignment ? (
              <div className="space-y-4">
                <AssignmentHeader assignment={assignment} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Assignment Details">
                    <dl className="text-sm">
                      <DetailRow label="Type" value={titleCase(assignment.assignment_type)} />
                      <DetailRow
                        label="Maximum marks"
                        value={
                          assignment.max_marks != null ? String(assignment.max_marks) : "—"
                        }
                      />
                      <DetailRow label="Deadline" value={formatDeadline(assignment.deadline)} />
                      <DetailRow
                        label="Late submission"
                        value={assignment.late_allowed ? "Allowed" : "Not allowed"}
                      />
                      <DetailRow
                        label="Weightage"
                        value={
                          assignment.weightage != null ? `${assignment.weightage}%` : "—"
                        }
                      />
                      <DetailRow
                        label="Visibility"
                        value={
                          assignment.visibility === "hidden"
                            ? "Hidden from students"
                            : "Visible"
                        }
                      />
                      <DetailRow
                        label="Description"
                        value={assignment.description || "—"}
                      />
                    </dl>
                    {assignment.instructions ? (
                      <div className="mt-3 border-t border-[var(--border-subtle)] pt-3">
                        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                          Instructions
                        </h3>
                        <p className="whitespace-pre-line text-sm leading-relaxed text-[var(--text-secondary)]">
                          {assignment.instructions}
                        </p>
                      </div>
                    ) : null}
                  </Section>

                  <Section title={`Rubric (${assignment.rubric.length})`}>
                    {assignment.rubric.length === 0 ? (
                      <p className="text-sm text-[var(--text-tertiary)]">
                        No rubric — grading records a single marks figure.
                      </p>
                    ) : (
                      <ul className="space-y-2 text-sm">
                        {assignment.rubric.map((criterion, index) => (
                          <li
                            key={`${criterion.criterion}-${index}`}
                            className="flex items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-2 last:border-0 last:pb-0"
                          >
                            <span className="text-[var(--text-primary)]">
                              {criterion.criterion}
                            </span>
                            <span className="text-[var(--text-secondary)]">
                              {criterion.marks != null ? `${criterion.marks} marks` : "—"}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Section>

                  <Section title="Attachment" className="lg:col-span-2">
                    <dl className="text-sm">
                      <DetailRow label="File name" value={assignment.attachment_file_name || "—"} />
                      <DetailRow
                        label="Size"
                        value={
                          assignment.attachment_file_size
                            ? formatFileSize(assignment.attachment_file_size)
                            : "—"
                        }
                      />
                      <DetailRow
                        label="MIME type"
                        value={assignment.attachment_mime_type || "—"}
                      />
                    </dl>
                    {fileError ? (
                      <p role="alert" className="mt-2 text-xs text-[var(--danger)]">
                        {fileError}
                      </p>
                    ) : null}
                    <p className="mt-3 text-xs text-[var(--text-tertiary)]">
                      The Google-Forms loop: export form responses as CSV and bring them back via
                      “Import marks CSV” — AcademicOS stays the primary store.
                    </p>
                  </Section>
                </div>

                <Section title="Submissions & Grading">
                  {gridState.error ? (
                    <p className="text-sm text-[var(--danger)]">{gridState.error}</p>
                  ) : (
                    <SubmissionGridTable
                      grid={gridState.grid}
                      assignment={assignment}
                      loading={gridState.loading}
                      onGraded={(_submissionId, marks) => {
                        gridState.refresh();
                        show("success", `Marks saved (${marks}).`);
                      }}
                      onError={(message) => show("error", message)}
                    />
                  )}
                </Section>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Created by" value={assignment.uploaded_by || "—"} />
                      <DetailRow
                        label="Created at"
                        value={formatDateTime(assignment.created_at)}
                      />
                      <DetailRow
                        label="Last updated"
                        value={
                          assignment.updated_at ? (
                            formatDateTime(assignment.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${assignment.version}`} />
                    </dl>
                  </Section>

                  <Section title="Timeline">
                    <ol className="space-y-3 text-sm">
                      <li className="flex gap-3">
                        <Clock
                          className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-tertiary)]"
                          aria-hidden="true"
                        />
                        <div>
                          <p className="text-[var(--text-primary)]">Assignment created</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(assignment.created_at)} ·{" "}
                            {assignment.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(assignment.events ?? []).map((event, index) => (
                        <li key={`${event}-${index}`} className="flex gap-3">
                          <ActivityIcon
                            className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-tertiary)]"
                            aria-hidden="true"
                          />
                          <p className="text-[var(--text-primary)]">{titleCase(event)}</p>
                        </li>
                      ))}
                    </ol>
                  </Section>
                </div>
              </div>
            ) : null}
          </div>
        </main>
      </div>

      {assignment ? (
        <>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            aria-hidden="true"
            tabIndex={-1}
            onChange={(event) => handleFileChosen(event.target.files?.[0])}
          />
          <AssignmentModal
            open={editOpen}
            classId={assignment.class_id}
            assignment={assignment}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <MarksCsvModal
            open={marksOpen}
            assignmentId={assignment.id}
            onClose={() => setMarksOpen(false)}
            onImported={handleMarksImported}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete assignment?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{assignment.title}”
                </span>{" "}
                will be permanently removed, together with all student submissions and their
                uploaded files. This action cannot be undone.
              </>
            }
            confirmLabel="Delete"
            loadingLabel="Deleting…"
            loading={deleting}
            error={deleteError}
            onConfirm={handleDelete}
            onCancel={() => {
              if (!deleting) {
                setConfirmOpen(false);
                setDeleteError(null);
              }
            }}
          />
        </>
      ) : null}

      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
