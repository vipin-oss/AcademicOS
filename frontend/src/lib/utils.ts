import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names (ShadCN convention). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Dates are formatted with a FIXED locale + UTC timezone on purpose: these
 * components are server-rendered and then hydrated, and a locale/timezone
 * dependent string would differ between the two passes (hydration mismatch).
 */
const DATE_OPTS: Intl.DateTimeFormatOptions = {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
};

const TIME_OPTS: Intl.DateTimeFormatOptions = {
  ...DATE_OPTS,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
};

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** `01 Aug 2026` — safe for SSR. Falls back to the raw value / em dash. */
export function formatDate(iso: string | null | undefined, fallback = "—"): string {
  const date = parse(iso);
  if (!date) return iso || fallback;
  return new Intl.DateTimeFormat("en-GB", DATE_OPTS).format(date);
}

/** `01 Aug 2026, 09:31 UTC` — safe for SSR. */
export function formatDateTime(iso: string | null | undefined, fallback = "—"): string {
  const date = parse(iso);
  if (!date) return iso || fallback;
  return `${new Intl.DateTimeFormat("en-GB", TIME_OPTS).format(date)} UTC`;
}

/** `research_project` -> `Research Project`. */
export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
