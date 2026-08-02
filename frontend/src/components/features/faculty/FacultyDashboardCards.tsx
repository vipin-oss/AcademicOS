import {
  BookOpen,
  FlaskConical,
  GraduationCap,
  Presentation,
  Users,
  Wallet,
} from "lucide-react";
import type { FacultyStats } from "@/types";

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

/** The PART 6 faculty dashboard: six computed cards (read from the payload's `stats`). */
export function FacultyDashboardCards({ stats }: { stats: FacultyStats }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      <StatCard
        icon={<BookOpen className="h-4 w-4" aria-hidden="true" />}
        label="Publications"
        value={String(stats.publications)}
      />
      <StatCard
        icon={<FlaskConical className="h-4 w-4" aria-hidden="true" />}
        label="Active Projects"
        value={String(stats.active_projects)}
        tone="success"
      />
      <StatCard
        icon={<Wallet className="h-4 w-4" aria-hidden="true" />}
        label="Research Grants"
        value={String(stats.grants)}
      />
      <StatCard
        icon={<GraduationCap className="h-4 w-4" aria-hidden="true" />}
        label="Students Supervised"
        value={String(stats.students_supervised)}
      />
      <StatCard
        icon={<Presentation className="h-4 w-4" aria-hidden="true" />}
        label="Courses"
        value={String(stats.courses)}
      />
      <StatCard
        icon={<Users className="h-4 w-4" aria-hidden="true" />}
        label="Committees"
        value={String(stats.committees)}
        tone="warning"
      />
    </div>
  );
}
