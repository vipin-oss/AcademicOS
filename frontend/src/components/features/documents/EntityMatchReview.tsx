/**
 * EntityMatchReview — shows possible document matches for professor review.
 *
 * Displays evidence clearly without technical jargon.
 * Allows professor to confirm (link) or reject (keep separate).
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { Link2, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import {
  fetchPendingMatches,
  confirmEntityMatch,
  rejectEntityMatch,
  type PendingMatch,
} from "@/lib/api/entityMatches";

interface EntityMatchReviewProps {
  documentId: string;
  documentTitle?: string;
  onMatchResolved?: () => void;
}

/** Parse evidence JSON into readable signal list */
function parseEvidence(evidence: string): string[] {
  try {
    const signals = JSON.parse(evidence);
    if (Array.isArray(signals)) {
      return signals.map((s: { evidence?: string }) => s.evidence || String(s)).filter(Boolean);
    }
  } catch {
    // Not JSON — use as-is
  }
  return evidence ? [evidence] : [];
}

/** Human-readable confidence label */
function confidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return "Strong match";
  if (confidence >= 0.5) return "Possible match";
  return "Weak match";
}

export function EntityMatchReview({
  documentId,
  documentTitle,
  onMatchResolved,
}: EntityMatchReviewProps) {
  const [matches, setMatches] = useState<PendingMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadMatches = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPendingMatches(documentId);
      setMatches(data.pending_matches);
    } catch {
      // Silently fail — matches are non-critical
      setMatches([]);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    loadMatches();
  }, [loadMatches]);

  const handleConfirm = useCallback(
    async (targetDocId: string) => {
      try {
        setActingId(targetDocId);
        setError(null);
        await confirmEntityMatch(documentId, targetDocId);
        // Remove from pending list
        setMatches((prev) => prev.filter((m) => m.target_doc_id !== targetDocId));
        onMatchResolved?.();
      } catch {
        setError("Failed to link documents. Please try again.");
      } finally {
        setActingId(null);
      }
    },
    [documentId, onMatchResolved],
  );

  const handleReject = useCallback(
    async (targetDocId: string) => {
      try {
        setActingId(targetDocId);
        setError(null);
        await rejectEntityMatch(documentId, targetDocId);
        // Remove from pending list
        setMatches((prev) => prev.filter((m) => m.target_doc_id !== targetDocId));
        onMatchResolved?.();
      } catch {
        setError("Failed to dismiss match. Please try again.");
      } finally {
        setActingId(null);
      }
    },
    [documentId, onMatchResolved],
  );

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking for related documents…
      </div>
    );
  }

  if (matches.length === 0) {
    return null; // Don't render anything if no pending matches
  }

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
      <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
        Possible Related Documents
      </h3>
      <p className="mb-4 text-xs text-[var(--text-tertiary)]">
        These documents may refer to the same academic work as &ldquo;{documentTitle || "this document"}&rdquo;.
      </p>

      {error && (
        <div className="mb-3 rounded-lg bg-[var(--danger-subtle)] p-2 text-xs text-[var(--danger)]">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {matches.map((match) => {
          const isActing = actingId === match.target_doc_id;
          const evidenceList = parseEvidence(match.evidence);

          return (
            <div
              key={match.target_doc_id}
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] p-3"
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">
                    {match.target_doc_id}
                  </p>
                  <p className="text-xs text-[var(--text-tertiary)]">
                    {confidenceLabel(match.confidence)}
                  </p>
                </div>
              </div>

              {/* Evidence */}
              {evidenceList.length > 0 && (
                <div className="mb-3">
                  <p className="mb-1 text-xs font-medium text-[var(--text-secondary)]">
                    Why we think these may be related:
                  </p>
                  <ul className="space-y-0.5">
                    {evidenceList.map((evidence, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-1.5 text-xs text-[var(--text-secondary)]"
                      >
                        <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-500" />
                        {evidence}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleConfirm(match.target_doc_id)}
                  disabled={isActing}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isActing ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Link2 className="h-3 w-3" />
                  )}
                  {isActing ? "Linking…" : "Link these documents"}
                </button>
                <button
                  type="button"
                  onClick={() => handleReject(match.target_doc_id)}
                  disabled={isActing}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <X className="h-3 w-3" />
                  Keep separate
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
