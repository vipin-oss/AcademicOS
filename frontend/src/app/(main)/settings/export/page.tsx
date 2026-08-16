"use client";

/**
 * Export / Data Portability page.
 * Allows the user to export their academic data as CSV using the
 * authenticated API client.
 */
import { useState } from "react";
import { Download, FileText, BookOpen, FlaskConical, UsersRound, Calendar, Award, Loader2 } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { api } from "@/lib/api/client";

interface ExportOption {
  id: string;
  label: string;
  description: string;
  icon: typeof FileText;
  endpoint: string;
}

const EXPORT_OPTIONS: ExportOption[] = [
  { id: "documents", label: "All Documents", description: "Export all document metadata (title, type, tags, status, dates)", icon: FileText, endpoint: "/documents" },
  { id: "publications", label: "Publications", description: "Export publication records", icon: BookOpen, endpoint: "/publications" },
  { id: "research", label: "Research Projects", description: "Export research project and grant records", icon: FlaskConical, endpoint: "/research" },
  { id: "faculty", label: "Faculty Records", description: "Export faculty profile data", icon: UsersRound, endpoint: "/faculty" },
  { id: "events", label: "Events & Conferences", description: "Export event and conference records", icon: Calendar, endpoint: "/events" },
  { id: "objects", label: "All Objects", description: "Export all academic objects (comprehensive)", icon: Award, endpoint: "/objects" },
];

function downloadCsv(data: Record<string, unknown>[], filename: string) {
  if (data.length === 0) return;
  const headers = Object.keys(data[0]);
  const csvRows = [
    headers.join(","),
    ...data.map((item) =>
      headers.map((h) => {
        const val = item[h];
        if (val === null || val === undefined) return "";
        const str = String(val);
        return str.includes(",") || str.includes('"') || str.includes("\n")
          ? `"${str.replace(/"/g, '""')}"` : str;
      }).join(",")
    ),
  ];
  const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function ExportPage() {
  const [exporting, setExporting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async (option: ExportOption) => {
    setExporting(option.id);
    setError(null);
    try {
      const data = await api.get<{ items?: Record<string, unknown>[] }>(option.endpoint, {
        query: { page_size: 500 },
      });
      const items = data.items ?? [];
      if (items.length === 0) {
        setError(`No ${option.label.toLowerCase()} found to export.`);
        return;
      }
      downloadCsv(items, `academicos_${option.id}_export.csv`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Settings", href: "/settings" }, { label: "Export" }]} />

          <div className="mt-4 max-w-2xl">
            <h1 className="text-xl font-semibold text-[var(--text-primary)]">Export Your Data</h1>
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">
              Download your academic data as CSV files. Your original uploaded documents are stored separately and can be accessed from the Documents page.
            </p>

            {error && (
              <p className="mt-4 rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">{error}</p>
            )}

            <div className="mt-6 space-y-3">
              {EXPORT_OPTIONS.map((option) => {
                const Icon = option.icon;
                const isExporting = exporting === option.id;
                return (
                  <div key={option.id} className="flex items-center gap-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--accent-subtle)] text-[var(--accent)]">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-[var(--text-primary)]">{option.label}</p>
                      <p className="text-xs text-[var(--text-tertiary)]">{option.description}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleExport(option)}
                      disabled={isExporting}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
                    >
                      {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                      {isExporting ? "Exporting..." : "Export CSV"}
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="mt-6 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">About Data Export</h2>
              <ul className="mt-2 space-y-1 text-xs text-[var(--text-tertiary)]">
                <li>• Exports include all records you have access to</li>
                <li>• Original uploaded files are stored separately and can be downloaded individually from the Documents page</li>
                <li>• AI-generated metadata is included where available</li>
                <li>• No secrets or passwords are included in exports</li>
              </ul>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
