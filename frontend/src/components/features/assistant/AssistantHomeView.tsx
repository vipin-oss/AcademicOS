"use client";

/**
 * AI Home view: the suggested-question grid grouped by intent group (served
 * verbatim by the backend), plus pinned & recent conversation shortcuts.
 * Clicking a suggestion asks it immediately.
 */
import { Pin } from "lucide-react";

import { groupMeta } from "@/lib/assistant/constants";
import type { AssistantHome, SuggestedPrompt } from "@/types";

export function AssistantHomeView({
  home,
  onSuggest,
  onOpen,
}: {
  home: AssistantHome;
  onSuggest: (prompt: SuggestedPrompt) => void;
  onOpen: (id: string) => void;
}) {
  const groups: { group: string; prompts: SuggestedPrompt[] }[] = [];
  for (const prompt of home.suggested) {
    let bucket = groups.find((entry) => entry.group === prompt.group);
    if (!bucket) {
      bucket = { group: prompt.group, prompts: [] };
      groups.push(bucket);
    }
    bucket.prompts.push(prompt);
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          What would you like to know?
        </h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Ask in plain English — answers come from your live AcademicOS data,
          always linked back to the module they came from.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {groups.map(({ group, prompts }) => {
          const meta = groupMeta(group);
          const Icon = meta.icon;
          return (
            <section
              key={group}
              aria-label={`Suggested: ${group}`}
              className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4"
            >
              <div className="mb-3 flex items-center gap-2">
                <Icon className="h-4 w-4 text-[var(--accent)]" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">{group}</h3>
                <span className="text-xs text-[var(--text-tertiary)]">{meta.blurb}</span>
              </div>
              <ul className="space-y-1.5">
                {prompts.map((prompt) => (
                  <li key={prompt.question}>
                    <button
                      type="button"
                      aria-label={`Suggested question ${prompt.question}`}
                      className="w-full rounded-lg border border-transparent px-2 py-1.5 text-left text-sm text-[var(--text-primary)] hover:border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]"
                      onClick={() => onSuggest(prompt)}
                    >
                      {prompt.question}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>

      {home.pinned.length > 0 ? (
        <section
          aria-label="Pinned conversations"
          className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4"
        >
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
            <Pin className="h-4 w-4 text-[var(--accent)]" /> Pinned
          </h3>
          <ConversationChips ids={home.pinned} onOpen={onOpen} label="pinned" />
        </section>
      ) : null}

      {home.recent.length > 0 ? (
        <section
          aria-label="Recent conversations"
          className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4"
        >
          <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">Recent</h3>
          <ConversationChips ids={home.recent} onOpen={onOpen} label="recent" />
        </section>
      ) : null}
    </div>
  );
}

function ConversationChips({
  ids,
  onOpen,
  label,
}: {
  ids: AssistantHome["recent"];
  onOpen: (id: string) => void;
  label: string;
}) {
  return (
    <ul className="flex flex-wrap gap-2">
      {ids.map((conversation) => (
        <li key={conversation.id}>
          <button
            type="button"
            aria-label={`Open ${label} conversation ${conversation.title}`}
            className="rounded-full border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
            onClick={() => onOpen(conversation.id)}
          >
            {conversation.title}
            <span className="ml-1.5 text-[var(--text-tertiary)]">
              {conversation.message_count} msg
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
