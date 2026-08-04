"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toErrorMessage, isAbortError } from "@/lib/api/client";
import { listIntakeSessions } from "@/lib/api/intake";
import { ACTIVE_STATUSES, INTAKE_ACTIVE_POLL_MS, INTAKE_PAGE_SIZE } from "@/lib/intake/constants";
import type { IntakeSession } from "@/types";

export interface UseIntakeSessionsResult {
  items: IntakeSession[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  /** True while at least one session is queued or running (drives polling). */
  hasActive: boolean;
  setPage: (page: number) => void;
  refresh: () => Promise<void>;
}

export function useIntakeSessions(pageSize: number = INTAKE_PAGE_SIZE): UseIntakeSessionsResult {
  const [items, setItems] = useState<IntakeSession[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(
    async (hard = false) => {
      if (hard) setLoading(true);
      else setRefreshing(true);
      try {
        const res = await listIntakeSessions({ page, pageSize });
        if (!mounted.current) return;
        setItems(res.items);
        setTotal(res.total_count);
        setError(null);
      } catch (err) {
        if (isAbortError(err)) return;
        if (mounted.current) setError(toErrorMessage(err));
      } finally {
        if (mounted.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [page, pageSize],
  );

  useEffect(() => {
    void load(true);
  }, [load]);

  const hasActive = useMemo(
    () => items.some((s) => ACTIVE_STATUSES.includes(s.status)),
    [items],
  );

  // Poll while anything is active so progress bars move on their own.
  useEffect(() => {
    if (!hasActive) return;
    const timer = window.setInterval(() => {
      void load(false);
    }, INTAKE_ACTIVE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [hasActive, load]);

  return {
    items,
    total,
    page,
    pageSize,
    totalPages: Math.max(1, Math.ceil(total / pageSize)),
    loading,
    refreshing,
    error,
    hasActive,
    setPage,
    refresh: () => load(false),
  };
}
