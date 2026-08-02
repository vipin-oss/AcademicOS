"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listClassAssignments } from "@/lib/api/teaching";
import type { AssignmentResponse } from "@/types";

export interface UseAssignmentsResult {
  assignments: AssignmentResponse[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The assignments of one Class (deadline-ordered by the backend). */
export function useAssignments(classId: string | null): UseAssignmentsResult {
  const [assignments, setAssignments] = useState<AssignmentResponse[]>([]);
  const [loading, setLoading] = useState(Boolean(classId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!classId) {
      setAssignments([]);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    listClassAssignments(classId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setAssignments(response.items);
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

  return { assignments, loading, error, refresh };
}
