"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, FlaskConical, Wallet, Calendar, Award, UsersRound, GraduationCap, FileText } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { api } from "@/lib/api/client";
import type { ListObjectsResponse, ObjectResponse } from "@/types";

interface RecordCategory { key: string; label: string; icon: typeof BookOpen; objectTypes: string[]; href: string; color: string; }

const CATEGORIES: RecordCategory[] = [
  { key: "publications", label: "Publications", icon: BookOpen, objectTypes: ["publication"], href: "/publications", color: "var(--accent)" },
  { key: "research", label: "Research & Grants", icon: FlaskConical, objectTypes: ["research_project", "grant"], href: "/research", color: "#059669" },
  { key: "teaching", label: "Teaching", icon: GraduationCap, objectTypes: ["course"], href: "/teaching", color: "#d97706" },
  { key: "conferences", label: "Conferences & Events", icon: Calendar, objectTypes: ["event", "conference"], href: "/events", color: "#7c3aed" },
  { key: "awards", label: "Awards", icon: Award, objectTypes: ["award"], href: "#", color: "#dc2626" },
  { key: "committees", label: "Committees & Service", icon: UsersRound, objectTypes: ["committee"], href: "/committees", color: "#0891b2" },
  { key: "finance", label: "Finance", icon: Wallet, objectTypes: ["purchase", "budget"], href: "/finance", color: "#65a30d" },
  { key: "documents", label: "All Documents", icon: FileText, objectTypes: ["document"], href: "/documents", color: "#6b7280" },
];

export default function RecordsPage() {
  const [objects, setObjects] = useState<ObjectResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<ListObjectsResponse>("/objects", { query: { page_size: 500 } }).then((data) => setObjects(data.items ?? [])).catch(() => setObjects([])).finally(() => setLoading(false));
  }, []);

  const countFor = (cat: RecordCategory) => objects.filter((o) => cat.objectTypes.includes(o.object_type)).length;

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Records" }]} />
          <div className="mt-4">
            <h1 className="text-xl font-semibold text-[var(--text-primary)]">My Academic Records</h1>
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">Your structured academic knowledge — publications, projects, teaching, and more.</p>
          </div>
          {loading ? (
            <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-32 animate-pulse rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-hover)]" />)}</div>
          ) : (
            <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {CATEGORIES.map((cat) => { const Icon = cat.icon; const count = countFor(cat); return (
                <Link key={cat.key} href={cat.href} className="group flex flex-col gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 transition-all hover:border-[var(--accent)] hover:shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ backgroundColor: `${cat.color}15`, color: cat.color }}><Icon className="h-5 w-5" /></div>
                    <div><p className="text-sm font-semibold text-[var(--text-primary)]">{cat.label}</p><p className="text-xs text-[var(--text-tertiary)]">{count} record{count !== 1 ? "s" : ""}</p></div>
                  </div>
                  {count > 0 && <div className="flex flex-wrap gap-1">{objects.filter((o) => cat.objectTypes.includes(o.object_type)).slice(0, 3).map((o) => <span key={o.id} className="truncate rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-xs text-[var(--text-secondary)]" style={{ maxWidth: "120px" }}>{o.title}</span>)}</div>}
                </Link>
              ); })}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
