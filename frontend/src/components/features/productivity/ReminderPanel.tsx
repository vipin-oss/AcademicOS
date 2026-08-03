"use client";

/**
 * Reminder panel (PART 5): the five engine buckets — overdue, due today,
 * upcoming today, tomorrow, this week — computed server-side over every
 * module. Pure read; the refresh sweep lives in the Notification Center.
 */
import Link from "next/link";
import { AlertTriangle, AlarmClock, CalendarClock, Sunrise, CalendarRange } from "lucide-react";

import { useReminders } from "@/hooks/useProductivity";
import { priorityLabel } from "@/lib/productivity/constants";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import type { ReminderItem, RemindersFeed } from "@/types";

import { formatDay, sourceColor, sourceLabel } from "./calendar-utils";

const BUCKETS: {
  key: keyof Pick<
    RemindersFeed,
    "overdue" | "due_today" | "upcoming_today" | "tomorrow" | "this_week"
  >;
  label: string;
  icon: React.ReactNode;
  toneClass: string;
}[] = [
  {
    key: "overdue",
    label: "Overdue",
    icon: <AlertTriangle className="h-4 w-4" aria-hidden="true" />,
    toneClass: "text-[var(--danger)]",
  },
  {
    key: "due_today",
    label: "Due today",
    icon: <AlarmClock className="h-4 w-4" aria-hidden="true" />,
    toneClass: "text-[var(--warning)]",
  },
  {
    key: "upcoming_today",
    label: "Upcoming today",
    icon: <Sunrise className="h-4 w-4" aria-hidden="true" />,
    toneClass: "text-[var(--accent)]",
  },
  {
    key: "tomorrow",
    label: "Tomorrow",
    icon: <CalendarClock className="h-4 w-4" aria-hidden="true" />,
    toneClass: "text-[var(--text-secondary)]",
  },
  {
    key: "this_week",
    label: "This week",
    icon: <CalendarRange className="h-4 w-4" aria-hidden="true" />,
    toneClass: "text-[var(--text-secondary)]",
  },
];

function ReminderRow({ item }: { item: ReminderItem }) {
  return (
    <li>
      <Link
        href={item.href}
        className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-[var(--bg-hover)]"
      >
        <span
          aria-hidden="true"
          className="h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: sourceColor(item.source) }}
        />
        <span className="w-20 shrink-0 text-xs tabular-nums text-[var(--text-tertiary)]">
          {formatDay(item.date)}
        </span>
        <span className="min-w-0 flex-1 truncate text-[var(--text-primary)]">{item.title}</span>
        {item.subtitle ? (
          <span className="hidden truncate text-xs text-[var(--text-tertiary)] sm:inline">
            {item.subtitle}
          </span>
        ) : null}
        {item.priority ? (
          <span
            className={`shrink-0 text-[11px] font-medium ${
              item.priority === "high" ? "text-[var(--danger)]" : "text-[var(--text-tertiary)]"
            }`}
          >
            {priorityLabel(item.priority)}
          </span>
        ) : null}
        <span className="shrink-0 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">
          {sourceLabel(item.source)}
        </span>
      </Link>
    </li>
  );
}

export function ReminderPanel() {
  const { reminders, loading, error } = useReminders();

  return (
    <section aria-label="Reminders" className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
        Reminders
      </h2>
      {loading ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
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
      ) : reminders ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {BUCKETS.map((bucket) => {
            const items = reminders[bucket.key];
            return (
              <section
                key={bucket.key}
                aria-label={bucket.label}
                className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]"
              >
                <h3
                  className={`flex items-center gap-2 border-b border-[var(--border-subtle)] px-3 py-2 text-xs font-semibold uppercase tracking-wide ${bucket.toneClass}`}
                >
                  {bucket.icon}
                  {bucket.label}
                  <span className="ml-auto rounded-full bg-[var(--bg-app)] px-2 py-0.5 text-[11px] tabular-nums text-[var(--text-secondary)]">
                    {items.length}
                  </span>
                </h3>
                {items.length > 0 ? (
                  <ul className="space-y-0.5 p-1.5">
                    {items.map((item) => (
                      <ReminderRow key={item.id} item={item} />
                    ))}
                  </ul>
                ) : (
                  <p className="px-3 py-4 text-center text-xs text-[var(--text-tertiary)]">
                    Nothing here.
                  </p>
                )}
              </section>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
