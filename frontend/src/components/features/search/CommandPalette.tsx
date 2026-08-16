"use client";

/**
 * Command Palette (⌘K) — universal search and command overlay.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, FileText, BookOpen, Sparkles, Settings, Home, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { searchObjects, type SearchHit } from "@/lib/api/search";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: typeof Home;
  action: () => void;
}

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const navCommands: CommandItem[] = [
    { id: "home", label: "Go to Home", icon: Home, action: () => router.push("/") },
    { id: "docs", label: "Go to Documents", icon: FileText, action: () => router.push("/documents") },
    { id: "records", label: "Go to Records", icon: BookOpen, action: () => router.push("/records") },
    { id: "ai", label: "Go to AI Assistant", icon: Sparkles, action: () => router.push("/ai") },
    { id: "settings", label: "Go to Settings", icon: Settings, action: () => router.push("/settings") },
    { id: "upload", label: "Upload Document", icon: FileText, action: () => router.push("/documents") },
  ];

  const aiCommands: CommandItem[] = [
    { id: "ai-cv", label: "Generate Academic CV", description: "Ask AI to generate your CV from records", icon: Sparkles, action: () => { router.push("/ai"); setOpen(false); } },
    { id: "ai-missing", label: "Find Missing Information", description: "Ask AI what's missing from your records", icon: Sparkles, action: () => { router.push("/ai"); setOpen(false); } },
  ];

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); setOpen((prev) => !prev); }
      if (e.key === "Escape" && open) setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open]);

  useEffect(() => {
    if (open) { setTimeout(() => inputRef.current?.focus(), 50); setQuery(""); setHits([]); setSelectedIndex(0); }
  }, [open]);

  useEffect(() => {
    if (!query.trim()) { setHits([]); return; }
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await searchObjects({ text: query, limit: 10 }, { signal: controller.signal });
        if (controllerRef.current !== controller) return;
        setHits(response.results);
      } catch { /* ignore */ }
      finally { if (controllerRef.current === controller) setLoading(false); }
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query]);

  const filteredNav = query.trim() ? navCommands.filter((cmd) => cmd.label.toLowerCase().includes(query.toLowerCase())) : navCommands;
  const filteredAi = query.trim() ? aiCommands.filter((cmd) => cmd.label.toLowerCase().includes(query.toLowerCase())) : aiCommands;
  const allItems = [...filteredNav.map((cmd) => ({ type: "command" as const, item: cmd })), ...filteredAi.map((cmd) => ({ type: "command" as const, item: cmd })), ...hits.map((hit) => ({ type: "hit" as const, item: hit }))];

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSelectedIndex((prev) => Math.min(prev + 1, allItems.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSelectedIndex((prev) => Math.max(prev - 1, 0)); }
    else if (e.key === "Enter") {
      e.preventDefault();
      const selected = allItems[selectedIndex];
      if (selected) { if (selected.type === "command") selected.item.action(); else router.push(`/objects/${selected.item.object_id}`); setOpen(false); }
    }
  }, [allItems, selectedIndex, router]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/50 pt-[15vh]" onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
      <div className="w-full max-w-lg overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-2xl">
        <div className="flex items-center gap-3 border-b border-[var(--border-subtle)] px-4 py-3">
          <Search className="h-5 w-5 text-[var(--text-tertiary)]" />
          <input ref={inputRef} type="text" value={query} onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0); }} onKeyDown={handleKeyDown} placeholder="Search documents, records, or type a command..." className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none" />
          <kbd className="hidden rounded border border-[var(--border-subtle)] px-1.5 py-0.5 text-xs text-[var(--text-tertiary)] sm:inline">ESC</kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto">
          {loading && <div className="px-4 py-3 text-sm text-[var(--text-tertiary)]">Searching...</div>}
          {!loading && query.trim() && hits.length === 0 && filteredNav.length === 0 && <div className="px-4 py-6 text-center text-sm text-[var(--text-tertiary)]">No results found for &quot;{query}&quot;</div>}
          {filteredNav.length > 0 && (
            <div>
              <p className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Navigation</p>
              {filteredNav.map((cmd, i) => { const Icon = cmd.icon; return (
                <button key={cmd.id} type="button" onClick={() => { cmd.action(); setOpen(false); }} className={cn("flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors", i === selectedIndex ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-primary)] hover:bg-[var(--bg-hover)]")}>
                  <Icon className="h-4 w-4 text-[var(--text-tertiary)]" /><span className="flex-1">{cmd.label}</span><ArrowRight className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />
                </button>
              ); })}
            </div>
          )}
          {filteredAi.length > 0 && (
            <div>
              <p className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">AI Actions</p>
              {filteredAi.map((cmd, i) => { const globalIndex = filteredNav.length + i; const Icon = cmd.icon; return (
                <button key={cmd.id} type="button" onClick={() => { cmd.action(); setOpen(false); }} className={cn("flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors", globalIndex === selectedIndex ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-primary)] hover:bg-[var(--bg-hover)]")}>
                  <Icon className="h-4 w-4 text-purple-500" /><div className="flex-1"><span>{cmd.label}</span>{cmd.description && <p className="text-xs text-[var(--text-tertiary)]">{cmd.description}</p>}</div>
                </button>
              ); })}
            </div>
          )}
          {hits.length > 0 && (
            <div>
              <p className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Documents & Records</p>
              {hits.map((hit, i) => { const globalIndex = filteredNav.length + filteredAi.length + i; return (
                <button key={hit.object_id} type="button" onClick={() => { router.push(`/objects/${hit.object_id}`); setOpen(false); }} className={cn("flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors", globalIndex === selectedIndex ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-primary)] hover:bg-[var(--bg-hover)]")}>
                  <FileText className="h-4 w-4 text-[var(--text-tertiary)]" /><div className="min-w-0 flex-1"><p className="truncate font-medium">{hit.title}</p><p className="text-xs text-[var(--text-tertiary)]">{hit.object_type} · {hit.index_source}</p></div>
                </button>
              ); })}
            </div>
          )}
        </div>
        <div className="flex items-center gap-4 border-t border-[var(--border-subtle)] px-4 py-2 text-xs text-[var(--text-tertiary)]"><span>↑↓ navigate</span><span>↵ select</span><span>esc close</span></div>
      </div>
    </div>
  );
}
