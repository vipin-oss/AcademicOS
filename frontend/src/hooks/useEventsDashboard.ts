"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getEventsDashboard } from "@/lib/api/events";
import type { EventsDashboard } from "@/types";

export interface UseEventsDashboardResult {
  dashboard: EventsDashboard | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The PART 9 cards. Mirrors `useFinanceDashboard` (single source). */
export function useEventsDashboard(): UseEventsDashboardResult {
  const [dashboard, setDashboard] = useState<EventsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getEventsDashboard({ signal: controller.signal })
      .then((cards) => {
        if (!active) return;
        setDashboard(cards);
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
