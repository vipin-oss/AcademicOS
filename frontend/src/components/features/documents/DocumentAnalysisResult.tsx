"use client";

/**
 * Document-intelligence result panel (ADR-068).
 *
 * Renders the compact post-upload analysis the user sees after uploading a
 * PDF: detected type + confidence, extracted fields, target module, duplicate/
 * conflict/review status, and which actual domain records were created (or
 * fell back to claim-only). Reuses the app design tokens.
 */
import { Loader2 } from "lucide-react";

import type {
  DocumentAnalysisField,
  DocumentAnalysisResponse,
} from "@/lib/api/documentIntake";

export interface DocumentAnalysisResultProps {
  analysis: DocumentAnalysisResponse | null;
  analyzing: boolean;
  fileName?: string;
}

const MODULE_LABELS: Record<string, string> = {
  research: "Research",
  publications: "Publications",
  faculty: "Faculty",
  teaching: "Teaching",
  committees: "Committees",
  events: "Events",
  students: "Students",
  finance: "Finance",
  general_document: "Documents",
};

function typeLabel(typeId: string | null): string {
  if (!typeId) return "Unknown";
  return typeId.replace(/_/g, " ");
}

function fieldLabel(field: DocumentAnalysisField): string {
  return field.predicate_id.replace(/_/g, " ");
}

export function DocumentAnalysisResult({
  analysis,
  analyzing,
  fileName,
}: DocumentAnalysisResultProps) {
  if (analyzing) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
        <Loader2 className="h-4 w-4 animate-spin" />
        Analyzing document…
      </div>
    );
  }

  if (!analysis) return null;

  const created = analysis.routing.filter((r) => r.kind === "created");
  const duplicates = analysis.routing.filter((r) => r.kind === "duplicate");
  const status = analysis.review_required ? "Review required" : "Ready";

  return (
    <div className="space-y-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--text-primary)]">Document analyzed</span>
        {fileName ? (
          <span className="text-xs text-[var(--text-tertiary)]">Source: {fileName}</span>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--text-secondary)]">
        <div>
          <span className="text-[var(--text-tertiary)]">Type: </span>
          <span className="capitalize">{typeLabel(analysis.document_type_id)}</span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">Confidence: </span>
          <span>{Math.round(analysis.confidence * 100)}%</span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">Target: </span>
          <span>{MODULE_LABELS[analysis.target_module] ?? analysis.target_module}</span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">Status: </span>
          <span>{status}</span>
        </div>
      </div>

      {analysis.fields.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--text-tertiary)]">
            Detected information:
          </div>
          <ul className="mt-1 space-y-0.5 text-[var(--text-secondary)]">
            {analysis.fields.slice(0, 8).map((f) => (
              <li key={f.predicate_id} className="truncate">
                <span className="capitalize">{fieldLabel(f)}</span>: {String(f.value)}
              </li>
            ))}
            {analysis.fields.length > 8 ? (
              <li className="text-[var(--text-tertiary)]">
                +{analysis.fields.length - 8} more
              </li>
            ) : null}
          </ul>
        </div>
      )}

      {created.length > 0 && (
        <div className="text-[var(--text-secondary)]">
          <span className="text-[var(--text-tertiary)]">Records detected: </span>
          {created.length}
          <span className="ml-1 text-[var(--text-tertiary)]">
            ({created.map((r) => MODULE_LABELS[r.module] ?? r.module).join(", ")})
          </span>
        </div>
      )}

      {duplicates.length > 0 && (
        <div className="text-[var(--text-secondary)]">
          Existing record matched — no duplicate created.
        </div>
      )}

      {analysis.conflicts.length > 0 && (
        <div className="rounded bg-[var(--bg-hover)] px-2 py-1 text-[var(--text-secondary)]">
          Review required: {analysis.conflicts.length} conflicting value(s) found.
        </div>
      )}

      {analysis.review_required && analysis.conflicts.length === 0 && created.length === 0 && (
        <div className="rounded bg-[var(--bg-hover)] px-2 py-1 text-[var(--text-secondary)]">
          Review required before saving structured data.
        </div>
      )}
    </div>
  );
}
