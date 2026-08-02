"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getEvent } from "@/lib/api/events";
import type { EventResponse } from "@/types";

export interface UseEventResult {
  event: EventResponse | null;
  /** First load for this id: render skeletons. */
  loading: boolean;
  /** Background reload (after an update): keep the current data on screen. */
  refreshing: boolean;
  error: string | null;
  /** Shown when the fetch 404s (deleted or wrong id). */
  notFound: boolean;
  /** Replace the local copy after a mutation that returns the payload. */
  applyUpdate: (event: EventResponse) => void;
  refresh: () => void;
}

/**
 * Load one Event by id (workspace page). Mirrors `useProposal`.
 *
 * `id` must be the DECODED ObjectId — decoding happens exactly once, in the
 * route component that owns `params.id`.
 */
export function useEvent(id: string | null): UseEventResult {
  const [event, setEvent] = useState<EventResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [refreshing, setRefreshing] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) {
      setEvent(null);
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

    getEvent(id, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        loadedIdRef.current = id;
        setEvent(response);
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
  const applyUpdate = useCallback((updated: EventResponse) => {
    loadedIdRef.current = updated.id;
    setEvent(updated);
  }, []);

  return { event, loading, refreshing, notFound, error, applyUpdate, refresh };
}
