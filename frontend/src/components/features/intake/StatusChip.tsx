"use client";

import type { IntakeItemStatus, IntakeSessionStatus } from "@/types";
import { ITEM_STATUS_META, SESSION_STATUS_META, type ChipTone } from "@/lib/intake/constants";
import { cn } from "@/lib/utils";

const TONE_CLASSES: Record<ChipTone, string> = {
  accent: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  success: "bg-[var(--success-subtle,#dcfce7)] text-[var(--success,#16a34a)]",
  warning: "bg-[var(--warning-subtle,#fef9c3)] text-[var(--warning,#a16207)]",
  danger: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  muted: "bg-[var(--bg-hover)] text-[var(--text-tertiary)]",
};

export function StatusChip({
  status,
  kind = "session",
}: {
  status: IntakeSessionStatus | IntakeItemStatus;
  kind?: "session" | "item";
}) {
  const meta =
    kind === "session"
      ? SESSION_STATUS_META[status as IntakeSessionStatus]
      : ITEM_STATUS_META[status as IntakeItemStatus];
  return (
    <span
      aria-label={`${kind === "session" ? "Session" : "Item"} status: ${meta.label}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        TONE_CLASSES[meta.tone],
      )}
    >
      {meta.label}
    </span>
  );
}
