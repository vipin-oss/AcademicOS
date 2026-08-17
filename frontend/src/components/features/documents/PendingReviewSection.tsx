"use client";

/**
 * PendingReviewSection — shows all pending review fields for a document.
 *
 * Fetches data from /documents/{id}/pending-review (not from analysis).
 * This ensures it always shows the REAL pending claims, even if re-analysis
 * creates different results.
 */

import { useCallback, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  XCircle,
  Edit3,
  FileText,
  Loader2,
  ChevronDown,
  ChevronRight,
  Eye,
  Sparkles,
  HelpCircle,
} from "lucide-react";
import { api } from "@/lib/api/client";
import type { PendingReviewItemResponse } from "@/lib/api/documentIntake";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function friendlyFieldName(predicateId: string): string {
  const map: Record<string, string> = {
    publication_title: "Title",
    publication_year: "Year",
    journal_name: "Journal",
    authors: "Authors",
    doi: "DOI",
    conference_name: "Conference",
    venue: "Venue",
    funding_agency: "Funding Agency",
    principal_investigator: "Principal Investigator",
    sanctioned_amount: "Amount",
    project_title: "Project Title",
    recipient: "Recipient",
    certificate_number: "Certificate Number",
    manuscript_id: "Manuscript ID",
    acceptance_date: "Acceptance Date",
    issuing_authority: "Issuing Authority",
    event_title: "Title",
    co_investigator: "Co-Investigator",
    project_duration_months: "Duration",
    sanction_order_number: "Sanction Number",
    start_date: "Start Date",
    end_date: "End Date",
    organizer: "Organizer",
    reference_number: "Reference Number",
    conference_organizer: "Organizer",
  };
  return map[predicateId] ?? predicateId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function confidenceLabel(c: number | null): { text: string; color: string } {
  if (c === null) return { text: "", color: "" };
  if (c >= 0.9) return { text: "High confidence", color: "text-emerald-700" };
  if (c >= 0.75) return { text: "Medium confidence", color: "text-amber-700" };
  return { text: "Low confidence", color: "text-red-700" };
}

function sourceFriendly(source: string): string {
  switch (source) {
    case "label": return "Found near a label in the document";
    case "regex": return "Matched a known pattern";
    case "prose": return "Extracted from document text";
    case "ai": return "AI suggestion";
    default: return "Extracted from document";
  }
}

/* ------------------------------------------------------------------ */
/* Single Review Item                                                  */
/* ------------------------------------------------------------------ */

function ReviewCard({
  item,
  onResolved,
}: {
  item: PendingReviewItemResponse;
  onResolved: (claimId: string) => void;
}) {
  const [acting, setActing] = useState(false);
  const [resolved, setResolved] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(item.display_value);
  const [localError, setLocalError] = useState<string | null>(null);

  const conf = confidenceLabel(item.confidence);
  const hasValue = item.display_value && item.display_value.trim() !== "";
  const fieldName = friendlyFieldName(item.predicate_id);

  const handleConfirm = useCallback(async () => {
    setActing(true);
    setLocalError(null);
    try {
      await api.post(`/confirmations/${item.claim_id}/approve`, {});
      setResolved(true);
      onResolved(item.claim_id);
    } catch {
      setLocalError("Could not confirm. Please try again.");
    } finally {
      setActing(false);
    }
  }, [item.claim_id, onResolved]);

  const handleReject = useCallback(async () => {
    setActing(true);
    setLocalError(null);
    try {
      await api.post(`/confirmations/${item.claim_id}/reject`, {});
      setResolved(true);
      onResolved(item.claim_id);
    } catch {
      setLocalError("Could not dismiss. Please try again.");
    } finally {
      setActing(false);
    }
  }, [item.claim_id, onResolved]);

  const handleEditSave = useCallback(async () => {
    if (!editValue.trim()) return;
    setActing(true);
    setLocalError(null);
    try {
      await api.post(`/confirmations/${item.claim_id}/correct`, {
        raw_value: editValue.trim(),
        notes: "Manual correction by user",
      });
      setEditing(false);
      setResolved(true);
      onResolved(item.claim_id);
    } catch {
      setLocalError("Could not save edit. Please try again.");
    } finally {
      setActing(false);
    }
  }, [item.claim_id, editValue, onResolved]);

  if (resolved) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
        <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
        <span className="text-sm text-emerald-800">{fieldName} — saved</span>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4" data-testid={`review-item-${item.predicate_id}`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-medium text-[var(--text-primary)]">{fieldName}</span>
        {item.status === "proposed" && (
          <span className="rounded-full bg-amber-100 text-amber-700 px-2 py-0.5 text-[10px] font-medium">
            Needs confirmation
          </span>
        )}
        {item.status === "auto_suggested" && (
          <span className="rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 text-[10px] font-medium">
            Suggested
          </span>
        )}
        {conf.text && (
          <span className={`ml-auto text-xs font-medium ${conf.color}`}>{conf.text}</span>
        )}
      </div>

      {/* Value */}
      {hasValue && !editing ? (
        <div className="mb-3 rounded-md bg-[var(--bg-hover)] px-3 py-2">
          <p className="text-base font-medium text-[var(--text-primary)] break-words">
            {item.display_value}
          </p>
          <div className="mt-1 flex items-center gap-1.5">
            <Eye className="h-3 w-3 text-[var(--text-tertiary)]" />
            <span className="text-xs text-[var(--text-tertiary)]">{sourceFriendly(item.source)}</span>
          </div>
        </div>
      ) : editing ? (
        <div className="mb-3 flex gap-2">
          <input
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="flex-1 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-1.5 text-sm text-[var(--text-primary)]"
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleEditSave();
              if (e.key === "Escape") setEditing(false);
            }}
            autoFocus
          />
          <button
            type="button"
            onClick={() => void handleEditSave()}
            disabled={acting}
            className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            Save
          </button>
          <button
            type="button"
            onClick={() => { setEditing(false); setEditValue(item.display_value); }}
            className="rounded-md border border-[var(--border-subtle)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="mb-3 rounded-md bg-[var(--bg-hover)] px-3 py-2">
          <p className="text-sm text-[var(--text-tertiary)] italic">Not found in the document</p>
        </div>
      )}

      {/* Why am I seeing this? */}
      <div className="mb-3 flex items-start gap-1.5 text-xs text-[var(--text-tertiary)]">
        <HelpCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
        <span>
          {hasValue
            ? "This information was extracted from the document and may need your confirmation."
            : `This field was not found. You can add it or leave it blank.`}
        </span>
      </div>

      {/* Error */}
      {localError && (
        <div className="mb-3 rounded-md bg-[var(--danger-subtle)] px-3 py-2 text-xs text-[var(--danger)]">
          {localError}
        </div>
      )}

      {/* Actions */}
      {hasValue ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handleConfirm()}
            disabled={acting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {acting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            {acting ? "Saving…" : "Confirm"}
          </button>
          <button
            type="button"
            onClick={() => { setEditing(true); setEditValue(item.display_value); }}
            disabled={acting}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Edit3 className="h-3.5 w-3.5" />
            Edit
          </button>
          <button
            type="button"
            onClick={() => void handleReject()}
            disabled={acting}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <XCircle className="h-3.5 w-3.5" />
            Not applicable
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => { setEditing(true); setEditValue(""); }}
            disabled={acting}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Edit3 className="h-3.5 w-3.5" />
            Add {fieldName}
          </button>
          <button
            type="button"
            onClick={() => void handleReject()}
            disabled={acting}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            Leave blank
          </button>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Section                                                        */
/* ------------------------------------------------------------------ */

export interface PendingReviewSectionProps {
  documentId: string;
  documentTitle: string;
  items: PendingReviewItemResponse[];
  loading: boolean;
  onItemResolved: () => void;
}

export function PendingReviewSection({
  documentId,
  documentTitle,
  items,
  loading,
  onItemResolved,
}: PendingReviewSectionProps) {
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState(true);

  const handleResolved = useCallback(
    (claimId: string) => {
      setResolvedIds((prev) => new Set(prev).add(claimId));
      onItemResolved();
    },
    [onItemResolved],
  );

  const pendingItems = items.filter((item) => !resolvedIds.has(item.claim_id));

  if (loading) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
          <span className="text-sm text-amber-800">Loading review items…</span>
        </div>
      </div>
    );
  }

  if (pendingItems.length === 0) {
    if (resolvedIds.size > 0) {
      return (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <div>
              <p className="text-sm font-semibold text-emerald-900">Review complete</p>
              <p className="text-xs text-emerald-700">
                Your document information has been saved.{" "}
                <Link href={`/documents/${encodeURIComponent(documentId)}`} className="underline hover:text-emerald-900">
                  View document
                </Link>
              </p>
            </div>
          </div>
        </div>
      );
    }
    return null;
  }

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50" id="review-section">
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 border-b border-amber-200 px-5 py-4 text-left hover:bg-amber-100 transition-colors"
      >
        <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-amber-900">
            Review required
          </h2>
          <p className="text-xs text-amber-700">
            AcademicOS found {pendingItems.length} {pendingItems.length === 1 ? "item" : "items"} that may need your confirmation.
          </p>
        </div>
        <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-800">
          {pendingItems.length}
        </span>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-amber-600" />
        ) : (
          <ChevronRight className="h-4 w-4 text-amber-600" />
        )}
      </button>

      {/* Items */}
      {expanded && (
        <div className="p-4 space-y-3">
          {pendingItems.map((item) => (
            <ReviewCard
              key={item.claim_id}
              item={item}
              onResolved={handleResolved}
            />
          ))}
        </div>
      )}
    </div>
  );
}
