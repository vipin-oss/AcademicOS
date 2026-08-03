"use client";

import { useEffect, useState } from "react";
import { getReportsDashboard } from "@/lib/api/reports";
import { toErrorMessage } from "@/lib/api/client";
import type { ReportsDashboard } from "@/types";

/** PART 1 dashboard cards (single fetch on mount — the events dashboard hook
 * convention). */
export function useReportsDashboard() {
  const [dashboard, setDashboard] = useState<ReportsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getReportsDashboard()
      .then((data) => {
        if (!cancelled) {
          setDashboard(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(toErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { dashboard, loading, error };
}
