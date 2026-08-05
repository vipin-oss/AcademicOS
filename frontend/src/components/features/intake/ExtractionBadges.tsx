"use client";

import type { IntakeItem } from "@/types";
import { EXTRACTION_BADGE_META, extractionBadgesOf } from "@/lib/intake/extraction";
import type { ChipTone } from "@/lib/intake/constants";
import { cn } from "@/lib/utils";

/** Same tone vocabulary as {@link StatusChip} — no new palette. */
const TONE_CLASSES: Record<ChipTone, string> = {
  accent: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  success: "bg-[var(--success-subtle)] text-[var(--success)]",
  warning: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  danger: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  muted: "bg-[var(--bg-hover)] text-[var(--text-tertiary)]",
};

/**
 * The M2 extraction badge set for one item: Extracted / Unsupported /
 * Needs OCR / Failed / Queued — every state derived from the real
 * descriptor or item error record, never assumed.
 */
export function ExtractionBadges({ item, size = "sm" }: { item: IntakeItem; size?: "sm" | "xs" }) {
  const badges = extractionBadgesOf(item);
  return (
    <span className="inline-flex flex-wrap items-center gap-1" aria-label="Extraction badges">
      {badges.map((key) => {
        const meta = EXTRACTION_BADGE_META[key];
        return (
          <span
            key={key}
            aria-label={meta.aria}
            title={
              key === "needs_ocr"
                ? "This file has no extractable text layer; OCR is a later milestone."
                : meta.aria
            }
            className={cn(
              "inline-flex items-center gap-1 rounded-full font-medium",
              size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-2 py-0 text-[11px]",
              TONE_CLASSES[meta.tone],
            )}
          >
            {meta.label}
          </span>
        );
      })}
    </span>
  );
}
