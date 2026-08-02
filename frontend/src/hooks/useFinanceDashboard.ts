"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { getFinanceDashboard, listBudgetLines } from "@/lib/api/finance";
import type { BudgetLine, FinanceDashboard } from "@/types";

export interface UseFinanceDashboardResult {
  dashboard: FinanceDashboard | null;
  budgets: BudgetLine[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The PART 11 cards + PART 9 budget lines. Mirrors `useCommitteesDashboard`. */
export function useFinanceDashboard(): UseFinanceDashboardResult {
  const [dashboard, setDashboard] = useState<FinanceDashboard | null>(null);
  const [budgets, setBudgets] = useState<BudgetLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([
      getFinanceDashboard({ signal: controller.signal }),
      listBudgetLines({ signal: controller.signal }).catch(() => null),
    ])
      .then(([cards, lines]) => {
        if (!active) return;
        setDashboard(cards);
        setBudgets(lines?.items ?? []);
      })
      .catch((err) => {
        if (!active || err?.name === "AbortError") return;
        setError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [reloadToken]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return { dashboard, budgets, loading, error, refresh };
}
