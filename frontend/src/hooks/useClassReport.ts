"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getClassReport } from "@/lib/api/teaching";
import type { ClassReport } from "@/types";

export interface UseClassReportResult {
  report: ClassReport | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The AI-report-ready aggregate of one Class (PART K). */
export function useClassReport(classId: string | null): UseClassReportResult {
  const [report, setReport] = useState<ClassReport | null>(null);
  const [loading, setLoading] = useState(Boolean(classId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!classId) {
      setReport(null);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getClassReport(classId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setReport(response);
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
  }, [classId, reloadToken]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return { report, loading, error, refresh };
}
