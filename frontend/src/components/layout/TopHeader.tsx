"use client";

import { Bell, Search } from "lucide-react";

export function TopHeader() {
  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-4 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 md:px-6">
      <span className="hidden text-base font-semibold text-[var(--text-primary)] sm:block">
        AcademicOS
      </span>
      <div className="relative w-full max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-tertiary)]" />
        <input
          type="text"
          placeholder="Search the knowledge graph…"
          className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] py-2 pl-9 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
        />
      </div>
      <button
        type="button"
        aria-label="Notifications"
        className="relative rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
      >
        <Bell className="h-5 w-5" />
        <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[var(--danger)]" />
      </button>
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--accent-subtle)] text-sm font-semibold text-[var(--accent)]">
        AU
      </div>
    </header>
  );
}
