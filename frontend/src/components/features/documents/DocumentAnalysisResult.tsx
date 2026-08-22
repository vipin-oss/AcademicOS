"use client";

/**
 * Document-intelligence result panel.
 * Shows what AcademicOS understood about a document in professor-friendly language.
 */
import Link from "next/link";
import { Loader2, CheckCircle2, AlertCircle, Clock, RefreshCw, Sparkles } from "lucide-react";

import { ConflictResolution } from "./ConflictResolution";
import { friendlyFieldName } from "@/lib/fieldLabels";
import type {
  DocumentAnalysisField,
  DocumentAnalysisResponse,
  FieldConfidence,
} from "@/lib/api/documentIntake";

export interface DocumentAnalysisResultProps {
  analysis: DocumentAnalysisResponse | null;
  analyzing: boolean;
  fileName?: string;
  documentId?: string;
  onRetryEnrichment?: () => void;
  onConflictResolved?: () => void;
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
    case "label": return "From document";
    case "regex": return "From document";
    case "prose": return "From document";
    case "ai": return "AI suggestion";
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
    running: { icon: <Loader2 className="h-4 w-4 animate-spin" />, label: "AI is analyzing this document…", color: "text-[var(--accent)]" },
    completed: { icon: <CheckCircle2 className="h-4 w-4" />, label: "AI analysis complete", color: "text-emerald-600" },
    failed: { icon: <AlertCircle className="h-4 w-4" />, label: "AI analysis failed — your document is still safe", color: "text-[var(--danger)]" },
    skipped: { icon: <Clock className="h-4 w-4" />, label: "AI analysis not available", color: "text-[var(--text-tertiary)]" },
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
    <div className="flex items-center justify-between py-1.5">
      <div className="flex items-center gap-2 min-w-0">
        {sourceIcon(field.source)}
        <span className="truncate text-xs text-[var(--text-primary)]">
          {friendlyFieldName(field.predicate_id)}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {/* Show actual value */}
        {field.value && field.value !== "null" && field.value !== "undefined" && field.value.trim() !== "" && (
          <span className="text-xs text-[var(--text-secondary)] truncate max-w-[180px]">
            {field.value}
          </span>
        )}
        {(!field.value || field.value === "null" || field.value.trim() === "") && (
          <span className="text-xs text-[var(--text-tertiary)] italic">
            Not found
          </span>
        )}
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
  documentId,
  onRetryEnrichment,
  onConflictResolved,
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
  const aiAssisted = analysis.extraction_mode === "ai_assisted";
  const targetLabel = MODULE_LABELS[analysis.target_module] ?? analysis.target_module;

  return (
    <div className="space-y-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--text-primary)]">What AcademicOS understood</span>
        {fileName ? (
          <span className="text-xs text-[var(--text-tertiary)]">{fileName}</span>
        ) : null}
      </div>

      {/* Document type and confidence — simplified */}
      <div className="text-sm text-[var(--text-secondary)]">
        <span>This is a </span>
        <span className="font-medium text-[var(--text-primary)] capitalize">{typeLabel(analysis.document_type_id)}</span>
        <span>. AcademicOS found </span>
        <span className="font-medium text-[var(--text-primary)]">{analysis.fields.length}</span>
        <span> {analysis.fields.length === 1 ? "piece" : "pieces"} of information.</span>
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
            Detected information:
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

      {/* Fallback: show fields without confidence */}
      {(!analysis.field_confidence || analysis.field_confidence.length === 0) && analysis.fields.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--text-tertiary)] mb-1">
            Detected information:
          </div>
          <ul className="space-y-1 text-[var(--text-secondary)]">
            {analysis.fields.slice(0, 8).map((f) => (
              <li key={f.predicate_id} className="flex items-center justify-between">
                <span className="text-xs text-[var(--text-primary)]">
                  {friendlyFieldName(f.predicate_id)}
                </span>
                <span className="text-xs text-[var(--text-secondary)] truncate max-w-[200px]">
                  {String(f.value)}
                  {f.extractor === "ai" ? (
                    <span className="ml-1 rounded bg-purple-100 px-1 text-[10px] text-purple-700">AI</span>
                  ) : null}
                </span>
              </li>
            ))}
            {analysis.fields.length > 8 && (
              <li className="text-[var(--text-tertiary)]">+{analysis.fields.length - 8} more</li>
            )}
          </ul>
        </div>
      )}

      {/* Records created — professor-friendly */}
      {created.length > 0 && created.map((r) => (
        <div key={r.module} className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span className="text-sm font-semibold text-emerald-900">
              {r.module === "event" ? "Conference recorded" :
               r.module === "publication" ? "Publication recorded" :
               r.module === "project" ? "Research project recorded" :
               "Record created"}
            </span>
          </div>
          {r.object_id && (
            <div className="mt-2 flex items-center gap-2">
              <Link
                href={r.module === "event" ? `/events/${r.object_id}` :
                      r.module === "publication" ? `/publications/${r.object_id}` :
                      r.module === "project" ? `/research/projects/${r.object_id}` :
                      `/objects/${r.object_id}`}
                className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:text-emerald-900 hover:underline"
              >
                View {r.module === "event" ? "Event" : "Record"} →
              </Link>
            </div>
          )}
        </div>
      ))}

      {/* Duplicates — professor-friendly */}
      {duplicates.length > 0 && duplicates.map((r) => (
        <div key={r.existing_id} className="rounded-lg border border-blue-200 bg-blue-50 p-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-semibold text-blue-900">
              {r.module === "event" ? "Certificate linked to existing conference" :
               r.module === "publication" ? "Certificate linked to existing publication" :
               "Linked to existing record"}
            </span>
          </div>
          <p className="mt-1 text-xs text-blue-700">
            This certificate matches an existing {r.module === "event" ? "conference" : "record"}, so AcademicOS linked it instead of creating a duplicate.
          </p>
          {r.existing_id && (
            <div className="mt-2 flex items-center gap-2">
              <Link
                href={r.module === "event" ? `/events/${r.existing_id}` :
                      r.module === "publication" ? `/publications/${r.existing_id}` :
                      r.module === "project" ? `/research/projects/${r.existing_id}` :
                      `/objects/${r.existing_id}`}
                className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:text-blue-900 hover:underline"
              >
                View {r.module === "event" ? "Event" : "Record"} →
              </Link>
            </div>
          )}
        </div>
      ))}

      {/* Conflicts — interactive resolution */}
      {analysis.conflicts && analysis.conflicts.length > 0 && documentId && (
        <ConflictResolution
          conflicts={analysis.conflicts}
          documentId={documentId}
          onResolved={onConflictResolved}
        />
      )}

      {/* Conflicts — fallback display if no documentId */}
      {analysis.conflicts && analysis.conflicts.length > 0 && !documentId && (
        <div className="rounded bg-amber-50 border border-amber-200 px-3 py-2 text-xs">
          <div className="font-medium text-amber-800 mb-1">Conflicting information found:</div>
          {analysis.conflicts.map((c, i) => (
            <div key={i} className="text-amber-700">
              {friendlyFieldName(c.predicate_id)}: existing &quot;{String(c.existing_value)}&quot; vs new &quot;{String(c.extracted_value)}&quot;
            </div>
          ))}
        </div>
      )}

      {/* Review required */}
      {analysis.review_required && analysis.conflicts?.length === 0 && created.length === 0 && (
        <div className="rounded bg-amber-50 border border-amber-200 px-2 py-1 text-xs text-amber-800">
          Some information needs your review before it can be saved.
        </div>
      )}
    </div>
  );
}
