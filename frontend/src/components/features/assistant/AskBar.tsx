"use client";

/**
 * The assistant ask bar — one textarea + send button, shared by the AI Home
 * empty state and every conversation thread. Enter sends, Shift+Enter adds a
 * newline; the bar locks while a question is in flight (`sending`).
 */
import { useEffect, useRef, useState } from "react";

import { SendHorizonal } from "lucide-react";

export const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

export function AskBar({
  sending,
  onAsk,
  prefill,
}: {
  sending: boolean;
  onAsk: (question: string) => void;
  /** When set (suggested question click), the bar refills and focuses. */
  prefill?: { question: string; nonce: number } | null;
}) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (prefill) {
      setValue(prefill.question);
      inputRef.current?.focus();
    }
  }, [prefill]);

  const submit = () => {
    const cleaned = value.trim();
    if (!cleaned || sending) return;
    setValue("");
    onAsk(cleaned);
  };

  return (
    <form
      aria-label="Ask the assistant"
      className="flex items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <textarea
        ref={inputRef}
        aria-label="Ask input"
        rows={2}
        value={value}
        disabled={sending}
        placeholder="Ask about your day, publications, projects, attendance, purchases, events, committees, reports…"
        className={`${FIELD_CLASS} resize-none`}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <button
        type="submit"
        aria-label="Send question"
        disabled={sending || !value.trim()}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        <SendHorizonal className="h-4 w-4" />
      </button>
    </form>
  );
}
