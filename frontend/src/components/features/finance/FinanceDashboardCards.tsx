import Link from "next/link";
import {
  Building2,
  FileText,
  Hourglass,
  Landmark,
  Package,
  Receipt,
  Wallet,
} from "lucide-react";
import { formatMoney } from "@/lib/finance/constants";
import type { FinanceDashboard } from "@/types";

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

/** The PART 11 dashboard: seven procurement cards. */
export function FinanceDashboardCards({ dashboard }: { dashboard: FinanceDashboard }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
      <StatCard
        icon={<FileText className="h-4 w-4" aria-hidden="true" />}
        label="Active Procurements"
        value={String(dashboard.active_procurements)}
      />
      <StatCard
        icon={<Hourglass className="h-4 w-4" aria-hidden="true" />}
        label="Pending Approvals"
        value={String(dashboard.pending_approvals)}
        tone="warning"
      />
      <StatCard
        icon={<Building2 className="h-4 w-4" aria-hidden="true" />}
        label="Total Vendors"
        value={String(dashboard.total_vendors)}
        href="/finance/vendors"
      />
      <StatCard
        icon={<Package className="h-4 w-4" aria-hidden="true" />}
        label="Total Purchase Orders"
        value={String(dashboard.total_purchase_orders)}
      />
      <StatCard
        icon={<Wallet className="h-4 w-4" aria-hidden="true" />}
        label="Budget Utilized"
        value={formatMoney(dashboard.budget_utilized)}
      />
      <StatCard
        icon={<Landmark className="h-4 w-4" aria-hidden="true" />}
        label="Budget Remaining"
        value={formatMoney(dashboard.budget_remaining)}
        tone="success"
      />
      <StatCard
        icon={<Receipt className="h-4 w-4" aria-hidden="true" />}
        label="Pending Bills"
        value={String(dashboard.pending_bills)}
        tone="warning"
      />
    </div>
  );
}
