"use client";

import { Search, X } from "lucide-react";
import { Spinner } from "./Spinner";

/**
 * Controlled search input. Debouncing lives in `useObjects`, so typing here
 * never fires a request per keystroke.
 */
export function SearchBar({
  value,
  onChange,
  placeholder = "Search objects…",
  busy = false,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  busy?: boolean;
}) {
  return (
    <div className="relative w-full sm:max-w-xs">
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-tertiary)]"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label="Search objects"
        autoComplete="off"
        className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] py-2 pl-9 pr-16 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      <div className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-1">
        {busy ? <Spinner className="h-3.5 w-3.5 text-[var(--text-tertiary)]" label="Searching" /> : null}
        {value ? (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Clear search"
            className="rounded p-1 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </div>
  );
}
