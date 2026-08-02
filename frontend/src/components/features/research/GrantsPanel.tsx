"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { Spinner } from "@/components/features/objects/Spinner";
import { formatAmount } from "@/lib/research/constants";
import { useGrants } from "@/hooks/useGrants";

/** The project's grants panel (FUNDS edges, reverse lens via project filter). */
export function GrantsPanel({
  projectId,
  onNewGrant,
}: {
  projectId: string;
  onNewGrant?: () => void;
}) {
  const { items, loading, error } = useGrants({ projectId, pageSize: 100 });

  return (
    <section
      aria-label="Grants"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Grants</h2>
        {onNewGrant ? (
          <button
            type="button"
            onClick={onNewGrant}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" /> New grant
          </button>
        ) : null}
      </div>
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
          <Spinner className="h-4 w-4" /> Loading grants…
        </p>
      ) : error ? (
        <p className="text-sm text-[var(--danger)]">{error}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No grants fund this project yet.
        </p>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {items.map((grant) => (
            <li key={grant.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <div className="min-w-0">
                <Link
                  href={`/research/grants/${encodeURIComponent(grant.id)}`}
                  className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                >
                  {grant.title}
                </Link>
                <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                  {[grant.grant_number, grant.release_schedule].filter(Boolean).join(" · ")}
                </p>
              </div>
              <div className="text-right text-sm">
                <p className="font-semibold text-[var(--text-primary)]">
                  {formatAmount(grant.budget?.approved ?? grant.amount)}
                </p>
                <p className="text-xs text-[var(--text-tertiary)]">
                  {formatAmount(grant.budget?.remaining)} remaining
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
