"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listAttendance } from "@/lib/api/teaching";
import type { AttendanceSessionResponse } from "@/types";

export interface UseAttendanceSessionsResult {
  sessions: AttendanceSessionResponse[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The dated attendance sessions of one Class (PART I register). */
export function useAttendanceSessions(classId: string | null): UseAttendanceSessionsResult {
  const [sessions, setSessions] = useState<AttendanceSessionResponse[]>([]);
  const [loading, setLoading] = useState(Boolean(classId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!classId) {
      setSessions([]);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    listAttendance(classId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setSessions(response);
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

  return { sessions, loading, error, refresh };
}
