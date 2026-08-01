"use client";

import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import { getCitation } from "@/lib/api/publications";
import { CITATION_STYLES } from "@/lib/publications/constants";
import type { CitationStyle } from "@/types";
import { Spinner } from "@/components/features/objects/Spinner";

/**
 * Citation generator (UI Spec §4): APA / IEEE / Vancouver / Chicago /
 * Harvard / BibTeX, rendered by the backend (`/publications/{id}/citation`)
 * so the formatting rules live in exactly one place.
 */
export function CitationPanel({ publicationId }: { publicationId: string }) {
  const [style, setStyle] = useState<CitationStyle>("apa");
  const [citation, setCitation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    getCitation(publicationId, style, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setCitation(response.citation);
      })
      .catch((err: unknown) => {
        if (!active || (err instanceof ApiError && err.isAborted)) return;
        setCitation(null);
        setError(toErrorMessage(err, "Could not format the citation."));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [publicationId, style]);

  const copy = async () => {
    if (!citation) return;
    try {
      await navigator.clipboard.writeText(citation);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable (permissions) — leave the text selectable */
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={style}
          onChange={(event) => setStyle(event.target.value as CitationStyle)}
          aria-label="Citation style"
          className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
        >
          {CITATION_STYLES.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={copy}
          disabled={!citation || loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-[var(--success)]" aria-hidden="true" />
          ) : (
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
          <Spinner className="h-3.5 w-3.5" label="Formatting citation" /> Formatting…
        </p>
      ) : error ? (
        <p role="alert" className="text-sm text-[var(--danger)]">
          {error}
        </p>
      ) : citation ? (
        <blockquote
          aria-live="polite"
          className="break-words rounded-lg bg-[var(--bg-surface-2)] px-3 py-2.5 text-sm leading-relaxed text-[var(--text-primary)]"
        >
          {citation}
        </blockquote>
      ) : null}
    </div>
  );
}
