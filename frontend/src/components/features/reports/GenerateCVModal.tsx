"use client";

/**
 * GenerateCVModal — lets professors generate their Academic CV.
 * 
 * Options:
 * - Format: PDF, CSV, XLSX
 * - Year filter (optional)
 * 
 * Downloads the CV directly.
 */

import { useState } from "react";
import { X, Download, FileText, Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface GenerateCVModalProps {
  open: boolean;
  onClose: () => void;
}

const FORMATS = [
  { value: "pdf", label: "PDF", description: "Print-ready document" },
  { value: "xlsx", label: "Excel", description: "Spreadsheet with sections" },
  { value: "csv", label: "CSV", description: "Plain text data" },
];

export function GenerateCVModal({ open, onClose }: GenerateCVModalProps) {
  const [format, setFormat] = useState("pdf");
  const [year, setYear] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("format", format);
      if (year.trim()) params.set("year", year.trim());

      const response = await fetch(`/api/v1/reports/academic-cv/export?${params.toString()}`, {
        credentials: "include",
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Failed to generate CV");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `academic-cv.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate CV");
    } finally {
      setGenerating(false);
    }
  };

  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 6 }, (_, i) => String(currentYear - i));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-md rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-600" />
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Generate Academic CV</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 hover:bg-[var(--bg-hover)]">
            <X className="h-5 w-5 text-[var(--text-tertiary)]" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-5 px-5 py-5">
          <p className="text-sm text-[var(--text-secondary)]">
            Generate a comprehensive CV from all your confirmed academic records — publications, conferences, research, teaching, committees, and more.
          </p>

          {/* Format selection */}
          <div>
            <label className="mb-2 block text-sm font-medium text-[var(--text-primary)]">Format</label>
            <div className="grid grid-cols-3 gap-2">
              {FORMATS.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() => setFormat(f.value)}
                  className={cn(
                    "flex flex-col items-center gap-1 rounded-lg border p-3 text-center transition-colors",
                    format === f.value
                      ? "border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]"
                      : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]",
                  )}
                >
                  <FileText className="h-5 w-5" />
                  <span className="text-sm font-medium">{f.label}</span>
                  <span className="text-[10px] text-[var(--text-tertiary)]">{f.description}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Year filter */}
          <div>
            <label className="mb-2 block text-sm font-medium text-[var(--text-primary)]">
              Year Filter <span className="text-[var(--text-tertiary)]">(optional)</span>
            </label>
            <select
              value={year}
              onChange={(e) => setYear(e.target.value)}
              className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none"
            >
              <option value="">All years</option>
              {yearOptions.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {error && (
            <p className="rounded-lg border border-[var(--danger-subtle)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-[var(--border-subtle)] px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={generating}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            {generating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Generate CV
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
