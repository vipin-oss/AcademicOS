"use client";

/**
 * Lightweight polling hook for document analysis/enrichment status.
 *
 * Polls only while status is "running" or "not_started".
 * Stops polling when completed, failed, or skipped.
 * Bounded: max 30 polls (5 minutes at 10s intervals).
 * Cleans up on unmount.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { analyzeDocument, type DocumentAnalysisResponse } from "@/lib/api/documentIntake";

const POLL_INTERVAL_MS = 10_000; // 10 seconds
const MAX_POLLS = 30; // 5 minutes max

interface UseAnalysisPollingOptions {
  documentId: string | null;
  enabled?: boolean;
  onStatusChange?: (status: string) => void;
}

export function useAnalysisPolling({
  documentId,
  enabled = true,
  onStatusChange,
}: UseAnalysisPollingOptions) {
  const [analysis, setAnalysis] = useState<DocumentAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollCountRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastStatusRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const fetchAnalysis = useCallback(async () => {
    if (!documentId) return;
    try {
      const result = await analyzeDocument(documentId);
      setAnalysis(result);
      setError(null);

      const status = result.enrichment_status ?? "not_started";
      if (status !== lastStatusRef.current) {
        lastStatusRef.current = status;
        onStatusChange?.(status);
      }

      // Stop polling when done
      if (status === "completed" || status === "failed" || status === "skipped") {
        stopPolling();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analysis");
    }
  }, [documentId, onStatusChange, stopPolling]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollCountRef.current = 0;
    timerRef.current = setInterval(() => {
      pollCountRef.current += 1;
      if (pollCountRef.current >= MAX_POLLS) {
        stopPolling();
        return;
      }
      void fetchAnalysis();
    }, POLL_INTERVAL_MS);
  }, [fetchAnalysis, stopPolling]);

  // Initial fetch and polling setup
  useEffect(() => {
    if (!documentId || !enabled) {
      stopPolling();
      return;
    }

    // Initial fetch
    setLoading(true);
    void fetchAnalysis().finally(() => setLoading(false));

    // Start polling if we might be processing
    startPolling();

    return () => {
      stopPolling();
    };
  }, [documentId, enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  const retry = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    try {
      await fetchAnalysis();
      startPolling(); // Restart polling after retry
    } finally {
      setLoading(false);
    }
  }, [documentId, fetchAnalysis, startPolling]);

  return {
    analysis,
    loading,
    error,
    retry,
    enrichmentStatus: analysis?.enrichment_status ?? "not_started",
    isPolling: timerRef.current !== null,
  };
}
