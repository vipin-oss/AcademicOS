"use client";

/**
 * Conversation sidebar for the AI Workspace: the full history list (server
 * pre-sorted pinned-first), per-item actions (open / pin / inline rename /
 * delete with confirm), and the New conversation button. All mutating
 * actions are delegated to the `useAssistant` hook (API parity by design).
 */
import { useState } from "react";

import { Check, Pencil, Pin, PinOff, Trash2, X } from "lucide-react";

import type { AssistantConversation } from "@/types";

const ICON_BUTTON_CLASS =
  "flex h-6 w-6 items-center justify-center rounded-md text-[var(--text-tertiary)] opacity-0 transition-opacity hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] focus:opacity-100 group-hover:opacity-100";

export function ConversationList({
  conversations,
  activeId,
  onOpen,
  onPin,
  onRename,
  onDelete,
}: {
  conversations: AssistantConversation[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onPin: (conversation: AssistantConversation) => void;
  onRename: (id: string, title: string) => Promise<boolean>;
  onDelete: (id: string) => void;
}) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  if (conversations.length === 0) {
    return (
      <p aria-label="Conversation list empty" className="px-2 text-xs text-[var(--text-tertiary)]">
        No conversations yet — ask something to begin.
      </p>
    );
  }

  const startRename = (conversation: AssistantConversation) => {
    setRenamingId(conversation.id);
    setDraft(conversation.title);
  };

  const commitRename = async (id: string) => {
    const title = draft.trim();
    setRenamingId(null);
    if (title && title !== conversations.find((c) => c.id === id)?.title) {
      await onRename(id, title);
    }
  };

  return (
    <ul aria-label="Conversation list" className="space-y-1">
      {conversations.map((conversation) => {
        const active = conversation.id === activeId;
        const renaming = renamingId === conversation.id;
        return (
          <li key={conversation.id}>
            <div
              className={`group flex items-center gap-1 rounded-lg border px-2 py-1.5 ${
                active
                  ? "border-[var(--accent)] bg-[var(--bg-hover)]"
                  : "border-transparent hover:border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]"
              }`}
            >
              {conversation.pinned ? (
                <Pin className="h-3 w-3 shrink-0 text-[var(--accent)]" aria-label="Pinned" />
              ) : null}
              {renaming ? (
                <input
                  aria-label="Rename input"
                  value={draft}
                  autoFocus
                  className="min-w-0 flex-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] px-1.5 py-0.5 text-xs text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none"
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={async (event) => {
                    if (event.key === "Enter") await commitRename(conversation.id);
                    if (event.key === "Escape") setRenamingId(null);
                  }}
                />
              ) : (
                <button
                  type="button"
                  aria-label={`Open conversation ${conversation.title}`}
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onOpen(conversation.id)}
                >
                  <span className="block truncate text-xs font-medium text-[var(--text-primary)]">
                    {conversation.title}
                  </span>
                  <span className="block text-[10px] text-[var(--text-tertiary)]">
                    {conversation.message_count} msg
                  </span>
                </button>
              )}
              {renaming ? (
                <>
                  <button
                    type="button"
                    aria-label="Save rename"
                    className={`${ICON_BUTTON_CLASS} opacity-100`}
                    onClick={() => void commitRename(conversation.id)}
                  >
                    <Check className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    aria-label="Cancel rename"
                    className={`${ICON_BUTTON_CLASS} opacity-100`}
                    onClick={() => setRenamingId(null)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    aria-label={conversation.pinned ? "Unpin conversation" : "Pin conversation"}
                    className={ICON_BUTTON_CLASS}
                    onClick={() => onPin(conversation)}
                  >
                    {conversation.pinned ? (
                      <PinOff className="h-3.5 w-3.5" />
                    ) : (
                      <Pin className="h-3.5 w-3.5" />
                    )}
                  </button>
                  <button
                    type="button"
                    aria-label="Rename conversation"
                    className={ICON_BUTTON_CLASS}
                    onClick={() => startRename(conversation)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    aria-label="Delete conversation"
                    className={ICON_BUTTON_CLASS}
                    onClick={() => onDelete(conversation.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
