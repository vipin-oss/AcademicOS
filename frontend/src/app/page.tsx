"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Upload, Search, Sparkles, BookOpen, FileText, Clock, ArrowRight } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { api } from "@/lib/api/client";
import type { ListDocumentsResponse, DocumentResponse } from "@/types";

export default function HomePage() {
  const [recentDocs, setRecentDocs] = useState<DocumentResponse[]>([]);
  const [totalObjects, setTotalObjects] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<ListDocumentsResponse>("/documents", { query: { page_size: 5 } }),
      api.get<{ total_count: number }>("/objects", { query: { page_size: 1 } }),
    ]).then(([docs, objects]) => { setRecentDocs(docs.items ?? []); setTotalObjects(objects.total_count ?? 0); }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Welcome to AcademicOS</h1>
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">Upload documents, ask questions, and let AcademicOS organize your academic life.</p>
          </div>
          <div className="mb-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Link href="/documents" className="flex items-center gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 transition-all hover:border-[var(--accent)] hover:shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--accent-subtle)] text-[var(--accent)]"><Upload className="h-5 w-5" /></div>
              <div><p className="text-sm font-semibold text-[var(--text-primary)]">Upload</p><p className="text-xs text-[var(--text-tertiary)]">Add documents</p></div>
            </Link>
            <Link href="/search" className="flex items-center gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 transition-all hover:border-[var(--accent)] hover:shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600"><Search className="h-5 w-5" /></div>
              <div><p className="text-sm font-semibold text-[var(--text-primary)]">Search</p><p className="text-xs text-[var(--text-tertiary)]">Find anything</p></div>
            </Link>
            <Link href="/ai" className="flex items-center gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 transition-all hover:border-[var(--accent)] hover:shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600"><Sparkles className="h-5 w-5" /></div>
              <div><p className="text-sm font-semibold text-[var(--text-primary)]">Ask AI</p><p className="text-xs text-[var(--text-tertiary)]">Get answers</p></div>
            </Link>
            <Link href="/records" className="flex items-center gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 transition-all hover:border-[var(--accent)] hover:shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600"><BookOpen className="h-5 w-5" /></div>
              <div><p className="text-sm font-semibold text-[var(--text-primary)]">Records</p><p className="text-xs text-[var(--text-tertiary)]">Academic data</p></div>
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
                <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
                  <h2 className="text-sm font-semibold text-[var(--text-primary)]">Recent Activity</h2>
                  <Link href="/documents" className="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline">View all <ArrowRight className="h-3 w-3" /></Link>
                </div>
                {loading ? <div className="space-y-3 p-5">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-12 animate-pulse rounded-lg bg-[var(--bg-hover)]" />)}</div> : recentDocs.length > 0 ? (
                  <div className="divide-y divide-[var(--border-subtle)]">
                    {recentDocs.map((doc) => (
                      <Link key={doc.id} href={`/documents/${doc.id}`} className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-[var(--bg-hover)]">
                        <FileText className="h-4 w-4 shrink-0 text-[var(--text-tertiary)]" />
                        <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-[var(--text-primary)]">{doc.title}</p><p className="text-xs text-[var(--text-tertiary)]">{doc.document_type?.toUpperCase() ?? "Document"} · {doc.status}</p></div>
                        <span className="flex items-center gap-1 text-xs text-[var(--text-tertiary)]"><Clock className="h-3 w-3" />{new Date(doc.created_at).toLocaleDateString()}</span>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 text-center"><FileText className="mx-auto h-8 w-8 text-[var(--text-tertiary)]" /><p className="mt-2 text-sm text-[var(--text-tertiary)]">No documents yet. Upload your first document to get started.</p><Link href="/documents" className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)]"><Upload className="h-4 w-4" /> Upload Document</Link></div>
                )}
              </div>
            </div>
            <div>
              <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
                <h2 className="mb-4 text-sm font-semibold text-[var(--text-primary)]">Academic Summary</h2>
                <div className="space-y-3">
                  <div className="flex items-center justify-between"><span className="text-sm text-[var(--text-secondary)]">Total Records</span><span className="text-sm font-semibold text-[var(--text-primary)]">{totalObjects}</span></div>
                  <div className="flex items-center justify-between"><span className="text-sm text-[var(--text-secondary)]">Recent Uploads</span><span className="text-sm font-semibold text-[var(--text-primary)]">{recentDocs.length}</span></div>
                </div>
              </div>
              <div className="mt-4 rounded-xl border border-purple-200 bg-purple-50 p-5">
                <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-purple-600" /><p className="text-sm font-semibold text-purple-900">AI Tip</p></div>
                <p className="mt-2 text-xs text-purple-700">Try asking: &quot;What information is missing from my academic records?&quot; or &quot;Generate my updated CV.&quot;</p>
                <Link href="/ai" className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-purple-600 hover:underline">Open AI Assistant <ArrowRight className="h-3 w-3" /></Link>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
