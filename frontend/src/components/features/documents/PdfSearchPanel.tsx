"use client";

/**
 * PDF full-text search panel (Sprint M10).
 *
 * Ctrl+F opens the panel; typing searches the pdf.js text layer with
 * case-sensitive / whole-word options, a match counter, and
 * Previous/Next navigation. The current match is rendered as a
 * highlight overlay in the viewer (rects in PDF units, scaled to zoom).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { CaseSensitive, ChevronDown, ChevronUp, X } from "lucide-react";

import { searchPdfText, type PdfSearchMatch } from "@/lib/pdf/searchPdf";
import type { PdfPageText } from "@/lib/pdf/textSync";
import { cn } from "@/lib/utils";

export interface PdfSearchPanelProps {
  pagesText: PdfPageText[];
  onMatch: (match: PdfSearchMatch | null) => void;
  onJump: (page: number) => void;
}

export function PdfSearchPanel({ pagesText, onMatch, onJump }: PdfSearchPanelProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [wholeWord, setWholeWord] = useState(false);
  const [matches, setMatches] = useState<PdfSearchMatch[]>([]);
  const [current, setCurrent] = useState(-1);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Recompute matches on query/options change.
  useEffect(() => {
    const results = searchPdfText(pagesText, query, { caseSensitive, wholeWord });
    setMatches(results);
    setCurrent(results.length > 0 ? 0 : -1);
    onMatch(results.length > 0 ? results[0] : null);
    if (results.length > 0) onJump(results[0].page);
  }, [query, caseSensitive, wholeWord, pagesText, onMatch, onJump]);

  const goTo = useCallback(
    (index: number) => {
      if (matches.length === 0) return;
      const next = (index + matches.length) % matches.length;
      setCurrent(next);
      onMatch(matches[next]);
      onJump(matches[next].page);
    },
    [matches, onMatch, onJump],
  );

  // Ctrl+F / Escape keyboard handling.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setOpen(true);
        window.setTimeout(() => inputRef.current?.focus(), 0);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
        onMatch(null);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onMatch]);

  const close = () => {
    setOpen(false);
    onMatch(null);
  };

  if (!open) return null;

  return (
    <div
      role="search"
      aria-label="Search in document"
      className="flex items-center gap-1.5 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-2 text-xs text-[var(--text-secondary)]"
    >
      <input
        ref={inputRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") goTo(e.shiftKey ? current - 1 : current + 1);
        }}
        placeholder="Find in document…"
        aria-label="Find in document"
        className="w-40 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none"
      />
      <span aria-live="polite" className="w-16 text-center">
        {matches.length > 0 ? `${current + 1}/${matches.length}` : "0/0"}
      </span>
      <button
        type="button"
        aria-label="Previous match"
        disabled={matches.length === 0}
        onClick={() => goTo(current - 1)}
        className="rounded-md p-1 hover:bg-[var(--bg-hover)] disabled:opacity-40"
      >
        <ChevronUp className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label="Next match"
        disabled={matches.length === 0}
        onClick={() => goTo(current + 1)}
        className="rounded-md p-1 hover:bg-[var(--bg-hover)] disabled:opacity-40"
      >
        <ChevronDown className="h-4 w-4" />
      </button>
      <button
        type="button"
        aria-label={caseSensitive ? "Case-sensitive on" : "Case-sensitive off"}
        aria-pressed={caseSensitive}
        onClick={() => setCaseSensitive((v) => !v)}
        className={cn(
          "flex items-center gap-1 rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]",
          caseSensitive && "bg-[var(--accent-subtle)] text-[var(--accent)]",
        )}
      >
        <CaseSensitive className="h-3.5 w-3.5" /> Aa
      </button>
      <button
        type="button"
        aria-label={wholeWord ? "Whole words only on" : "Whole words only off"}
        aria-pressed={wholeWord}
        onClick={() => setWholeWord((v) => !v)}
        className={cn(
          "rounded-md px-2 py-1 hover:bg-[var(--bg-hover)]",
          wholeWord && "bg-[var(--accent-subtle)] text-[var(--accent)]",
        )}
      >
        Whole word
      </button>
      <button
        type="button"
        aria-label="Close search"
        onClick={close}
        className="ml-auto rounded-md p-1 hover:bg-[var(--bg-hover)]"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
