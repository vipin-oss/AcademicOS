"use client";

/**
 * Global search (Sprint-5 M2 + M26) — now with:
 * - Entity type filter chips (Events, Publications, Research, etc.)
 * - Rich result cards with professor-friendly metadata
 * - Keyboard shortcut hints
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Search, Calendar, BookOpen, FlaskConical, FileText, Users, GraduationCap, Filter, X } from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";

import { SearchBar } from "@/components/features/objects/SearchBar";
import { Spinner } from "@/components/features/objects/Spinner";
import { searchObjects, type SearchHit } from "@/lib/api/search";
import { isAbortError, toErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface TypeFilter {
  value: string;
  label: string;
  icon: typeof FileText;
  color: string;
}

const TYPE_FILTERS: TypeFilter[] = [
  { value: "event", label: "Events", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  { value: "publication", label: "Publications", icon: BookOpen, color: "text-blue-600 bg-blue-50 border-blue-200" },
  { value: "project", label: "Research", icon: FlaskConical, color: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  { value: "committee", label: "Committees", icon: Users, color: "text-amber-600 bg-amber-50 border-amber-200" },
  { value: "student", label: "Students", icon: GraduationCap, color: "text-rose-600 bg-rose-50 border-rose-200" },
  { value: "document", label: "Documents", icon: FileText, color: "text-gray-600 bg-gray-50 border-gray-200" },
];

function typeFilterInfo(type: string): TypeFilter {
  return TYPE_FILTERS.find((f) => f.value === type) ?? { value: type, label: type, icon: FileText, color: "text-gray-600 bg-gray-50 border-gray-200" };
}

/**
 * Global search (Sprint-5 M2 + M26). Queries the hybrid search API and
 * renders typed hits with provenance (lexical / semantic / both) and the
 * deterministic score. Deep-linkable via `?q=` (the TopHeader search box
 * navigates here); typing re-searches with a 300 ms debounce.
 */
export default function SearchPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const urlQuery = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(urlQuery);
  const [debounced, setDebounced] = useState(urlQuery);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);

  // Sync with the URL when the header search navigates here again.
  useEffect(() => {
    setQuery(urlQuery);
    setDebounced(urlQuery);
  }, [urlQuery]);
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

  const run = useCallback(async (text: string, objectType?: string | null) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const response = await searchObjects(
        { text, object_type: objectType ?? undefined, limit: 50 },
        { signal: controller.signal },
      );
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
      void run(debounced.trim(), typeFilter);
    } else {
      setHits([]);
      setSearched(false);
    }
  }, [debounced, typeFilter, run]);

  const handleTypeFilter = (value: string) => {
    const newFilter = typeFilter === value ? null : value;
    setTypeFilter(newFilter);
    if (debounced.trim()) {
      void run(debounced.trim(), newFilter);
    }
  };

  const clearAll = () => {
    setQuery("");
    setTypeFilter(null);
    setHits([]);
    setSearched(false);
  };

  // Group hits by type for section headers
  const groupedHits = hits.reduce<Record<string, SearchHit[]>>((acc, hit) => {
    const type = hit.object_type;
    if (!acc[type]) acc[type] = [];
    acc[type].push(hit);
    return acc;
  }, {});

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Search</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Find anything across your academic records — events, publications, research, and more.
        </p>
      </header>

      <SearchBar
        value={query}
        onChange={setQuery}
        placeholder="Search conferences, papers, projects, certificates…"
        busy={loading}
      />

      {/* Entity type filter chips */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
          <Filter className="h-4 w-4" /> Type:
        </div>
        {TYPE_FILTERS.map((filter) => {
          const Icon = filter.icon;
          const active = typeFilter === filter.value;
          return (
            <button
              key={filter.value}
              type="button"
              onClick={() => handleTypeFilter(filter.value)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                active
                  ? filter.color
                  : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {filter.label}
            </button>
          );
        })}
        {(typeFilter || searched) && (
          <button
            type="button"
            onClick={clearAll}
            className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] px-2.5 py-1 text-xs text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)]"
          >
            <X className="h-3 w-3" /> Clear
          </button>
        )}
      </div>

      {error ? (
        <p className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-3 text-sm text-[var(--text-danger)]">
          {error}
        </p>
      ) : null}

      {searched && !loading && hits.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-[var(--text-tertiary)]">
          <Search className="h-10 w-10" />
          <p className="text-sm">No results for &ldquo;{debounced}&rdquo;{typeFilter ? ` in ${typeFilterInfo(typeFilter).label}` : ""}.</p>
          <p className="text-xs">Try different keywords or remove the type filter.</p>
        </div>
      ) : null}

      {/* Results grouped by type */}
      {searched && !loading && hits.length > 0 && (
        <div className="space-y-6">
          <p className="text-xs text-[var(--text-tertiary)]">
            {hits.length} result{hits.length === 1 ? "" : "s"} for &ldquo;{debounced}&rdquo;
          </p>

          {Object.entries(groupedHits).map(([type, typeHits]) => {
            const info = typeFilterInfo(type);
            const Icon = info.icon;
            return (
              <div key={type}>
                <div className="mb-2 flex items-center gap-2">
                  <Icon className={cn("h-4 w-4", info.color.split(" ")[0])} />
                  <h2 className="text-sm font-semibold text-[var(--text-primary)]">{info.label}</h2>
                  <span className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-tertiary)]">
                    {typeHits.length}
                  </span>
                </div>
                <ul className="flex flex-col gap-2">
                  {typeHits.map((hit) => (
                    <li key={hit.object_id}>
                      <button
                        type="button"
                        onClick={() => router.push(`/objects/${hit.object_id}`)}
                        className="flex w-full items-start justify-between gap-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-3 text-left transition-colors hover:border-[var(--accent)] hover:shadow-sm"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-[var(--text-primary)]">
                            {hit.title}
                          </p>
                          <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                            {hit.object_type.replace(/_/g, " ")}
                            {hit.version > 1 ? ` · v${hit.version}` : ""}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span
                            title={`Matched by the ${hit.index_source} index leg`}
                            className={cn(
                              "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                              hit.index_source === "both"
                                ? "bg-[var(--accent-subtle)] text-[var(--accent)]"
                                : hit.index_source === "semantic"
                                  ? "bg-[var(--bg-hover)] text-[var(--text-secondary)]"
                                  : "bg-[var(--bg-hover)] text-[var(--text-tertiary)]",
                            )}
                          >
                            {hit.index_source}
                          </span>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}

      {!searched && !loading && hits.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-[var(--text-tertiary)]">
          <Search className="h-10 w-10" aria-hidden="true" />
          <p className="text-sm">Type a query to search your academic records.</p>
          <div className="mt-2 flex flex-wrap justify-center gap-2">
            {["conferences 2024", "FDP certificates", "journal publications", "research grants"].map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setQuery(example)}
                className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
