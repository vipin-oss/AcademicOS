"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getGradebook } from "@/lib/api/teaching";
import type { Gradebook } from "@/types";

export interface UseGradebookResult {
  gradebook: Gradebook | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The computed weighted marks matrix of one Class (PART H). */
export function useGradebook(classId: string | null): UseGradebookResult {
  const [gradebook, setGradebook] = useState<Gradebook | null>(null);
  const [loading, setLoading] = useState(Boolean(classId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!classId) {
      setGradebook(null);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getGradebook(classId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setGradebook(response);
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

  return { gradebook, loading, error, refresh };
}
