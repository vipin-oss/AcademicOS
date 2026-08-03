/**
 * Theme engine for the Settings & Preferences module.
 *
 * The stylesheet contract already exists: `globals.css` defines a `.dark`
 * token block alongside `:root`, so applying a theme is *only* toggling the
 * `dark` class on `<html>` — no CSS changes, no inline styles. "system"
 * resolves through `prefers-color-scheme` and is re-resolved live while the
 * preference stays "system" (a single shared media listener, idempotent).
 *
 * No storage of its own: the settings document on the backend is the single
 * source of truth; {@link applyThemePreference} is called by the
 * `<ThemeEffect/>` bootstrap (root layout) and by the Appearance section
 * right after a successful save.
 */
"use client";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const MEDIA_QUERY = "(prefers-color-scheme: dark)";

let currentPreference: ThemePreference = "system";
let mediaListener: ((event: MediaQueryListEvent) => void) | null = null;

/** Guard unknown strings coming from older/curated data. */
export function toThemePreference(value: string | null | undefined): ThemePreference {
  return value === "light" || value === "dark" ? value : "system";
}

export function getThemePreference(): ThemePreference {
  return currentPreference;
}

export function resolveSystemDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(MEDIA_QUERY).matches
  );
}

export function resolveTheme(preference: ThemePreference = currentPreference): ResolvedTheme {
  if (preference === "system") return resolveSystemDark() ? "dark" : "light";
  return preference;
}

function applyResolved(): void {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", resolveTheme() === "dark");
}

function detachMediaListener(): void {
  if (mediaListener && typeof window !== "undefined") {
    window.matchMedia(MEDIA_QUERY).removeEventListener("change", mediaListener);
  }
  mediaListener = null;
}

function attachMediaListener(): void {
  if (mediaListener || typeof window === "undefined") return;
  mediaListener = () => applyResolved();
  window.matchMedia(MEDIA_QUERY).addEventListener("change", mediaListener);
}

/**
 * Make `preference` the active theme and apply it immediately. While the
 * preference is "system" a live OS-level listener stays attached; otherwise
 * it is detached. Safe to call repeatedly — fully idempotent.
 */
export function applyThemePreference(preference: ThemePreference): void {
  currentPreference = preference;
  if (preference === "system") attachMediaListener();
  else detachMediaListener();
  applyResolved();
}
