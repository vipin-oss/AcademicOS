"use client";

import { useCallback, useState } from "react";
import { CalendarPlus, CheckCircle2, Circle, Loader, MessageSquarePlus, Trash2 } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { deleteMilestone, updateMilestone } from "@/lib/api/research";
import { formatDate } from "@/lib/research/constants";
import { MilestoneStatusBadge } from "./ResearchBadges";
import type { ProjectMilestone, ProjectResponse } from "@/types";

/**
 * PART 8 timeline: milestones (with mark-done / delete) + the progress-update
 * feed + the completion bar. Mutations flow back through `onChanged` so the
 * workspace re-fetches the enriched payload (single source of truth).
 */
export function TimelinePanel({
  project,
  onAddMilestone,
  onLogUpdate,
  onChanged,
}: {
  project: ProjectResponse;
  onAddMilestone: () => void;
  onLogUpdate: () => void;
  onChanged: () => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const latestPercent =
    project.progress_updates.length > 0
      ? project.progress_updates[project.progress_updates.length - 1].percent
      : null;

  const mutate = useCallback(
    async (milestone: ProjectMilestone, action: "done" | "delete") => {
      if (busyId) return;
      setBusyId(milestone.id);
      setError(null);
      try {
        if (action === "done") await updateMilestone(milestone.id, { status: "done" });
        else await deleteMilestone(milestone.id);
        onChanged();
      } catch (err) {
        setError(toErrorMessage(err, "Milestone update failed."));
      } finally {
        setBusyId(null);
      }
    },
    [busyId, onChanged],
  );

  return (
    <section
      aria-label="Timeline"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Timeline</h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onAddMilestone}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <CalendarPlus className="h-3.5 w-3.5" aria-hidden="true" /> Add milestone
          </button>
          <button
            type="button"
            onClick={onLogUpdate}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden="true" /> Log update
          </button>
        </div>
      </div>

      {latestPercent != null ? (
        <div className="mb-4">
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(latestPercent)}
            aria-label="Project completion"
          >
            <div
              className="h-full rounded-full bg-[var(--success)] transition-all"
              style={{ width: `${Math.round(latestPercent)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            {Math.round(latestPercent)}% complete (latest logged update)
          </p>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="mb-2 text-xs text-[var(--danger)]">{error}</p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
            Milestones
          </h3>
          {project.milestones.length === 0 ? (
            <p className="text-sm text-[var(--text-tertiary)]">No milestones yet.</p>
          ) : (
            <ul className="divide-y divide-[var(--border-subtle)]">
              {project.milestones.map((milestone) => (
                <li key={milestone.id} className="flex items-start justify-between gap-2 py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {milestone.title}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                      {formatDate(milestone.date)}
                      {milestone.notes ? ` · ${milestone.notes}` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <MilestoneStatusBadge status={milestone.status} />
                    {milestone.status !== "done" ? (
                      <button
                        type="button"
                        onClick={() => mutate(milestone, "done")}
                        disabled={busyId != null}
                        aria-label={`Mark ${milestone.title} done`}
                        title="Mark done"
                        className="rounded-lg p-1 text-[var(--text-secondary)] transition-colors hover:text-[var(--success)] disabled:opacity-50"
                      >
                        {busyId === milestone.id ? (
                          <Loader className="h-4 w-4 animate-spin" aria-hidden="true" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                        )}
                      </button>
                    ) : (
                      <Circle className="h-4 w-4 text-[var(--success)]" aria-hidden="true" />
                    )}
                    <button
                      type="button"
                      onClick={() => mutate(milestone, "delete")}
                      disabled={busyId != null}
                      aria-label={`Delete ${milestone.title}`}
                      title="Delete"
                      className="rounded-lg p-1 text-[var(--text-secondary)] transition-colors hover:text-[var(--danger)] disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
            Progress updates
          </h3>
          {project.progress_updates.length === 0 ? (
            <p className="text-sm text-[var(--text-tertiary)]">No updates logged yet.</p>
          ) : (
            <ul className="divide-y divide-[var(--border-subtle)]">
              {[...project.progress_updates].reverse().map((update, index) => (
                <li key={`${update.date}-${index}`} className="flex items-start justify-between gap-2 py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm text-[var(--text-secondary)]">{update.remark}</p>
                    <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                      {formatDate(update.date)}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-semibold text-[var(--text-primary)]">
                    {update.percent}%
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
