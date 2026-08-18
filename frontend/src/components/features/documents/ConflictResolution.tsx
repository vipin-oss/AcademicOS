"use client";

/**
 * Conflict Resolution Panel
 *
 * Shows conflicts between existing data and AI suggestions in
 * professor-friendly language. Allows the user to:
 * 1. Keep existing value
 * 2. Accept AI suggestion
 * 3. Edit manually
 * 4. Leave unresolved
 */

import { useState, useCallback } from "react";
import { AlertCircle, CheckCircle2, RefreshCw, Edit3 } from "lucide-react";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { friendlyFieldName } from "@/lib/fieldLabels";

interface Conflict {
  predicate_id: string;
  existing_claim_id: string;
  existing_value: unknown;
  extracted_value: unknown;
}

interface ConflictResolutionProps {
  conflicts: Conflict[];
  documentId: string;
  onResolved?: () => void;
}

export function ConflictResolution({ conflicts, documentId, onResolved }: ConflictResolutionProps) {
  const [resolving, setResolving] = useState<string | null>(null);
  const [resolved, setResolved] = useState<Set<string>>(new Set());
  const [manualEdit, setManualEdit] = useState<string | null>(null);
  const [manualValue, setManualValue] = useState("");

  const handleAcceptSuggestion = useCallback(async (conflict: Conflict) => {
    setResolving(conflict.predicate_id);
    try {
      // Approve the AI-suggested claim
      await api.post(`/confirmations/${conflict.existing_claim_id}/approve`, {});
      setResolved((prev) => new Set(prev).add(conflict.predicate_id));
      onResolved?.();
    } catch {
      // Silent failure - user can retry
    } finally {
      setResolving(null);
    }
  }, [onResolved]);

  const handleKeepExisting = useCallback(async (conflict: Conflict) => {
    setResolving(conflict.predicate_id);
    try {
      // Reject the AI suggestion, keeping the existing confirmed value
      await api.post(`/confirmations/${conflict.existing_claim_id}/reject`, {});
      setResolved((prev) => new Set(prev).add(conflict.predicate_id));
      onResolved?.();
    } catch {
      // Silent failure
    } finally {
      setResolving(null);
    }
  }, [onResolved]);

  const handleManualCorrection = useCallback(async (conflict: Conflict) => {
    if (!manualValue.trim()) return;
    setResolving(conflict.predicate_id);
    try {
      // Correct the claim with manual value
      await api.post(`/confirmations/${conflict.existing_claim_id}/correct`, {
        raw_value: manualValue.trim(),
        notes: "Manual correction by user",
      });
      setResolved((prev) => new Set(prev).add(conflict.predicate_id));
      setManualEdit(null);
      setManualValue("");
      onResolved?.();
    } catch {
      // Silent failure
    } finally {
      setResolving(null);
    }
  }, [manualValue, onResolved]);

  const unresolvedConflicts = conflicts.filter((c) => !resolved.has(c.predicate_id));

  if (unresolvedConflicts.length === 0) return null;

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50">
      <div className="flex items-center gap-2 border-b border-amber-200 px-5 py-4">
        <AlertCircle className="h-5 w-5 text-amber-600" />
        <div>
          <h2 className="text-sm font-semibold text-amber-900">Conflicting Information Found</h2>
          <p className="text-xs text-amber-700">
            AcademicOS found different values for some fields. Please choose which to keep.
          </p>
        </div>
      </div>

      <div className="divide-y divide-amber-200">
        {unresolvedConflicts.map((conflict) => (
          <div key={conflict.predicate_id} className="px-5 py-4">
            <p className="mb-3 text-sm font-medium text-amber-900">
              {friendlyFieldName(conflict.predicate_id)}
            </p>

            <div className="mb-3 grid grid-cols-2 gap-3">
              {/* Existing value */}
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-emerald-600">
                  Current Value
                </p>
                <p className="text-sm text-emerald-900">{String(conflict.existing_value)}</p>
              </div>

              {/* AI suggestion */}
              <div className="rounded-lg border border-purple-200 bg-purple-50 p-3">
                <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-purple-600">
                  AI Suggestion
                </p>
                <p className="text-sm text-purple-900">{String(conflict.extracted_value)}</p>
              </div>
            </div>

            {/* Manual edit */}
            {manualEdit === conflict.predicate_id ? (
              <div className="mb-3 flex gap-2">
                <input
                  type="text"
                  value={manualValue}
                  onChange={(e) => setManualValue(e.target.value)}
                  placeholder="Enter the correct value"
                  className="flex-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-1.5 text-sm"
                  onKeyDown={(e) => e.key === "Enter" && void handleManualCorrection(conflict)}
                />
                <button
                  type="button"
                  onClick={() => void handleManualCorrection(conflict)}
                  disabled={resolving === conflict.predicate_id}
                  className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm text-white disabled:opacity-50"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => { setManualEdit(null); setManualValue(""); }}
                  className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-sm"
                >
                  Cancel
                </button>
              </div>
            ) : null}

            {/* Actions */}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void handleKeepExisting(conflict)}
                disabled={resolving === conflict.predicate_id}
                className="inline-flex items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
              >
                <CheckCircle2 className="h-3 w-3" /> Keep Current
              </button>
              <button
                type="button"
                onClick={() => void handleAcceptSuggestion(conflict)}
                disabled={resolving === conflict.predicate_id}
                className="inline-flex items-center gap-1 rounded-lg border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-50"
              >
                <RefreshCw className="h-3 w-3" /> Accept AI Suggestion
              </button>
              <button
                type="button"
                onClick={() => { setManualEdit(conflict.predicate_id); setManualValue(String(conflict.existing_value)); }}
                disabled={resolving === conflict.predicate_id}
                className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50"
              >
                <Edit3 className="h-3 w-3" /> Edit Manually
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
