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
import { CommitteeHeader } from "@/components/features/committees/CommitteeHeader";
import { MembersPanel } from "@/components/features/committees/MembersPanel";
import { MeetingsPanel } from "@/components/features/committees/MeetingsPanel";
import { LinkedLinksPanel } from "@/components/features/committees/LinkedLinksPanel";
import {
  CommitteeModal,
  type CommitteeSaveResult,
} from "@/components/features/committees/CommitteeModal";
import {
  MeetingModal,
  type MeetingSaveResult,
} from "@/components/features/committees/MeetingModal";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { ChipList } from "@/components/features/publications/PublicationBadge";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useCommittee } from "@/hooks/useCommittee";
import { deleteCommittee } from "@/lib/api/committees";
import { toErrorMessage } from "@/lib/api/client";
import { consumeFlash, setFlash } from "@/lib/objects/flash";
import { formatDateTime, titleCase } from "@/lib/utils";

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

/** The committee workspace: header, members, meetings, links and lenses. */
export default function CommitteeWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const committeeId = decodeRouteId(params?.id);

  const {
    committee,
    loading,
    refreshing,
    error,
    notFound,
    applyUpdate,
    refresh,
  } = useCommittee(committeeId);
  const { toast, show, dismiss } = useToast();

  // Pick up a message handed over by another page (e.g. "meeting deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const [editOpen, setEditOpen] = useState(false);
  const [meetingOpen, setMeetingOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleSaved = useCallback(
    (result: CommitteeSaveResult) => {
      setEditOpen(false);
      applyUpdate(result.committee);
      show("success", "Committee updated successfully.");
    },
    [applyUpdate, show],
  );

  const handleMeetingSaved = useCallback(
    (result: MeetingSaveResult) => {
      setMeetingOpen(false);
      refresh(); // the meetings list + stats derive from the meeting objects
      show(
        "success",
        `“${result.meeting.title}” ${result.mode === "edit" ? "updated" : "scheduled"} successfully.`,
      );
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!committee || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteCommittee(committee.id);
      setFlash({ kind: "success", message: `“${committee.name}” was deleted.` });
      setConfirmOpen(false);
      router.push("/committees");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this committee."));
      setDeleting(false);
    }
  }, [committee, deleting, router]);

  const actions = committee ? (
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
            {committee ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh committee"
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
              { label: committee?.name ?? (notFound ? "Not found" : "Committee") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Committee not found"
                description="This committee may have been deleted, or the link is invalid."
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
                title="Could not load this committee"
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
            ) : committee ? (
              <div className="space-y-4">
                <CommitteeHeader committee={committee} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Committee Record">
                    <dl className="text-sm">
                      <DetailRow label="Code" value={committee.committee_code || "—"} />
                      <DetailRow label="School" value={committee.school || "—"} />
                      <DetailRow
                        label="Meetings"
                        value={String(committee.stats?.meetings ?? 0)}
                      />
                      <DetailRow
                        label="Pending actions"
                        value={String(committee.stats?.pending_actions ?? 0)}
                      />
                      <DetailRow
                        label="Completed actions"
                        value={String(committee.stats?.completed_actions ?? 0)}
                      />
                      <DetailRow
                        label="Tags"
                        value={<ChipList items={committee.tags} />}
                      />
                      <DetailRow label="Notes" value={committee.notes || "—"} />
                    </dl>
                  </Section>

                  <MembersPanel
                    members={committee.members ?? []}
                    onManage={() => setEditOpen(true)}
                  />

                  <MeetingsPanel
                    meetings={committee.meetings ?? []}
                    onAdd={() => setMeetingOpen(true)}
                  />

                  <LinkedLinksPanel links={committee.links ?? {}} />

                  <Section title="Documents">
                    <ObjectDocuments objectId={committee.id} />
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Committee ID" value={committee.id} mono />
                      <DetailRow label="Added by" value={committee.uploaded_by || "—"} />
                      <DetailRow
                        label="Added at"
                        value={formatDateTime(committee.created_at)}
                      />
                      <DetailRow
                        label="Last updated"
                        value={
                          committee.updated_at ? (
                            formatDateTime(committee.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${committee.version}`} />
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
                          <p className="text-[var(--text-primary)]">Committee created</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(committee.created_at)} ·{" "}
                            {committee.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(committee.events ?? []).map((event, index) => (
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

      {committee ? (
        <>
          <CommitteeModal
            open={editOpen}
            committee={committee}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <MeetingModal
            open={meetingOpen}
            committeeId={committee.id}
            onClose={() => setMeetingOpen(false)}
            onSaved={handleMeetingSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete committee?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{committee.name}”
                </span>{" "}
                will be permanently removed together with its meetings and action items.
                Members, linked projects and documents are kept. This action cannot be undone.
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
