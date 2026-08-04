"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Ban,
  CirclePause,
  CirclePlay,
  Trash2,
} from "lucide-react";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Pagination } from "@/components/features/objects/Pagination";
import { useIntakeSession } from "@/hooks/useIntakeSession";
import { INTAKE_STAGES, formatBytes } from "@/lib/intake/constants";
import { StatusChip } from "./StatusChip";
import { cn } from "@/lib/utils";

function ProgressCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div
      aria-label={`Progress card: ${label}`}
      className="flex flex-col gap-1 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
        {label}
      </p>
      <p className="text-lg font-semibold text-[var(--text-primary)]">{value}</p>
      {hint && <p className="truncate text-xs text-[var(--text-tertiary)]">{hint}</p>}
    </div>
  );
}

function StageTracker({ currentStage, status }: { currentStage: string; status: string }) {
  const currentIndex = INTAKE_STAGES.findIndex((s) => s.key === currentStage);
  return (
    <div aria-label="Pipeline stages" className="flex flex-wrap items-center gap-1.5">
      {INTAKE_STAGES.map((stage, index) => {
        const reached = currentIndex >= 0 && index <= currentIndex && stage.key !== "commit";
        const isCurrent = stage.key === currentStage && (status === "running" || status === "queued");
        return (
          <span
            key={stage.key}
            aria-label={`Stage ${stage.label}${stage.milestone ? ` (${stage.milestone})` : ""}`}
            title={
              stage.milestone
                ? `${stage.label} — placeholder stage, real logic lands in ${stage.milestone}`
                : stage.label
            }
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs",
              isCurrent
                ? "border-[var(--accent)] bg-[var(--accent-subtle)] font-medium text-[var(--accent)]"
                : reached
                  ? "border-[var(--success,#16a34a)] bg-[var(--success-subtle,#dcfce7)] text-[var(--success,#16a34a)]"
                  : "border-dashed border-[var(--border-strong)] text-[var(--text-tertiary)]",
            )}
          >
            {stage.label}
            {stage.milestone && (
              <span className="text-[10px] opacity-70">{stage.milestone}</span>
            )}
          </span>
        );
      })}
    </div>
  );
}

export function SessionDetailsView({ sessionId }: { sessionId: string }) {
  const {
    session,
    items,
    itemsTotal,
    page,
    pageSize,
    totalPages,
    loading,
    refreshing,
    error,
    notFound,
    busyAction,
    actionError,
    setPage,
    refresh,
    act,
    remove,
  } = useIntakeSession(sessionId);

  const [confirmCancel, setConfirmCancel] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleted, setDeleted] = useState(false);

  if (deleted || notFound) {
    return (
      <section
        aria-label="Session not found"
        className="flex flex-col items-start gap-3 rounded-xl border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface)] p-8"
      >
        <h1 className="text-lg font-semibold text-[var(--text-primary)]">Session not found</h1>
        <p className="text-sm text-[var(--text-tertiary)]">
          This intake session does not exist (anymore). It may have been deleted.
        </p>
        <Link
          href="/intake"
          aria-label="Back to intake"
          className="rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        >
          Back to Intake
        </Link>
      </section>
    );
  }

  if (loading && !session) {
    return (
      <div className="flex flex-col gap-3" aria-label="Loading session">
        <div className="h-8 w-64 animate-pulse rounded-lg bg-[var(--bg-hover)]" />
        <div className="h-28 animate-pulse rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-hover)]" />
        <div className="h-64 animate-pulse rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-hover)]" />
      </div>
    );
  }

  if (!session) {
    return (
      <p role="alert" className="text-sm text-[var(--danger)]">
        {error ?? "Could not load this session."}
      </p>
    );
  }

  const { progress, statistics } = session;
  const canPause = session.status === "queued" || session.status === "running";
  const canResume = session.status === "paused" || session.status === "failed";
  const canCancel = canPause || session.status === "paused";

  return (
    <section aria-label="Session details" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Link
            href="/intake"
            aria-label="Back to intake"
            className="mt-0.5 rounded-lg border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-xl font-semibold text-[var(--text-primary)]">
                {session.title}
              </h1>
              <StatusChip status={session.status} />
              {refreshing && (
                <span className="text-xs text-[var(--text-tertiary)]" aria-live="polite">
                  refreshing…
                </span>
              )}
            </div>
            <p className="truncate text-sm text-[var(--text-tertiary)]" aria-label="Session source">
              {session.source.display} • stage: {session.current_stage}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2" aria-label="Session actions">
          {canPause && (
            <button
              type="button"
              aria-label="Pause session"
              disabled={busyAction !== null}
              onClick={() => void act("pause")}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50"
            >
              <CirclePause className="h-4 w-4" />
              {busyAction === "pause" ? "Pausing…" : "Pause"}
            </button>
          )}
          {canResume && (
            <button
              type="button"
              aria-label="Resume session"
              disabled={busyAction !== null}
              onClick={() => void act("resume")}
              className="flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-strong,#1d4ed8)] disabled:opacity-50"
            >
              <CirclePlay className="h-4 w-4" />
              {busyAction === "resume" ? "Resuming…" : "Resume"}
            </button>
          )}
          {canCancel && (
            <button
              type="button"
              aria-label="Cancel session"
              disabled={busyAction !== null}
              onClick={() => setConfirmCancel(true)}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-50"
            >
              <Ban className="h-4 w-4" />
              Cancel
            </button>
          )}
          <button
            type="button"
            aria-label="Delete session"
            disabled={busyAction !== null}
            onClick={() => setConfirmDelete(true)}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)] hover:bg-[var(--danger-subtle)] disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
          <button
            type="button"
            aria-label="Refresh session"
            onClick={() => void refresh()}
            className="rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            Refresh
          </button>
        </div>
      </div>

      {actionError && (
        <p role="alert" className="text-sm text-[var(--danger)]">
          {actionError}
        </p>
      )}
      {session.error && (
        <p role="alert" aria-label="Session error" className="rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
          {session.error.stage}: {session.error.message}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <ProgressCard
          label="Items"
          value={`${progress.processed}/${progress.total}`}
          hint={`${progress.percent}% processed`}
        />
        <ProgressCard label="Hashed" value={String(progress.hashed)} hint="sha-256 verified" />
        <ProgressCard
          label="Awaiting review"
          value={String(progress.awaiting_review)}
          hint="commit arrives in M9"
        />
        <ProgressCard
          label="Errors"
          value={String(progress.errors)}
          hint={
            statistics.skipped_junk > 0
              ? `${statistics.skipped_junk} junk file(s) skipped`
              : "no junk skipped"
          }
        />
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
          Pipeline
        </p>
        <StageTracker currentStage={session.current_stage} status={session.status} />
        {session.summary && (
          <p aria-label="Session summary" className="text-sm text-[var(--text-secondary)]">
            {session.summary}
          </p>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-3">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]" aria-label={`Files (${itemsTotal})`}>
            Files ({itemsTotal})
          </h2>
          <p className="text-xs text-[var(--text-tertiary)]">
            structure only — extraction lands in M3
          </p>
        </div>
        {items.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-[var(--text-tertiary)]" aria-label="No files discovered">
            {session.status === "completed"
              ? "No supported files were discovered in this import."
              : "Files will appear here as the pipeline enumerates them."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table aria-label="Session items" className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                  <th className="px-4 py-2 font-medium">File</th>
                  <th className="px-4 py-2 font-medium">Ext</th>
                  <th className="px-4 py-2 font-medium">Size</th>
                  <th className="px-4 py-2 font-medium">MIME</th>
                  <th className="px-4 py-2 font-medium">Stage</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.id}
                    className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]"
                  >
                    <td className="max-w-[22rem] px-4 py-2.5">
                      <p
                        className="truncate font-medium text-[var(--text-primary)]"
                        title={item.relative_path}
                        aria-label={`File ${item.relative_path}`}
                      >
                        {item.relative_path}
                      </p>
                      {item.error && (
                        <p className="truncate text-xs text-[var(--danger)]" title={item.error.message}>
                          {item.error.stage}: {item.error.message}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text-tertiary)]">{item.extension || "—"}</td>
                    <td className="px-4 py-2.5 text-[var(--text-tertiary)]">
                      {formatBytes(item.size_bytes)}
                    </td>
                    <td className="max-w-[14rem] truncate px-4 py-2.5 text-xs text-[var(--text-tertiary)]" title={item.mime_type ?? undefined}>
                      {item.mime_type ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-[var(--text-tertiary)]">{item.stage}</td>
                    <td className="px-4 py-2.5">
                      <StatusChip kind="item" status={item.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {totalPages > 1 && (
          <div className="border-t border-[var(--border-subtle)] px-4 py-2">
            <Pagination
              page={page}
              pageSize={pageSize}
              total={itemsTotal}
              onPageChange={setPage}
              disabled={refreshing}
            />
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmCancel}
        title="Cancel this import?"
        description="Processing stops at the next checkpoint. Files already staged stay recorded, but no new ones will be processed. This cannot be resumed."
        confirmLabel="Cancel import"
        loadingLabel="Cancelling…"
        loading={busyAction === "cancel"}
        onCancel={() => setConfirmCancel(false)}
        onConfirm={() => {
          void act("cancel").then((ok) => {
            if (ok) setConfirmCancel(false);
          });
        }}
      />
      <ConfirmDialog
        open={confirmDelete}
        title="Delete this session?"
        description="The session, its file records and its staged copies are permanently removed. Source files are never touched."
        confirmLabel="Delete session"
        loadingLabel="Deleting…"
        loading={busyAction === "delete"}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          void remove().then((ok) => {
            if (ok) {
              setConfirmDelete(false);
              setDeleted(true);
            }
          });
        }}
      />
    </section>
  );
}
