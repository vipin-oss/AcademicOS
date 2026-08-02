import { Building2, CalendarDays, MapPin, Users } from "lucide-react";
import {
  EventPriorityBadge,
  EventStatusBadge,
  EventTypeBadge,
  UniversalStatusBadge,
} from "@/components/features/events/EventBadges";
import { formatDate } from "@/lib/utils";
import type { EventResponse } from "@/types";

function dateRange(event: EventResponse): string | null {
  if (!event.start_date) return null;
  if (!event.end_date || event.end_date === event.start_date) {
    return formatDate(event.start_date);
  }
  return `${formatDate(event.start_date)} – ${formatDate(event.end_date)}`;
}

/** Workspace identity header (PART 1 core fields + badges). */
export function EventHeader({ event }: { event: EventResponse }) {
  const dates = dateRange(event);
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 shadow-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">{event.title}</h1>
          <p className="mt-1 font-mono text-xs text-[var(--text-tertiary)]">
            {event.event_code || "No event code"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {event.event_type ? <EventTypeBadge type={event.event_type} /> : null}
          <EventStatusBadge status={event.event_status} />
          {event.priority ? <EventPriorityBadge priority={event.priority} /> : null}
          <UniversalStatusBadge status={event.status} />
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm text-[var(--text-secondary)]">
        {event.organizer ? (
          <span className="inline-flex items-center gap-1.5">
            <Users className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
            {event.organizer}
          </span>
        ) : null}
        {dates ? (
          <span className="inline-flex items-center gap-1.5">
            <CalendarDays className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
            {dates}
          </span>
        ) : null}
        {event.venue ? (
          <span className="inline-flex items-center gap-1.5">
            <MapPin className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
            {event.venue}
          </span>
        ) : null}
        {event.department ? (
          <span className="inline-flex items-center gap-1.5">
            <Building2 className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
            {event.department}
            {event.school ? ` · ${event.school}` : ""}
          </span>
        ) : null}
      </div>
    </div>
  );
}
