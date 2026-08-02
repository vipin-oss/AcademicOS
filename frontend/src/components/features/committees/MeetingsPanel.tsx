"use client";

import Link from "next/link";
import { CalendarDays, Plus } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { MeetingModeBadge } from "./CommitteeBadges";
import type { CommitteeMeetingSummary } from "@/types";

/**
 * PART 3 meetings list (date-desc, computed server-side). Each row links to
 * the meeting workspace; creation goes through the meeting modal.
 */
export function MeetingsPanel({
  meetings,
  onAdd,
}: {
  meetings: CommitteeMeetingSummary[];
  onAdd?: () => void;
}) {
  return (
    <section
      aria-label="Committee meetings"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Meetings ({meetings.length})
        </h2>
        {onAdd ? (
          <button
            type="button"
            onClick={onAdd}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" /> New meeting
          </button>
        ) : null}
      </div>
      {meetings.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No meetings yet — schedule the first meeting to start the agenda and action tracker.
        </p>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {meetings.map((meeting) => (
            <li key={meeting.id} className="flex items-start gap-3 py-2.5">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--bg-hover)] text-[var(--text-tertiary)]">
                <CalendarDays className="h-4 w-4" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    href={`/committees/meetings/${encodeURIComponent(meeting.id)}`}
                    className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {meeting.title}
                  </Link>
                  {meeting.mode ? <MeetingModeBadge mode={meeting.mode} /> : null}
                </div>
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                  {[
                    meeting.meeting_number ? `No. ${meeting.meeting_number}` : null,
                    meeting.meeting_date ? formatDate(meeting.meeting_date) : "No date",
                    meeting.venue,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
