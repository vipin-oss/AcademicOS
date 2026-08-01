"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { ListObjectsResponse } from "@/types";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { SummaryCards } from "./SummaryCards";
import { RecentObjectsTable } from "./RecentObjectsTable";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: ListObjectsResponse };

export function DashboardView() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    api
      .get<ListObjectsResponse>("/objects")
      .then((data) => {
        if (!cancelled) setState({ kind: "ready", data });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({ kind: "error", message: err instanceof Error ? err.message : String(err) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const items = state.kind === "ready" ? state.data.items : [];
  const total = state.kind === "ready" ? state.data.total_count : 0;
  const draft = items.filter((o) => o.status === "draft").length;
  const active = items.filter((o) => o.status === "active").length;
  const archived = items.filter((o) => o.status === "archived").length;

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <h1 className="mb-6 text-xl font-semibold text-[var(--text-primary)]">Dashboard</h1>

          {state.kind === "loading" && (
            <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-8 text-center text-[var(--text-secondary)]">
              Loading objects…
            </div>
          )}

          {state.kind === "error" && (
            <div className="rounded-xl border border-[var(--danger)] bg-[var(--bg-surface)] p-8 text-center text-[var(--danger)]">
              Failed to load objects: {state.message}
            </div>
          )}

          {state.kind === "ready" && (
            <div className="flex flex-col gap-6">
              <SummaryCards total={total} draft={draft} active={active} archived={archived} />
              <RecentObjectsTable objects={items} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
