"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GraduationCap, Home, FileText, BookOpen, Sparkles, Settings, Menu, X, GripVertical, Eye, EyeOff, RotateCcw, Plus, Trash2, Layout, Calendar, FlaskConical, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCallback, useEffect, useState } from "react";

interface NavItem { id: string; label: string; icon: typeof Home; href: string; visible: boolean; custom?: boolean; modules?: string[]; }

const AVAILABLE_MODULES = [
  { id: "publications", label: "Publications", icon: BookOpen, href: "/publications" },
  { id: "research", label: "Research", icon: Sparkles, href: "/research" },
  { id: "teaching", label: "Teaching", icon: GraduationCap, href: "/teaching" },
  { id: "committees", label: "Committees", icon: GraduationCap, href: "/committees" },
  { id: "events", label: "Events", icon: GraduationCap, href: "/events" },
  { id: "students", label: "Students", icon: GraduationCap, href: "/students" },
  { id: "finance", label: "Finance", icon: GraduationCap, href: "/finance" },
  { id: "faculty", label: "Faculty", icon: GraduationCap, href: "/faculty" },
];

const DEFAULT_NAV: NavItem[] = [
  { id: "home", label: "Home", icon: Home, href: "/", visible: true },
  { id: "docs", label: "Documents", icon: FileText, href: "/documents", visible: true },
  { id: "events", label: "Events", icon: Calendar, href: "/events", visible: true },
  { id: "publications", label: "Publications", icon: BookOpen, href: "/publications", visible: true },
  { id: "research", label: "Research", icon: FlaskConical, href: "/research", visible: true },
  { id: "search", label: "Search", icon: Search, href: "/search", visible: true },
];

const STORAGE_KEY = "academicos-nav-config";
const WORKSPACE_KEY = "academicos-workspaces";

function loadNavConfig(): NavItem[] {
  if (typeof window === "undefined") return DEFAULT_NAV;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return DEFAULT_NAV;
    const parsed = JSON.parse(stored) as { id: string; label?: string; icon?: string; href?: string; visible: boolean; order: number; custom?: boolean; modules?: string[] }[];
    const allDefaults = [...DEFAULT_NAV, ...AVAILABLE_MODULES.map((m) => ({ ...m, visible: false }))];
    const merged = allDefaults.map((item) => {
      const saved = parsed.find((s) => s.id === item.id);
      return saved ? { ...item, visible: saved.visible, custom: saved.custom, modules: saved.modules } : item;
    });
    const customItems = parsed.filter((s) => s.custom && !allDefaults.find((d) => d.id === s.id));
    for (const c of customItems) {
      merged.push({ id: c.id, label: c.label ?? c.id, icon: c.modules && c.modules.length > 1 ? Layout : FileText, href: c.href ?? "/", visible: c.visible, custom: true, modules: c.modules });
    }
    const orderMap = new Map(parsed.map((s, i) => [s.id, s.order]));
    merged.sort((a, b) => (orderMap.get(a.id) ?? 99) - (orderMap.get(b.id) ?? 99));
    return merged;
  } catch { return DEFAULT_NAV; }
}

function saveNavConfig(items: NavItem[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items.map((item, i) => ({ id: item.id, label: item.label, href: item.href, visible: item.visible, order: i, custom: item.custom, modules: item.modules }))));
}

function saveWorkspace(id: string, name: string, modules: string[]) {
  if (typeof window === "undefined") return;
  try {
    const stored = localStorage.getItem(WORKSPACE_KEY);
    const workspaces = stored ? JSON.parse(stored) : [];
    const existing = workspaces.findIndex((w: { id: string }) => w.id === id);
    const workspace = { id, name, modules };
    if (existing >= 0) workspaces[existing] = workspace;
    else workspaces.push(workspace);
    localStorage.setItem(WORKSPACE_KEY, JSON.stringify(workspaces));
  } catch { /* ignore */ }
}

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [customizing, setCustomizing] = useState(false);
  const [navItems, setNavItems] = useState<NavItem[]>(DEFAULT_NAV);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [mounted, setMounted] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTabName, setNewTabName] = useState("");
  const [selectedModules, setSelectedModules] = useState<string[]>([]);

  useEffect(() => { setNavItems(loadNavConfig()); setMounted(true); }, []);

  const isActive = (href: string) => href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  const toggleVisibility = useCallback((id: string) => {
    setNavItems((prev) => { const next = prev.map((item) => item.id === id ? { ...item, visible: !item.visible } : item); saveNavConfig(next); return next; });
  }, []);

  const resetConfig = useCallback(() => {
    setNavItems(DEFAULT_NAV);
    saveNavConfig(DEFAULT_NAV);
    localStorage.removeItem(WORKSPACE_KEY);
  }, []);

  const addCustomTab = useCallback(() => {
    if (!newTabName.trim()) return;
    const id = `workspace-${Date.now()}`;
    const isWorkspace = selectedModules.length > 1;
    const href = isWorkspace ? `/workspace?id=${id}` : (AVAILABLE_MODULES.find((m) => m.id === selectedModules[0])?.href ?? "/documents");
    const icon = isWorkspace ? Layout : (AVAILABLE_MODULES.find((m) => m.id === selectedModules[0])?.icon ?? FileText);

    setNavItems((prev) => {
      const next = [...prev, { id, label: newTabName.trim(), icon, href, visible: true, custom: true, modules: selectedModules }];
      saveNavConfig(next);
      return next;
    });

    if (isWorkspace) {
      saveWorkspace(id, newTabName.trim(), selectedModules);
    }

    setNewTabName("");
    setSelectedModules([]);
    setShowCreateForm(false);
  }, [newTabName, selectedModules]);

  const removeCustomTab = useCallback((id: string) => {
    setNavItems((prev) => { const next = prev.filter((item) => item.id !== id); saveNavConfig(next); return next; });
    // Also remove workspace config
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(WORKSPACE_KEY);
        if (stored) {
          const workspaces = JSON.parse(stored).filter((w: { id: string }) => w.id !== id);
          localStorage.setItem(WORKSPACE_KEY, JSON.stringify(workspaces));
        }
      } catch { /* ignore */ }
    }
  }, []);

  const toggleModule = useCallback((moduleId: string) => {
    setSelectedModules((prev) =>
      prev.includes(moduleId) ? prev.filter((id) => id !== moduleId) : [...prev, moduleId]
    );
  }, []);

  const onDragStart = useCallback((index: number) => setDragIndex(index), []);
  const onDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === index) return;
    setNavItems((prev) => { const next = [...prev]; const [moved] = next.splice(dragIndex, 1); next.splice(index, 0, moved); setDragIndex(index); saveNavConfig(next); return next; });
  }, [dragIndex]);
  const onDragEnd = useCallback(() => setDragIndex(null), []);

  const visibleItems = navItems.filter((item) => item.visible || customizing);

  const navLink = (item: NavItem, index: number) => {
    const Icon = item.icon;
    const active = isActive(item.href);
    if (customizing) {
      return (
        <div key={item.id} draggable onDragStart={() => onDragStart(index)} onDragOver={(e) => onDragOver(e, index)} onDragEnd={onDragEnd} className={cn("flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors", !item.visible ? "opacity-40" : "", dragIndex === index ? "bg-[var(--accent-subtle)]" : "hover:bg-[var(--bg-hover)]")}>
          <GripVertical className="h-3.5 w-3.5 cursor-grab text-[var(--text-tertiary)]" /><Icon className="h-4 w-4 text-[var(--text-secondary)]" /><span className="flex-1 text-[var(--text-primary)]">{item.label}</span>
          {item.custom && (
            <button type="button" onClick={(e) => { e.stopPropagation(); removeCustomTab(item.id); }} aria-label={`Remove ${item.label}`} className="rounded p-0.5 hover:bg-red-100 text-red-500">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          <button type="button" onClick={(e) => { e.stopPropagation(); toggleVisibility(item.id); }} aria-label={item.visible ? `Hide ${item.label}` : `Show ${item.label}`} className="rounded p-0.5 hover:bg-[var(--bg-hover)]">
            {item.visible ? <Eye className="h-3.5 w-3.5 text-[var(--text-tertiary)]" /> : <EyeOff className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />}
          </button>
        </div>
      );
    }
    return (
      <Link key={item.id} href={item.href} aria-current={active ? "page" : undefined} onClick={() => setMobileOpen(false)} className={cn("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors", active ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]")}>
        <Icon className="h-4 w-4" />{item.label}
      </Link>
    );
  };

  if (!mounted) {
    return (
      <aside className="hidden w-56 shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-5 md:flex">
        <div className="mb-6 flex items-center gap-2 px-2"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)] text-white"><GraduationCap className="h-5 w-5" /></div><span className="text-lg font-semibold text-[var(--text-primary)]">AcademicOS</span></div>
        <nav className="flex flex-1 flex-col gap-1">{DEFAULT_NAV.filter((item) => item.visible).map((item) => navLink(item, 0))}</nav>
        <div className="mt-auto flex flex-col gap-1 border-t border-[var(--border-subtle)] pt-3"><Link href="/settings" className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"><Settings className="h-4 w-4" /> Settings</Link></div>
      </aside>
    );
  }

  return (
    <>
      <button type="button" aria-label="Toggle navigation" onClick={() => setMobileOpen(!mobileOpen)} className="fixed left-3 top-3 z-50 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-2 text-[var(--text-secondary)] md:hidden">
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>
      {mobileOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setMobileOpen(false)} />}
      <aside className={cn("flex w-56 shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-5 transition-transform", "fixed inset-y-0 left-0 z-40 md:static md:translate-x-0", mobileOpen ? "translate-x-0" : "-translate-x-full")}>
        <div className="mb-6 flex items-center gap-2 px-2"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)] text-white"><GraduationCap className="h-5 w-5" /></div><span className="text-lg font-semibold text-[var(--text-primary)]">AcademicOS</span></div>
        <nav className="flex flex-1 flex-col gap-1">{visibleItems.map((item, i) => navLink(item, i))}</nav>
        {customizing && (
          <div className="border-t border-[var(--border-subtle)] pt-2 space-y-1">
            {!showCreateForm ? (
              <button type="button" onClick={() => setShowCreateForm(true)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--accent)] hover:bg-[var(--bg-hover)]">
                <Plus className="h-3 w-3" /> Create workspace
              </button>
            ) : (
              <div className="space-y-2 px-3 py-2">
                <input
                  type="text"
                  value={newTabName}
                  onChange={(e) => setNewTabName(e.target.value)}
                  placeholder="Workspace name (e.g. My Research)"
                  className="w-full rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-xs"
                  onKeyDown={(e) => { if (e.key === "Enter" && selectedModules.length > 0) addCustomTab(); }}
                />
                <p className="text-[10px] text-[var(--text-tertiary)]">Select modules to include:</p>
                <div className="flex flex-wrap gap-1">
                  {AVAILABLE_MODULES.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => toggleModule(m.id)}
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors",
                        selectedModules.includes(m.id)
                          ? "bg-[var(--accent)] text-white"
                          : "bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                      )}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={addCustomTab}
                    disabled={selectedModules.length === 0 || !newTabName.trim()}
                    className="flex-1 rounded bg-[var(--accent)] px-2 py-1 text-xs text-white disabled:opacity-50"
                  >
                    Add ({selectedModules.length})
                  </button>
                  <button type="button" onClick={() => { setShowCreateForm(false); setSelectedModules([]); setNewTabName(""); }} className="flex-1 rounded border border-[var(--border-subtle)] px-2 py-1 text-xs">Cancel</button>
                </div>
              </div>
            )}
            <button type="button" onClick={resetConfig} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)]"><RotateCcw className="h-3 w-3" /> Reset to defaults</button>
          </div>
        )}
        <div className="mt-auto flex flex-col gap-1 border-t border-[var(--border-subtle)] pt-3">
          <button type="button" onClick={() => setCustomizing(!customizing)} className={cn("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors", customizing ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-secondary)]")}>{customizing ? "Done" : "Customize"}</button>
          <Link href="/settings" onClick={() => setMobileOpen(false)} className={cn("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors", isActive("/settings") ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]")}><Settings className="h-4 w-4" />Settings</Link>
        </div>
      </aside>
    </>
  );
}
