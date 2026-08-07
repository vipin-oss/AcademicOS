"use client";

/**
 * Multi-document workspace (Sprint M10).
 *
 * Opens PDF documents in tabs with per-tab viewer state (zoom, page,
 * annotations, extracted text). Documents are selected via the URL
 * query (?ids=obj:document:a,obj:document:b) or opened from the list.
 */
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { DocumentWorkspace } from "@/components/features/documents/DocumentWorkspace";
import { getDocument } from "@/lib/api/documents";
import { toErrorMessage } from "@/lib/api/client";
import type { DocumentResponse } from "@/types";

export default function DocumentWorkspacePage() {
  const router = useRouter();
  const params = useSearchParams();
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ids = (params.get("ids") ?? "")
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
    if (ids.length === 0) {
      setDocuments([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all(ids.map((id) => getDocument(id)))
      .then((docs) => {
        if (!cancelled) setDocuments(docs);
      })
      .catch((err) => {
        if (!cancelled) setError(toErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params]);

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs
            items={[
              { label: "Dashboard", href: "/" },
              { label: "Documents", href: "/documents" },
              { label: "Workspace" },
            ]}
          />
          <h1 className="mt-2 text-xl font-semibold">Document workspace</h1>
          {error && (
            <p role="alert" className="mt-3 rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
          )}
          <div className="mt-4">
            {loading ? (
              <p className="text-sm text-[var(--text-tertiary)]">Loading documents…</p>
            ) : (
              <DocumentWorkspace documents={documents} onCloseWorkspace={() => router.push("/documents")} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
