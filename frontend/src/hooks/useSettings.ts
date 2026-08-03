"use client";

/**
 * Settings & Preferences data hook (mirror useProductivity / useReportsDashboard).
 * Fetch-once with `refresh()`; `saveSection` performs the verbatim-merge PUT of
 * one section and folds the returned section values back into the cached
 * document. Photo / import / reset flows either `setSettings` with the fresh
 * document they receive, or call `refresh()`.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { isAbortError, toErrorMessage } from "@/lib/api/client";
import { getSettings, updateSection } from "@/lib/api/settings";
import type {
  SettingsDocument,
  SettingsSectionCode,
  SettingsSectionResult,
  SettingsSections,
} from "@/types";

export function useSettings() {
  const [settings, setSettings] = useState<SettingsDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const aliveRef = useRef(true);

  const load = useCallback(async (signal?: AbortSignal, silent = false) => {
    // `silent` re-fetches without the skeleton swap, so section-local state
    // (e.g. "Photo updated.") survives refresh-after-action.
    if (!silent) setLoading(true);
    setError(null);
    try {
      const doc = await getSettings(signal ? { signal } : undefined);
      if (aliveRef.current) setSettings(doc);
    } catch (err) {
      if (isAbortError(err)) return;
      if (aliveRef.current) setError(toErrorMessage(err, "Could not load your settings."));
    } finally {
      if (!silent && aliveRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    const controller = new AbortController();
    void load(controller.signal);
    return () => {
      aliveRef.current = false;
      controller.abort();
    };
  }, [load]);

  const refresh = useCallback((options?: { silent?: boolean }) => {
    void load(undefined, options?.silent ?? false);
  }, [load]);

  const saveSection = useCallback(
    async <K extends SettingsSectionCode>(
      section: K,
      values: Partial<SettingsSections[K]>,
    ): Promise<SettingsSectionResult<K>> => {
      const result = await updateSection(section, values);
      setSettings((prev) =>
        prev
          ? { ...prev, sections: { ...prev.sections, [result.section]: result.values } }
          : prev,
      );
      return result;
    },
    [],
  );

  return { settings, setSettings, loading, error, refresh, saveSection };
}
