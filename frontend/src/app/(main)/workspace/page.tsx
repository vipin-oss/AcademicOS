"use client";

/**
 * Dynamic Workspace Page — renders a custom workspace with multiple modules.
 *
 * The workspace configuration is stored in localStorage (same as sidebar config).
 * Each workspace can contain multiple modules displayed as sections.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  BookOpen, FlaskConical, GraduationCap, Calendar, Award,
  UsersRound, Wallet, FileText, Sparkles, Settings,
  ArrowRight, Layout
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { api } from "@/lib/api/client";
import type { ListObjectsResponse, ObjectResponse, ListDocumentsResponse, DocumentResponse } from "@/types";

interface WorkspaceModule {
  id: string;
  label: string;
  objectTypes: string[];
  href: string;
  icon: typeof BookOpen;
}

const AVAILABLE_MODULES: WorkspaceModule[] = [
  { id: "publications", label: "Publications", objectTypes: ["publication"], href: "/publications", icon: BookOpen },
  { id: "research", label: "Research Projects", objectTypes: ["research_project", "grant"], href: "/research", icon: FlaskConical },
  { id: "teaching", label: "Teaching", objectTypes: ["course"], href: "/teaching", icon: GraduationCap },
  { id: "conferences", label: "Conferences", objectTypes: ["event", "conference"], href: "/events", icon: Calendar },
  { id: "awards", label: "Awards", objectTypes: ["award"], href: "#", icon: Award },
  { id: "committees", label: "Committees", objectTypes: ["committee"], href: "/committees", icon: UsersRound },
  { id: "finance", label: "Finance", objectTypes: ["purchase", "budget"], href: "/finance", icon: Wallet },
  { id: "documents", label: "Documents", objectTypes: ["document"], href: "/documents", icon: FileText },
];

interface WorkspaceConfig {
  id: string;
  name: string;
  modules: string[]; // module ids
}

const WORKSPACE_STORAGE_KEY = "academicos-workspaces";

function loadWorkspace(id: string): WorkspaceConfig | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (!stored) return null;
    const workspaces: WorkspaceConfig[] = JSON.parse(stored);
    return workspaces.find((w) => w.id === id) ?? null;
  } catch { return null; }
}

export default function WorkspacePage() {
  const searchParams = useSearchParams();
  const workspaceId = searchParams.get("id") ?? "";
  const [workspace, setWorkspace] = useState<WorkspaceConfig | null>(null);
  const [objects, setObjects] = useState<ObjectResponse[]>([]);
  const [recentDocs, setRecentDocs] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspaceId) return;
    const config = loadWorkspace(workspaceId);
    setWorkspace(config);

    if (config) {
      Promise.all([
        api.get<ListObjectsResponse>("/objects", { query: { page_size: 500 } }),
        api.get<ListDocumentsResponse>("/documents", { query: { page_size: 5 } }),
      ]).then(([objs, docs]) => {
        setObjects(objs.items ?? []);
        setRecentDocs(docs.items ?? []);
      }).catch(() => {}).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [workspaceId]);

  if (!workspaceId) {
    return (
      <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopHeader />
          <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
            <div className="flex flex-col items-center justify-center py-16">
              <Layout className="h-12 w-12 text-[var(--text-tertiary)]" />
              <h1 className="mt-4 text-xl font-semibold">No Workspace Selected</h1>
              <p className="mt-2 text-sm text-[var(--text-tertiary)]">
                Create a custom workspace from the sidebar customization panel.
              </p>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopHeader />
          <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
            <div className="flex flex-col items-center justify-center py-16">
              <Layout className="h-12 w-12 text-[var(--text-tertiary)]" />
              <h1 className="mt-4 text-xl font-semibold">Workspace Not Found</h1>
              <p className="mt-2 text-sm text-[var(--text-tertiary)]">
                This workspace may have been deleted. Create a new one from the sidebar.
              </p>
            </div>
          </main>
        </div>
      </div>
    );
  }

  const modules = workspace.modules
    .map((id) => AVAILABLE_MODULES.find((m) => m.id === id))
    .filter((m): m is WorkspaceModule => m !== undefined);

  const filteredObjects = objects.filter((o) =>
    modules.some((m) => m.objectTypes.includes(o.object_type))
  );

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: workspace.name }]} />

          <div className="mt-4 mb-6">
            <h1 className="text-xl font-semibold text-[var(--text-primary)]">{workspace.name}</h1>
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">
              Custom workspace with {modules.length} module{modules.length !== 1 ? "s" : ""}
            </p>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-32 animate-pulse rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-hover)]" />
              ))}
            </div>
          ) : (
            <div className="space-y-6">
              {/* Module sections */}
              {modules.map((mod) => {
                const Icon = mod.icon;
                const modObjects = filteredObjects.filter((o) => mod.objectTypes.includes(o.object_type));
                return (
                  <div key={mod.id} className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
                    <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-[var(--accent)]" />
                        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{mod.label}</h2>
                        <span className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-xs text-[var(--text-tertiary)]">{modObjects.length}</span>
                      </div>
                      {mod.href !== "#" && (
                        <Link href={mod.href} className="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline">
                          View all <ArrowRight className="h-3 w-3" />
                        </Link>
                      )}
                    </div>
                    {modObjects.length > 0 ? (
                      <div className="divide-y divide-[var(--border-subtle)]">
                        {modObjects.slice(0, 5).map((obj) => (
                          <Link
                            key={obj.id}
                            href={`/objects/${obj.id}`}
                            className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-[var(--bg-hover)]"
                          >
                            <Icon className="h-4 w-4 shrink-0 text-[var(--text-tertiary)]" />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium text-[var(--text-primary)]">{obj.title}</p>
                              <p className="text-xs text-[var(--text-tertiary)]">{obj.object_type} · {obj.status}</p>
                            </div>
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <div className="p-6 text-center">
                        <p className="text-sm text-[var(--text-tertiary)]">No {mod.label.toLowerCase()} records yet.</p>
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Recent documents across all modules */}
              {recentDocs.length > 0 && (
                <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
                  <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-[var(--text-tertiary)]" />
                      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Recent Documents</h2>
                    </div>
                    <Link href="/documents" className="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline">
                      View all <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                  <div className="divide-y divide-[var(--border-subtle)]">
                    {recentDocs.map((doc) => (
                      <Link
                        key={doc.id}
                        href={`/documents/${doc.id}`}
                        className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-[var(--bg-hover)]"
                      >
                        <FileText className="h-4 w-4 shrink-0 text-[var(--text-tertiary)]" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-[var(--text-primary)]">{doc.title}</p>
                          <p className="text-xs text-[var(--text-tertiary)]">{doc.document_type?.toUpperCase()}</p>
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
