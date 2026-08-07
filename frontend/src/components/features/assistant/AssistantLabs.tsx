"use client";

/** Assistant Labs (final release): memory recall + consolidation, the
 * human review queue, and evaluation-run history — the previously
 * backend-only assistant surfaces, now usable from the UI. */
import { useCallback, useEffect, useState } from "react";
import { BrainCircuit, CheckCircle2, ClipboardList, History, XCircle } from "lucide-react";

import {
  approveReview,
  consolidateMemory,
  listEvalRuns,
  listPendingReviews,
  recallMemory,
  rejectReview,
  type MemoryRecall,
  type ReviewQueueItem,
} from "@/lib/api/assistant";
import { toErrorMessage } from "@/lib/api/client";

type Tab = "memory" | "review" | "eval";

export function AssistantLabs() {
  const [tab, setTab] = useState<Tab>("memory");
  const [error, setError] = useState<string | null>(null);

  const tabs: { id: Tab; label: string; icon: typeof BrainCircuit }[] = [
    { id: "memory", label: "Memory", icon: BrainCircuit },
    { id: "review", label: "Review queue", icon: ClipboardList },
    { id: "eval", label: "Evaluation history", icon: History },
  ];

  return (
    <section className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">Assistant Labs</h2>
        <div className="flex gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] p-1">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              aria-pressed={tab === id}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                tab === id
                  ? "bg-[var(--accent)] text-white"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <p role="alert" className="mb-3 rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
          {error}
        </p>
      )}
      {tab === "memory" && <MemoryTab onError={setError} />}
      {tab === "review" && <ReviewTab onError={setError} />}
      {tab === "eval" && <EvalTab onError={setError} />}
    </section>
  );
}

function MemoryTab({ onError }: { onError: (message: string | null) => void }) {
  const [query, setQuery] = useState("quantum");
  const [recall, setRecall] = useState<MemoryRecall | null>(null);
  const [busy, setBusy] = useState(false);
  const [consolidating, setConsolidating] = useState(false);
  const [consolidation, setConsolidation] = useState<string | null>(null);

  const run = useCallback(
    (q: string) => {
      setBusy(true);
      onError(null);
      recallMemory(q)
        .then((r) => setRecall(r))
        .catch((err) => onError(toErrorMessage(err)))
        .finally(() => setBusy(false));
    },
    [onError],
  );

  useEffect(() => {
    run("quantum");
  }, [run]);

  const consolidate = () => {
    setConsolidating(true);
    onError(null);
    consolidateMemory()
      .then((r) => {
        setConsolidation(`Consolidated ${r.consolidated} duplicate conversation(s).`);
        run(query);
      })
      .catch((err) => onError(toErrorMessage(err)))
      .finally(() => setConsolidating(false));
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") run(query);
          }}
          placeholder="Recall query…"
          className="w-full max-w-sm rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none"
        />
        <button
          type="button"
          onClick={() => run(query)}
          disabled={busy}
          className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--accent-hover)] disabled:opacity-60"
        >
          {busy ? "Recalling…" : "Recall"}
        </button>
        <button
          type="button"
          onClick={consolidate}
          disabled={consolidating}
          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)] disabled:opacity-60"
        >
          {consolidating ? "Consolidating…" : "Consolidate duplicates"}
        </button>
      </div>
      {consolidation && <p className="text-sm text-[var(--success)]">{consolidation}</p>}
      {recall && (
        <div className="space-y-2">
          {recall.conversations.length === 0 && (
            <p className="text-sm text-[var(--text-tertiary)]">No memories matched.</p>
          )}
          {recall.conversations.map((m) => (
            <div
              key={m.conversation_id}
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-[var(--text-primary)]">{m.title}</span>
                <span className="text-xs text-[var(--text-tertiary)]">
                  score {m.score.toFixed(3)} · review {m.review_score.toFixed(2)} ·{" "}
                  {m.citations.length} citation(s)
                </span>
              </div>
              <p className="mt-1 text-[var(--text-secondary)]">Q: {m.question}</p>
              {m.answer && <p className="mt-1 text-[var(--text-secondary)]">A: {m.answer}</p>}
            </div>
          ))}
          {recall.knowledge.length > 0 && (
            <p className="text-xs text-[var(--text-tertiary)]">
              Graph knowledge: {recall.knowledge.map((k) => k.title).join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewTab({ onError }: { onError: (message: string | null) => void }) {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setBusy(true);
    onError(null);
    listPendingReviews()
      .then((r) => setItems(r.items))
      .catch((err) => onError(toErrorMessage(err)))
      .finally(() => setBusy(false));
  }, [onError]);

  useEffect(() => {
    load();
  }, [load]);

  const act = (id: string, approve: boolean) => {
    const action = approve ? approveReview(id) : rejectReview(id);
    void action
      .then(load)
      .catch((err) => onError(toErrorMessage(err)));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--text-secondary)]">
          {items.length === 0 ? "No conversations awaiting review." : `${items.length} awaiting review.`}
        </p>
        <button
          type="button"
          onClick={load}
          disabled={busy}
          className="rounded-lg border border-[var(--border-subtle)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        >
          Refresh
        </button>
      </div>
      {items.map((item) => (
        <div
          key={item.conversation.id}
          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-sm"
        >
          <p className="font-medium text-[var(--text-primary)]">{item.question}</p>
          <p className="mt-1 text-[var(--text-secondary)]">{item.answer}</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => act(item.conversation.id, true)}
              className="flex items-center gap-1 rounded-md bg-[var(--success-subtle)] px-3 py-1 text-xs font-semibold text-[var(--success)] hover:opacity-80"
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> Approve
            </button>
            <button
              type="button"
              onClick={() => act(item.conversation.id, false)}
              className="flex items-center gap-1 rounded-md bg-[var(--danger-subtle)] px-3 py-1 text-xs font-semibold text-[var(--danger)] hover:opacity-80"
            >
              <XCircle className="h-3.5 w-3.5" /> Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function EvalTab({ onError }: { onError: (message: string | null) => void }) {
  const [runs, setRuns] = useState<unknown[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBusy(true);
    onError(null);
    listEvalRuns(undefined, 20)
      .then((r) => setRuns(r.items))
      .catch(() => setRuns([]))
      .finally(() => setBusy(false));
  }, [onError]);

  return (
    <div className="space-y-2">
      <p className="text-sm text-[var(--text-secondary)]">
        {busy
          ? "Loading…"
          : runs.length === 0
            ? "No evaluation runs recorded yet. Runs are produced by the benchmark harness."
            : `${runs.length} recorded run(s).`}
      </p>
      {runs.map((run, index) => {
        const r = run as {
          run_id: string;
          model_id: string;
          model_version: string;
          prompt_version: number;
          passed: number;
          total: number;
          created_at: string;
        };
        return (
          <div
            key={r.run_id ?? index}
            className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2 text-sm"
          >
            <span className="font-medium text-[var(--text-primary)]">{r.model_id}</span>
            <span className="ml-2 text-xs text-[var(--text-tertiary)]">
              {r.model_version} · prompt v{r.prompt_version} · {r.passed}/{r.total} passed ·{" "}
              {r.created_at}
            </span>
          </div>
        );
      })}
    </div>
  );
}
