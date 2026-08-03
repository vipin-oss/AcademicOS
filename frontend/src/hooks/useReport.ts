"use client";

import { useEffect, useMemo, useState } from "react";
import { getReport } from "@/lib/api/reports";
import { toErrorMessage } from "@/lib/api/client";
import type { ReportFilters, ReportView } from "@/types";

/**
 * Generic report hook — (kind, filters) → computed ReportView. Debounced on
 * the filter payload (the useEvents list convention) so filter changes fire
 * one recomputation per pause.
 */
export function useReport(kind: string, filters: ReportFilters) {
  const [report, setReport] = useState<ReportView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filtersKey = useMemo(() => JSON.stringify(filters), [filters]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const handle = setTimeout(() => {
      getReport(kind, JSON.parse(filtersKey) as ReportFilters)
        .then((data) => {
          if (!cancelled) {
            setReport(data);
            setError(null);
          }
        })
        .catch((err) => {
          if (!cancelled) {
            setError(toErrorMessage(err));
            setReport(null);
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [kind, filtersKey]);

  return { report, loading, error };
}
