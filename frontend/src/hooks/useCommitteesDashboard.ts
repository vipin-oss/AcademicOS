"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getCommitteesDashboard } from "@/lib/api/committees";
import type { CommitteesDashboard } from "@/types";

export interface UseCommitteesDashboardResult {
  dashboard: CommitteesDashboard | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The PART 8 committees dashboard aggregates. Mirrors `useResearchDashboard`. */
export function useCommitteesDashboard(): UseCommitteesDashboardResult {
  const [dashboard, setDashboard] = useState<CommitteesDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getCommitteesDashboard({ signal: controller.signal })
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
