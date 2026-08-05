"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { countMatches, highlightSegments } from "@/lib/intake/extraction";
import { cn } from "@/lib/utils";

/**
 * Whitespace-preserving, scrollable, selectable monospace text pane shared
 * by the Preview and Extracted-text tabs. Renders exactly the string it is
 * given — the empty state is the caller's job and is never invented here.
 */
export function TextPane({
  text,
  query = "",
  ariaLabel,
  maxHeightClass = "max-h-[30rem]",
}: {
  text: string;
  query?: string;
  ariaLabel: string;
  maxHeightClass?: string;
}) {
  const segments = useMemo(() => highlightSegments(text, query), [text, query]);
  return (
    <div
      role="region"
      aria-label={ariaLabel}
      className={cn(
        "overflow-auto rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)]",
        maxHeightClass,
      )}
    >
      <pre
        aria-label={`${ariaLabel} content`}
        className="whitespace-pre-wrap break-words p-3 font-mono text-xs leading-relaxed text-[var(--text-primary)] selection:bg-[var(--accent-subtle)]"
      >
        {segments.map((segment, index) =>
          segment.match ? (
            <mark
              key={index}
              aria-label="Search match"
              className="rounded-sm bg-[var(--warning-subtle)] px-0.5 text-inherit outline outline-1 outline-[var(--warning)]"
            >
              {segment.text}
            </mark>
          ) : (
            <span key={index}>{segment.text}</span>
          ),
        )}
      </pre>
    </div>
  );
}

/**
 * The raw extracted-text viewer (M2 Part 2): scrollable, selectable,
 * copy-friendly, monospace, formatting preserved, read-only — with client-
 * side search (highlight + match count; zero backend traffic while typing).
 */
export function ExtractedTextViewer({ text, itemLabel }: { text: string; itemLabel: string }) {
  const [query, setQuery] = useState("");
  const matches = useMemo(() => countMatches(text, query), [text, query]);

  return (
    <div className="flex flex-col gap-2" aria-label="Extracted text viewer">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative flex-1 min-w-[14rem]">
          <span className="sr-only">Search extracted text</span>
          <Search
            aria-hidden
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-tertiary)]"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={`Search extracted text of ${itemLabel}`}
            placeholder="Search within extracted text…"
            spellCheck={false}
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] py-1.5 pl-8 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
          />
        </label>
        <span
          role="status"
          aria-live="polite"
          aria-label="Search match count"
          className={cn(
            "text-xs",
            query.trim() && matches === 0
              ? "text-[var(--danger)]"
              : "text-[var(--text-tertiary)]",
          )}
        >
          {query.trim()
            ? matches === 0
              ? "No matches"
              : `${matches} match${matches === 1 ? "" : "es"}`
            : "Type to highlight matches"}
        </span>
      </div>
      <TextPane text={text} query={query} ariaLabel={`Extracted text of ${itemLabel}`} />
      <p className="text-xs text-[var(--text-tertiary)]">
        {text.length.toLocaleString()} characters • read-only • formatting preserved
      </p>
    </div>
  );
}
