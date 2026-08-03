"use client";

/**
 * Theme bootstrap mounted once in the root layout: reads the stored theme
 * from the settings document (`GET /settings`) and applies it via the theme
 * engine. Deliberately silent — if the backend is unreachable the app simply
 * renders with the default (light) tokens; nothing else depends on it.
 */
import { useEffect } from "react";

import { getSettings } from "@/lib/api/settings";
import { applyThemePreference, toThemePreference } from "@/lib/settings/theme";

export function ThemeEffect() {
  useEffect(() => {
    let alive = true;
    getSettings()
      .then((doc) => {
        if (alive) applyThemePreference(toThemePreference(doc.sections.appearance.theme));
      })
      .catch(() => {
        /* settings unreachable → default tokens; the settings page reports it */
      });
    return () => {
      alive = false;
    };
  }, []);
  return null;
}
