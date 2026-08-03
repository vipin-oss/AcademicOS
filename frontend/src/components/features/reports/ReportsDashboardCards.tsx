"use client";

import {
  Award,
  BookOpen,
  Calendar,
  Coins,
  FlaskConical,
  GraduationCap,
  Presentation,
  Users,
  UsersRound,
  Wallet,
  Wallet2,
} from "lucide-react";
import { formatMoney } from "@/lib/finance/constants";
import type { ReportsDashboard } from "@/types";

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
}

function StatCard({ icon, label, value }: StatCardProps) {
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-[var(--accent)]">
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

/** PART 1 dashboard: module totals + the budget triplet (computed read). */
export function ReportsDashboardCards({ dashboard }: { dashboard: ReportsDashboard }) {
  const cards: StatCardProps[] = [
    { icon: <BookOpen className="h-4 w-4" aria-hidden="true" />, label: "Publications",
      value: String(dashboard.total_publications) },
    { icon: <FlaskConical className="h-4 w-4" aria-hidden="true" />, label: "Research Projects",
      value: String(dashboard.total_projects) },
    { icon: <Coins className="h-4 w-4" aria-hidden="true" />, label: "Grants",
      value: String(dashboard.total_grants) },
    { icon: <GraduationCap className="h-4 w-4" aria-hidden="true" />, label: "Students",
      value: String(dashboard.total_students) },
    { icon: <Presentation className="h-4 w-4" aria-hidden="true" />, label: "Classes",
      value: String(dashboard.total_classes) },
    { icon: <Users className="h-4 w-4" aria-hidden="true" />, label: "Faculty",
      value: String(dashboard.total_faculty) },
    { icon: <UsersRound className="h-4 w-4" aria-hidden="true" />, label: "Committees",
      value: String(dashboard.total_committees) },
    { icon: <Calendar className="h-4 w-4" aria-hidden="true" />, label: "Events",
      value: String(dashboard.total_events) },
    { icon: <Award className="h-4 w-4" aria-hidden="true" />, label: "Budget Approved",
      value: formatMoney(dashboard.budget_approved) },
    { icon: <Wallet className="h-4 w-4" aria-hidden="true" />, label: "Budget Utilized",
      value: formatMoney(dashboard.budget_utilized) },
    { icon: <Wallet2 className="h-4 w-4" aria-hidden="true" />, label: "Budget Remaining",
      value: formatMoney(dashboard.budget_remaining) },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {cards.map((card) => (
        <StatCard key={card.label} {...card} />
      ))}
    </div>
  );
}
