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
import { ProposalHeader } from "@/components/features/finance/ProposalHeader";
import { ProcurementCommitteePanel } from "@/components/features/finance/ProcurementCommitteePanel";
import { QuotationsPanel } from "@/components/features/finance/QuotationsPanel";
import { ComparativePanel } from "@/components/features/finance/ComparativePanel";
import { PurchaseOrdersPanel } from "@/components/features/finance/PurchaseOrdersPanel";
import { BillsPanel } from "@/components/features/finance/BillsPanel";
import { AssetsPanel } from "@/components/features/finance/AssetsPanel";
import { LinkedLinksPanel } from "@/components/features/finance/LinkedLinksPanel";
import {
  ProposalModal,
  type ProposalSaveResult,
} from "@/components/features/finance/ProposalModal";
import type { PickerOption } from "@/components/features/finance/SectionPanel";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { ChipList } from "@/components/features/publications/PublicationBadge";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useProposal } from "@/hooks/useProposal";
import { useObjectDocuments } from "@/hooks/useObjectDocuments";
import { deleteProposal } from "@/lib/api/finance";
import { listVendors } from "@/lib/api/finance";
import { toErrorMessage } from "@/lib/api/client";
import { formatMoney } from "@/lib/finance/constants";
import { consumeFlash, setFlash } from "@/lib/objects/flash";
import { formatDate, formatDateTime, titleCase } from "@/lib/utils";

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

/**
 * The purchase-proposal workspace: PART 1 record, PART 2 committee lens,
 * PART 4-8 section panels, links, documents lens and audit trail.
 */
export default function ProposalWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const proposalId = decodeRouteId(params?.id);

  const {
    proposal,
    loading,
    refreshing,
    error,
    notFound,
    applyUpdate,
    refresh,
  } = useProposal(proposalId);
  const { toast, show, dismiss } = useToast();

  // Vendor options for every section panel's vendor pickers (one fetch).
  const [vendorOptions, setVendorOptions] = useState<PickerOption[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    listVendors({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setVendorOptions(
          response.items.map((vendor) => ({ id: vendor.id, label: vendor.name })),
        ),
      )
      .catch(() => setVendorOptions([]));
    return () => controller.abort();
  }, []);

  // PART 10 documents integration: pickers offer this proposal's documents.
  const { documents } = useObjectDocuments(proposal?.id);
  const documentOptions: PickerOption[] = documents.map((document) => ({
    id: document.id,
    label: document.title || document.file_name,
  }));

  // Pick up a message handed over by another page.
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const [editOpen, setEditOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleSaved = useCallback(
    (result: ProposalSaveResult) => {
      setEditOpen(false);
      applyUpdate(result.proposal);
      show("success", "Proposal updated successfully.");
    },
    [applyUpdate, show],
  );

  const handleDelete = useCallback(async () => {
    if (!proposal || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteProposal(proposal.id);
      setFlash({ kind: "success", message: `“${proposal.title}” was deleted.` });
      setConfirmOpen(false);
      router.push("/finance");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this proposal."));
      setDeleting(false);
    }
  }, [proposal, deleting, router]);

  const actions = proposal ? (
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
            {proposal ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh proposal"
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
              { label: "Finance", href: "/finance" },
              { label: proposal?.title ?? (notFound ? "Not found" : "Proposal") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Proposal not found"
                description="This proposal may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/finance")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Finance
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this proposal"
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
            ) : proposal ? (
              <div className="space-y-4">
                <ProposalHeader proposal={proposal} />
                <div className="flex flex-wrap justify-end gap-2">{actions}</div>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Proposal Record">
                    <dl className="text-sm">
                      <DetailRow
                        label="Proposal number"
                        value={proposal.proposal_number || "—"}
                      />
                      <DetailRow label="Department" value={proposal.department || "—"} />
                      <DetailRow
                        label="Requested by"
                        value={proposal.requested_name || "—"}
                      />
                      <DetailRow
                        label="Proposal date"
                        value={
                          proposal.proposal_date ? formatDate(proposal.proposal_date) : "—"
                        }
                      />
                      <DetailRow label="Budget head" value={proposal.budget_head || "—"} />
                      <DetailRow
                        label="Estimated cost"
                        value={formatMoney(proposal.estimated_cost)}
                      />
                      <DetailRow
                        label="Committed (POs)"
                        value={formatMoney(proposal.stats?.committed)}
                      />
                      <DetailRow
                        label="Spent (paid bills)"
                        value={formatMoney(proposal.stats?.spent)}
                      />
                      <DetailRow
                        label="Pending bills"
                        value={String(proposal.stats?.pending_bills ?? 0)}
                      />
                      <DetailRow label="Purpose" value={proposal.purpose || "—"} />
                      <DetailRow label="Tags" value={<ChipList items={proposal.tags} />} />
                      <DetailRow label="Notes" value={proposal.notes || "—"} />
                    </dl>
                  </Section>

                  <ProcurementCommitteePanel proposal={proposal} />

                  <QuotationsPanel
                    proposal={proposal}
                    vendors={vendorOptions}
                    documents={documentOptions}
                    onUpdated={applyUpdate}
                  />

                  <ComparativePanel
                    proposal={proposal}
                    vendors={vendorOptions}
                    onUpdated={applyUpdate}
                  />

                  <PurchaseOrdersPanel
                    proposal={proposal}
                    vendors={vendorOptions}
                    documents={documentOptions}
                    onUpdated={applyUpdate}
                  />

                  <BillsPanel
                    proposal={proposal}
                    vendors={vendorOptions}
                    documents={documentOptions}
                    onUpdated={applyUpdate}
                  />

                  <AssetsPanel proposal={proposal} onUpdated={applyUpdate} />

                  <LinkedLinksPanel links={proposal.links ?? {}} />

                  <Section title="Documents">
                    <ObjectDocuments objectId={proposal.id} />
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Proposal ID" value={proposal.id} mono />
                      <DetailRow label="Added by" value={proposal.uploaded_by || "—"} />
                      <DetailRow
                        label="Added at"
                        value={formatDateTime(proposal.created_at)}
                      />
                      <DetailRow
                        label="Last updated"
                        value={
                          proposal.updated_at ? (
                            formatDateTime(proposal.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${proposal.version}`} />
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
                          <p className="text-[var(--text-primary)]">Proposal created</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(proposal.created_at)} ·{" "}
                            {proposal.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(proposal.events ?? []).map((event, index) => (
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

      {proposal ? (
        <>
          <ProposalModal
            open={editOpen}
            proposal={proposal}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete proposal?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{proposal.title}”
                </span>{" "}
                will be permanently removed together with its quotations, comparative
                statement, purchase orders, bills and asset rows. Vendors, linked
                projects, committees and documents are kept. This action cannot be undone.
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
