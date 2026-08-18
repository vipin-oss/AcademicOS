"use client";

/**
 * ReviewItem — a single extracted-field card for professor review.
 *
 * Shows the field name, actual value, confidence, source evidence,
 * and action buttons (Confirm / Edit / Not applicable).
 *
 * Three display modes:
 *   A. Confirmable  — value extracted, needs professor confirmation
 *   B. Missing      — value not found, professor can add or skip
 *   C. Conflict     — value differs from existing record
 */

import { useState, useCallback } from "react";
import {
  CheckCircle2,
  XCircle,
  Edit3,
  AlertCircle,
  FileText,
  Sparkles,
  Eye,
  HelpCircle,
} from "lucide-react";
import { api } from "@/lib/api/client";
import { friendlyFieldName } from "@/lib/fieldLabels";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface ReviewItemField {
  field_name: string;
  predicate_id: string;
  value: string;
  confidence: number;
  source: string; // "label" | "regex" | "prose" | "ai" | "agreement"
  risk: string; // "low" | "medium" | "high"
  status: string; // "auto_applied" | "proposed" | "review_required" | "conflict"
}

export interface ReviewItemProps {
  field: ReviewItemField;
  claimId?: string; // For confirmations API
  documentId?: string;
  /** Called after a successful action */
  onResolved?: (predicateId: string, action: "confirmed" | "rejected" | "edited") => void;
  /** Whether to show the action buttons (hide for auto_applied) */
  showActions?: boolean;
  /** Existing value in case of conflict */
  existingValue?: string;
  /** Label for the record type (e.g., "Publication", "Event") */
  targetRecordLabel?: string;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function confidenceLabel(confidence: number): { label: string; color: string; bg: string } {
  if (confidence >= 0.9) return { label: "High confidence", color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200" };
  if (confidence >= 0.75) return { label: "Medium confidence", color: "text-amber-700", bg: "bg-amber-50 border-amber-200" };
  return { label: "Low confidence", color: "text-red-700", bg: "bg-red-50 border-red-200" };
}

function sourceDescription(source: string): string {
  switch (source) {
    case "label": return "Found near a label in the document";
    case "regex": return "Matched a known pattern in the document";
    case "prose": return "Extracted from document text";
    case "ai": return "Suggested by AI analysis";
    case "agreement": return "Confirmed previously";
    default: return source;
  }
}

function sourceIcon(source: string) {
  switch (source) {
    case "ai": return <Sparkles className="h-3.5 w-3.5 text-purple-500" />;
    case "agreement": return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />;
    case "label":
    case "regex":
    case "prose": return <FileText className="h-3.5 w-3.5 text-blue-500" />;
    default: return <Eye className="h-3.5 w-3.5 text-gray-400" />;
  }
}

function statusBadge(status: string): { label: string; color: string } | null {
  switch (status) {
    case "auto_applied": return null; // Don't show badge for auto-applied
    case "proposed": return { label: "Suggested", color: "bg-blue-100 text-blue-700" };
    case "review_required": return { label: "Needs confirmation", color: "bg-amber-100 text-amber-700" };
    case "conflict": return { label: "Conflicts with existing", color: "bg-red-100 text-red-700" };
    default: return { label: status, color: "bg-gray-100 text-gray-600" };
  }
}

function recordActionHint(status: string, targetRecordLabel?: string): string | null {
  if (status === "auto_applied") return null;
  if (status === "conflict") return "This field conflicts with an existing record.";
  if (targetRecordLabel) return `Will be saved to ${targetRecordLabel} when confirmed.`;
  return "Needs your confirmation before it can be saved.";
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export function ReviewItem({
  field,
  claimId,
  documentId,
  onResolved,
  showActions = true,
  existingValue,
  targetRecordLabel,
}: ReviewItemProps) {
  const [acting, setActing] = useState(false);
  const [resolved, setResolved] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(field.value);
  const [localError, setLocalError] = useState<string | null>(null);

  const conf = confidenceLabel(field.confidence);
  const badge = statusBadge(field.status);
  const hint = recordActionHint(field.status, targetRecordLabel);
  const isValueless = !field.value || field.value === "null" || field.value === "undefined" || field.value.trim() === "";

  const handleConfirm = useCallback(async () => {
    if (!claimId) {
      // No claim to confirm — just report success
      setResolved(true);
      onResolved?.(field.predicate_id, "confirmed");
      return;
    }
    setActing(true);
    setLocalError(null);
    try {
      await api.post(`/confirmations/${claimId}/approve`, {});
      setResolved(true);
      onResolved?.(field.predicate_id, "confirmed");
    } catch {
      setLocalError("Could not confirm. Please try again.");
    } finally {
      setActing(false);
    }
  }, [claimId, field.predicate_id, onResolved]);

  const handleReject = useCallback(async () => {
    if (!claimId) {
      setResolved(true);
      onResolved?.(field.predicate_id, "rejected");
      return;
    }
    setActing(true);
    setLocalError(null);
    try {
      await api.post(`/confirmations/${claimId}/reject`, {});
      setResolved(true);
      onResolved?.(field.predicate_id, "rejected");
    } catch {
      setLocalError("Could not dismiss. Please try again.");
    } finally {
      setActing(false);
    }
  }, [claimId, field.predicate_id, onResolved]);

  const handleEditSave = useCallback(async () => {
    if (!editValue.trim()) return;
    if (!claimId) {
      setEditing(false);
      setResolved(true);
      onResolved?.(field.predicate_id, "edited");
      return;
    }
    setActing(true);
    setLocalError(null);
    try {
      await api.post(`/confirmations/${claimId}/correct`, {
        raw_value: editValue.trim(),
        notes: "Manual correction by user",
      });
      setEditing(false);
      setResolved(true);
      onResolved?.(field.predicate_id, "edited");
    } catch {
      setLocalError("Could not save edit. Please try again.");
    } finally {
      setActing(false);
    }
  }, [claimId, editValue, field.predicate_id, onResolved]);

  if (resolved) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
        <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
        <span className="text-sm text-emerald-800">
          {friendlyFieldName(field.predicate_id)} — saved
        </span>
      </div>
    );
  }

  // Auto-applied fields: just show as confirmed, no actions needed
  if (field.status === "auto_applied" && !showActions) {
    return null; // Don't render auto-applied items in review queue
  }

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
      {/* Header: field name + badge */}
      <div className="flex items-center gap-2 mb-2">
        {sourceIcon(field.source)}
        <span className="text-sm font-medium text-[var(--text-primary)]">
          {friendlyFieldName(field.predicate_id)}
        </span>
        {badge && (
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${badge.color}`}>
            {badge.label}
          </span>
        )}
        <span className={`ml-auto text-xs font-medium ${conf.color}`}>
          {conf.label}
        </span>
      </div>

      {/* Value display */}
      {isValueless ? (
        <div className="mb-3 rounded-md bg-[var(--bg-hover)] px-3 py-2">
          <p className="text-sm text-[var(--text-tertiary)] italic">
            Not found in the document
          </p>
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
            onClick={() => { setEditing(false); setEditValue(field.value); }}
            className="rounded-md border border-[var(--border-subtle)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="mb-3 rounded-md bg-[var(--bg-hover)] px-3 py-2">
          <p className="text-base font-medium text-[var(--text-primary)] break-words">
            {field.value}
          </p>
          {/* Source evidence */}
          <div className="mt-1.5 flex items-center gap-2">
            <span className="text-xs text-[var(--text-tertiary)]">
              {sourceDescription(field.source)}
            </span>
          </div>
        </div>
      )}

      {/* Conflict: show existing value */}
      {field.status === "conflict" && existingValue && (
        <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2">
          <p className="text-xs font-medium text-red-600 mb-1">Existing record says:</p>
          <p className="text-sm text-red-900">{existingValue}</p>
        </div>
      )}

      {/* Why am I seeing this? */}
      {hint && (
        <div className="mb-3 flex items-start gap-1.5 text-xs text-[var(--text-tertiary)]">
          <HelpCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>{hint}</span>
        </div>
      )}

      {/* Error */}
      {localError && (
        <div className="mb-3 rounded-md bg-[var(--danger-subtle)] px-3 py-2 text-xs text-[var(--danger)]">
          {localError}
        </div>
      )}

      {/* Actions */}
      {showActions && field.status !== "auto_applied" && !isValueless && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handleConfirm()}
            disabled={acting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {acting ? "Saving…" : "Confirm"}
          </button>
          <button
            type="button"
            onClick={() => { setEditing(true); setEditValue(field.value); }}
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
      )}

      {/* Missing field: add or skip */}
      {showActions && isValueless && (
        <div className="flex flex-wrap gap-2">
          {editing ? (
            <div className="flex gap-2 w-full">
              <input
                type="text"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                placeholder={`Enter ${friendlyFieldName(field.predicate_id).toLowerCase()}`}
                className="flex-1 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-1.5 text-sm"
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
                onClick={() => { setEditing(false); setEditValue(""); }}
                className="rounded-md border border-[var(--border-subtle)] px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                onClick={() => { setEditing(true); setEditValue(""); }}
                disabled={acting}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
              >
                <Edit3 className="h-3.5 w-3.5" />
                Add {friendlyFieldName(field.predicate_id)}
              </button>
              <button
                type="button"
                onClick={() => void handleReject()}
                disabled={acting}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)]"
              >
                Leave blank
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
