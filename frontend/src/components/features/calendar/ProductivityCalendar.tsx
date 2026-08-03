"use client";

/**
 * Aggregated calendar — Day / Week / Month / Agenda views (PART 1) over the
 * PART 2 read-only feed. Zero-dependency rendering (the SvgChart doctrine):
 * CSS grid month matrix, week/day columns, grouped agenda — all layouts of
 * the same window feed, no chart/calendar library.
 */
import Link from "next/link";
import { useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, ListPlus } from "lucide-react";

import { useCalendarFeed } from "@/hooks/useProductivity";
import type { CalendarItem, CalendarView } from "@/types";
import {
  addDays,
  datesBetween,
  formatDay,
  formatLong,
  monthMatrix,
  SOURCE_ORDER,
  sourceColor,
  sourceLabel,
  todayIso,
} from "@/components/features/productivity/calendar-utils";

function chipsFor(items: CalendarItem[], max = 3) {
  const shown = items.slice(0, max);
  return (
    <>
      {shown.map((item) => (
        <Link
          key={item.id}
          href={item.href}
          title={`${item.title}${item.subtitle ? ` — ${item.subtitle}` : ""}`}
          className="block truncate rounded px-1 py-0.5 text-[11px] leading-4 text-white hover:opacity-80"
          style={{ backgroundColor: sourceColor(item.source) }}
        >
          {item.start_time ? `${item.start_time} ` : ""}
          {item.title}
        </Link>
      ))}
      {items.length > max ? (
        <span className="px-1 text-[10px] text-[var(--text-tertiary)]">+{items.length - max} more</span>
      ) : null}
    </>
  );
}

function DayColumn({ date, items, today }: { date: string; items: CalendarItem[]; today: string }) {
  const isToday = date === today;
  return (
    <section
      aria-label={formatLong(date)}
      className={`rounded-lg border p-2 ${
        isToday ? "border-[var(--accent)] bg-[var(--accent-subtle,var(--bg-surface))]" : "border-[var(--border-subtle)] bg-[var(--bg-surface)]"
      }`}
    >
      <header className="mb-1.5 flex items-baseline justify-between">
        <span className={`text-xs font-semibold ${isToday ? "text-[var(--accent)]" : "text-[var(--text-secondary)]"}`}>
          {formatDay(date)}
        </span>
        {isToday ? <span className="text-[10px] font-medium uppercase text-[var(--accent)]">Today</span> : null}
      </header>
      <div className="space-y-1">
        {items.length === 0 ? (
          <p className="text-[11px] text-[var(--text-tertiary)]">—</p>
        ) : (
          chipsFor(items, 6)
        )}
      </div>
    </section>
  );
}

export function ProductivityCalendar({
  onAddEntry,
  refreshKey = 0,
}: {
  onAddEntry?: (date: string) => void;
  /** Bump to force the window feed to refetch (e.g. after editing entries). */
  refreshKey?: number;
}) {
  const [view, setView] = useState<CalendarView>("month");
  const [cursor, setCursor] = useState(todayIso());
  const [enabled, setEnabled] = useState<string[]>([...SOURCE_ORDER]);
  const today = todayIso();

  const window = useMemo(() => {
    if (view === "month") {
      const matrix = monthMatrix(cursor);
      return { from: matrix[0][0], to: matrix[matrix.length - 1][6] };
    }
    if (view === "week") {
      const day = new Date(`${cursor}T00:00:00`);
      const offset = (day.getDay() + 6) % 7;
      const start = addDays(cursor, -offset);
      return { from: start, to: addDays(start, 6) };
    }
    if (view === "day") return { from: cursor, to: cursor };
    return { from: cursor, to: addDays(cursor, 29) }; // agenda: 30 days
  }, [view, cursor]);

  const { feed, loading, error } = useCalendarFeed(window.from, window.to, enabled, refreshKey);

  const itemsByDate = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    for (const item of feed?.items ?? []) {
      const key = item.date;
      if (!map.has(key)) map.set(key, []);
      map.get(key)?.push(item);
    }
    return map;
  }, [feed]);

  const weeks = useMemo(() => monthMatrix(cursor), [cursor]);

  function shift(delta: number) {
    if (view === "month") {
      const [y, m] = cursor.split("-").map(Number);
      const target = new Date(y, m - 1 + delta, 1);
      setCursor(
        `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, "0")}-01`,
      );
    } else if (view === "week") setCursor(addDays(cursor, delta * 7));
    else if (view === "day") setCursor(addDays(cursor, delta));
    else setCursor(addDays(cursor, delta * 30));
  }

  function toggleSource(source: string) {
    setEnabled((prev) =>
      prev.includes(source) ? prev.filter((s) => s !== source) : [...prev, source],
    );
  }

  const heading =
    view === "month"
      ? new Date(`${cursor}T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" })
      : view === "day"
        ? formatLong(cursor)
        : `${formatDay(window.from)} – ${formatDay(window.to)}`;

  return (
    <section aria-label="Productivity calendar" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-0.5" role="tablist" aria-label="Calendar view">
          {(["day", "week", "month", "agenda"] as CalendarView[]).map((v) => (
            <button
              key={v}
              role="tab"
              aria-selected={view === v}
              onClick={() => setView(v)}
              className={`rounded-md px-3 py-1 text-xs font-medium capitalize ${
                view === v ? "bg-[var(--accent)] text-white" : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <button aria-label="Previous" onClick={() => shift(-1)} className="rounded-md border border-[var(--border-subtle)] p-1.5 hover:bg-[var(--bg-hover)]">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button onClick={() => setCursor(today)} className="rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs font-medium hover:bg-[var(--bg-hover)]">
            Today
          </button>
          <button aria-label="Next" onClick={() => shift(1)} className="rounded-md border border-[var(--border-subtle)] p-1.5 hover:bg-[var(--bg-hover)]">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        <h2 className="text-base font-semibold text-[var(--text-primary)]">{heading}</h2>
        {onAddEntry ? (
          <button
            onClick={() => onAddEntry(cursor)}
            className="ml-auto inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
          >
            <ListPlus className="h-3.5 w-3.5" aria-hidden="true" /> Add entry
          </button>
        ) : null}
      </div>

      <fieldset className="flex flex-wrap gap-1.5" aria-label="Calendar sources">
        {SOURCE_ORDER.map((source) => {
          const on = enabled.includes(source);
          return (
            <button
              key={source}
              onClick={() => toggleSource(source)}
              aria-pressed={on}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                on
                  ? "border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-primary)]"
                  : "border-dashed border-[var(--border-subtle)] text-[var(--text-tertiary)]"
              }`}
            >
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: on ? sourceColor(source) : "var(--border-subtle)" }}
              />
              {sourceLabel(source)}
            </button>
          );
        })}
      </fieldset>

      {error ? (
        <p role="alert" className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </p>
      ) : null}

      <div aria-busy={loading} className={loading ? "opacity-60" : ""}>
        {view === "month" ? (
          <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
            <div className="grid grid-cols-7 border-b border-[var(--border-subtle)] bg-[var(--bg-app)] text-center text-[11px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                <div key={d} className="py-2">{d}</div>
              ))}
            </div>
            {weeks.map((week, wi) => (
              <div key={wi} className="grid grid-cols-7 divide-x divide-[var(--border-subtle)] border-b border-[var(--border-subtle)] last:border-b-0">
                {week.map((day) => {
                  const inMonth = day.slice(5, 7) === cursor.slice(5, 7);
                  const isToday = day === today;
                  return (
                    <div
                      key={day}
                      data-date={day}
                      className={`min-h-[88px] p-1.5 align-top ${inMonth ? "" : "bg-[var(--bg-app)]"} ${
                        isToday ? "outline outline-1 outline-[var(--accent)]" : ""
                      }`}
                    >
                      <div className={`mb-1 text-right text-[11px] font-medium ${
                        isToday ? "text-[var(--accent)]" : inMonth ? "text-[var(--text-secondary)]" : "text-[var(--text-tertiary)]"
                      }`}>
                        {Number(day.slice(8, 10))}
                      </div>
                      <div className="space-y-1">{chipsFor(itemsByDate.get(day) ?? [], 3)}</div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        ) : view === "week" ? (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 lg:grid-cols-7">
            {datesBetween(window.from, window.to).map((day) => (
              <DayColumn key={day} date={day} items={itemsByDate.get(day) ?? []} today={today} />
            ))}
          </div>
        ) : view === "day" ? (
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3">
            <DayColumn date={cursor} items={itemsByDate.get(cursor) ?? []} today={today} />
          </div>
        ) : (
          <AgendaList itemsByDate={itemsByDate} from={window.from} to={window.to} today={today} />
        )}
      </div>

      {(feed?.items.length ?? 0) === 0 && !loading && !error ? (
        <p className="flex items-center gap-2 rounded-lg border border-dashed border-[var(--border-subtle)] px-3 py-4 text-sm text-[var(--text-tertiary)]">
          <CalendarDays className="h-4 w-4" aria-hidden="true" />
          Nothing scheduled in this window for the selected sources.
        </p>
      ) : null}
    </section>
  );
}

function AgendaList({
  itemsByDate,
  from,
  to,
  today,
}: {
  itemsByDate: Map<string, CalendarItem[]>;
  from: string;
  to: string;
  today: string;
}) {
  const days = datesBetween(from, to).filter((day) => (itemsByDate.get(day) ?? []).length > 0);
  return (
    <div className="space-y-3" aria-label="Agenda">
      {days.length === 0 ? null : (
        days.map((day) => (
          <section key={day} aria-label={formatLong(day)} className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
            <h3 className={`border-b border-[var(--border-subtle)] px-4 py-2 text-sm font-semibold ${
              day === today ? "text-[var(--accent)]" : "text-[var(--text-primary)]"
            }`}>
              {formatDay(day)}
              {day === today ? <span className="ml-2 text-[10px] font-medium uppercase">Today</span> : null}
            </h3>
            <ul className="divide-y divide-[var(--border-subtle)]">
              {(itemsByDate.get(day) ?? []).map((item) => (
                <li key={item.id}>
                  <Link href={item.href} className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-[var(--bg-hover)]">
                    <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: sourceColor(item.source) }} />
                    <span className="w-12 shrink-0 text-xs tabular-nums text-[var(--text-tertiary)]">
                      {item.start_time ?? "—"}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[var(--text-primary)]">{item.title}</span>
                    {item.subtitle ? (
                      <span className="hidden truncate text-xs text-[var(--text-tertiary)] sm:inline">{item.subtitle}</span>
                    ) : null}
                    <span className="shrink-0 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)]">
                      {sourceLabel(item.source)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
