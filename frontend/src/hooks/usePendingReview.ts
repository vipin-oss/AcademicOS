"use client";

/**
 * Hook to fetch pending review fields for a specific document.
 * Uses the dedicated /documents/{id}/pending-review endpoint
 * instead of relying on the analysis re-run.
 */

import { useCallback, useEffect, useState } from "react";
import {
  fetchDocumentPendingReview,
  type PendingReviewItemResponse,
  type PendingReviewResponse,
} from "@/lib/api/documentIntake";

export interface UsePendingReviewResult {
  /** Pending review items (PROPOSED/AUTO_SUGGESTED claims) for this document. */
  items: PendingReviewItemResponse[];
  documentTitle: string;
  totalPending: number;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function usePendingReview(documentId: string | null): UsePendingReviewResult {
  const [items, setItems] = useState<PendingReviewItemResponse[]>([]);
  const [documentTitle, setDocumentTitle] = useState("");
  const [totalPending, setTotalPending] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const fetch_ = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchDocumentPendingReview(documentId);
      setItems(result.items);
      setDocumentTitle(result.document_title);
      setTotalPending(result.total_pending);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load pending review");
      setItems([]);
      setTotalPending(0);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    void fetch_();
  }, [fetch_, reloadToken]);

  const refresh = useCallback(() => setReloadToken((t) => t + 1), []);

  return { items, documentTitle, totalPending, loading, error, refresh };
}
