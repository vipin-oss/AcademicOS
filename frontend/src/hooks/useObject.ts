"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { getObject } from "@/lib/api/objects";
import type { ObjectResponse } from "@/types";

export interface UseObjectResult {
  object: ObjectResponse | null;
  /** First load for this id: render skeletons. */
  loading: boolean;
  /** Background reload (after an update): keep the current data on screen. */
  refreshing: boolean;
  error: string | null;
  notFound: boolean;
  refresh: () => void;
}

/**
 * Loads a single object.
 *
 * `id` must be the DECODED ObjectId (`obj:course:AB12…`). Decoding happens
 * exactly once, in the route component that owns `params.id`; this hook and
 * the API layer pass the value through untouched.
 */
export function useObject(id: string | null | undefined): UseObjectResult {
  const [object, setObject] = useState<ObjectResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) {
      setObject(null);
      setLoading(false);
      setError(null);
      setNotFound(false);
      loadedIdRef.current = null;
      return;
    }

    const controller = new AbortController();
    let active = true;

    // Same object being re-fetched -> soft refresh (no skeleton flicker).
    if (loadedIdRef.current === id) setRefreshing(true);
    else setLoading(true);
    setError(null);
    setNotFound(false);

    getObject(id, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        loadedIdRef.current = id;
        setObject(response);
      })
      .catch((err: unknown) => {
        if (!active || (err instanceof ApiError && err.isAborted)) return;
        loadedIdRef.current = null;
        setObject(null);
        if (err instanceof ApiError && err.isNotFound) setNotFound(true);
        else setError(toErrorMessage(err, "Failed to load this object."));
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

  return { object, loading, refreshing, error, notFound, refresh };
}
