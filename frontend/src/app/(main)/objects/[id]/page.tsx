"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Clock,
  Activity as ActivityIcon,
  Network,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { ObjectHeader } from "@/components/features/objects/ObjectHeader";
import { ObjectMetadata } from "@/components/features/objects/ObjectMetadata";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  CreateObjectModal,
  type ObjectSaveResult,
} from "@/components/features/objects/CreateObjectModal";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, SectionPlaceholder, DetailRow } from "@/components/features/objects/DetailSection";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useObject } from "@/hooks/useObject";
import { deleteObject } from "@/lib/api/objects";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDateTime, titleCase } from "@/lib/utils";

/**
 * Next.js hands the dynamic segment back percent-encoded (`obj%3Acourse%3A…`).
 * This is the ONE and ONLY decode in the whole flow — the hook and the API
 * layer forward the decoded id untouched, so the backend receives
 * `obj:course:…` exactly as `ObjectId.parse` expects.
 */
function decodeRouteId(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value; // malformed escape sequence — use the raw segment
  }
}

export default function ObjectDetailsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const objectId = decodeRouteId(params?.id);

  const { object, loading, refreshing, error, notFound, refresh } = useObject(objectId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleSaved = useCallback(
    (result: ObjectSaveResult) => {
      setEditOpen(false);
      refresh();
      if (result.warning) show("warning", result.warning);
      else show("success", "Object updated successfully.");
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!object || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteObject(object.id);
      // The toast must outlive this page, so hand it to /objects.
      setFlash({ kind: "success", message: `“${object.title}” was deleted.` });
      setConfirmOpen(false);
      router.push("/objects");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this object."));
      setDeleting(false);
    }
  }, [object, deleting, router]);

  const actions = object ? (
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
            {object ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh object"
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
              { label: "Objects", href: "/objects" },
              { label: object?.title ?? (notFound ? "Not found" : "Object") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Object not found"
                description="This object may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/objects")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Objects
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this object"
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
            ) : object ? (
              <div className="space-y-4">
                <ObjectHeader object={object} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Overview">
                    <dl className="text-sm">
                      <DetailRow label="Object ID" value={object.id} mono />
                      <DetailRow label="Type" value={titleCase(object.object_type)} />
                      <DetailRow label="Title" value={object.title} />
                      <DetailRow label="Status" value={titleCase(object.status)} />
                      <DetailRow
                        label="Department"
                        value={object.metadata?.department || "Not set"}
                      />
                    </dl>
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Created by" value={object.created_by || "—"} />
                      <DetailRow label="Created at" value={formatDateTime(object.created_at)} />
                      <DetailRow
                        label="Last updated"
                        value={
                          <span className="text-[var(--text-tertiary)]">
                            Not exposed by the API
                          </span>
                        }
                      />
                      <DetailRow label="Current version" value={`v${object.version}`} />
                    </dl>
                  </Section>

                  <Section title="Metadata" className="lg:col-span-2">
                    <ObjectMetadata object={object} />
                  </Section>

                  <Section title="Version">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                        v{object.version}
                      </span>
                      <span className="text-sm text-[var(--text-tertiary)]">current revision</span>
                    </div>
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">
                      The version increments on every status or metadata change. Version history
                      browsing requires a backend snapshots endpoint.
                    </p>
                  </Section>

                  <Section title="Timeline">
                    <ol className="space-y-3 text-sm">
                      <li className="flex gap-3">
                        <Clock
                          className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-tertiary)]"
                          aria-hidden="true"
                        />
                        <div>
                          <p className="text-[var(--text-primary)]">Object created</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(object.created_at)} · {object.created_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(object.events ?? []).map((event, index) => (
                        <li key={`${event}-${index}`} className="flex gap-3">
                          <ActivityIcon
                            className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-tertiary)]"
                            aria-hidden="true"
                          />
                          <p className="text-[var(--text-primary)]">{titleCase(event)}</p>
                        </li>
                      ))}
                    </ol>
                    <p className="mt-3 text-xs text-[var(--text-tertiary)]">
                      Full event history requires a domain-events endpoint.
                    </p>
                  </Section>

                  <SectionPlaceholder
                    title="Relationships"
                    description="Typed graph edges (authored_by, belongs_to, cites…) will appear here once the API exposes an object's relationships."
                    icon={<Network className="h-4 w-4" aria-hidden="true" />}
                  />
                  <Section title="Documents">
                    <ObjectDocuments objectId={object.id} />
                  </Section>
                  <SectionPlaceholder
                    title="Activity"
                    description="Who changed what, and when — available once the audit-log endpoint is implemented."
                    icon={<ActivityIcon className="h-4 w-4" aria-hidden="true" />}
                  />
                </div>
              </div>
            ) : null}
          </div>
        </main>
      </div>

      {object ? (
        <>
          <CreateObjectModal
            open={editOpen}
            object={object}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete object?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">“{object.title}”</span>{" "}
                will be permanently removed. This action cannot be undone.
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
