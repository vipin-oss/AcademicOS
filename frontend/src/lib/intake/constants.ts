/** Intake UI constants — mirrors backend dtos/intake.py vocabulary. */
import type {
  IntakeItemStatus,
  IntakeSessionStatus,
  IntakeStageName,
} from "@/types";

export const INTAKE_PAGE_SIZE = 12;
export const INTAKE_ITEMS_PAGE_SIZE = 25;
/** Polling cadence while any session is active (queued/running). */
export const INTAKE_ACTIVE_POLL_MS = 1_500;

export type ChipTone = "accent" | "success" | "warning" | "danger" | "muted";

export const SESSION_STATUS_META: Record<
  IntakeSessionStatus,
  { label: string; tone: ChipTone }
> = {
  queued: { label: "Queued", tone: "muted" },
  running: { label: "Running", tone: "accent" },
  paused: { label: "Paused", tone: "warning" },
  cancelled: { label: "Cancelled", tone: "muted" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

export const ITEM_STATUS_META: Record<
  IntakeItemStatus,
  { label: string; tone: ChipTone }
> = {
  pending: { label: "Pending", tone: "muted" },
  staged: { label: "Staged", tone: "accent" },
  // M2.3: live attempt states from the extraction queue.
  extracting: { label: "Extracting", tone: "accent" },
  retrying: { label: "Retrying", tone: "warning" },
  awaiting_review: { label: "Awaiting review", tone: "success" },
  error: { label: "Error", tone: "danger" },
};

export const ACTIVE_STATUSES: IntakeSessionStatus[] = ["queued", "running"];

export interface IntakeStageMeta {
  key: IntakeStageName;
  label: string;
  /** Deferred stages name the milestone that will own their real logic. */
  milestone?: string;
}

/** Canonical pipeline order shown in the stage tracker. */
export const INTAKE_STAGES: IntakeStageMeta[] = [
  { key: "enumerate", label: "Enumerate" },
  { key: "stage", label: "Stage" },
  { key: "hash", label: "Hash" },
  // Extract is real since M2 — no milestone marker (the remaining markers
  // name the deferred stages' owners, same doctrine as M1).
  { key: "extract", label: "Extract" },
  { key: "classify", label: "Classify", milestone: "M5" },
  { key: "match", label: "Match", milestone: "M7" },
  { key: "propose", label: "Propose", milestone: "M8" },
  { key: "review", label: "Review" },
  { key: "commit", label: "Commit", milestone: "M9" },
];

export function formatBytes(num: number): string {
  const value = Math.max(num, 0);
  if (value < 1024) return `${Math.round(value)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  for (let i = 0; i < units.length; i += 1) {
    if (size < 1024 || i === units.length - 1) return `${size.toFixed(1)} ${units[i]}`;
    size /= 1024;
  }
  return `${size.toFixed(1)} TB`;
}
