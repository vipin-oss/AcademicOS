"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { getPublication } from "@/lib/api/publications";
import type { PublicationResponse } from "@/types";

export interface UsePublicationResult {
  publication: PublicationResponse | null;
  /** First load for this id: render skeletons. */
  loading: boolean;
  /** Background reload (after an update): keep the current data on screen. */
  refreshing: boolean;
  error: string | null;
  notFound: boolean;
  refresh: () => void;
}

/**
 * Loads a single publication.
 *
 * `id` must be the DECODED ObjectId. Decoding happens exactly once, in the
 * route component that owns `params.id`; this hook and the API layer forward
 * the value through untouched. (Mirrors `useDocument`.)
 */
export function usePublication(id: string | null | undefined): UsePublicationResult {
  const [publication, setPublication] = useState<PublicationResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) {
      setPublication(null);
      setLoading(false);
      setError(null);
      setNotFound(false);
      loadedIdRef.current = null;
      return;
    }

    const controller = new AbortController();
    let active = true;

    if (loadedIdRef.current === id) setRefreshing(true);
    else setLoading(true);
    setError(null);
    setNotFound(false);

    getPublication(id, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        loadedIdRef.current = id;
        setPublication(response);
      })
      .catch((err: unknown) => {
        if (!active || (err instanceof ApiError && err.isAborted)) return;
        loadedIdRef.current = null;
        setPublication(null);
        if (err instanceof ApiError && err.isNotFound) setNotFound(true);
        else setError(toErrorMessage(err, "Failed to load this publication."));
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

  return { publication, loading, refreshing, error, notFound, refresh };
}
