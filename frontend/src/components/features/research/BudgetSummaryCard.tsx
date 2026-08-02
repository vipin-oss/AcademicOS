"use client";

import { formatAmount, utilizationRatio } from "@/lib/research/constants";
import type { ProjectBudget } from "@/types";

function AmountRow({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
        {label}
      </span>
      <span className="text-sm font-semibold text-[var(--text-primary)]">{formatAmount(value)}</span>
    </div>
  );
}

/** PART 7 project budget card: approved / grants released / utilized / remaining. */
export function BudgetSummaryCard({ budget }: { budget: ProjectBudget }) {
  const ratio = utilizationRatio(budget.utilized, budget.approved);
  return (
    <section
      aria-label="Budget summary"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Budget</h2>
      <div className="mt-2 divide-y divide-[var(--border-subtle)]">
        <AmountRow label="Approved" value={budget.approved} />
        <AmountRow label="Released (grants)" value={budget.grants_released} />
        <AmountRow label="Utilized" value={budget.utilized} />
        <AmountRow label="Remaining" value={budget.remaining} />
      </div>
      {ratio != null ? (
        <div className="mt-3">
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(ratio * 100)}
            aria-label="Budget utilization"
          >
            <div
              className="h-full rounded-full bg-[var(--accent)] transition-all"
              style={{ width: `${Math.round(ratio * 100)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            {Math.round(ratio * 100)}% of the approved budget utilized
          </p>
        </div>
      ) : (
        <p className="mt-3 text-xs text-[var(--text-tertiary)]">
          Record approved/utilized amounts on the project to track the budget.
        </p>
      )}
    </section>
  );
}
