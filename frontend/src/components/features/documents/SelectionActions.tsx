"use client";

/**
 * AI selection hooks (Sprint M10).
 *
 * Extension points only — NO fake AI. When text is selected, the panel
 * exposes actions; the LLM-backed ones (Explain / Summarize / Rewrite)
 * are registered as a pluggable handler and render as "coming with LLM
 * integration" until a real handler is provided. Highlight / Create
 * note / Bookmark are fully implemented through the existing annotation
 * framework.
 */
import { useCallback } from "react";
import { Bookmark, Highlighter, Sparkles, StickyNote } from "lucide-react";

export interface SelectionActionHandler {
  /** Invoked when an LLM-backed action is requested (no-op until wired). */
  onLlmAction?: (action: "explain" | "summarize" | "rewrite", text: string) => void;
}

export interface SelectionActionsProps extends SelectionActionHandler {
  selection: string;
  onHighlight: (text: string) => void;
  onCreateNote: (text: string) => void;
  onBookmark: (page: number) => void;
  currentPage: number;
}

const LLM_ACTIONS: { key: "explain" | "summarize" | "rewrite"; label: string }[] = [
  { key: "explain", label: "Explain" },
  { key: "summarize", label: "Summarize" },
  { key: "rewrite", label: "Rewrite" },
];

export function SelectionActions({
  selection,
  onHighlight,
  onCreateNote,
  onBookmark,
  currentPage,
  onLlmAction,
}: SelectionActionsProps) {
  const runLlm = useCallback(
    (action: "explain" | "summarize" | "rewrite") => {
      if (onLlmAction) {
        onLlmAction(action, selection);
      }
    },
    [selection, onLlmAction],
  );

  if (!selection) return null;

  return (
    <div
      role="toolbar"
      aria-label="Selection actions"
      className="flex flex-wrap items-center gap-1.5 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-2 text-xs"
    >
      {LLM_ACTIONS.map((action) => (
        <button
          key={action.key}
          type="button"
          onClick={() => runLlm(action.key)}
          className="flex items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2.5 py-1.5 font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          title={onLlmAction ? undefined : "Available once LLM integration is wired"}
        >
          <Sparkles className="h-3.5 w-3.5" />
          {action.label}
          {!onLlmAction && <span className="sr-only">(extension point)</span>}
        </button>
      ))}
      <span className="mx-1 h-4 w-px bg-[var(--border-subtle)]" />
      <button
        type="button"
        onClick={() => onHighlight(selection)}
        className="flex items-center gap-1 rounded-md bg-[var(--accent)] px-2.5 py-1.5 font-semibold text-white hover:bg-[var(--accent-hover)]"
      >
        <Highlighter className="h-3.5 w-3.5" /> Highlight
      </button>
      <button
        type="button"
        onClick={() => onCreateNote(selection)}
        className="flex items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2.5 py-1.5 font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
      >
        <StickyNote className="h-3.5 w-3.5" /> Create note
      </button>
      <button
        type="button"
        onClick={() => onBookmark(currentPage)}
        className="flex items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2.5 py-1.5 font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
      >
        <Bookmark className="h-3.5 w-3.5" /> Bookmark page
      </button>
    </div>
  );
}
