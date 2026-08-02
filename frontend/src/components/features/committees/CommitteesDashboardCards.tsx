import Link from "next/link";
import {
  CalendarClock,
  CalendarDays,
  CheckCircle2,
  ListChecks,
  UsersRound,
  Workflow,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { CommitteesDashboard } from "@/types";

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  href?: string;
  tone?: "default" | "warning" | "success";
}

function StatCard({ icon, label, value, href, tone = "default" }: StatCardProps) {
  const toneClass =
    tone === "warning"
      ? "text-[var(--warning)]"
      : tone === "success"
        ? "text-[var(--success)]"
        : "text-[var(--accent)]";
  const body = (
    <>
      <div
        className={`flex items-center gap-2 text-xs font-medium uppercase tracking-wide ${toneClass}`}
      >
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</p>
    </>
  );
  const className =
    "rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm";
  return href ? (
    <Link
      href={href}
      className={`${className} block transition-colors hover:border-[var(--accent)]`}
    >
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

/** The PART 8 dashboard: six cards + the upcoming-meetings panel. */
export function CommitteesDashboardCards({ dashboard }: { dashboard: CommitteesDashboard }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <StatCard
          icon={<UsersRound className="h-4 w-4" aria-hidden="true" />}
          label="Total Committees"
          value={String(dashboard.total_committees)}
        />
        <StatCard
          icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
          label="Active Committees"
          value={String(dashboard.active_committees)}
          tone="success"
        />
        <StatCard
          icon={<CalendarDays className="h-4 w-4" aria-hidden="true" />}
          label="Meetings This Month"
          value={String(dashboard.meetings_this_month)}
        />
        <StatCard
          icon={<ListChecks className="h-4 w-4" aria-hidden="true" />}
          label="Pending Actions"
          value={String(dashboard.pending_actions)}
          tone="warning"
        />
        <StatCard
          icon={<Workflow className="h-4 w-4" aria-hidden="true" />}
          label="Completed Actions"
          value={String(dashboard.completed_actions)}
          tone="success"
        />
        <StatCard
          icon={<CalendarClock className="h-4 w-4" aria-hidden="true" />}
          label="Upcoming Meetings"
          value={String(dashboard.upcoming_meetings.length)}
        />
      </div>

      <section
        aria-label="Upcoming meetings"
        className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
      >
        <div className="mb-3 flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-[var(--accent)]" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Upcoming meetings</h2>
        </div>
        {dashboard.upcoming_meetings.length === 0 ? (
          <p className="text-sm text-[var(--text-tertiary)]">
            No scheduled meetings — add meetings to committees to see them here.
          </p>
        ) : (
          <ul className="divide-y divide-[var(--border-subtle)]">
            {dashboard.upcoming_meetings.map((meeting) => (
              <li
                key={meeting.meeting_id}
                className="flex flex-wrap items-center justify-between gap-2 py-2.5"
              >
                <div className="min-w-0">
                  <Link
                    href={`/committees/meetings/${encodeURIComponent(meeting.meeting_id)}`}
                    className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {meeting.title}
                  </Link>
                  <Link
                    href={`/committees/${encodeURIComponent(meeting.committee_id)}`}
                    className="mt-0.5 block text-xs text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {meeting.committee_title}
                  </Link>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">
                    {formatDate(meeting.date)}
                  </p>
                  <p className="text-xs text-[var(--text-tertiary)]">
                    {[meeting.venue, meeting.mode].filter(Boolean).join(" · ") || " "}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
