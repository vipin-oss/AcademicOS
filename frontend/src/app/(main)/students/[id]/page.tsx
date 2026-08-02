"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  Clock,
  ExternalLink,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { StudentHeader } from "@/components/features/students/StudentHeader";
import { StudentLinks } from "@/components/features/students/StudentLinks";
import {
  StudentModal,
  type StudentSaveResult,
} from "@/components/features/students/StudentModal";
import { ObjectClasses } from "@/components/features/teaching/ObjectClasses";
import { ObjectPublications } from "@/components/features/publications/ObjectPublications";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { ChipList } from "@/components/features/publications/PublicationBadge";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useStudent } from "@/hooks/useStudent";
import { deleteStudent } from "@/lib/api/students";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDate, formatDateTime, titleCase } from "@/lib/utils";
import { ORCID_URL } from "@/lib/publications/constants";

/** Google Scholar profile base URL (PART A registry field). */
const SCHOLAR_URL = "https://scholar.google.com/citations?user=";

/**
 * Next.js hands the dynamic segment back percent-encoded. This is the ONE and
 * ONLY decode in the whole flow — the hook and the API layer forward the
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

export default function StudentDetailsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const studentId = decodeRouteId(params?.id);

  const { student, loading, refreshing, error, notFound, refresh } = useStudent(studentId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleSaved = useCallback(
    (result: StudentSaveResult) => {
      setEditOpen(false);
      refresh();
      show("success", "Student updated successfully.");
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!student || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteStudent(student.id);
      setFlash({ kind: "success", message: `“${student.name}” was deleted.` });
      setConfirmOpen(false);
      router.push("/students");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this student."));
      setDeleting(false);
    }
  }, [student, deleting, router]);

  const actions = student ? (
    <>
      <button
        type="button"
        onClick={() => setEditOpen(true)}
        disabled={deleting}
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
        disabled={deleting}
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
            {student ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh student"
                title="Refresh"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
            ) : null}
          </div>

          <Breadcrumbs
            items={[
              { label: "Dashboard", href: "/" },
              { label: "Students", href: "/students" },
              { label: student?.name ?? (notFound ? "Not found" : "Student") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Student not found"
                description="This student may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/students")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Students
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this student"
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
            ) : student ? (
              <div className="space-y-4">
                <StudentHeader student={student} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Registry">
                    <dl className="text-sm">
                      <DetailRow label="Roll number" value={student.roll_number || "—"} mono />
                      <DetailRow
                        label="Registration number"
                        value={student.registration_number || "—"}
                        mono
                      />
                      <DetailRow
                        label="University enrollment"
                        value={student.university_enrollment || "—"}
                        mono
                      />
                      <DetailRow label="Email" value={student.email || "—"} />
                      <DetailRow label="Phone" value={student.phone || "—"} />
                      <DetailRow label="Programme" value={student.programme || "—"} />
                      <DetailRow label="Department" value={student.department || "—"} />
                      <DetailRow
                        label="Semester"
                        value={student.semester != null ? `Semester ${student.semester}` : "—"}
                      />
                      <DetailRow label="Section" value={student.section || "—"} />
                      <DetailRow label="Batch" value={student.batch || "—"} />
                      <DetailRow
                        label="Admission date"
                        value={student.admission_date || "—"}
                      />
                      <DetailRow
                        label="Expected graduation"
                        value={student.expected_graduation || "—"}
                      />
                    </dl>
                  </Section>

                  <Section title="Research &amp; Identifiers">
                    <dl className="text-sm">
                      <DetailRow label="Research area" value={student.research_area || "—"} />
                      <DetailRow
                        label="ORCID"
                        value={
                          student.orcid ? (
                            <a
                              href={`${ORCID_URL}${student.orcid}`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 break-all font-mono text-xs text-[var(--accent)] hover:underline"
                            >
                              {student.orcid}
                              <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                            </a>
                          ) : (
                            "—"
                          )
                        }
                      />
                      <DetailRow
                        label="Google Scholar"
                        value={
                          student.google_scholar ? (
                            <a
                              href={`${SCHOLAR_URL}${student.google_scholar}`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 break-all font-mono text-xs text-[var(--accent)] hover:underline"
                            >
                              {student.google_scholar}
                              <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                            </a>
                          ) : (
                            "—"
                          )
                        }
                      />
                      <DetailRow label="Student ID" value={student.id} mono />
                    </dl>
                  </Section>

                  <Section title="Supervision &amp; Links">
                    <StudentLinks student={student} />
                  </Section>

                  <Section title="Classes Enrolled">
                    <ObjectClasses objectId={student.id} />
                  </Section>

                  <Section title="Publications">
                    <ObjectPublications objectId={student.id} />
                  </Section>

                  <Section title="Documents">
                    <ObjectDocuments objectId={student.id} />
                  </Section>

                  <Section title="Organisation">
                    <dl className="text-sm">
                      <DetailRow label="Tags" value={<ChipList items={student.tags} />} />
                      <DetailRow label="Notes" value={student.notes || "—"} />
                    </dl>
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Added by" value={student.uploaded_by || "—"} />
                      <DetailRow label="Added at" value={formatDateTime(student.created_at)} />
                      <DetailRow
                        label="Last updated"
                        value={
                          student.updated_at ? (
                            formatDateTime(student.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${student.version}`} />
                      <DetailRow label="Student since" value={formatDate(student.created_at)} />
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
                          <p className="text-[var(--text-primary)]">Student admitted</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(student.created_at)} ·{" "}
                            {student.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(student.events ?? []).map((event, index) => (
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

      {student ? (
        <>
          <StudentModal
            open={editOpen}
            student={student}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete student?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">“{student.name}”</span>{" "}
                will be permanently removed from the registry. Submissions, marks and attendance
                evidence recorded against this student are kept. This action cannot be undone.
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
