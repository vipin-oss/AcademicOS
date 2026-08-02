"use client";

import { useState } from "react";
import { CheckCircle2, Pencil, Plus, Trash2 } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { deleteActionItem, updateActionItem } from "@/lib/api/committees";
import { formatDate } from "@/lib/utils";
import { Spinner } from "@/components/features/objects/Spinner";
import { ActionPriorityBadge, ActionStatusBadge } from "./CommitteeBadges";
import type { ActionItem, MeetingResponse } from "@/types";

/**
 * PART 5 action tracker: per-item status/progress with quick actions
 * (mark done, edit, delete). All mutations return the item; the workspace
 * reloads the meeting afterwards so the stats stay consistent.
 */
export function ActionTrackerPanel({
  meeting,
  onAdd,
  onEdit,
  onChanged,
  onError,
}: {
  meeting: MeetingResponse;
  onAdd: () => void;
  onEdit: (action: ActionItem) => void;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const items = meeting.action_items ?? [];

  const handleMarkDone = async (item: ActionItem) => {
    if (busyId) return;
    setBusyId(item.id);
    try {
      await updateActionItem(item.id, {
        status: "done",
        progress: 100,
        completion_date:
          item.completion_date ?? new Date().toISOString().slice(0, 10),
      });
      onChanged();
    } catch (err) {
      onError(toErrorMessage(err, "Could not update the action item."));
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (item: ActionItem) => {
    if (busyId) return;
    setBusyId(item.id);
    try {
      await deleteActionItem(item.id);
      onChanged();
    } catch (err) {
      onError(toErrorMessage(err, "Could not delete the action item."));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section
      aria-label="Action tracker"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Action Tracker ({items.length})
        </h2>
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add action
        </button>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No action items yet — add follow-ups assigned to faculty with due dates.
        </p>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {items.map((item) => (
            <li key={item.id} className="py-2.5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p
                      className={`font-medium ${
                        item.status === "done"
                          ? "text-[var(--text-tertiary)] line-through"
                          : "text-[var(--text-primary)]"
                      }`}
                    >
                      {item.title}
                    </p>
                    <ActionStatusBadge status={item.status} />
                    {item.priority ? <ActionPriorityBadge priority={item.priority} /> : null}
                  </div>
                  <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                    {[
                      item.assigned_name ? `Assigned to ${item.assigned_name}` : null,
                      item.due_date ? `due ${formatDate(item.due_date)}` : null,
                      item.completion_date
                        ? `completed ${formatDate(item.completion_date)}`
                        : null,
                      item.remarks,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {busyId === item.id ? <Spinner className="h-3.5 w-3.5" /> : null}
                  {item.status !== "done" ? (
                    <button
                      type="button"
                      onClick={() => handleMarkDone(item)}
                      disabled={busyId !== null}
                      aria-label={`Mark "${item.title}" done`}
                      title="Mark done"
                      className="rounded-lg p-1.5 text-[var(--success)] transition-colors hover:bg-[var(--success-subtle)] disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => onEdit(item)}
                    disabled={busyId !== null}
                    aria-label={`Edit "${item.title}"`}
                    title="Edit"
                    className="rounded-lg p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
                  >
                    <Pencil className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(item)}
                    disabled={busyId !== null}
                    aria-label={`Delete "${item.title}"`}
                    title="Delete"
                    className="rounded-lg p-1.5 text-[var(--danger)] transition-colors hover:bg-[var(--danger-subtle)] disabled:opacity-50"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <div
                  role="progressbar"
                  aria-valuenow={item.progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Progress of "${item.title}"`}
                  className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-[var(--bg-hover)]"
                >
                  <div
                    className={`h-full rounded-full ${
                      item.status === "done" ? "bg-[var(--success)]" : "bg-[var(--accent)]"
                    }`}
                    style={{ width: `${Math.min(100, Math.max(0, item.progress))}%` }}
                  />
                </div>
                <span className="text-xs text-[var(--text-tertiary)]">{item.progress}%</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
