"use client";

import Link from "next/link";
import { FolderOpen, Files } from "lucide-react";
import type { IntakeSession } from "@/types";
import { ACTIVE_STATUSES, formatBytes } from "@/lib/intake/constants";
import { StatusChip } from "./StatusChip";
import { cn } from "@/lib/utils";

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function SessionCard({ session }: { session: IntakeSession }) {
  const active = ACTIVE_STATUSES.includes(session.status);
  const { progress } = session;
  const KindIcon = session.source.kind === "folder" ? FolderOpen : Files;
  const href = `/intake/${session.id}`;
  return (
    <Link
      href={href}
      aria-label={`Open session ${session.title}`}
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 transition-colors",
        "hover:border-[var(--border-strong)] hover:bg-[var(--bg-hover)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-subtle)] text-[var(--accent)]">
            <KindIcon className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[var(--text-primary)]">
              {session.title}
            </p>
            <p className="truncate text-xs text-[var(--text-tertiary)]">
              {session.source.display}
            </p>
          </div>
        </div>
        <StatusChip status={session.status} />
      </div>

      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress.percent}
        aria-label={`Progress: ${progress.percent}%`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]"
      >
        <div
          className={cn(
            "h-full rounded-full transition-all",
            session.status === "failed"
              ? "bg-[var(--danger)]"
              : session.status === "cancelled"
                ? "bg-[var(--text-tertiary)]"
                : "bg-[var(--accent)]",
          )}
          style={{ width: `${Math.min(100, Math.max(progress.percent, active ? 3 : 0))}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-[var(--text-tertiary)]">
        <span aria-label="Session progress detail">
          {progress.processed}/{progress.total} items
          {session.statistics.errors > 0 ? ` • ${session.statistics.errors} errors` : ""}
          {session.statistics.total_bytes > 0
            ? ` • ${formatBytes(session.statistics.total_bytes)}`
            : ""}
        </span>
        <span suppressHydrationWarning>{timeAgo(session.updated_at ?? session.created_at)}</span>
      </div>
    </Link>
  );
}
