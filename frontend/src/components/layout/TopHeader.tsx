"use client";

import { useState } from "react";
import { Bell, LogOut, Search } from "lucide-react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth/session";
import NotificationBell from "@/components/features/notifications/NotificationBell";

export function TopHeader() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const initials = (user?.username ?? "AU").slice(0, 2).toUpperCase();

  const submitSearch = () => {
    const q = query.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
  };

  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-4 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 md:px-6">
      <span className="hidden text-base font-semibold text-[var(--text-primary)] sm:block">
        AcademicOS
      </span>
      <div className="relative w-full max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-tertiary)]" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submitSearch();
          }}
          placeholder="Search the knowledge graph… (Enter)"
          aria-label="Search the knowledge graph"
          className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] py-2 pl-9 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
        />
      </div>
      <NotificationBell />
      <div className="hidden items-center gap-2 sm:flex">
        <span className="max-w-[10rem] truncate text-sm text-[var(--text-secondary)]">
          {user?.username ?? ""}
        </span>
      </div>
      <div
        className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--accent-subtle)] text-sm font-semibold text-[var(--accent)]"
        title={user?.username ?? ""}
      >
        {initials}
      </div>
      <button
        type="button"
        aria-label="Sign out"
        title="Sign out"
        onClick={logout}
        className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--danger)]"
      >
        <LogOut className="h-5 w-5" />
      </button>
    </header>
  );
}
