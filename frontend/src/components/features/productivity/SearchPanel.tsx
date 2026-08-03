"use client";

/**
 * Unified productivity search (PART 7): tasks + notifications + the calendar
 * feed, filtered by title text, date range, priority, category and source
 * module. Hits link straight back into the owning module.
 */
import { useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";

import { useProductivitySearch } from "@/hooks/useProductivity";
import {
  NOTIFICATION_CATEGORIES,
  TASK_CATEGORIES,
  TASK_PRIORITIES,
  notificationCategoryLabel,
  priorityLabel,
  taskCategoryLabel,
} from "@/lib/productivity/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { ProductivitySearchHit } from "@/types";

import { formatDay, sourceColor, sourceLabel } from "./calendar-utils";

const FILTER_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none";

const SEARCH_SOURCES = [
  { value: "tasks", label: "Tasks" },
  { value: "notifications", label: "Notifications" },
  { value: "calendar", label: "Calendar" },
] as const;

function categoryLabelFor(result: ProductivitySearchHit): string {
  if (!result.category) return "";
  if (result.source === "notifications") return notificationCategoryLabel(result.category);
  return taskCategoryLabel(result.category);
}

function ResultRow({ result }: { result: ProductivitySearchHit }) {
  return (
    <li>
      <Link
        href={result.href}
        className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-[var(--bg-hover)]"
      >
        <span
          aria-hidden="true"
          className="h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: sourceColor(result.source) }}
        />
        <span className="w-24 shrink-0 rounded-full bg-[var(--bg-app)] px-2 py-0.5 text-center text-[11px] font-medium text-[var(--text-secondary)]">
          {result.kind}
        </span>
        <span className="min-w-0 flex-1 truncate text-[var(--text-primary)]">{result.title}</span>
        {result.snippet ? (
          <span className="hidden max-w-56 truncate text-xs text-[var(--text-tertiary)] lg:inline">
            {result.snippet}
          </span>
        ) : null}
        {result.priority ? (
          <span
            className={`shrink-0 text-[11px] font-medium ${
              result.priority === "high" ? "text-[var(--danger)]" : "text-[var(--text-tertiary)]"
            }`}
          >
            {priorityLabel(result.priority)}
          </span>
        ) : null}
        {categoryLabelFor(result) ? (
          <span className="shrink-0 text-[11px] text-[var(--text-tertiary)]">
            {categoryLabelFor(result)}
          </span>
        ) : null}
        <span className="w-20 shrink-0 text-right text-xs tabular-nums text-[var(--text-tertiary)]">
          {result.date ? formatDay(result.date) : "—"}
        </span>
        <span className="shrink-0 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">
          {sourceLabel(result.source)}
        </span>
      </Link>
    </li>
  );
}

export function SearchPanel() {
  const [q, setQ] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");

  const { results, loading, error } = useProductivitySearch({
    q,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    priority: priority || undefined,
    category: category || undefined,
    source: source || undefined,
  });

  const hasQuery = Boolean(q.trim() || dateFrom || source);

  return (
    <section aria-label="Productivity search" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-40 flex-1 sm:max-w-sm">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-tertiary)]"
            aria-hidden="true"
          />
          <input
            type="text"
            value={q}
            onChange={(change) => setQ(change.target.value)}
            aria-label="Search productivity"
            placeholder="Search tasks, notifications, calendar…"
            className={`${FILTER_CLASS} w-full pl-8`}
          />
        </div>
        <select
          value={source}
          onChange={(change) => setSource(change.target.value)}
          aria-label="Filter by source"
          className={FILTER_CLASS}
        >
          <option value="">Everywhere</option>
          {SEARCH_SOURCES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={priority}
          onChange={(change) => setPriority(change.target.value)}
          aria-label="Filter by priority"
          className={FILTER_CLASS}
        >
          <option value="">All priorities</option>
          {TASK_PRIORITIES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={category}
          onChange={(change) => setCategory(change.target.value)}
          aria-label="Filter by category"
          className={FILTER_CLASS}
        >
          <option value="">All categories</option>
          <optgroup label="Task categories">
            {TASK_CATEGORIES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </optgroup>
          <optgroup label="Notification categories">
            {NOTIFICATION_CATEGORIES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </optgroup>
        </select>
        <input
          type="date"
          value={dateFrom}
          onChange={(change) => setDateFrom(change.target.value)}
          aria-label="From date"
          className={FILTER_CLASS}
        />
        <input
          type="date"
          value={dateTo}
          onChange={(change) => setDateTo(change.target.value)}
          aria-label="To date"
          className={FILTER_CLASS}
        />
      </div>

      {error ? (
        <p
          role="alert"
          className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
        >
          {error}
        </p>
      ) : !hasQuery ? (
        <p className="rounded-xl border border-dashed border-[var(--border-subtle)] px-4 py-8 text-center text-sm text-[var(--text-tertiary)]">
          Type a title, or pick a source / date range, to search across tasks, notifications and
          the calendar.
        </p>
      ) : loading ? (
        <p className="flex items-center gap-2 px-1 py-4 text-sm text-[var(--text-tertiary)]">
          <Spinner className="h-4 w-4" label="Searching" />
          Searching…
        </p>
      ) : results && results.items.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
          <p className="border-b border-[var(--border-subtle)] px-4 py-2 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
            {results.total_count} result{results.total_count === 1 ? "" : "s"}
          </p>
          <ul aria-label="Search results" className="space-y-0.5 p-1.5">
            {results.items.map((result) => (
              <ResultRow key={result.id} result={result} />
            ))}
          </ul>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-[var(--border-subtle)] px-4 py-8 text-center text-sm text-[var(--text-tertiary)]">
          No matches — try widening the date range or removing filters.
        </p>
      )}
    </section>
  );
}
