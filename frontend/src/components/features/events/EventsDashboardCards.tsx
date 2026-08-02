import {
  Award,
  CalendarClock,
  CheckCircle2,
  Mic,
  Presentation,
  UserCheck,
  Users,
} from "lucide-react";
import type { EventsDashboard } from "@/types";

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: "default" | "warning" | "success";
}

function StatCard({ icon, label, value, tone = "default" }: StatCardProps) {
  const toneClass =
    tone === "warning"
      ? "text-[var(--warning)]"
      : tone === "success"
        ? "text-[var(--success)]"
        : "text-[var(--accent)]";
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm">
      <div
        className={`flex items-center gap-2 text-xs font-medium uppercase tracking-wide ${toneClass}`}
      >
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

/** The PART 9 dashboard: seven personal activity cards (computed read). */
export function EventsDashboardCards({ dashboard }: { dashboard: EventsDashboard }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
      <StatCard
        icon={<CalendarClock className="h-4 w-4" aria-hidden="true" />}
        label="Upcoming Events"
        value={String(dashboard.upcoming_events)}
      />
      <StatCard
        icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
        label="Completed Events"
        value={String(dashboard.completed_events)}
        tone="success"
      />
      <StatCard
        icon={<Users className="h-4 w-4" aria-hidden="true" />}
        label="Events Organized"
        value={String(dashboard.events_organized)}
      />
      <StatCard
        icon={<UserCheck className="h-4 w-4" aria-hidden="true" />}
        label="Events Attended"
        value={String(dashboard.events_attended)}
      />
      <StatCard
        icon={<Award className="h-4 w-4" aria-hidden="true" />}
        label="Certificates"
        value={String(dashboard.certificates)}
        tone="success"
      />
      <StatCard
        icon={<Presentation className="h-4 w-4" aria-hidden="true" />}
        label="Presentations"
        value={String(dashboard.presentations)}
      />
      <StatCard
        icon={<Mic className="h-4 w-4" aria-hidden="true" />}
        label="Invited Talks"
        value={String(dashboard.invited_talks)}
        tone="warning"
      />
    </div>
  );
}
