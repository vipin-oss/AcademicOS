"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getResearchDashboard } from "@/lib/api/research";
import type { ResearchDashboard } from "@/types";

export interface UseResearchDashboardResult {
  dashboard: ResearchDashboard | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The Research dashboard aggregates (PART 10). Mirrors `useTeachingDashboard`. */
export function useResearchDashboard(): UseResearchDashboardResult {
  const [dashboard, setDashboard] = useState<ResearchDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getResearchDashboard({ signal: controller.signal })
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
