"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getClass } from "@/lib/api/teaching";
import type { ClassResponse } from "@/types";

export interface UseClassResult {
  cls: ClassResponse | null;
  /** First load for this id: render skeletons. */
  loading: boolean;
  /** Background reload (after an update): keep the current data on screen. */
  refreshing: boolean;
  error: string | null;
  notFound: boolean;
  refresh: () => void;
}

/** Load one Class by id (class workspace). Mirrors `usePublication`. */
export function useClass(id: string | null): UseClassResult {
  const [cls, setCls] = useState<ClassResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [refreshing, setRefreshing] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) {
      setCls(null);
      setLoading(false);
      setNotFound(false);
      setError(null);
      loadedIdRef.current = null;
      return;
    }
    const controller = new AbortController();
    let active = true;

    if (loadedIdRef.current === id) setRefreshing(true);
    else setLoading(true);
    setError(null);
    setNotFound(false);

    getClass(id, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        loadedIdRef.current = id;
        setCls(response);
      })
      .catch((err) => {
        if (!active || err?.name === "AbortError") return;
        if (err?.status === 404) setNotFound(true);
        else setError(toErrorMessage(err));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
        setRefreshing(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [id, reloadToken]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return { cls, loading, refreshing, notFound, error, refresh };
}
