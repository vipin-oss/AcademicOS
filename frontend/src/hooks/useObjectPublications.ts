"use client";

import { useEffect, useState } from "react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { listPublicationsByObject } from "@/lib/api/publications";
import type { PublicationResponse } from "@/types";

export interface UseObjectPublicationsResult {
  publications: PublicationResponse[];
  loading: boolean;
  /** True only when the request genuinely failed (e.g. endpoint not shipped). */
  error: string | null;
  refresh: () => void;
}

/**
 * Publications linked to a single object, for the "Publications" section on
 * the Object detail page (the object lens: papers of a project / grant /
 * person). Designed to degrade gracefully — on failure the parent section
 * shows an empty state instead of breaking the Object page.
 * (Mirrors `useObjectDocuments`.)
 */
export function useObjectPublications(
  objectId: string | null | undefined,
): UseObjectPublicationsResult {
  const [publications, setPublications] = useState<PublicationResponse[]>([]);
  const [loading, setLoading] = useState(Boolean(objectId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!objectId) {
      setPublications([]);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    let active = true;

    setLoading(true);
    setError(null);

    listPublicationsByObject(objectId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setPublications(response.items ?? []);
      })
      .catch((err: unknown) => {
        if (!active || (err instanceof ApiError && err.isAborted)) return;
        setPublications([]);
        // Surface quietly — the parent section renders an empty state.
        setError(toErrorMessage(err, "Publications are unavailable."));
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

  return { publications, loading, error, refresh };
}
