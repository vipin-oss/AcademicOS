import Link from "next/link";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import {
  EventModeBadge,
  EventPriorityBadge,
  EventStatusBadge,
  EventTypeBadge,
} from "@/components/features/events/EventBadges";
import { formatDate } from "@/lib/utils";
import type { EventResponse } from "@/types";

function dateRange(event: EventResponse): string {
  if (!event.start_date) return "—";
  if (!event.end_date || event.end_date === event.start_date) {
    return formatDate(event.start_date);
  }
  return `${formatDate(event.start_date)} – ${formatDate(event.end_date)}`;
}

/** PART 1 directory table (title+code/type/dates/venue/dept/status/priority). */
export function EventTable({
  events,
  loading,
}: {
  events: EventResponse[];
  loading: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[940px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-4 py-3 font-medium">Event</th>
            <th className="px-4 py-3 font-medium">Type</th>
            <th className="px-4 py-3 font-medium">Dates</th>
            <th className="px-4 py-3 font-medium">Venue / Mode</th>
            <th className="px-4 py-3 font-medium">Department</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Priority</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={5} cols={7} />
          ) : (
            events.map((event) => (
              <tr
                key={event.id}
                className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/events/${encodeURIComponent(event.id)}`}
                    className="font-medium text-[var(--accent)] hover:underline"
                  >
                    {event.title}
                  </Link>
                  <p className="mt-0.5 font-mono text-xs text-[var(--text-tertiary)]">
                    {event.event_code || "—"}
                  </p>
                </td>
                <td className="px-4 py-3">
                  {event.event_type ? <EventTypeBadge type={event.event_type} /> : "—"}
                </td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">{dateRange(event)}</td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  <span className="block">{event.venue || "—"}</span>
                  {event.mode ? (
                    <span className="mt-1 inline-block">
                      <EventModeBadge mode={event.mode} />
                    </span>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  {event.department || "—"}
                </td>
                <td className="px-4 py-3">
                  <EventStatusBadge status={event.event_status} />
                </td>
                <td className="px-4 py-3">
                  {event.priority ? <EventPriorityBadge priority={event.priority} /> : "—"}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
