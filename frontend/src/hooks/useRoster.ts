"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getRoster } from "@/lib/api/teaching";
import type { RosterEntry } from "@/types";

export interface UseRosterResult {
  roster: RosterEntry[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The enrolled students of one Class (PART C — roster from ENROLLED_IN edges). */
export function useRoster(classId: string | null): UseRosterResult {
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [loading, setLoading] = useState(Boolean(classId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!classId) {
      setRoster([]);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getRoster(classId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setRoster(response);
      })
      .catch((err) => {
        if (!active || err?.name === "AbortError") return;
        setError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [classId, reloadToken]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return { roster, loading, error, refresh };
}
