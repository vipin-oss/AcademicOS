"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Upload, Search, Sparkles, BookOpen, FileText, Clock, ArrowRight, AlertCircle, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { api } from "@/lib/api/client";
import type { ListDocumentsResponse, DocumentResponse } from "@/types";

interface PendingConfirmation {
  claim_id: string;
  predicate_id: string;
  value_schema: string;
  source_document_id: string;
  fact_confidence: number | null;
  tier: string;
}

interface MissingItem {
  record_id: string;
  record_type: string;
  record_title: string;
  missing_field: string;
  predicate_id: string;
  why_it_matters: string;
  source_document_id: string | null;
}

export default function HomePage() {
  const [recentDocs, setRecentDocs] = useState<DocumentResponse[]>([]);
  const [totalObjects, setTotalObjects] = useState(0);
  const [pendingItems, setPendingItems] = useState<PendingConfirmation[]>([]);
  const [missingItems, setMissingItems] = useState<MissingItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<ListDocumentsResponse>("/documents", { query: { page_size: 5 } }),
      api.get<{ total_count: number }>("/objects", { query: { page_size: 1 } }),
      api.get<PendingConfirmation[]>("/confirmations/pending", { query: { page_size: 5 } }).catch(() => []),
      api.get<MissingItem[]>("/missing-info", { query: { limit: 5 } }).catch(() => []),
    ]).then(([docs, objects, pending, missing]) => {
      setRecentDocs(docs.items ?? []);
      setTotalObjects(objects.total_count ?? 0);
      setPendingItems(Array.isArray(pending) ? pending : []);
      setMissingItems(Array.isArray(missing) ? missing : []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleApprove = async (claimId: string) => {
    try {
      await api.post(`/confirmations/${claimId}/approve`, {});
      setPendingItems((prev) => prev.filter((item) => item.claim_id !== claimId));
    } catch { /* ignore */ }
  };

  const handleReject = async (claimId: string) => {
    try {
      await api.post(`/confirmations/${claimId}/reject`, {});
      setPendingItems((prev) => prev.filter((item) => item.claim_id !== claimId));
    } catch { /* ignore */ }
  };

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

          {/* Quick actions */}
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
            <div className="lg:col-span-2 space-y-6">
              {/* Review Queue — attention signals */}
              {pendingItems.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50">
                  <div className="flex items-center justify-between border-b border-amber-200 px-5 py-4">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 text-amber-600" />
                      <h2 className="text-sm font-semibold text-amber-900">Needs Your Attention</h2>
                    </div>
                    <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-800">{pendingItems.length} pending</span>
                  </div>
                  <div className="divide-y divide-amber-200">
                    {pendingItems.slice(0, 5).map((item) => (
                      <div key={item.claim_id} className="flex items-center gap-3 px-5 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-amber-900">
                            {item.predicate_id.replace(/_/g, " ")}: {String(item.value_schema)}
                          </p>
                          <p className="text-xs text-amber-700">
                            Confidence: {item.fact_confidence != null ? `${Math.round(item.fact_confidence * 100)}%` : "unknown"} · Tier: {item.tier}
                          </p>
                        </div>
                        <div className="flex items-center gap-1">
                          <button type="button" onClick={() => void handleApprove(item.claim_id)} className="rounded-lg bg-emerald-100 p-1.5 text-emerald-700 hover:bg-emerald-200" aria-label="Approve">
                            <CheckCircle2 className="h-4 w-4" />
                          </button>
                          <button type="button" onClick={() => void handleReject(item.claim_id)} className="rounded-lg bg-red-100 p-1.5 text-red-700 hover:bg-red-200" aria-label="Reject">
                            <XCircle className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Missing Information */}
              {missingItems.length > 0 && (
                <div className="rounded-xl border border-orange-200 bg-orange-50">
                  <div className="flex items-center justify-between border-b border-orange-200 px-5 py-4">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-orange-600" />
                      <h2 className="text-sm font-semibold text-orange-900">Incomplete Records</h2>
                    </div>
                    <span className="rounded-full bg-orange-200 px-2 py-0.5 text-xs font-medium text-orange-800">{missingItems.length} items</span>
                  </div>
                  <div className="divide-y divide-orange-200">
                    {missingItems.slice(0, 5).map((item, i) => (
                      <Link
                        key={`${item.record_id}-${item.predicate_id}-${i}`}
                        href={`/documents/${item.source_document_id ?? item.record_id}`}
                        className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-orange-100"
                      >
                        <AlertTriangle className="h-4 w-4 shrink-0 text-orange-500" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-orange-900">
                            {item.missing_field.replace(/_/g, " ")} missing
                          </p>
                          <p className="text-xs text-orange-700">
                            {item.record_title} · {item.why_it_matters}
                          </p>
                        </div>
                        <ArrowRight className="h-3.5 w-3.5 text-orange-400" />
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent Activity */}
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

            <div className="space-y-4">
              <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
                <h2 className="mb-4 text-sm font-semibold text-[var(--text-primary)]">Academic Summary</h2>
                <div className="space-y-3">
                  <div className="flex items-center justify-between"><span className="text-sm text-[var(--text-secondary)]">Total Records</span><span className="text-sm font-semibold text-[var(--text-primary)]">{totalObjects}</span></div>
                  <div className="flex items-center justify-between"><span className="text-sm text-[var(--text-secondary)]">Recent Uploads</span><span className="text-sm font-semibold text-[var(--text-primary)]">{recentDocs.length}</span></div>
                  {pendingItems.length > 0 && (
                    <div className="flex items-center justify-between"><span className="text-sm text-[var(--text-secondary)]">Pending Review</span><span className="text-sm font-semibold text-amber-600">{pendingItems.length}</span></div>
                  )}
                  {missingItems.length > 0 && (
                    <div className="flex items-center justify-between"><span className="text-sm text-[var(--text-secondary)]">Incomplete Records</span><span className="text-sm font-semibold text-orange-600">{missingItems.length}</span></div>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-purple-200 bg-purple-50 p-5">
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
