"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listClassesByObject } from "@/lib/api/teaching";
import type { ClassResponse } from "@/types";

export interface UseObjectClassesResult {
  classes: ClassResponse[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * The object lens for classes: "classes this Student is enrolled in" and
 * "classes this Faculty member teaches" — one edge query on the backend.
 */
export function useObjectClasses(objectId: string | null): UseObjectClassesResult {
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [loading, setLoading] = useState(Boolean(objectId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!objectId) {
      setClasses([]);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    listClassesByObject(objectId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setClasses(response.items);
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
  }, [objectId, reloadToken]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return { classes, loading, error, refresh };
}
