"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getIntakeExtractedText } from "@/lib/api/intake";
import { isAbortError, toErrorMessage } from "@/lib/api/client";

export interface UseExtractedTextResult {
  /** Raw extracted text, exactly as served; `null` while not loaded. */
  text: string | null;
  loading: boolean;
  /** Transport/API error message (an honest 404 surfaces here too). */
  error: string | null;
  /** True when the backend honestly answered "no text exists" (404). */
  unavailable: boolean;
  reload: () => void;
}

/**
 * Lazily load the raw extracted text of one intake item (M2 viewer).
 *
 * - Nothing is fetched while `enabled` is false (tab not open / item has no
 *   text record) — no request storms, and switching items aborts in-flight
 *   requests.
 * - A 404 is *not* retried silently: it is the backend's honest "there is no
 *   extracted text for this item", surfaced as `unavailable`.
 */
export function useExtractedText(
  sessionId: string,
  itemId: string | null,
  enabled: boolean,
): UseExtractedTextResult {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [nonce, setNonce] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled || !itemId) {
      setText(null);
      setError(null);
      setUnavailable(false);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setUnavailable(false);
    setText(null);
    getIntakeExtractedText(sessionId, itemId, { signal: controller.signal })
      .then((body) => {
        if (!mounted.current || controller.signal.aborted) return;
        setText(body);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!mounted.current || isAbortError(err) || controller.signal.aborted) return;
        const message = toErrorMessage(err);
        // The endpoint's only 404 meanings are honest "no text here" states.
        if (
          err instanceof Object &&
          "status" in err &&
          (err as { status?: unknown }).status === 404
        ) {
          setUnavailable(true);
        }
        setError(message);
        setLoading(false);
      });
    return () => controller.abort();
  }, [sessionId, itemId, enabled, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return useMemo(
    () => ({ text, loading, error, unavailable, reload }),
    [text, loading, error, unavailable, reload],
  );
}
