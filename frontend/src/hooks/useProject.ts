"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getProject } from "@/lib/api/research";
import type { ProjectResponse } from "@/types";

export interface UseProjectResult {
  project: ProjectResponse | null;
  /** First load for this id: render skeletons. */
  loading: boolean;
  /** Background reload (after an update): keep the current data on screen. */
  refreshing: boolean;
  error: string | null;
  /** Shown when the fetch 404s (deleted or wrong id). */
  notFound: boolean;
  /** Replace the local copy after a mutation that returns the payload. */
  applyUpdate: (project: ProjectResponse) => void;
  refresh: () => void;
}

/**
 * Load one Research Project by id (workspace page). Mirrors `useStudent`.
 *
 * `id` must be the DECODED ObjectId — decoding happens exactly once, in the
 * route component that owns `params.id`.
 */
export function useProject(id: string | null): UseProjectResult {
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [refreshing, setRefreshing] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) {
      setProject(null);
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

    getProject(id, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        loadedIdRef.current = id;
        setProject(response);
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
  const applyUpdate = useCallback((updated: ProjectResponse) => {
    loadedIdRef.current = updated.id;
    setProject(updated);
  }, []);

  return { project, loading, refreshing, notFound, error, applyUpdate, refresh };
}
