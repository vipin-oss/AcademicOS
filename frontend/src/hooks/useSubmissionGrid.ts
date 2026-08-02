"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getSubmissionGrid } from "@/lib/api/teaching";
import type { SubmissionGrid } from "@/types";

export interface UseSubmissionGridResult {
  grid: SubmissionGrid | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  refresh: () => void;
}

/** The student × assignment submission matrix (UI Spec §2.5 C7). */
export function useSubmissionGrid(assignmentId: string | null): UseSubmissionGridResult {
  const [grid, setGrid] = useState<SubmissionGrid | null>(null);
  const [loading, setLoading] = useState(Boolean(assignmentId));
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!assignmentId) {
      setGrid(null);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setError(null);

    getSubmissionGrid(assignmentId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setGrid(response);
      })
      .catch((err) => {
        if (!active || err?.name === "AbortError") return;
        setError(toErrorMessage(err));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
        setRefreshing(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [assignmentId, reloadToken]);

  const refresh = useCallback(() => {
    setRefreshing(true);
    setReloadToken((token) => token + 1);
  }, []);

  return { grid, loading, refreshing, error, refresh };
}
