"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getAttendanceSummary } from "@/lib/api/teaching";
import { ATTENDANCE_THRESHOLD_DEFAULT } from "@/lib/teaching/constants";
import type { AttendanceSummary } from "@/types";

export interface UseAttendanceSummaryResult {
  summary: AttendanceSummary | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The per-student attendance summary of one Class (PART I → J/K). */
export function useAttendanceSummary(
  classId: string | null,
  threshold: number = ATTENDANCE_THRESHOLD_DEFAULT,
): UseAttendanceSummaryResult {
  const [summary, setSummary] = useState<AttendanceSummary | null>(null);
  const [loading, setLoading] = useState(Boolean(classId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!classId) {
      setSummary(null);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getAttendanceSummary(classId, threshold, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setSummary(response);
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
  }, [classId, threshold, reloadToken]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return { summary, loading, error, refresh };
}
