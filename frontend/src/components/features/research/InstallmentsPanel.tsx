"use client";

import { useCallback, useState } from "react";
import { IndianRupee, Loader, Trash2 } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { deleteInstallment } from "@/lib/api/research";
import { formatAmount, formatDate } from "@/lib/research/constants";
import { InstallmentStatusBadge } from "./ResearchBadges";
import type { GrantResponse } from "@/types";

/**
 * PART 3 release schedule: the grant's installments (released/scheduled).
 * Deletions flow back through `onChanged` so the workspace re-fetches the
 * enriched grant payload (budget totals are computed from children).
 */
export function InstallmentsPanel({
  grant,
  onAddInstallment,
  onChanged,
}: {
  grant: GrantResponse;
  onAddInstallment: () => void;
  onChanged: () => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const remove = useCallback(
    async (installmentId: string) => {
      if (busyId) return;
      setBusyId(installmentId);
      setError(null);
      try {
        await deleteInstallment(installmentId);
        onChanged();
      } catch (err) {
        setError(toErrorMessage(err, "Could not delete the installment."));
      } finally {
        setBusyId(null);
      }
    },
    [busyId, onChanged],
  );

  return (
    <section
      aria-label="Installments"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Installments <span className="font-normal text-[var(--text-tertiary)]">({grant.installments.length})</span>
        </h2>
        <button
          type="button"
          onClick={onAddInstallment}
          className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <IndianRupee className="h-3.5 w-3.5" aria-hidden="true" /> Add installment
        </button>
      </div>

      {error ? (
        <p role="alert" className="mb-2 text-xs text-[var(--danger)]">
          {error}
        </p>
      ) : null}

      {grant.installments.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No installments recorded yet — add scheduled and released tranches to track the
          release schedule.
        </p>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {grant.installments.map((installment) => (
            <li
              key={installment.id}
              className="flex flex-wrap items-center justify-between gap-2 py-2.5"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)]">
                  Installment #{installment.installment_no ?? "—"}
                </p>
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                  {formatDate(installment.date)}
                  {installment.notes ? ` · ${installment.notes}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-sm font-semibold text-[var(--text-primary)]">
                  {formatAmount(installment.amount)}
                </span>
                <InstallmentStatusBadge status={installment.status} />
                <button
                  type="button"
                  onClick={() => remove(installment.id)}
                  disabled={busyId != null}
                  aria-label={`Delete installment ${installment.installment_no ?? ""}`}
                  title="Delete"
                  className="rounded-lg p-1 text-[var(--text-secondary)] transition-colors hover:text-[var(--danger)] disabled:opacity-50"
                >
                  {busyId === installment.id ? (
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
