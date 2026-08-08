"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";

import { SearchBar } from "@/components/features/objects/SearchBar";
import { Spinner } from "@/components/features/objects/Spinner";
import { searchObjects, type SearchHit } from "@/lib/api/search";
import { isAbortError, toErrorMessage } from "@/lib/api/client";

/**
 * Global search page (Sprint-5 M2). Queries the hybrid search API and
 * renders typed hits with provenance (lexical / semantic / both) and the
 * deterministic score. Reuses the objects SearchBar component.
 */
export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  // Debounce: typing never fires a request per keystroke (mirrors useObjects).
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const run = useCallback(async (text: string) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const response = await searchObjects({ text, limit: 50 }, { signal: controller.signal });
      // A newer request may have superseded this one while it was in flight
      // (rapid typing). Only the LATEST request is allowed to publish results.
      if (controllerRef.current !== controller) return;
      setHits(response.results);
      setSearched(true);
    } catch (err) {
      // A superseded/unmounted request is aborted by the client as an
      // ApiError("Request cancelled.", { kind: "aborted" }) — or, when the
      // fetch itself is interrupted, a DOMException named "AbortError". Both
      // are INTENTIONAL cancellations, not failures: they must stay silent and
      // must never surface "Request cancelled." to the user.
      if (isAbortError(err)) return;
      if (controllerRef.current !== controller) return;
      setError(toErrorMessage(err, "Search failed."));
    } finally {
      // Only the latest request clears the loading spinner — a superseded
      // request's finally must not clobber the active request's loading state.
      if (controllerRef.current === controller) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounced.trim()) {
      void run(debounced.trim());
    } else {
      setHits([]);
      setSearched(false);
    }
  }, [debounced, run]);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Search</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Hybrid lexical + semantic search across all objects.
        </p>
      </header>

      <SearchBar
        value={query}
        onChange={setQuery}
        placeholder="Search titles, metadata, content…"
        busy={loading}
      />

      {error ? (
        <p className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-3 text-sm text-[var(--text-danger)]">
          {error}
        </p>
      ) : null}

      {searched && !loading && hits.length === 0 ? (
        <p className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-3 text-sm text-[var(--text-secondary)]">
          No results for &ldquo;{debounced}&rdquo;.
        </p>
      ) : null}

      <ul className="flex flex-col gap-3">
        {hits.map((hit) => (
          <li
            key={hit.object_id}
            className="flex items-start justify-between gap-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                {hit.title}
              </p>
              <p className="mt-0.5 truncate text-xs text-[var(--text-tertiary)]">
                {hit.object_id} · {hit.object_type} · v{hit.version}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span
                title={`Matched by the ${hit.index_source} index leg`}
                className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                  hit.index_source === "both"
                    ? "bg-[var(--accent-subtle)] text-[var(--accent)]"
                    : hit.index_source === "semantic"
                      ? "bg-[var(--bg-hover)] text-[var(--text-secondary)]"
                      : "bg-[var(--bg-hover)] text-[var(--text-tertiary)]"
                }`}
              >
                {hit.index_source}
              </span>
              <span className="text-xs tabular-nums text-[var(--text-tertiary)]">
                {hit.score.toFixed(4)}
              </span>
            </div>
          </li>
        ))}
      </ul>

      {!searched && !loading && hits.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-[var(--text-tertiary)]">
          <Search className="h-10 w-10" aria-hidden="true" />
          <p className="text-sm">Type a query to search the knowledge graph.</p>
        </div>
      ) : null}
    </div>
  );
}
