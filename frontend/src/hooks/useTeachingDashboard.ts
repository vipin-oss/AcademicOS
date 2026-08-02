"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getTeachingDashboard } from "@/lib/api/teaching";
import type { TeachingDashboard } from "@/types";

export interface UseTeachingDashboardResult {
  dashboard: TeachingDashboard | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The faculty Teaching dashboard aggregates (PART J). */
export function useTeachingDashboard(): UseTeachingDashboardResult {
  const [dashboard, setDashboard] = useState<TeachingDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getTeachingDashboard({ signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setDashboard(response);
      })
      .catch((err) => {
        if (!active || err?.name === "AbortError") return;
        setError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [reloadToken]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return { dashboard, loading, error, refresh };
}
