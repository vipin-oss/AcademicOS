import Link from "next/link";
import {
  AlarmClockCheck,
  Banknote,
  CheckCircle2,
  FlaskConical,
  Landmark,
  PiggyBank,
  Wallet,
} from "lucide-react";
import { formatAmount, formatDate } from "@/lib/research/constants";
import type { ResearchDashboard } from "@/types";

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
      <div className={`flex items-center gap-2 text-xs font-medium uppercase tracking-wide ${toneClass}`}>
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</p>
    </>
  );
  const className =
    "rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm";
  return href ? (
    <Link href={href} className={`${className} block transition-colors hover:border-[var(--accent)]`}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

/** The PART 10 dashboard: six cards + the upcoming-deadlines panel. */
export function ResearchDashboardCards({ dashboard }: { dashboard: ResearchDashboard }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <StatCard
          icon={<FlaskConical className="h-4 w-4" aria-hidden="true" />}
          label="Total Projects"
          value={String(dashboard.total_projects)}
        />
        <StatCard
          icon={<Landmark className="h-4 w-4" aria-hidden="true" />}
          label="Active Projects"
          value={String(dashboard.active_projects)}
          tone="success"
        />
        <StatCard
          icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
          label="Completed"
          value={String(dashboard.completed_projects)}
        />
        <StatCard
          icon={<PiggyBank className="h-4 w-4" aria-hidden="true" />}
          label="Total Grants"
          value={String(dashboard.total_grants)}
          href="/research/grants"
        />
        <StatCard
          icon={<Banknote className="h-4 w-4" aria-hidden="true" />}
          label="Budget Approved"
          value={formatAmount(dashboard.budget_approved)}
        />
        <StatCard
          icon={<Wallet className="h-4 w-4" aria-hidden="true" />}
          label="Budget Utilized"
          value={formatAmount(dashboard.budget_utilized)}
          tone="warning"
        />
      </div>

      <section
        aria-label="Upcoming deadlines"
        className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
      >
        <div className="mb-3 flex items-center gap-2">
          <AlarmClockCheck className="h-4 w-4 text-[var(--accent)]" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Upcoming deadlines</h2>
        </div>
        {dashboard.upcoming_deadlines.length === 0 ? (
          <p className="text-sm text-[var(--text-tertiary)]">
            No pending milestones — add project milestones to track progress reports and reviews.
          </p>
        ) : (
          <ul className="divide-y divide-[var(--border-subtle)]">
            {dashboard.upcoming_deadlines.map((deadline) => (
              <li
                key={deadline.milestone_id}
                className="flex flex-wrap items-center justify-between gap-2 py-2.5"
              >
                <div className="min-w-0">
                  <p className="font-medium text-[var(--text-primary)]">{deadline.title}</p>
                  <Link
                    href={`/research/projects/${encodeURIComponent(deadline.project_id)}`}
                    className="mt-0.5 block text-xs text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:underline"
                  >
                    {deadline.project_title}
                  </Link>
                </div>
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  {formatDate(deadline.date)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
