"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, toErrorMessage, isAbortError } from "@/lib/api/client";
import {
  bulkReviewIntakeItems,
  cancelIntakeSession,
  deleteIntakeSession,
  getIntakeSession,
  listIntakeItems,
  pauseIntakeSession,
  resumeIntakeSession,
  retryIntakeSession,
  reviewIntakeItem,
} from "@/lib/api/intake";
import { ACTIVE_STATUSES, INTAKE_ACTIVE_POLL_MS, INTAKE_ITEMS_PAGE_SIZE } from "@/lib/intake/constants";
import type { IntakeItem, IntakeSession } from "@/types";

export type IntakeAction = "pause" | "resume" | "cancel" | "retry";

export interface UseIntakeSessionResult {
  session: IntakeSession | null;
  items: IntakeItem[];
  itemsTotal: number;
  page: number;
  pageSize: number;
  totalPages: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  /** 404 state — the session id does not exist (anymore). */
  notFound: boolean;
  busyAction: IntakeAction | "delete" | "review" | null;
  actionError: string | null;
  setPage: (page: number) => void;
  refresh: () => Promise<void>;
  act: (action: IntakeAction) => Promise<boolean>;
  remove: () => Promise<boolean>;
  /** M9: approve (commit) or reject one item; returns {ok, error?}. */
  reviewItem: (itemId: string, decision: "approve" | "reject") => Promise<{ ok: boolean; error?: string }>;
  /** M9: bulk approve/reject; returns {succeeded, failed}. */
  bulkReview: (decision: "approve" | "reject") => Promise<{ succeeded: number; failed: number }>;
}

export function useIntakeSession(
  sessionId: string,
  pageSize: number = INTAKE_ITEMS_PAGE_SIZE,
): UseIntakeSessionResult {
  const [session, setSession] = useState<IntakeSession | null>(null);
  const [items, setItems] = useState<IntakeItem[]>([]);
  const [itemsTotal, setItemsTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [busyAction, setBusyAction] = useState<IntakeAction | "delete" | "review" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
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
        const [sessionRes, itemsRes] = await Promise.all([
          getIntakeSession(sessionId),
          listIntakeItems(sessionId, { page, pageSize }),
        ]);
        if (!mounted.current) return;
        setSession(sessionRes);
        setItems(itemsRes.items);
        setItemsTotal(itemsRes.total_count);
        setNotFound(false);
        setError(null);
      } catch (err) {
        if (isAbortError(err)) return;
        if (!mounted.current) return;
        if (err instanceof ApiError && err.isNotFound) {
          setNotFound(true);
          setSession(null);
        } else {
          setError(toErrorMessage(err));
        }
      } finally {
        if (mounted.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [sessionId, page, pageSize],
  );

  useEffect(() => {
    void load(true);
  }, [load]);

  // Poll while active so the stage tracker and item rows advance live.
  useEffect(() => {
    if (!session || !ACTIVE_STATUSES.includes(session.status)) return;
    const timer = window.setInterval(() => {
      void load(false);
    }, INTAKE_ACTIVE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [session, load]);

  const act = useCallback(
    async (action: IntakeAction): Promise<boolean> => {
      setBusyAction(action);
      setActionError(null);
      const call =
        action === "pause"
          ? pauseIntakeSession
          : action === "resume"
            ? resumeIntakeSession
            : action === "retry"
              ? retryIntakeSession
              : cancelIntakeSession;
      try {
        const updated = await call(sessionId);
        if (!mounted.current) return true;
        setSession(updated);
        await load(false);
        return true;
      } catch (err) {
        if (mounted.current) setActionError(toErrorMessage(err));
        return false;
      } finally {
        if (mounted.current) setBusyAction(null);
      }
    },
    [sessionId, load],
  );

  const reviewItem = useCallback(
    async (
      itemId: string,
      decision: "approve" | "reject",
    ): Promise<{ ok: boolean; error?: string }> => {
      setBusyAction("review");
      setActionError(null);
      try {
        await reviewIntakeItem(itemId, decision);
        await load(false);
        return { ok: true };
      } catch (err) {
        const message = toErrorMessage(err);
        if (mounted.current) setActionError(message);
        return { ok: false, error: message };
      } finally {
        if (mounted.current) setBusyAction(null);
      }
    },
    [load],
  );

  const bulkReview = useCallback(
    async (decision: "approve" | "reject"): Promise<{ succeeded: number; failed: number }> => {
      setBusyAction("review");
      setActionError(null);
      try {
        const result = await bulkReviewIntakeItems(sessionId, decision);
        await load(false);
        return {
          succeeded: result.succeeded,
          failed: result.items.length - result.succeeded,
        };
      } catch (err) {
        if (mounted.current) setActionError(toErrorMessage(err));
        return { succeeded: 0, failed: 0 };
      } finally {
        if (mounted.current) setBusyAction(null);
      }
    },
    [sessionId, load],
  );

  const remove = useCallback(async (): Promise<boolean> => {
    setBusyAction("delete");
    setActionError(null);
    try {
      await deleteIntakeSession(sessionId);
      return true;
    } catch (err) {
      if (mounted.current) setActionError(toErrorMessage(err));
      return false;
    } finally {
      if (mounted.current) setBusyAction(null);
    }
  }, [sessionId]);

  return useMemo(
    () => ({
      session,
      items,
      itemsTotal,
      page,
      pageSize,
      totalPages: Math.max(1, Math.ceil(itemsTotal / pageSize)),
      loading,
      refreshing,
      error,
      notFound,
      busyAction,
      actionError,
      setPage,
      refresh: () => load(false),
      act,
      remove,
      reviewItem,
      bulkReview,
    }),
    [
      session,
      items,
      itemsTotal,
      page,
      pageSize,
      loading,
      refreshing,
      error,
      notFound,
      busyAction,
      actionError,
      load,
      act,
      remove,
    ],
  );
}
