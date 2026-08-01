"use client";

import { useCallback, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  Clock,
  Download,
  ExternalLink,
  FileUp,
  Pencil,
  Quote,
  RefreshCw,
  Star,
  Trash2,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { PublicationHeader } from "@/components/features/publications/PublicationHeader";
import { PublicationLinks } from "@/components/features/publications/PublicationLinks";
import { CitationPanel } from "@/components/features/publications/CitationPanel";
import {
  PublicationModal,
  type PublicationSaveResult,
} from "@/components/features/publications/PublicationModal";
import {
  ChipList,
  IndexingChips,
  QuartileBadge,
} from "@/components/features/publications/PublicationBadge";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { usePublication } from "@/hooks/usePublication";
import { attachPublicationPdf, deletePublication } from "@/lib/api/publications";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDate, formatDateTime, titleCase } from "@/lib/utils";
import { formatFileSize } from "@/lib/documents/constants";
import { DOI_URL, ORCID_URL } from "@/lib/publications/constants";

/**
 * Next.js hands the dynamic segment back percent-encoded. This is the ONE and
 * ONLY decode in the whole flow — the hook and the API layer forward the
 * decoded id untouched (mirrors the Documents detail page).
 */
function decodeRouteId(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value; // malformed escape sequence — use the raw segment
  }
}

export default function PublicationDetailsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const publicationId = decodeRouteId(params?.id);

  const { publication, loading, refreshing, error, notFound, refresh } =
    usePublication(publicationId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const pdfInputRef = useRef<HTMLInputElement>(null);
  const [pdfProgress, setPdfProgress] = useState<number | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const attaching = pdfProgress !== null;

  const handleSaved = useCallback(
    (result: PublicationSaveResult) => {
      setEditOpen(false);
      refresh();
      show("success", "Publication updated successfully.");
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!publication || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deletePublication(publication.id);
      setFlash({ kind: "success", message: `“${publication.title}” was deleted.` });
      setConfirmOpen(false);
      router.push("/publications");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this publication."));
      setDeleting(false);
    }
  }, [publication, deleting, router]);

  const handlePdfChosen = useCallback(
    async (file: File | undefined) => {
      if (!publication || !file) return;
      setPdfError(null);
      setPdfProgress(0);
      try {
        await attachPublicationPdf(publication.id, file, {
          uploadedBy: publication.uploaded_by,
          onProgress: ({ percent }) => setPdfProgress(percent),
        });
        refresh();
        show("success", `“${file.name}” attached as the primary PDF.`);
      } catch (err) {
        setPdfError(toErrorMessage(err, "Failed to attach the PDF."));
      } finally {
        setPdfProgress(null);
        if (pdfInputRef.current) pdfInputRef.current.value = "";
      }
    },
    [publication, refresh, show],
  );

  const actions = publication ? (
    <>
      {publication.pdf_url ? (
        <a
          href={publication.pdf_url}
          download={publication.pdf_file_name || publication.title}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <Download className="h-4 w-4" aria-hidden="true" /> Download PDF
        </a>
      ) : null}
      <button
        type="button"
        onClick={() => pdfInputRef.current?.click()}
        disabled={attaching || deleting}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {attaching ? <Spinner /> : <FileUp className="h-4 w-4" aria-hidden="true" />}
        {attaching
          ? `Uploading ${pdfProgress ?? 0}%`
          : publication.pdf_url
            ? "Replace PDF"
            : "Attach PDF"}
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
            {publication ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh publication"
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
              { label: "Publications", href: "/publications" },
              { label: publication?.title ?? (notFound ? "Not found" : "Publication") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Publication not found"
                description="This publication may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/publications")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Publications
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this publication"
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
            ) : publication ? (
              <div className="space-y-4">
                <PublicationHeader publication={publication} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Bibliography">
                    <dl className="text-sm">
                      <DetailRow label="Type" value={titleCase(publication.publication_type)} />
                      <DetailRow
                        label="Pipeline stage"
                        value={
                          publication.pipeline_stage
                            ? titleCase(publication.pipeline_stage)
                            : "—"
                        }
                      />
                      <DetailRow label="Journal" value={publication.journal || "—"} />
                      <DetailRow label="Conference" value={publication.conference || "—"} />
                      <DetailRow label="Volume" value={publication.volume || "—"} />
                      <DetailRow label="Issue" value={publication.issue || "—"} />
                      <DetailRow label="Pages" value={publication.pages || "—"} />
                      <DetailRow
                        label="Year"
                        value={publication.year != null ? String(publication.year) : "—"}
                      />
                      <DetailRow
                        label="Publication date"
                        value={publication.date || formatDate(publication.created_at)}
                      />
                      <DetailRow label="Language" value={publication.language || "—"} />
                      <DetailRow label="Publisher" value={publication.publisher || "—"} />
                      <DetailRow
                        label="Publisher URL"
                        value={
                          publication.publisher_url ? (
                            <a
                              href={publication.publisher_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 break-all text-[var(--accent)] hover:underline"
                            >
                              {publication.publisher_url}
                              <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                            </a>
                          ) : (
                            "—"
                          )
                        }
                      />
                    </dl>
                  </Section>

                  <Section title="Identifiers">
                    <dl className="text-sm">
                      <DetailRow
                        label="DOI"
                        value={
                          publication.doi ? (
                            <a
                              href={`${DOI_URL}${publication.doi}`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 break-all font-mono text-xs text-[var(--accent)] hover:underline"
                            >
                              {publication.doi}
                              <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                            </a>
                          ) : (
                            "—"
                          )
                        }
                      />
                      <DetailRow label="ISSN" value={publication.issn || "—"} mono />
                      <DetailRow label="ISBN" value={publication.isbn || "—"} mono />
                      <DetailRow label="Publication ID" value={publication.id} mono />
                    </dl>
                  </Section>

                  <Section title={`Authors (${publication.authors.length})`}>
                    {publication.authors.length === 0 ? (
                      <p className="text-sm text-[var(--text-tertiary)]">No authors recorded yet.</p>
                    ) : (
                      <ul className="space-y-2.5 text-sm">
                        {publication.authors.map((author, index) => (
                          <li
                            key={`${author.name}-${index}`}
                            className="border-b border-[var(--border-subtle)] pb-2.5 last:border-0 last:pb-0"
                          >
                            <p className="flex flex-wrap items-center gap-2 text-[var(--text-primary)]">
                              <span className="font-medium">{author.name}</span>
                              {author.corresponding ? (
                                <span
                                  title="Corresponding author"
                                  className="inline-flex items-center gap-1 rounded-full bg-[var(--warning-subtle)] px-2 py-0.5 text-xs text-[var(--warning)]"
                                >
                                  <Star className="h-3 w-3 fill-current" aria-hidden="true" />
                                  Corresponding
                                </span>
                              ) : null}
                            </p>
                            <p className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-[var(--text-tertiary)]">
                              {author.orcid ? (
                                <a
                                  href={`${ORCID_URL}${author.orcid}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 font-mono text-[var(--accent)] hover:underline"
                                >
                                  {author.orcid}
                                  <ExternalLink className="h-3 w-3" aria-hidden="true" />
                                </a>
                              ) : null}
                              {author.affiliation ? <span>{author.affiliation}</span> : null}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Section>

                  <Section title="Metrics &amp; Indexing">
                    <dl className="text-sm">
                      <DetailRow
                        label="Citation count"
                        value={String(publication.citation_count ?? 0)}
                      />
                      <DetailRow
                        label="Impact factor"
                        value={
                          publication.impact_factor != null
                            ? String(publication.impact_factor)
                            : "—"
                        }
                      />
                      <DetailRow
                        label="Quartile"
                        value={
                          publication.quartile ? (
                            <QuartileBadge quartile={publication.quartile} />
                          ) : (
                            "—"
                          )
                        }
                      />
                      <DetailRow
                        label="Indexing"
                        value={
                          publication.indexing.length ? (
                            <IndexingChips indexing={publication.indexing} />
                          ) : (
                            "—"
                          )
                        }
                      />
                    </dl>
                  </Section>

                  {publication.abstract ? (
                    <Section title="Abstract" className="lg:col-span-2">
                      <p className="whitespace-pre-line text-sm leading-relaxed text-[var(--text-secondary)]">
                        {publication.abstract}
                      </p>
                    </Section>
                  ) : null}

                  <Section title="Organisation">
                    <dl className="text-sm">
                      <DetailRow label="Keywords" value={<ChipList items={publication.keywords} />} />
                      <DetailRow label="Tags" value={<ChipList items={publication.tags} />} />
                      <DetailRow
                        label="Collections"
                        value={<ChipList items={publication.collections} />}
                      />
                      <DetailRow
                        label="Affiliations"
                        value={<ChipList items={publication.affiliations} />}
                      />
                      <DetailRow label="Notes" value={publication.notes || "—"} />
                    </dl>
                  </Section>

                  <Section title="Linked Objects">
                    <PublicationLinks publication={publication} />
                  </Section>

                  <Section title="PDF">
                    <dl className="text-sm">
                      <DetailRow label="File name" value={publication.pdf_file_name || "—"} />
                      <DetailRow
                        label="Size"
                        value={
                          publication.pdf_file_size
                            ? formatFileSize(publication.pdf_file_size)
                            : "—"
                        }
                      />
                      <DetailRow label="MIME type" value={publication.pdf_mime_type || "—"} />
                    </dl>
                    {pdfError ? (
                      <p role="alert" className="mt-2 text-xs text-[var(--danger)]">
                        {pdfError}
                      </p>
                    ) : null}
                    <p className="mt-3 text-xs text-[var(--text-tertiary)]">
                      Supplementary files (appendices, datasets) are linked via the Documents
                      module.
                    </p>
                  </Section>

                  <Section
                    title="Citation"
                    action={<Quote className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />}
                  >
                    <CitationPanel publicationId={publication.id} />
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Added by" value={publication.uploaded_by || "—"} />
                      <DetailRow label="Added at" value={formatDateTime(publication.created_at)} />
                      <DetailRow
                        label="Last updated"
                        value={
                          publication.updated_at ? (
                            formatDateTime(publication.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${publication.version}`} />
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
                          <p className="text-[var(--text-primary)]">Publication added</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(publication.created_at)} ·{" "}
                            {publication.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(publication.events ?? []).map((event, index) => (
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

      {publication ? (
        <>
          <input
            ref={pdfInputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            aria-hidden="true"
            tabIndex={-1}
            onChange={(event) => handlePdfChosen(event.target.files?.[0])}
          />
          <PublicationModal
            open={editOpen}
            publication={publication}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete publication?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{publication.title}”
                </span>{" "}
                will be permanently removed, together with its attached PDF. This action cannot
                be undone.
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
