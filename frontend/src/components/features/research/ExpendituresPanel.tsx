"use client";

import { useCallback, useState } from "react";
import { Loader, Receipt, Trash2 } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { deleteExpenditure } from "@/lib/api/research";
import { formatAmount, formatDate } from "@/lib/research/constants";
import type { GrantResponse } from "@/types";

/**
 * PART 3 utilisation: the grant's expenditure entries by budget head.
 * Deletions flow back through `onChanged` so the workspace re-fetches the
 * enriched grant payload (budget totals are computed from children).
 */
export function ExpendituresPanel({
  grant,
  onAddExpenditure,
  onChanged,
}: {
  grant: GrantResponse;
  onAddExpenditure: () => void;
  onChanged: () => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const remove = useCallback(
    async (expenditureId: string) => {
      if (busyId) return;
      setBusyId(expenditureId);
      setError(null);
      try {
        await deleteExpenditure(expenditureId);
        onChanged();
      } catch (err) {
        setError(toErrorMessage(err, "Could not delete the expenditure."));
      } finally {
        setBusyId(null);
      }
    },
    [busyId, onChanged],
  );

  return (
    <section
      aria-label="Expenditure"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Expenditure <span className="font-normal text-[var(--text-tertiary)]">({grant.expenditures.length})</span>
        </h2>
        <button
          type="button"
          onClick={onAddExpenditure}
          className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <Receipt className="h-3.5 w-3.5" aria-hidden="true" /> Record expenditure
        </button>
      </div>

      {error ? (
        <p role="alert" className="mb-2 text-xs text-[var(--danger)]">
          {error}
        </p>
      ) : null}

      {grant.expenditures.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No expenditure recorded yet — book vouchers by budget head to track utilisation.
        </p>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {grant.expenditures.map((expenditure) => (
            <li
              key={expenditure.id}
              className="flex flex-wrap items-center justify-between gap-2 py-2.5"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)]">
                  {expenditure.head ?? "Expenditure"}
                </p>
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                  {[
                    formatDate(expenditure.date),
                    expenditure.reference ? `Ref ${expenditure.reference}` : null,
                    expenditure.notes,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-sm font-semibold text-[var(--text-primary)]">
                  {formatAmount(expenditure.amount)}
                </span>
                <button
                  type="button"
                  onClick={() => remove(expenditure.id)}
                  disabled={busyId != null}
                  aria-label={`Delete expenditure ${expenditure.head ?? ""}`}
                  title="Delete"
                  className="rounded-lg p-1 text-[var(--text-secondary)] transition-colors hover:text-[var(--danger)] disabled:opacity-50"
                >
                  {busyId === expenditure.id ? (
                    <Loader className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
