"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
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
import { GrantHeader } from "@/components/features/research/GrantHeader";
import { InstallmentsPanel } from "@/components/features/research/InstallmentsPanel";
import { ExpendituresPanel } from "@/components/features/research/ExpendituresPanel";
import {
  GrantModal,
  type GrantSaveResult,
} from "@/components/features/research/GrantModal";
import { InstallmentModal } from "@/components/features/research/InstallmentModal";
import { ExpenditureModal } from "@/components/features/research/ExpenditureModal";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useGrant } from "@/hooks/useGrant";
import { deleteGrant } from "@/lib/api/research";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
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

/** The grant workspace: budget header, installments, expenditure and links. */
export default function GrantWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const grantId = decodeRouteId(params?.id);

  const { grant, loading, refreshing, error, notFound, applyUpdate, refresh } =
    useGrant(grantId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [installmentOpen, setInstallmentOpen] = useState(false);
  const [expenditureOpen, setExpenditureOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleSaved = useCallback(
    (result: GrantSaveResult) => {
      setEditOpen(false);
      applyUpdate(result.grant);
      show("success", "Grant updated successfully.");
    },
    [applyUpdate, show],
  );

  const handleEntrySaved = useCallback(
    (message: string) => {
      setInstallmentOpen(false);
      setExpenditureOpen(false);
      refresh(); // budget totals derive from the child entries
      show("success", message);
    },
    [refresh, show],
  );

  const handleDelete = useCallback(async () => {
    if (!grant || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteGrant(grant.id);
      setFlash({ kind: "success", message: `“${grant.title}” was deleted.` });
      setConfirmOpen(false);
      router.push("/research/grants");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this grant."));
      setDeleting(false);
    }
  }, [grant, deleting, router]);

  const actions = grant ? (
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
            {grant ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh grant"
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
              { label: "Research", href: "/research" },
              { label: "Grants", href: "/research/grants" },
              { label: grant?.grant_number ?? (notFound ? "Not found" : "Grant") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Grant not found"
                description="This grant may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/research/grants")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Grants
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this grant"
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
            ) : grant ? (
              <div className="space-y-4">
                <GrantHeader grant={grant} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <InstallmentsPanel
                    grant={grant}
                    onAddInstallment={() => setInstallmentOpen(true)}
                    onChanged={refresh}
                  />

                  <ExpendituresPanel
                    grant={grant}
                    onAddExpenditure={() => setExpenditureOpen(true)}
                    onChanged={refresh}
                  />

                  <Section title="Funded Projects">
                    {(grant.links?.projects ?? []).length === 0 ? (
                      <p className="text-sm text-[var(--text-tertiary)]">
                        No projects linked — edit the grant to fund a project.
                      </p>
                    ) : (
                      <ul className="space-y-2 text-sm">
                        {(grant.links?.projects ?? []).map((project) => (
                          <li key={project.id}>
                            <Link
                              href={`/research/projects/${encodeURIComponent(project.id)}`}
                              className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                            >
                              {project.title}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Section>

                  <Section title="Documents">
                    <p className="mb-2 text-xs text-[var(--text-tertiary)]">
                      Sanction letters and utilisation certificates are attached here.
                    </p>
                    <ObjectDocuments objectId={grant.id} />
                  </Section>

                  <Section title="Notes &amp; Administration">
                    <dl className="text-sm">
                      <DetailRow label="Notes" value={grant.notes || "—"} />
                      <DetailRow label="Grant ID" value={grant.id} mono />
                      <DetailRow label="Added by" value={grant.uploaded_by || "—"} />
                      <DetailRow label="Added at" value={formatDateTime(grant.created_at)} />
                      <DetailRow
                        label="Last updated"
                        value={
                          grant.updated_at ? (
                            formatDateTime(grant.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${grant.version}`} />
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
                          <p className="text-[var(--text-primary)]">Grant registered</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(grant.created_at)} ·{" "}
                            {grant.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(grant.events ?? []).map((event, index) => (
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

      {grant ? (
        <>
          <GrantModal
            open={editOpen}
            grant={grant}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <InstallmentModal
            open={installmentOpen}
            grantId={grant.id}
            onClose={() => setInstallmentOpen(false)}
            onSaved={() => handleEntrySaved("Installment added.")}
          />
          <ExpenditureModal
            open={expenditureOpen}
            grantId={grant.id}
            onClose={() => setExpenditureOpen(false)}
            onSaved={() => handleEntrySaved("Expenditure recorded.")}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete grant?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{grant.title}”
                </span>{" "}
                will be permanently removed together with its installments and expenditure
                records. Linked projects and agencies are kept. This action cannot be undone.
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
