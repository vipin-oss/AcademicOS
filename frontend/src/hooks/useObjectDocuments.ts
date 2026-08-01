"use client";

import { useEffect, useState } from "react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { listDocumentsByObject } from "@/lib/api/documents";
import type { DocumentResponse } from "@/types";

export interface UseObjectDocumentsResult {
  documents: DocumentResponse[];
  loading: boolean;
  /** True only when the request genuinely failed (e.g. endpoint not shipped). */
  error: string | null;
  refresh: () => void;
}

/**
 * Documents attached to a single object, for the "Documents" section on the
 * Object detail page.
 *
 * Designed to degrade gracefully: if the backend has no documents endpoint
 * yet, `error` is set but the section simply shows an empty state instead of
 * crashing the (working) Object detail page.
 */
export function useObjectDocuments(objectId: string | null | undefined): UseObjectDocumentsResult {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(Boolean(objectId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!objectId) {
      setDocuments([]);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    let active = true;

    setLoading(true);
    setError(null);

    listDocumentsByObject(objectId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setDocuments(response.items ?? []);
      })
      .catch((err: unknown) => {
        if (!active || (err instanceof ApiError && err.isAborted)) return;
        setDocuments([]);
        // Surface quietly — the parent section renders an empty state.
        setError(toErrorMessage(err, "Documents are unavailable."));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [objectId, reloadToken]);

  const refresh = () => setReloadToken((token) => token + 1);

  return { documents, loading, error, refresh };
}
