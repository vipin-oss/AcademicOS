/**
 * useNotifications — polls for unread notification count.
 *
 * Returns the current unread count and a function to refresh it.
 * Polls every 30 seconds when the tab is visible.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchUnreadCount } from "@/lib/api/notifications";

export function useNotifications() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const count = await fetchUnreadCount();
      setUnreadCount(count);
    } catch {
      // Silently fail — notifications are non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + polling
  useEffect(() => {
    refresh();

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);

    // Poll every 30 seconds when visible
    intervalRef.current = setInterval(() => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    }, 30_000);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [refresh]);

  return { unreadCount, loading, refresh };
}
