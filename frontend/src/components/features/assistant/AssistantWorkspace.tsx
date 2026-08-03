"use client";

/**
 * Academic Intelligence Assistant workspace (PART 1 AI Home + PART 15 shell).
 *
 * Two panes: the left rail holds the New conversation button and the full
 * history (pinned first); the right pane shows either the AI Home (suggested
 * questions, pinned/recent shortcuts) or the open conversation thread. The
 * AskBar is shared by both states — asking from the home starts a fresh
 * conversation on the server. The engine badge documents the V1 constraint:
 * local, deterministic, no external AI (PART 14).
 */
import { ArrowLeft, PlusCircle, Sparkles } from "lucide-react";

import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { useAssistant } from "@/hooks/useAssistant";
import { AskBar } from "./AskBar";
import { AssistantHomeView } from "./AssistantHomeView";
import { ConversationList } from "./ConversationList";
import { MessageThread } from "./MessageThread";
import type { SuggestedPrompt } from "@/types";
import { useState } from "react";

export function AssistantWorkspace() {
  const {
    home,
    conversations,
    thread,
    loading,
    threadLoading,
    sending,
    error,
    refresh,
    ask,
    openConversation,
    backToHome,
    newConversation,
    rename,
    togglePin,
    remove,
  } = useAssistant();
  const [prefill, setPrefill] = useState<{ question: string; nonce: number } | null>(null);

  const handleSuggest = (prompt: SuggestedPrompt) => {
    setPrefill({ question: prompt.question, nonce: Date.now() });
    void ask(prompt.question);
  };

  const handleDelete = (id: string, title: string) => {
    if (window.confirm(`Delete "${title}"? This cannot be undone.`)) {
      void remove(id);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6" aria-label="Assistant loading" aria-busy="true">
        {Array.from({ length: 3 }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    );
  }

  if (error && !home) {
    return (
      <div className="space-y-3">
        <p
          role="alert"
          className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
        >
          {error}
        </p>
        <button
          type="button"
          aria-label="Retry loading assistant"
          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
          onClick={() => void refresh()}
        >
          Try again
        </button>
      </div>
    );
  }

  const activeTitle = thread?.conversation.title ?? "";

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
      {/* ------------------------------------------------------- left rail */}
      <aside className="space-y-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3">
        <button
          type="button"
          aria-label="New conversation"
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"
          onClick={() => void newConversation()}
        >
          <PlusCircle className="h-4 w-4" /> New conversation
        </button>
        <ConversationList
          conversations={conversations}
          activeId={thread?.conversation.id ?? null}
          onOpen={(id) => void openConversation(id)}
          onPin={(conversation) => void togglePin(conversation)}
          onRename={rename}
          onDelete={(id) => {
            const target = conversations.find((c) => c.id === id);
            handleDelete(id, target?.title ?? "this conversation");
          }}
        />
      </aside>

      {/* ------------------------------------------------------ main pane */}
      <section className="flex min-h-[60vh] flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {thread ? (
              <button
                type="button"
                aria-label="Back to AI Home"
                className="flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                onClick={backToHome}
              >
                <ArrowLeft className="h-3.5 w-3.5" /> AI Home
              </button>
            ) : (
              <Sparkles className="h-4 w-4 text-[var(--accent)]" />
            )}
            <h2 className="truncate text-sm font-semibold text-[var(--text-primary)]">
              {thread ? activeTitle : "AI Home"}
            </h2>
          </div>
          <span
            aria-label="Assistant status"
            className="rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-[var(--text-tertiary)]"
          >
            rules-v1 · local · no external AI
          </span>
        </div>

        {error ? (
          <p
            role="alert"
            className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
          >
            {error}
          </p>
        ) : null}

        <div className="flex-1 space-y-4">
          {threadLoading ? (
            <div aria-label="Thread loading" aria-busy="true" className="space-y-4">
              <CardSkeleton />
            </div>
          ) : thread ? (
            <MessageThread messages={thread.messages} sending={sending} />
          ) : home ? (
            <AssistantHomeView home={home} onSuggest={handleSuggest} onOpen={(id) => void openConversation(id)} />
          ) : null}
        </div>

        <div className="sticky bottom-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3 shadow-sm">
          <AskBar sending={sending} onAsk={(question) => void ask(question)} prefill={prefill} />
        </div>
      </section>
    </div>
  );
}
