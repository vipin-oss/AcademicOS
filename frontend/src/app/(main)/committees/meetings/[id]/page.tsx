"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  Clock,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { AgendaPanel } from "@/components/features/committees/AgendaPanel";
import { AttendancePanel } from "@/components/features/committees/AttendancePanel";
import { MinutesDecisionsPanel } from "@/components/features/committees/MinutesDecisionsPanel";
import { ActionTrackerPanel } from "@/components/features/committees/ActionTrackerPanel";
import {
  ActionItemModal,
  type ActionItemSaveResult,
} from "@/components/features/committees/ActionItemModal";
import {
  MeetingModal,
  type MeetingSaveResult,
} from "@/components/features/committees/MeetingModal";
import { MeetingModeBadge } from "@/components/features/committees/CommitteeBadges";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useMeeting } from "@/hooks/useMeeting";
import { getCommittee, deleteMeeting } from "@/lib/api/committees";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDate, formatDateTime, titleCase } from "@/lib/utils";
import type { ActionItem, CommitteeMember, MeetingResponse } from "@/types";

/**
 * Next.js hands the dynamic segment back percent-encoded. This is the ONE and
 * ONLY decode in the whole flow — the hook and the API layer forward the
 * decoded id untouched (same encoding contract as every module).
 */
function decodeRouteId(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value; // malformed escape sequence — use the raw segment
  }
}

/** The meeting workspace: agenda, attendance, minutes, action tracker. */
export default function MeetingWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const meetingId = decodeRouteId(params?.id);

  const {
    meeting,
    loading,
    refreshing,
    error,
    notFound,
    applyUpdate,
    refresh,
  } = useMeeting(meetingId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [actionOpen, setActionOpen] = useState(false);
  const [editingAction, setEditingAction] = useState<ActionItem | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  // Attendance options come from the parent committee's members roster.
  const [committeeMembers, setCommitteeMembers] = useState<CommitteeMember[]>([]);

  useEffect(() => {
    const committeeId = meeting?.committee?.id;
    if (!committeeId) {
      setCommitteeMembers([]);
      return;
    }
    const controller = new AbortController();
    getCommittee(committeeId, { signal: controller.signal })
      .then((response) => setCommitteeMembers(response.members ?? []))
      .catch(() => setCommitteeMembers([]));
    return () => controller.abort();
  }, [meeting?.committee?.id]);

  const handleMeetingSaved = useCallback(
    (result: MeetingSaveResult) => {
      setEditOpen(false);
      applyUpdate(result.meeting);
      show("success", "Meeting updated successfully.");
    },
    [applyUpdate, show],
  );

  const handleActionSaved = useCallback(
    (_result: ActionItemSaveResult) => {
      setActionOpen(false);
      setEditingAction(null);
      refresh(); // the tracker list + stats derive from the action objects
      show(
        "success",
        `Action item ${_result.mode === "edit" ? "updated" : "added"} successfully.`,
      );
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!meeting || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteMeeting(meeting.id);
      setFlash({ kind: "success", message: `“${meeting.title}” was deleted.` });
      setConfirmOpen(false);
      if (meeting.committee?.id) {
        router.push(`/committees/${encodeURIComponent(meeting.committee.id)}`);
      } else {
        router.push("/committees");
      }
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this meeting."));
      setDeleting(false);
    }
  }, [meeting, deleting, router]);

  const handlePanelSaved = useCallback(
    (updated: MeetingResponse) => {
      applyUpdate(updated);
      show("success", "Meeting saved successfully.");
    },
    [applyUpdate, show],
  );

  const handlePanelError = useCallback(
    (message: string) => show("error", message),
    [show],
  );

  const actions = meeting ? (
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
              onClick={() => {
                if (meeting?.committee?.id) {
                  router.push(`/committees/${encodeURIComponent(meeting.committee.id)}`);
                } else {
                  router.back();
                }
              }}
              className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--accent)]"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />{" "}
              {meeting?.committee ? "Back to committee" : "Back"}
            </button>
            {meeting ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh meeting"
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
              { label: "Committees", href: "/committees" },
              ...(meeting?.committee
                ? [
                    {
                      label: meeting.committee.title,
                      href: `/committees/${encodeURIComponent(meeting.committee.id)}`,
                    },
                  ]
                : []),
              { label: meeting?.title ?? (notFound ? "Not found" : "Meeting") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Meeting not found"
                description="This meeting may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/committees")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Committees
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this meeting"
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
            ) : meeting ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                          {meeting.title}
                        </h2>
                        {meeting.mode ? <MeetingModeBadge mode={meeting.mode} /> : null}
                      </div>
                      <p className="mt-1 text-sm text-[var(--text-secondary)]">
                        {[
                          meeting.meeting_number ? `Meeting no. ${meeting.meeting_number}` : null,
                          meeting.meeting_date ? formatDate(meeting.meeting_date) : "No date set",
                          meeting.venue,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                        {[
                          `Agenda items: ${meeting.stats?.agenda_items ?? 0}`,
                          `Pending actions: ${meeting.stats?.pending_actions ?? 0}`,
                          `Completed actions: ${meeting.stats?.completed_actions ?? 0}`,
                        ].join(" · ")}
                      </p>
                      {meeting.remarks ? (
                        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                          {meeting.remarks}
                        </p>
                      ) : null}
                    </div>
                    {actions ? (
                      <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
                    ) : null}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                  <AgendaPanel meeting={meeting} onSaved={handlePanelSaved} onError={handlePanelError} />
                  <AttendancePanel
                    meeting={meeting}
                    members={committeeMembers}
                    onSaved={handlePanelSaved}
                    onError={handlePanelError}
                  />
                  <MinutesDecisionsPanel
                    meeting={meeting}
                    onSaved={handlePanelSaved}
                    onError={handlePanelError}
                  />
                  <ActionTrackerPanel
                    meeting={meeting}
                    onAdd={() => {
                      setEditingAction(null);
                      setActionOpen(true);
                    }}
                    onEdit={(action) => {
                      setEditingAction(action);
                      setActionOpen(true);
                    }}
                    onChanged={refresh}
                    onError={handlePanelError}
                  />
                  <Section title="Documents">
                    <ObjectDocuments objectId={meeting.id} />
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Meeting ID" value={meeting.id} mono />
                      <DetailRow label="Added by" value={meeting.uploaded_by || "—"} />
                      <DetailRow label="Added at" value={formatDateTime(meeting.created_at)} />
                      <DetailRow
                        label="Last updated"
                        value={
                          meeting.updated_at ? (
                            formatDateTime(meeting.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${meeting.version}`} />
                    </dl>
                  </Section>

                  <Section title="Audit Timeline">
                    <ol className="space-y-3 text-sm">
                      <li className="flex gap-3">
                        <Clock
                          className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-tertiary)]"
                          aria-hidden="true"
                        />
                        <div>
                          <p className="text-[var(--text-primary)]">Meeting created</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(meeting.created_at)} ·{" "}
                            {meeting.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(meeting.events ?? []).map((event, index) => (
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

      {meeting ? (
        <>
          <MeetingModal
            open={editOpen}
            meeting={meeting}
            onClose={() => setEditOpen(false)}
            onSaved={handleMeetingSaved}
          />
          <ActionItemModal
            open={actionOpen}
            meetingId={meeting.id}
            action={editingAction}
            onClose={() => {
              setActionOpen(false);
              setEditingAction(null);
            }}
            onSaved={handleActionSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete meeting?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{meeting.title}”
                </span>{" "}
                will be permanently removed together with its action items. The committee and
                its documents are kept. This action cannot be undone.
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
