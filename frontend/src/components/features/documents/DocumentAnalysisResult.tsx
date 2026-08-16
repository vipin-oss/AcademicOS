"use client";

/**
 * Document-intelligence result panel (ADR-068, enhanced Revision #7).
 *
 * Renders the compact post-upload analysis the user sees after uploading a
 * document: detected type + confidence, extracted fields with source and
 * confidence, enrichment status, and which actual domain records were created.
 * Reuses the app design tokens.
 */
import { Loader2, CheckCircle2, AlertCircle, Clock, RefreshCw, Sparkles } from "lucide-react";

import type {
  DocumentAnalysisField,
  DocumentAnalysisResponse,
  FieldConfidence,
} from "@/lib/api/documentIntake";

export interface DocumentAnalysisResultProps {
  analysis: DocumentAnalysisResponse | null;
  analyzing: boolean;
  fileName?: string;
  onRetryEnrichment?: () => void;
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

function confidenceLabel(confidence: number): string {
  if (confidence >= 0.9) return "High";
  if (confidence >= 0.75) return "Medium";
  return "Low";
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.9) return "text-emerald-600";
  if (confidence >= 0.75) return "text-amber-600";
  return "text-red-600";
}

function sourceLabel(source: string): string {
  switch (source) {
    case "label": return "Extracted";
    case "regex": return "Extracted";
    case "prose": return "Extracted";
    case "ai": return "AI";
    case "agreement": return "Confirmed";
    default: return source;
  }
}

function sourceIcon(source: string) {
  if (source === "ai") return <Sparkles className="h-3 w-3 text-purple-500" />;
  if (source === "agreement") return <CheckCircle2 className="h-3 w-3 text-emerald-500" />;
  return null;
}

function EnrichmentStatus({ status, timestamp, onRetry }: {
  status: string;
  timestamp?: string | null;
  onRetry?: () => void;
}) {
  const statusConfig: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
    not_started: { icon: <Clock className="h-4 w-4" />, label: "AI analysis pending", color: "text-[var(--text-tertiary)]" },
    running: { icon: <Loader2 className="h-4 w-4 animate-spin" />, label: "AI is analyzing…", color: "text-[var(--accent)]" },
    completed: { icon: <CheckCircle2 className="h-4 w-4" />, label: "AI analysis complete", color: "text-emerald-600" },
    failed: { icon: <AlertCircle className="h-4 w-4" />, label: "AI analysis failed", color: "text-[var(--danger)]" },
    skipped: { icon: <Clock className="h-4 w-4" />, label: "AI analysis skipped", color: "text-[var(--text-tertiary)]" },
  };

  const config = statusConfig[status] ?? statusConfig.not_started;

  return (
    <div className="flex items-center justify-between rounded-lg bg-[var(--bg-hover)] px-3 py-2">
      <div className="flex items-center gap-2">
        <span className={config.color}>{config.icon}</span>
        <span className="text-xs font-medium text-[var(--text-secondary)]">{config.label}</span>
      </div>
      {status === "failed" && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-[var(--accent)] hover:bg-[var(--bg-surface)]"
        >
          <RefreshCw className="h-3 w-3" /> Retry
        </button>
      )}
    </div>
  );
}

function FieldConfidenceRow({ field }: { field: FieldConfidence }) {
  const statusConfig: Record<string, { label: string; color: string }> = {
    auto_applied: { label: "Applied", color: "bg-emerald-100 text-emerald-700" },
    proposed: { label: "Suggested", color: "bg-amber-100 text-amber-700" },
    review_required: { label: "Review", color: "bg-red-100 text-red-700" },
    conflict: { label: "Conflict", color: "bg-red-100 text-red-700" },
  };

  const config = statusConfig[field.status] ?? statusConfig.proposed;

  return (
    <div className="flex items-center justify-between py-1">
      <div className="flex items-center gap-2 min-w-0">
        {sourceIcon(field.source)}
        <span className="truncate text-xs text-[var(--text-primary)]">
          {field.field_name.replace(/_/g, " ")}
        </span>
        <span className="text-xs text-[var(--text-tertiary)]">
          {sourceLabel(field.source)}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className={`text-xs font-medium ${confidenceColor(field.confidence)}`}>
          {confidenceLabel(field.confidence)}
        </span>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${config.color}`}>
          {config.label}
        </span>
      </div>
    </div>
  );
}

export function DocumentAnalysisResult({
  analysis,
  analyzing,
  fileName,
  onRetryEnrichment,
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
  const aiAssisted = analysis.extraction_mode === "ai_assisted";
  const targetLabel = MODULE_LABELS[analysis.target_module] ?? analysis.target_module;

  return (
    <div className="space-y-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--text-primary)]">Document analyzed</span>
        {fileName ? (
          <span className="text-xs text-[var(--text-tertiary)]">Source: {fileName}</span>
        ) : null}
      </div>

      {/* Document type and confidence */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--text-secondary)]">
        <div>
          <span className="text-[var(--text-tertiary)]">Type: </span>
          <span className="capitalize">{typeLabel(analysis.document_type_id)}</span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">Confidence: </span>
          <span className={confidenceColor(analysis.confidence)}>
            {Math.round(analysis.confidence * 100)}%
          </span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">Extraction: </span>
          <span>{aiAssisted ? "AI-assisted" : "Deterministic"}</span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">Status: </span>
          <span>{status}</span>
        </div>
        <div className="col-span-2">
          <span className="text-[var(--text-tertiary)]">Target: </span>
          <span>{targetLabel}</span>
        </div>
      </div>

      {/* AI Enrichment Status */}
      {analysis.enrichment_status && analysis.enrichment_status !== "not_started" && (
        <EnrichmentStatus
          status={analysis.enrichment_status}
          timestamp={analysis.enrichment_timestamp}
          onRetry={onRetryEnrichment}
        />
      )}

      {/* Field-level confidence */}
      {analysis.field_confidence && analysis.field_confidence.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--text-tertiary)] mb-1">
            Extracted information:
          </div>
          <div className="divide-y divide-[var(--border-subtle)]">
            {analysis.field_confidence.slice(0, 8).map((f) => (
              <FieldConfidenceRow key={f.predicate_id} field={f} />
            ))}
            {analysis.field_confidence.length > 8 && (
              <div className="pt-1 text-xs text-[var(--text-tertiary)]">
                +{analysis.field_confidence.length - 8} more
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fallback: show fields without confidence if field_confidence not available */}
      {(!analysis.field_confidence || analysis.field_confidence.length === 0) && analysis.fields.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--text-tertiary)] mb-1">
            Detected information:
          </div>
          <ul className="space-y-0.5 text-[var(--text-secondary)]">
            {analysis.fields.slice(0, 8).map((f) => (
              <li key={f.predicate_id} className="truncate">
                <span className="capitalize">{fieldLabel(f)}</span>: {String(f.value)}
                {f.extractor === "ai" ? (
                  <span className="ml-1 rounded bg-purple-100 px-1 text-[10px] text-purple-700">
                    AI
                  </span>
                ) : null}
              </li>
            ))}
            {analysis.fields.length > 8 && (
              <li className="text-[var(--text-tertiary)]">
                +{analysis.fields.length - 8} more
              </li>
            )}
          </ul>
        </div>
      )}

      {/* Records created */}
      {created.length > 0 && (
        <div className="text-[var(--text-secondary)]">
          <span className="text-[var(--text-tertiary)]">Records detected: </span>
          {created.length}
          <span className="ml-1 text-[var(--text-tertiary)]">
            ({created.map((r) => MODULE_LABELS[r.module] ?? r.module).join(", ")})
          </span>
        </div>
      )}

      {/* Duplicates */}
      {duplicates.length > 0 && (
        <div className="text-[var(--text-secondary)]">
          Existing record matched — no duplicate created.
        </div>
      )}

      {/* Conflicts */}
      {analysis.conflicts && analysis.conflicts.length > 0 && (
        <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs">
          <div className="font-medium text-red-800 mb-1">Conflicts detected:</div>
          {analysis.conflicts.map((c, i) => (
            <div key={i} className="text-red-700">
              {c.predicate_id.replace(/_/g, " ")}: existing "{String(c.existing_value)}" vs extracted "{String(c.extracted_value)}"
            </div>
          ))}
        </div>
      )}

      {/* Review required */}
      {analysis.review_required && analysis.conflicts?.length === 0 && created.length === 0 && (
        <div className="rounded bg-amber-50 border border-amber-200 px-2 py-1 text-xs text-amber-800">
          Review required before saving structured data.
        </div>
      )}
    </div>
  );
}
