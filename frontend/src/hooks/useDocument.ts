"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { getDocument } from "@/lib/api/documents";
import type { DocumentResponse } from "@/types";

export interface UseDocumentResult {
  document: DocumentResponse | null;
  /** First load for this id: render skeletons. */
  loading: boolean;
  /** Background reload (after an update): keep the current data on screen. */
  refreshing: boolean;
  error: string | null;
  notFound: boolean;
  refresh: () => void;
}

/**
 * Loads a single document.
 *
 * `id` must be the DECODED DocumentId. Decoding happens exactly once, in the
 * route component that owns `params.id`; this hook and the API layer forward
 * the value through untouched.
 */
export function useDocument(id: string | null | undefined): UseDocumentResult {
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) {
      setDocument(null);
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

    getDocument(id, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        loadedIdRef.current = id;
        setDocument(response);
      })
      .catch((err: unknown) => {
        if (!active || (err instanceof ApiError && err.isAborted)) return;
        loadedIdRef.current = null;
        setDocument(null);
        if (err instanceof ApiError && err.isNotFound) setNotFound(true);
        else setError(toErrorMessage(err, "Failed to load this document."));
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

  return { document, loading, refreshing, error, notFound, refresh };
}
