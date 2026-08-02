import { AlarmClockCheck, CheckCircle2, ClipboardList, Hourglass, Percent, Presentation, TrendingDown, TrendingUp, Users } from "lucide-react";
import Link from "next/link";
import type { StudentSignal, TeachingDashboard } from "@/types";

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
      <div className={`flex items-center gap-2 text-xs font-medium uppercase tracking-wide ${toneClass}`}>
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

function SignalList({
  title,
  icon,
  signals,
  empty,
}: {
  title: string;
  icon: React.ReactNode;
  signals: StudentSignal[];
  empty: string;
}) {
  return (
    <section className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex items-center gap-2">
        {icon}
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
      </div>
      {signals.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">{empty}</p>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {signals.map((signal) => (
            <li
              key={`${signal.student_id}-${signal.class_id ?? ""}`}
              className="flex flex-wrap items-center justify-between gap-2 py-2.5"
            >
              <div className="min-w-0">
                <Link
                  href={`/students/${encodeURIComponent(signal.student_id)}`}
                  className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                >
                  {signal.name}
                </Link>
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                  {[
                    signal.roll_number,
                    signal.class_title,
                    signal.reasons?.length ? signal.reasons.join(" · ") : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <div className="text-right text-sm">
                <p className="font-semibold text-[var(--text-primary)]">
                  {signal.average_marks_percent}%
                </p>
                {signal.attendance_percent != null ? (
                  <p className="text-xs text-[var(--text-tertiary)]">
                    {signal.attendance_percent}% attendance
                  </p>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * The faculty Teaching dashboard (PART J): headline counters + the two
 * signal lists every report needs — weak students (low marks / attendance)
 * and top performers.
 */
export function DashboardCards({ dashboard }: { dashboard: TeachingDashboard }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard
          icon={<Presentation className="h-4 w-4" aria-hidden="true" />}
          label="Classes"
          value={String(dashboard.class_count)}
        />
        <StatCard
          icon={<Users className="h-4 w-4" aria-hidden="true" />}
          label="Students"
          value={String(dashboard.student_count)}
        />
        <StatCard
          icon={<ClipboardList className="h-4 w-4" aria-hidden="true" />}
          label="Assessments"
          value={String(dashboard.assignment_count)}
        />
        <StatCard
          icon={<Hourglass className="h-4 w-4" aria-hidden="true" />}
          label="Pending"
          value={String(dashboard.pending_submissions)}
          tone={dashboard.pending_submissions > 0 ? "warning" : "default"}
        />
        <StatCard
          icon={<AlarmClockCheck className="h-4 w-4" aria-hidden="true" />}
          label="Late"
          value={String(dashboard.late_submissions)}
          tone={dashboard.late_submissions > 0 ? "warning" : "default"}
        />
        <StatCard
          icon={
            dashboard.average_marks_percent != null ? (
              <Percent className="h-4 w-4" aria-hidden="true" />
            ) : (
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            )
          }
          label="Avg marks"
          value={
            dashboard.average_marks_percent != null
              ? `${dashboard.average_marks_percent}%`
              : "—"
          }
          tone="success"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SignalList
          title="Weak students"
          icon={<TrendingDown className="h-4 w-4 text-[var(--danger)]" aria-hidden="true" />}
          signals={dashboard.weak_students}
          empty="No weak-student signals — nobody is below the marks/attendance thresholds."
        />
        <SignalList
          title="Top performers"
          icon={<TrendingUp className="h-4 w-4 text-[var(--success)]" aria-hidden="true" />}
          signals={dashboard.top_performers}
          empty="Top performers appear once marks are graded (≥ 85% average)."
        />
      </div>
    </div>
  );
}
