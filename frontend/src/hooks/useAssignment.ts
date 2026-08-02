"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getAssignment } from "@/lib/api/teaching";
import type { AssignmentResponse } from "@/types";

export interface UseAssignmentResult {
  assignment: AssignmentResponse | null;
  /** First load for this id: render skeletons. */
  loading: boolean;
  /** Background reload (after an update): keep the current data on screen. */
  refreshing: boolean;
  error: string | null;
  notFound: boolean;
  refresh: () => void;
}

/** Load one Assignment by id (assignment workspace). Mirrors `usePublication`. */
export function useAssignment(id: string | null): UseAssignmentResult {
  const [assignment, setAssignment] = useState<AssignmentResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [refreshing, setRefreshing] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const loadedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!id) {
      setAssignment(null);
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

    getAssignment(id, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        loadedIdRef.current = id;
        setAssignment(response);
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

  return { assignment, loading, refreshing, notFound, error, refresh };
}
