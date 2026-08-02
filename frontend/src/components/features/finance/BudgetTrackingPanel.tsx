import Link from "next/link";
import { formatMoney } from "@/lib/finance/constants";
import type { BudgetLine } from "@/types";

/**
 * PART 9 budget tracking: per-project approved / released / utilized /
 * remaining, computed server-side (research budgets + procurement spend).
 */
export function BudgetTrackingPanel({ lines }: { lines: BudgetLine[] }) {
  return (
    <section
      aria-label="Budget tracking"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
        Budget Tracking (per project)
      </h2>
      {lines.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--text-tertiary)]">
          No research project budgets yet. Budgets appear once projects carry an
          approved budget in the Research module.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-4 font-medium">Project</th>
                <th className="py-2 pr-4 font-medium">Approved</th>
                <th className="py-2 pr-4 font-medium">Released</th>
                <th className="py-2 pr-4 font-medium">Utilized</th>
                <th className="py-2 pr-4 font-medium">Remaining</th>
                <th className="py-2 font-medium">Procurements</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => (
                <tr
                  key={line.project_id}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2.5 pr-4">
                    <Link
                      href={`/research/projects/${encodeURIComponent(line.project_id)}`}
                      className="font-medium text-[var(--accent)] hover:underline"
                    >
                      {line.title}
                    </Link>
                  </td>
                  <td className="py-2.5 pr-4 text-[var(--text-secondary)]">
                    {formatMoney(line.approved)}
                  </td>
                  <td className="py-2.5 pr-4 text-[var(--text-secondary)]">
                    {formatMoney(line.released)}
                  </td>
                  <td className="py-2.5 pr-4 text-[var(--text-secondary)]">
                    {formatMoney(line.utilized)}
                  </td>
                  <td
                    className={`py-2.5 pr-4 ${
                      (line.remaining ?? 0) < 0
                        ? "font-medium text-[var(--danger)]"
                        : "text-[var(--success)]"
                    }`}
                  >
                    {formatMoney(line.remaining)}
                  </td>
                  <td className="py-2.5 text-[var(--text-secondary)]">
                    {line.proposals} proposal{line.proposals === 1 ? "" : "s"}
                    {line.spent > 0 ? ` · spent ${formatMoney(line.spent)}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
