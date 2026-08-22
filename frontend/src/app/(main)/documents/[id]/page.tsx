"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Clock,
  Download,
  Pencil,
  RefreshCw,
  Trash2,
  Loader2,
  AlertCircle,
  Calendar,
  BookOpen,
  FlaskConical,
  Users,
  FileText,
  ExternalLink,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { DocumentHeader } from "@/components/features/documents/DocumentHeader";
import { DocumentMetadata } from "@/components/features/documents/DocumentMetadata";
import { DocumentViewer } from "@/components/features/documents/DocumentViewer";
import { DocumentAnalysisResult } from "@/components/features/documents/DocumentAnalysisResult";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  UploadModal,
  type DocumentSaveResult,
} from "@/components/features/documents/UploadModal";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useDocument } from "@/hooks/useDocument";
import { useDocumentDownload } from "@/hooks/useDocumentDownload";
import { useAnalysisPolling } from "@/hooks/useAnalysisPolling";
import { usePendingReview } from "@/hooks/usePendingReview";
import { PendingReviewSection } from "@/components/features/documents/PendingReviewSection";
import { deleteDocument } from "@/lib/api/documents";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDateTime, titleCase } from "@/lib/utils";
import { formatFileSize } from "@/lib/documents/constants";

function decodeRouteId(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
  try { return decodeURIComponent(value); } catch { return value; }
}

export default function DocumentDetailsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const documentId = decodeRouteId(params?.id);

  const { document, loading, refreshing, error, notFound, refresh } = useDocument(documentId);
  const { toast, show, dismiss } = useToast();
  const { download, downloadingId, error: downloadError } = useDocumentDownload();

  const {
    items: pendingReviewItems,
    totalPending,
    loading: pendingReviewLoading,
    refresh: refreshPendingReview,
  } = usePendingReview(documentId);

  const { analysis, enrichmentStatus, retry: retryEnrichment } = useAnalysisPolling({ documentId, enabled: !!document });

  // Fetch related records (events, publications, etc. linked to this document)
  const [relatedRecords, setRelatedRecords] = useState<Array<{ document_id: string; title: string; object_type: string; relationship_kind: string }>>([]);
  useEffect(() => {
    if (!documentId) return;
    fetch(`/api/v1/documents/${documentId}/related`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : { related: [] })
      .then((d) => setRelatedRecords(d.related || []))
      .catch(() => setRelatedRecords([]));
  }, [documentId]);

  useEffect(() => { if (downloadError) show("error", downloadError); }, [downloadError, show]);

  const [viewerPage, setViewerPage] = useState(1);
  const [editOpen, setEditOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleSaved = useCallback((result: DocumentSaveResult) => {
    setEditOpen(false);
    refresh();
    if (result.warning) show("warning", result.warning);
    else show("success", "Document updated.");
  }, [refresh, show]);

  const handleDelete = useCallback(async () => {
    if (!document || deleting) return;
    setDeleting(true); setDeleteError(null);
    try {
      await deleteDocument(document.id);
      setFlash({ kind: "success", message: `"${document.title}" deleted.` });
      setConfirmOpen(false); router.push("/documents"); router.refresh();
    } catch (err) { setDeleteError(toErrorMessage(err, "Failed to delete.")); setDeleting(false); }
  }, [document, deleting, router]);

  const actions = document ? (
    <>
      {document.url ? (
        <button type="button" onClick={(e) => { e.stopPropagation(); void download(document); }}
          disabled={downloadingId === document.id}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50">
          {downloadingId === document.id ? <Spinner className="h-4 w-4" /> : <Download className="h-4 w-4" />}
          {downloadingId === document.id ? "Downloading..." : "Download"}
        </button>
      ) : null}
      <button type="button" onClick={() => setEditOpen(true)} disabled={deleting}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50">
        <Pencil className="h-4 w-4" /> Edit
      </button>
      <button type="button" onClick={() => { setDeleteError(null); setConfirmOpen(true); }} disabled={deleting}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger)] px-3 py-2 text-sm font-medium text-[var(--danger)] hover:bg-[var(--danger-subtle)] disabled:opacity-50">
        {deleting ? <Spinner /> : <Trash2 className="h-4 w-4" />}
        {deleting ? "Deleting..." : "Delete"}
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
            <button type="button" onClick={() => router.back()}
              className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--accent)]">
              <ArrowLeft className="h-4 w-4" /> Back
            </button>
            {document ? (
              <button type="button" onClick={refresh} disabled={refreshing}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50">
                <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
                {refreshing ? "Refreshing..." : "Refresh"}
              </button>
            ) : null}
          </div>

          <Breadcrumbs items={[
            { label: "Dashboard", href: "/" },
            { label: "Documents", href: "/documents" },
            { label: document?.title ?? (notFound ? "Not found" : "Document") },
          ]} />

          <div className="mt-4">
            {loading ? <DetailSkeleton /> : notFound ? (
              <EmptyState title="Document not found"
                description="This document may have been deleted, or the link is invalid."
                action={<button type="button" onClick={() => router.push("/documents")}
                  className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]">Back to Documents</button>} />
            ) : error ? (
              <EmptyState title="Could not load this document" description={error}
                action={<button type="button" onClick={refresh}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]">
                  <RefreshCw className="h-4 w-4" /> Try again</button>} />
            ) : document ? (
              <div className="space-y-4">
                <DocumentHeader document={document} actions={actions} />

                {/* Pending review — most important, shown first */}
                {(totalPending > 0 || pendingReviewLoading) && (
                  <PendingReviewSection
                    documentId={document.id}
                    documentTitle={document.title}
                    items={pendingReviewItems}
                    loading={pendingReviewLoading}
                    onItemResolved={() => { refreshPendingReview(); refresh(); }}
                  />
                )}

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  {/* Document info — consolidated */}
                  <Section title="Document Information">
                    <dl className="text-sm">
                      <DetailRow label="Title" value={document.title} />
                      <DetailRow label="Type" value={titleCase(document.document_type)} />
                      <DetailRow label="Status" value={titleCase(document.status)} />
                      <DetailRow label="Uploaded" value={`${formatDateTime(document.created_at)} by ${document.uploaded_by || "unknown"}`} />
                      <DetailRow label="File" value={`${document.file_name || "—"} (${formatFileSize(document.file_size)})`} />
                    </dl>
                  </Section>

                  {/* AI Analysis */}
                  <Section title="AI Analysis">
                    <DocumentAnalysisResult
                      analysis={analysis}
                      analyzing={enrichmentStatus === "running"}
                      fileName={document.file_name}
                      documentId={document.id}
                      onRetryEnrichment={retryEnrichment}
                    />
                    {!analysis && enrichmentStatus === "not_started" && (
                      <p className="text-sm text-[var(--text-tertiary)]">
                        Analysis will start automatically in the background.
                      </p>
                    )}
                  </Section>

                  {/* Linked Records */}
                  <Section title="Linked Records">
                    {(() => {
                      // Combine direct link + relationship links
                      const allLinks: Array<{ id: string; title: string; type: string }> = [];

                      // Direct link (document.object_id)
                      if (document.object_id) {
                        allLinks.push({
                          id: document.object_id,
                          title: document.object_title || document.object_id,
                          type: document.object_type || "record",
                        });
                      }

                      // Relationship links
                      for (const rel of relatedRecords) {
                        if (!allLinks.some((l) => l.id === rel.document_id)) {
                          allLinks.push({
                            id: rel.document_id,
                            title: rel.title || rel.document_id,
                            type: rel.object_type || "record",
                          });
                        }
                      }

                      if (allLinks.length === 0) {
                        return (
                          <p className="text-sm text-[var(--text-tertiary)] italic">
                            No academic record linked yet.
                          </p>
                        );
                      }

                      const typeIcons: Record<string, typeof FileText> = {
                        event: Calendar,
                        publication: BookOpen,
                        research_project: FlaskConical,
                        committee: Users,
                        student: Users,
                      };

                      const typeLabels: Record<string, string> = {
                        event: "Conference / Event",
                        publication: "Publication",
                        research_project: "Research Project",
                        committee: "Committee",
                        student: "Student",
                      };

                      const typePaths: Record<string, string> = {
                        event: "/events/",
                        publication: "/publications/",
                        research_project: "/research/projects/",
                        committee: "/committees/",
                        student: "/students/",
                      };

                      return (
                        <div className="space-y-2">
                          {allLinks.map((link) => {
                            const Icon = typeIcons[link.type] || FileText;
                            const label = typeLabels[link.type] || link.type;
                            const path = typePaths[link.type] || "/objects/";
                            return (
                              <Link
                                key={link.id}
                                href={`${path}${encodeURIComponent(link.id)}`}
                                className="flex items-center gap-3 rounded-lg border border-[var(--border-subtle)] p-3 transition-colors hover:border-[var(--accent)] hover:bg-[var(--bg-hover)]"
                              >
                                <Icon className="h-4 w-4 text-[var(--text-tertiary)] shrink-0" />
                                <div className="min-w-0 flex-1">
                                  <p className="text-xs text-[var(--text-tertiary)]">{label}</p>
                                  <p className="text-sm font-medium text-[var(--text-primary)] truncate">{link.title}</p>
                                </div>
                                <ExternalLink className="h-4 w-4 text-[var(--text-tertiary)] shrink-0" />
                              </Link>
                            );
                          })}
                        </div>
                      );
                    })()}
                  </Section>

                  {/* Metadata */}
                  <Section title="Details" className="lg:col-span-2">
                    <DocumentMetadata document={document} />
                  </Section>
                </div>

                {/* Preview */}
                <Section title="Preview">
                  <DocumentViewer document={document} onPageChange={setViewerPage} />
                </Section>
              </div>
            ) : null}
          </div>
        </main>
      </div>

      {document ? (
        <>
          <UploadModal open={editOpen} document={document} onClose={() => setEditOpen(false)} onSaved={handleSaved} />
          <ConfirmDialog open={confirmOpen} title="Delete document?"
            description={<><span className="font-medium">{document.title}</span> will be permanently removed.</>}
            confirmLabel="Delete" loadingLabel="Deleting..." loading={deleting} error={deleteError}
            onConfirm={handleDelete}
            onCancel={() => { if (!deleting) { setConfirmOpen(false); setDeleteError(null); } }} />
        </>
      ) : null}

      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
