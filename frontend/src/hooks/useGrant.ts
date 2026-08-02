"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getGrant } from "@/lib/api/research";
import type { GrantResponse } from "@/types";

export interface UseGrantResult {
  grant: GrantResponse | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  notFound: boolean;
  applyUpdate: (grant: GrantResponse) => void;
  refresh: () => void;
}

/** Load one Grant by id (workspace page). Mirrors `useProject`. */
export function useGrant(id: string | null): UseGrantResult {
  const [grant, setGrant] = useState<GrantResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [refreshing, setRefreshing] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) {
      setGrant(null);
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

    getGrant(id, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        loadedIdRef.current = id;
        setGrant(response);
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
  const applyUpdate = useCallback((updated: GrantResponse) => {
    loadedIdRef.current = updated.id;
    setGrant(updated);
  }, []);

  return { grant, loading, refreshing, notFound, error, applyUpdate, refresh };
}
