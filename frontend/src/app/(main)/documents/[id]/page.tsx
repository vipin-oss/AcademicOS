"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Clock,
  Activity as ActivityIcon,
  Download,
  HardDrive,
  Link2,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { DocumentHeader } from "@/components/features/documents/DocumentHeader";
import { DocumentMetadata } from "@/components/features/documents/DocumentMetadata";
import { CitationPanel } from "@/components/features/documents/CitationPanel";
import { KgLinks } from "@/components/features/documents/KgLinks";
import { DocumentPreview } from "@/components/features/documents/DocumentPreview";
import { DocumentViewer } from "@/components/features/documents/DocumentViewer";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  UploadModal,
  type DocumentSaveResult,
} from "@/components/features/documents/UploadModal";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, SectionPlaceholder, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useDocument } from "@/hooks/useDocument";
import { deleteDocument } from "@/lib/api/documents";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDateTime, titleCase } from "@/lib/utils";
import { formatFileSize } from "@/lib/documents/constants";

/**
 * Next.js hands the dynamic segment back percent-encoded. This is the ONE and
 * ONLY decode in the whole flow — the hook and the API layer forward the
 * decoded id untouched, so the backend receives `doc:pdf:…` exactly as
 * `ObjectId.parse` (or its document equivalent) expects.
 */
function decodeRouteId(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value; // malformed escape sequence — use the raw segment
  }
}

export default function DocumentDetailsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const documentId = decodeRouteId(params?.id);

  const { document, loading, refreshing, error, notFound, refresh } = useDocument(documentId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleSaved = useCallback(
    (result: DocumentSaveResult) => {
      setEditOpen(false);
      refresh();
      if (result.warning) show("warning", result.warning);
      else show("success", "Document updated successfully.");
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!document || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteDocument(document.id);
      setFlash({ kind: "success", message: `“${document.title}” was deleted.` });
      setConfirmOpen(false);
      router.push("/documents");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this document."));
      setDeleting(false);
    }
  }, [document, deleting, router]);

  const objectHref = document?.object_id
    ? `/objects/${encodeURIComponent(document.object_id)}`
    : null;

  const actions = document ? (
    <>
      {document.url ? (
        <a
          href={document.url}
          download={document.file_name || document.title}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <Download className="h-4 w-4" aria-hidden="true" /> Download
        </a>
      ) : null}
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
            {document ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh document"
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
              { label: "Documents", href: "/documents" },
              { label: document?.title ?? (notFound ? "Not found" : "Document") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Document not found"
                description="This document may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/documents")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Documents
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this document"
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
            ) : document ? (
              <div className="space-y-4">
                <DocumentHeader document={document} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Overview">
                    <dl className="text-sm">
                      <DetailRow label="Document ID" value={document.id} mono />
                      <DetailRow label="Type" value={titleCase(document.document_type)} />
                      <DetailRow label="Title" value={document.title} />
                      <DetailRow label="Status" value={titleCase(document.status)} />
                      <DetailRow label="Uploaded by" value={document.uploaded_by || "—"} />
                    </dl>
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Uploaded by" value={document.uploaded_by || "—"} />
                      <DetailRow label="Uploaded at" value={formatDateTime(document.created_at)} />
                      <DetailRow
                        label="Last updated"
                        value={
                          document.updated_at ? (
                            formatDateTime(document.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not exposed by the API</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${document.version}`} />
                    </dl>
                  </Section>

                  <Section title="Metadata" className="lg:col-span-2">
                    <DocumentMetadata document={document} />
                  </Section>

                  <Section title="Linked Object">
                    {objectHref ? (
                      <a
                        href={objectHref}
                        className="inline-flex items-center gap-1.5 text-sm text-[var(--accent)] hover:underline"
                        title={document.object_title ?? document.object_id ?? undefined}
                      >
                        <Link2 className="h-4 w-4" aria-hidden="true" />
                        {document.object_title ?? document.object_id ?? "—"}
                      </a>
                    ) : (
                      <p className="text-sm text-[var(--text-tertiary)]">
                        Not linked to any object.
                      </p>
                    )}
                  </Section>

                  <Section title="File Information">
                    <dl className="text-sm">
                      <DetailRow label="File name" value={document.file_name || "—"} />
                      <DetailRow label="Size" value={formatFileSize(document.file_size)} />
                      <DetailRow
                        label="MIME type"
                        value={document.mime_type || document.document_type}
                      />
                      <DetailRow label="Type" value={titleCase(document.document_type)} />
                    </dl>
                  </Section>

                  <Section title="Version History">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-2xl font-semibold text-[var(--text-primary)]">
                        v{document.version}
                      </span>
                      <span className="text-sm text-[var(--text-tertiary)]">current revision</span>
                    </div>
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">
                      The version increments on every change. Browsing past revisions requires a
                      backend snapshots endpoint.
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
                          <p className="text-[var(--text-primary)]">Document uploaded</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(document.created_at)} · {document.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(document.events ?? []).map((event, index) => (
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
                    title="Activity"
                    description="Who changed what, and when — available once the audit-log endpoint is implemented."
                    icon={<ActivityIcon className="h-4 w-4" aria-hidden="true" />}
                  />
                </div>

                <Section title="Preview">
                  <DocumentViewer document={document} />
                </Section>

                <CitationPanel document={document} currentPage={1} selection="" />
                <KgLinks document={document} />
              </div>
            ) : null}
          </div>
        </main>
      </div>

      {document ? (
        <>
          <UploadModal
            open={editOpen}
            document={document}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete document?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">“{document.title}”</span>{" "}
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
