import {
  AlarmClock,
  Bell,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  Flame,
} from "lucide-react";
import type { ProductivityDashboard } from "@/types";

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: "default" | "warning" | "success" | "danger";
}

function StatCard({ icon, label, value, tone = "default" }: StatCardProps) {
  const toneClass =
    tone === "warning"
      ? "text-[var(--warning)]"
      : tone === "danger"
        ? "text-[var(--danger)]"
        : tone === "success"
          ? "text-[var(--success)]"
          : "text-[var(--accent)]";
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm">
      <div className={`flex items-center gap-2 text-xs font-medium uppercase tracking-wide ${toneClass}`}>
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

/** The PART 6 dashboard: six personal productivity cards (computed read). */
export function ProductivityDashboardCards({ dashboard }: { dashboard: ProductivityDashboard }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6" aria-label="Productivity dashboard">
      <StatCard
        icon={<ClipboardList className="h-4 w-4" aria-hidden="true" />}
        label="Today's Tasks"
        value={String(dashboard.todays_tasks)}
      />
      <StatCard
        icon={<AlarmClock className="h-4 w-4" aria-hidden="true" />}
        label="Deadlines (7d)"
        value={String(dashboard.upcoming_deadlines)}
        tone={dashboard.upcoming_deadlines > 0 ? "warning" : "default"}
      />
      <StatCard
        icon={<CalendarClock className="h-4 w-4" aria-hidden="true" />}
        label="Meetings (7d)"
        value={String(dashboard.upcoming_meetings)}
      />
      <StatCard
        icon={<Bell className="h-4 w-4" aria-hidden="true" />}
        label="Unread Nudges"
        value={String(dashboard.unread_notifications)}
        tone={dashboard.unread_notifications > 0 ? "warning" : "default"}
      />
      <StatCard
        icon={<Flame className="h-4 w-4" aria-hidden="true" />}
        label="Overdue"
        value={String(dashboard.overdue_items)}
        tone={dashboard.overdue_items > 0 ? "danger" : "default"}
      />
      <StatCard
        icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
        label="Done Today"
        value={String(dashboard.completed_today)}
        tone="success"
      />
    </div>
  );
}
