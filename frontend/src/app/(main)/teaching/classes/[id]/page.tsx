"use client";

import { useCallback, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CalendarCheck,
  ClipboardList,
  FileBarChart,
  Link2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  UserMinus,
  UserPlus,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { ClassHeader, scheduleLine } from "@/components/features/teaching/ClassHeader";
import {
  ClassModal,
  type ClassSaveResult,
} from "@/components/features/teaching/ClassModal";
import {
  AssignmentModal,
  type AssignmentSaveResult,
} from "@/components/features/teaching/AssignmentModal";
import { AssignmentTable } from "@/components/features/teaching/AssignmentTable";
import { EnrollModal } from "@/components/features/teaching/EnrollModal";
import { AttendanceModal } from "@/components/features/teaching/AttendanceModal";
import {
  AttendanceSessionTable,
  AttendanceSummaryTable,
} from "@/components/features/teaching/AttendanceTable";
import { GradebookTable } from "@/components/features/teaching/GradebookTable";
import { ChipList } from "@/components/features/publications/PublicationBadge";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton, TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useClass } from "@/hooks/useClass";
import { useRoster } from "@/hooks/useRoster";
import { useAssignments } from "@/hooks/useAssignments";
import { useAttendanceSessions } from "@/hooks/useAttendanceSessions";
import { useAttendanceSummary } from "@/hooks/useAttendanceSummary";
import { useGradebook } from "@/hooks/useGradebook";
import { useClassReport } from "@/hooks/useClassReport";
import { deleteClass, unenrollStudent } from "@/lib/api/teaching";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { assignmentTypeLabel, formatDeadline } from "@/lib/teaching/constants";
import type {
  AttendanceImportResult,
  AttendanceSessionResponse,
  EnrollmentResult,
  RosterEntry,
} from "@/types";

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

export default function ClassWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const classId = decodeRouteId(params?.id);

  const { cls, loading, refreshing, error, notFound, refresh } = useClass(classId);
  const rosterState = useRoster(classId);
  const assignmentsState = useAssignments(classId);
  const sessionsState = useAttendanceSessions(classId);
  const summaryState = useAttendanceSummary(classId);
  const gradebookState = useGradebook(classId);
  const reportState = useClassReport(classId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [assignmentOpen, setAssignmentOpen] = useState(false);
  const [attendanceOpen, setAttendanceOpen] = useState(false);
  const [correcting, setCorrecting] = useState<AttendanceSessionResponse | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [unenrollTarget, setUnenrollTarget] = useState<RosterEntry | null>(null);
  const [unenrolling, setUnenrolling] = useState(false);
  const [unenrollError, setUnenrollError] = useState<string | null>(null);

  const refreshAll = useCallback(() => {
    refresh();
    rosterState.refresh();
    assignmentsState.refresh();
    sessionsState.refresh();
    summaryState.refresh();
    gradebookState.refresh();
    reportState.refresh();
  }, [
    refresh,
    rosterState,
    assignmentsState,
    sessionsState,
    summaryState,
    gradebookState,
    reportState,
  ]);

  const refreshMarksViews = useCallback(() => {
    gradebookState.refresh();
    reportState.refresh();
  }, [gradebookState, reportState]);

  const refreshAttendanceViews = useCallback(() => {
    sessionsState.refresh();
    summaryState.refresh();
    reportState.refresh();
  }, [sessionsState, summaryState, reportState]);

  const enrolledIds = useMemo(
    () => new Set(rosterState.roster.map((entry) => entry.student_id)),
    [rosterState.roster],
  );

  const handleSaved = useCallback(
    (result: ClassSaveResult) => {
      setEditOpen(false);
      refresh();
      show("success", "Class updated successfully.");
    },
    [refresh, show],
  );

  const handleAssignmentSaved = useCallback(
    (result: AssignmentSaveResult) => {
      setAssignmentOpen(false);
      assignmentsState.refresh();
      refreshMarksViews();
      show(
        "success",
        `“${result.assignment.title}” ${result.mode === "edit" ? "updated" : "created"} successfully.`,
      );
    },
    [assignmentsState, refreshMarksViews, show],
  );

  const handleEnrolled = useCallback(
    (result: EnrollmentResult) => {
      setEnrollOpen(false);
      refresh();
      rosterState.refresh();
      gradebookState.refresh();
      reportState.refresh();
      const parts = [
        `Enrolled ${result.enrolled.length} student${result.enrolled.length === 1 ? "" : "s"}`,
      ];
      if (result.already_enrolled.length) {
        parts.push(`${result.already_enrolled.length} already enrolled`);
      }
      if (result.errors.length) parts.push(`${result.errors.length} failed`);
      show(
        result.errors.length ? "warning" : "success",
        `${parts.join(" · ")}.`,
      );
    },
    [refresh, rosterState, gradebookState, reportState, show],
  );

  const handleDelete = useCallback(async () => {
    if (!cls || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const result = await deleteClass(cls.id);
      const cascaded = [
        result.assignments ? `${result.assignments} assignment${result.assignments === 1 ? "" : "s"}` : null,
        result.submissions ? `${result.submissions} submission${result.submissions === 1 ? "" : "s"}` : null,
        result.attendance_sessions
          ? `${result.attendance_sessions} attendance session${result.attendance_sessions === 1 ? "" : "s"}`
          : null,
      ]
        .filter(Boolean)
        .join(", ");
      setFlash({
        kind: "success",
        message: `“${cls.title}” was deleted${cascaded ? ` (with ${cascaded})` : ""}.`,
      });
      setConfirmOpen(false);
      router.push("/teaching");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this class."));
      setDeleting(false);
    }
  }, [cls, deleting, router]);

  const handleUnenroll = useCallback(async () => {
    if (!cls || !unenrollTarget || unenrolling) return;
    setUnenrolling(true);
    setUnenrollError(null);
    try {
      await unenrollStudent(cls.id, unenrollTarget.student_id);
      setUnenrollTarget(null);
      refresh();
      rosterState.refresh();
      gradebookState.refresh();
      reportState.refresh();
      show("success", `“${unenrollTarget.name}” was removed from the class.`);
    } catch (err) {
      setUnenrollError(toErrorMessage(err, "Failed to remove this student."));
    } finally {
      setUnenrolling(false);
    }
  }, [cls, unenrollTarget, unenrolling, refresh, rosterState, gradebookState, reportState, show]);

  const handleAttendanceRecorded = useCallback(
    (recorded: AttendanceSessionResponse) => {
      setAttendanceOpen(false);
      setCorrecting(null);
      refreshAttendanceViews();
      show(
        "success",
        `Attendance recorded for ${recorded.session_date} (${Object.keys(recorded.records ?? {}).length} student${Object.keys(recorded.records ?? {}).length === 1 ? "" : "s"}).`,
      );
    },
    [refreshAttendanceViews, show],
  );

  const handleAttendanceImported = useCallback(
    (result: AttendanceImportResult) => {
      setAttendanceOpen(false);
      setCorrecting(null);
      refreshAttendanceViews();
      const parts = [`Applied ${result.applied.length} record${result.applied.length === 1 ? "" : "s"}`];
      if (result.unknown.length) parts.push(`${result.unknown.length} unknown roll no`);
      if (result.errors.length) parts.push(`${result.errors.length} failed`);
      show(result.errors.length ? "warning" : "success", `${parts.join(" · ")}.`);
    },
    [refreshAttendanceViews, show],
  );

  const actions = cls ? (
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

  const report = reportState.report;

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
            {cls ? (
              <button
                type="button"
                onClick={refreshAll}
                disabled={refreshing}
                aria-label="Refresh class"
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
              { label: "Teaching", href: "/teaching" },
              { label: cls?.title ?? (notFound ? "Not found" : "Class") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Class not found"
                description="This class may have been deleted, or the link is invalid."
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
                title="Could not load this class"
                description={error}
                action={
                  <button
                    type="button"
                    onClick={refreshAll}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" /> Try again
                  </button>
                }
              />
            ) : cls ? (
              <div className="space-y-4">
                <ClassHeader cls={cls} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Class Details">
                    <dl className="text-sm">
                      <DetailRow label="Course code" value={cls.course_code || "—"} mono />
                      <DetailRow label="Programme" value={cls.programme || "—"} />
                      <DetailRow
                        label="Semester"
                        value={cls.semester != null ? `Semester ${cls.semester}` : "—"}
                      />
                      <DetailRow label="Section" value={cls.section || "—"} />
                      <DetailRow label="Session" value={cls.session || "—"} />
                      <DetailRow
                        label="Credits"
                        value={cls.credits != null ? String(cls.credits) : "—"}
                      />
                      <DetailRow
                        label="Weekly schedule"
                        value={scheduleLine(cls.weekly_schedule) || "—"}
                      />
                      <DetailRow label="Room" value={cls.room || "—"} />
                      <DetailRow label="Tags" value={<ChipList items={cls.tags} />} />
                      <DetailRow label="Notes" value={cls.notes || "—"} />
                    </dl>
                  </Section>

                  <Section title="Teachers &amp; Departments">
                    {cls.links.teachers.length === 0 && cls.links.departments.length === 0 ? (
                      <p className="text-sm text-[var(--text-tertiary)]">
                        No teachers or departments linked yet — link the faculty Object via Edit.
                      </p>
                    ) : (
                      <dl className="space-y-3 text-sm">
                        {cls.links.teachers.length > 0 ? (
                          <div className="flex flex-col gap-1 border-b border-[var(--border-subtle)] py-2 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                            <dt className="shrink-0 text-[var(--text-tertiary)]">Teachers</dt>
                            <dd className="flex flex-wrap justify-start gap-1.5 sm:justify-end">
                              {cls.links.teachers.map((teacher) => (
                                <span
                                  key={teacher.id}
                                  className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-hover)] px-2.5 py-0.5 text-xs text-[var(--accent)]"
                                  title={`${teacher.title} (${teacher.kind})`}
                                >
                                  <Link2 className="h-3 w-3" aria-hidden="true" />
                                  {teacher.title}
                                </span>
                              ))}
                            </dd>
                          </div>
                        ) : null}
                        {cls.links.departments.length > 0 ? (
                          <div className="flex flex-col gap-1 py-2 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                            <dt className="shrink-0 text-[var(--text-tertiary)]">Departments</dt>
                            <dd className="flex flex-wrap justify-start gap-1.5 sm:justify-end">
                              {cls.links.departments.map((department) => (
                                <span
                                  key={department.id}
                                  className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-hover)] px-2.5 py-0.5 text-xs text-[var(--accent)]"
                                  title={`${department.title} (${department.kind})`}
                                >
                                  <Link2 className="h-3 w-3" aria-hidden="true" />
                                  {department.title}
                                </span>
                              ))}
                            </dd>
                          </div>
                        ) : null}
                      </dl>
                    )}
                  </Section>
                </div>

                <Section
                  title={`Roster (${rosterState.roster.length})`}
                  action={
                    <button
                      type="button"
                      onClick={() => setEnrollOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                    >
                      <UserPlus className="h-3.5 w-3.5" aria-hidden="true" /> Enroll students
                    </button>
                  }
                >
                  {rosterState.loading ? (
                    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)]">
                      <table className="w-full min-w-[680px] border-collapse text-left" aria-busy="true">
                        <thead>
                          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                            <th scope="col" className="px-4 py-2.5 font-medium">Student</th>
                            <th scope="col" className="px-4 py-2.5 font-medium">Programme</th>
                            <th scope="col" className="px-4 py-2.5 font-medium">Email</th>
                            <th scope="col" className="px-4 py-2.5 font-medium">
                              <span className="sr-only">Actions</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          <TableSkeleton rows={4} cols={4} />
                        </tbody>
                      </table>
                    </div>
                  ) : rosterState.error ? (
                    <p className="text-sm text-[var(--danger)]">{rosterState.error}</p>
                  ) : rosterState.roster.length === 0 ? (
                    <p className="text-sm text-[var(--text-tertiary)]">
                      No students enrolled yet — enroll manually or via CSV (roll numbers).
                    </p>
                  ) : (
                    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)]">
                      <table className="w-full min-w-[680px] border-collapse text-left">
                        <thead>
                          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                            <th scope="col" className="px-4 py-2.5 font-medium">Student</th>
                            <th scope="col" className="px-4 py-2.5 font-medium">Programme</th>
                            <th scope="col" className="px-4 py-2.5 font-medium">Email</th>
                            <th scope="col" className="px-4 py-2.5 font-medium">
                              <span className="sr-only">Actions</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {rosterState.roster.map((entry) => (
                            <tr
                              key={entry.student_id}
                              className="border-b border-[var(--border-subtle)] last:border-b-0"
                            >
                              <td className="px-4 py-2.5">
                                <span
                                  className="font-medium text-[var(--text-primary)]"
                                  title={entry.student_id}
                                >
                                  {entry.name}
                                </span>
                                <span className="ml-2 text-xs text-[var(--text-tertiary)]">
                                  {entry.roll_number ?? "—"}
                                </span>
                              </td>
                              <td className="px-4 py-2.5 text-sm text-[var(--text-secondary)]">
                                {[
                                  entry.programme,
                                  entry.semester != null ? `Sem ${entry.semester}` : null,
                                  entry.section ? `Sec ${entry.section}` : null,
                                ]
                                  .filter(Boolean)
                                  .join(" · ") || "—"}
                              </td>
                              <td className="px-4 py-2.5 text-sm text-[var(--text-secondary)]">
                                {entry.email ?? "—"}
                              </td>
                              <td className="px-4 py-2.5 text-right">
                                <button
                                  type="button"
                                  onClick={() => {
                                    setUnenrollError(null);
                                    setUnenrollTarget(entry);
                                  }}
                                  aria-label={`Remove ${entry.name} from the class`}
                                  className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                                >
                                  <UserMinus className="h-3.5 w-3.5" aria-hidden="true" /> Remove
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Section>

                <Section
                  title={`Assignments & Assessments (${assignmentsState.assignments.length})`}
                  action={
                    <button
                      type="button"
                      onClick={() => setAssignmentOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                    >
                      <Plus className="h-3.5 w-3.5" aria-hidden="true" /> New assignment
                    </button>
                  }
                >
                  {assignmentsState.error ? (
                    <p className="text-sm text-[var(--danger)]">{assignmentsState.error}</p>
                  ) : !assignmentsState.loading &&
                    assignmentsState.assignments.length === 0 ? (
                    <p className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
                      <ClipboardList className="h-4 w-4" aria-hidden="true" />
                      No assessments yet — create the first assignment, quiz or exam.
                    </p>
                  ) : (
                    <AssignmentTable
                      assignments={assignmentsState.assignments}
                      loading={assignmentsState.loading}
                    />
                  )}
                </Section>

                <Section
                  title="Attendance"
                  action={
                    <button
                      type="button"
                      onClick={() => {
                        setCorrecting(null);
                        setAttendanceOpen(true);
                      }}
                      disabled={rosterState.roster.length === 0}
                      title={
                        rosterState.roster.length === 0
                          ? "Enroll students first"
                          : "Record or import attendance"
                      }
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <CalendarCheck className="h-3.5 w-3.5" aria-hidden="true" /> Record attendance
                    </button>
                  }
                >
                  <div className="space-y-4">
                    {sessionsState.error ? (
                      <p className="text-sm text-[var(--danger)]">{sessionsState.error}</p>
                    ) : (
                      <AttendanceSessionTable
                        sessions={sessionsState.sessions}
                        loading={sessionsState.loading}
                        onCorrect={(session) => {
                          setCorrecting(session);
                          setAttendanceOpen(true);
                        }}
                      />
                    )}
                    {summaryState.error ? (
                      <p className="text-sm text-[var(--danger)]">{summaryState.error}</p>
                    ) : (
                      <AttendanceSummaryTable
                        summary={summaryState.summary}
                        loading={summaryState.loading}
                      />
                    )}
                  </div>
                </Section>

                <Section title="Gradebook" action={<FileBarChart className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />}>
                  {gradebookState.error ? (
                    <p className="text-sm text-[var(--danger)]">{gradebookState.error}</p>
                  ) : (
                    <GradebookTable
                      gradebook={gradebookState.gradebook}
                      loading={gradebookState.loading}
                    />
                  )}
                </Section>

                <Section title="Class Report Snapshot">
                  {reportState.loading ? (
                    <div className="space-y-2.5 py-1" aria-busy="true">
                      <div className="h-4 w-2/5 animate-pulse rounded bg-[var(--bg-hover)]" />
                      <div className="h-4 w-3/5 animate-pulse rounded bg-[var(--bg-hover)]" />
                      <div className="h-4 w-1/2 animate-pulse rounded bg-[var(--bg-hover)]" />
                      <div className="h-4 w-2/3 animate-pulse rounded bg-[var(--bg-hover)]" />
                    </div>
                  ) : reportState.error ? (
                    <p className="text-sm text-[var(--danger)]">{reportState.error}</p>
                  ) : report ? (
                    <div className="space-y-4">
                      <dl className="text-sm">
                        <DetailRow
                          label="Average marks"
                          value={
                            report.average_marks_percent != null
                              ? `${report.average_marks_percent}%`
                              : "—"
                          }
                        />
                        <DetailRow
                          label="Pending submissions"
                          value={String(report.pending_submissions)}
                        />
                        <DetailRow
                          label="Late submissions"
                          value={String(report.late_submissions)}
                        />
                        <DetailRow
                          label="Sessions held"
                          value={String(report.attendance.session_count)}
                        />
                      </dl>

                      {report.assignment_stats.length > 0 ? (
                        <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)]">
                          <table className="w-full min-w-[720px] border-collapse text-left">
                            <thead>
                              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                                <th scope="col" className="px-4 py-2.5 font-medium">Assessment</th>
                                <th scope="col" className="px-4 py-2.5 font-medium">Submitted</th>
                                <th scope="col" className="px-4 py-2.5 font-medium">Late</th>
                                <th scope="col" className="px-4 py-2.5 font-medium">Pending</th>
                                <th scope="col" className="px-4 py-2.5 font-medium">Graded</th>
                                <th scope="col" className="px-4 py-2.5 font-medium">Average</th>
                              </tr>
                            </thead>
                            <tbody>
                              {report.assignment_stats.map((stat) => (
                                <tr
                                  key={stat.assignment_id}
                                  className="border-b border-[var(--border-subtle)] last:border-b-0"
                                >
                                  <td className="px-4 py-2.5">
                                    <span className="font-medium text-[var(--text-primary)]">
                                      {stat.title}
                                    </span>
                                    <span className="ml-2 text-xs text-[var(--text-tertiary)]">
                                      {assignmentTypeLabel(stat.assignment_type)} · due{" "}
                                      {formatDeadline(stat.deadline)}
                                    </span>
                                  </td>
                                  <td className="px-4 py-2.5 text-sm text-[var(--text-secondary)]">
                                    {stat.submitted}
                                  </td>
                                  <td className="px-4 py-2.5 text-sm text-[var(--text-secondary)]">
                                    {stat.late}
                                  </td>
                                  <td className="px-4 py-2.5 text-sm text-[var(--text-secondary)]">
                                    {stat.pending}
                                  </td>
                                  <td className="px-4 py-2.5 text-sm text-[var(--text-secondary)]">
                                    {stat.graded}
                                  </td>
                                  <td className="px-4 py-2.5 text-sm font-medium text-[var(--text-primary)]">
                                    {stat.average_marks != null
                                      ? `${stat.average_marks}${stat.max_marks != null ? ` /${stat.max_marks}` : ""}`
                                      : "—"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : null}

                      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                        <div>
                          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--danger)]">
                            Weak students ({report.weak_students.length})
                          </h3>
                          {report.weak_students.length === 0 ? (
                            <p className="text-sm text-[var(--text-tertiary)]">
                              Nobody is below the marks/attendance thresholds.
                            </p>
                          ) : (
                            <ul className="space-y-1.5 text-sm">
                              {report.weak_students.map((signal) => (
                                <li
                                  key={signal.student_id}
                                  className="flex items-center justify-between gap-2"
                                >
                                  <span className="min-w-0">
                                    <span className="font-medium text-[var(--text-primary)]">
                                      {signal.name}
                                    </span>
                                    <span className="ml-2 text-xs text-[var(--text-tertiary)]">
                                      {signal.reasons?.join(" · ") ?? ""}
                                    </span>
                                  </span>
                                  <span className="text-sm font-semibold text-[var(--text-primary)]">
                                    {signal.average_marks_percent}%
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                        <div>
                          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--success)]">
                            Top performers ({report.top_performers.length})
                          </h3>
                          {report.top_performers.length === 0 ? (
                            <p className="text-sm text-[var(--text-tertiary)]">
                              Top performers appear once marks are graded (≥ 85% average).
                            </p>
                          ) : (
                            <ul className="space-y-1.5 text-sm">
                              {report.top_performers.map((signal) => (
                                <li
                                  key={signal.student_id}
                                  className="flex items-center justify-between gap-2"
                                >
                                  <span className="font-medium text-[var(--text-primary)]">
                                    {signal.name}
                                  </span>
                                  <span className="text-sm font-semibold text-[var(--text-primary)]">
                                    {signal.average_marks_percent}%
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </Section>
              </div>
            ) : null}
          </div>
        </main>
      </div>

      {cls ? (
        <>
          <ClassModal
            open={editOpen}
            cls={cls}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <EnrollModal
            open={enrollOpen}
            classId={cls.id}
            enrolledIds={enrolledIds}
            onClose={() => setEnrollOpen(false)}
            onEnrolled={handleEnrolled}
          />
          <AssignmentModal
            open={assignmentOpen}
            classId={cls.id}
            onClose={() => setAssignmentOpen(false)}
            onSaved={handleAssignmentSaved}
          />
          <AttendanceModal
            open={attendanceOpen}
            classId={cls.id}
            roster={rosterState.roster}
            session={correcting}
            onClose={() => {
              setAttendanceOpen(false);
              setCorrecting(null);
            }}
            onRecorded={handleAttendanceRecorded}
            onImported={handleAttendanceImported}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete class?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">“{cls.title}”</span> will
                be permanently removed, together with its assignments, submissions (including
                uploaded files) and attendance sessions. Students are unenrolled but stay in the
                registry. This action cannot be undone.
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
          <ConfirmDialog
            open={unenrollTarget !== null}
            title="Remove student from class?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{unenrollTarget?.name}”
                </span>{" "}
                will be unenrolled from <span className="font-medium">“{cls.title}”</span>.
                Recorded submissions, marks and attendance stay as evidence.
              </>
            }
            confirmLabel="Remove"
            loadingLabel="Removing…"
            loading={unenrolling}
            error={unenrollError}
            onConfirm={handleUnenroll}
            onCancel={() => {
              if (!unenrolling) {
                setUnenrollTarget(null);
                setUnenrollError(null);
              }
            }}
          />
        </>
      ) : null}

      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
