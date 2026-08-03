"use client";

/**
 * Calendar workspace — the PART 1 aggregated calendar (read-only feed from
 * every module + personal entries) above the personal entry list (PART 2
 * tail). Owns the EntryModal so both the calendar "Add entry" affordance and
 * the list share one editor, and bumps the calendar refreshKey after writes.
 */
import { useCallback, useEffect, useState } from "react";
import { MapPin, Pencil, Plus, Trash2 } from "lucide-react";

import { toErrorMessage } from "@/lib/api/client";
import { deleteCalendarEntry, listCalendarEntries } from "@/lib/api/productivity";
import { taskCategoryLabel } from "@/lib/productivity/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ProductivityCalendar } from "@/components/features/calendar/ProductivityCalendar";
import type { CalendarEntry, CalendarEntryListResult } from "@/types";

import { EntryModal, type EntrySaveResult } from "./EntryModal";
import { formatDay } from "./calendar-utils";

const ACTION_BUTTON_CLASS =
  "rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50";

function formatSpan(entry: CalendarEntry): string {
  if (entry.end_date && entry.end_date !== entry.start_date) {
    return `${formatDay(entry.start_date)} – ${formatDay(entry.end_date)}`;
  }
  return formatDay(entry.start_date);
}

function formatTimes(entry: CalendarEntry): string | null {
  if (!entry.start_time) return null;
  return entry.end_time ? `${entry.start_time}–${entry.end_time}` : entry.start_time;
}

function EntryRow({
  entry,
  busy,
  onEdit,
  onDelete,
}: {
  entry: CalendarEntry;
  busy: boolean;
  onEdit: (entry: CalendarEntry) => void;
  onDelete: (entry: CalendarEntry) => void;
}) {
  const times = formatTimes(entry);
  return (
    <li
      aria-label={entry.title}
      className="flex flex-wrap items-start gap-3 px-4 py-3 sm:flex-nowrap sm:items-center"
    >
      <div className="w-28 shrink-0">
        <p className="text-xs font-semibold text-[var(--accent)]">{formatSpan(entry)}</p>
        {times ? <p className="mt-0.5 text-[11px] tabular-nums text-[var(--text-tertiary)]">{times}</p> : null}
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[var(--text-primary)]">{entry.title}</p>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-[var(--text-tertiary)]">
          {entry.location ? (
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3 w-3" aria-hidden="true" />
              {entry.location}
            </span>
          ) : null}
          {entry.description ? <span className="truncate">{entry.description}</span> : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {entry.category ? (
          <span className="rounded-full bg-[var(--bg-app)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]">
            {taskCategoryLabel(entry.category)}
          </span>
        ) : null}
        {entry.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full border border-[var(--border-subtle)] px-2 py-0.5 text-[11px] text-[var(--text-tertiary)]"
          >
            #{tag}
          </span>
        ))}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          disabled={busy}
          onClick={() => onEdit(entry)}
          aria-label={`Edit: ${entry.title}`}
          title="Edit"
          className={ACTION_BUTTON_CLASS}
        >
          <Pencil className="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDelete(entry)}
          aria-label={`Delete: ${entry.title}`}
          title="Delete"
          className={ACTION_BUTTON_CLASS}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </li>
  );
}

export function CalendarWorkspace() {
  const [entries, setEntries] = useState<CalendarEntryListResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CalendarEntry | null>(null);
  const [initialDate, setInitialDate] = useState<string | undefined>(undefined);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listCalendarEntries()
      .then((data) => {
        if (!cancelled) {
          setEntries(data);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setEntries(null);
          setError(toErrorMessage(err));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const openNew = (date?: string) => {
    setEditing(null);
    setInitialDate(date);
    setModalOpen(true);
  };

  const handleEdit = (entry: CalendarEntry) => {
    setEditing(entry);
    setInitialDate(undefined);
    setModalOpen(true);
  };

  const handleDelete = async (entry: CalendarEntry) => {
    if (!window.confirm(`Delete entry "${entry.title}"?`)) return;
    setBusyId(entry.id);
    setActionError(null);
    try {
      await deleteCalendarEntry(entry.id);
    } catch (err) {
      setActionError(toErrorMessage(err));
    } finally {
      setBusyId(null);
      refresh();
    }
  };

  const handleSaved = (_result: EntrySaveResult) => {
    setModalOpen(false);
    setEditing(null);
    setInitialDate(undefined);
    refresh();
  };

  return (
    <div className="space-y-6">
      <ProductivityCalendar onAddEntry={(date) => openNew(date)} refreshKey={tick} />

      <section aria-label="Personal calendar entries" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            Personal Entries
          </h2>
          <button
            type="button"
            onClick={() => openNew()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            New entry
          </button>
        </div>

        {actionError ? (
          <p
            role="alert"
            className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
          >
            {actionError}
          </p>
        ) : null}

        {loading ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {Array.from({ length: 2 }).map((_, index) => (
              <CardSkeleton key={index} />
            ))}
          </div>
        ) : error ? (
          <p
            role="alert"
            className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
          >
            {error}
          </p>
        ) : entries && entries.items.length > 0 ? (
          <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
            <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-2">
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                {entries.total_count} entr{entries.total_count === 1 ? "y" : "ies"}
              </p>
              {busyId ? <Spinner className="h-3.5 w-3.5" label="Updating entry" /> : null}
            </div>
            <ul aria-label="Personal entry list" className="divide-y divide-[var(--border-subtle)]">
              {entries.items.map((entry) => (
                <EntryRow
                  key={entry.id}
                  entry={entry}
                  busy={busyId === entry.id}
                  onEdit={handleEdit}
                  onDelete={(target) => void handleDelete(target)}
                />
              ))}
            </ul>
          </div>
        ) : (
          <p className="rounded-xl border border-dashed border-[var(--border-subtle)] px-4 py-8 text-center text-sm text-[var(--text-tertiary)]">
            No personal entries yet — add one to see it on the calendar.
          </p>
        )}
      </section>

      <EntryModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditing(null);
          setInitialDate(undefined);
        }}
        onSaved={handleSaved}
        entry={editing}
        initialDate={initialDate}
      />
    </div>
  );
}
