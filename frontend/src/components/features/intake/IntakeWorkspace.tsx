"use client";

import { useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { Pagination } from "@/components/features/objects/Pagination";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useIntakeSessions } from "@/hooks/useIntakeSessions";
import { CreateSessionForm } from "./CreateSessionForm";
import { SessionCard } from "./SessionCard";

export function IntakeWorkspace({ onOpenSession }: { onOpenSession: (id: string) => void }) {
  const { toast, show, dismiss } = useToast();
  const {
    items,
    total,
    page,
    pageSize,
    totalPages,
    loading,
    refreshing,
    error,
    hasActive,
    setPage,
    refresh,
  } = useIntakeSessions();

  const handleCreated = useCallback(
    (id: string) => {
      show("success", "Import started — tracking progress below.");
      void refresh();
      onOpenSession(id);
    },
    [show, refresh, onOpenSession],
  );

  return (
    <section aria-label="Intake home" className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">Intake</h1>
          <p className="text-sm text-[var(--text-tertiary)]">
            Intelligent import pipeline — enumerate, stage, hash, then hold for review.
            {hasActive ? " Live progress is being tracked automatically." : ""}
          </p>
        </div>
        <button
          type="button"
          aria-label="Refresh sessions"
          onClick={() => void refresh()}
          className="flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <CreateSessionForm onCreated={handleCreated} />

      {error && (
        <p role="alert" className="rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </p>
      )}

      {loading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" aria-label="Loading sessions">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="h-32 animate-pulse rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-hover)]"
            />
          ))}
        </div>
      ) : total === 0 ? (
        <div aria-label="No intake sessions">
          <EmptyState
            title="No intake sessions yet"
            description="Start your first import above. AcademicOS will walk, stage and hash every file — and then wait for your review before anything becomes a record."
          />
        </div>
      ) : (
        <>
          <div
            className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"
            aria-label={`${total} intake session(s)`}
          >
            {items.map((session) => (
              <SessionCard key={session.id} session={session} />
            ))}
          </div>
          {totalPages > 1 && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              disabled={refreshing}
            />
          )}
        </>
      )}

      <Toast toast={toast} onClose={dismiss} />
    </section>
  );
}
