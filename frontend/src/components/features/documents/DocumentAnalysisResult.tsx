"use client";

/**
 * Document-intelligence result panel.
 * Shows what AcademicOS understood about a document in professor-friendly language.
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

/** Convert predicate_id to professor-friendly label */
function friendlyFieldName(predicateId: string): string {
  const map: Record<string, string> = {
    publication_title: "Title",
    publication_year: "Year",
    journal_name: "Journal",
    authors: "Authors",
    doi: "DOI",
    conference_name: "Conference",
    venue: "Venue",
    funding_agency: "Funding Agency",
    principal_investigator: "Principal Investigator",
    sanctioned_amount: "Amount",
    project_title: "Project Title",
    recipient: "Recipient",
    certificate_number: "Certificate Number",
    manuscript_id: "Manuscript ID",
    acceptance_date: "Acceptance Date",
    issuing_authority: "Issuing Authority",
    event_title: "Title",
    co_investigator: "Co-Investigator",
    project_duration_months: "Duration",
    sanction_order_number: "Sanction Number",
  };
  return map[predicateId] ?? predicateId.replace(/_/g, " ");
}

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
    <div className="flex items-center justify-between py-1">
      <div className="flex items-center gap-2 min-w-0">
        {sourceIcon(field.source)}
        <span className="truncate text-xs text-[var(--text-primary)]">
          {friendlyFieldName(field.predicate_id)}
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

      {/* Document type and confidence */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--text-secondary)]">
        <div>
          <span className="text-[var(--text-tertiary)]">Document type: </span>
          <span className="capitalize">{typeLabel(analysis.document_type_id)}</span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">Confidence: </span>
          <span className={confidenceColor(analysis.confidence)}>
            {confidenceLabel(analysis.confidence)}
          </span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">Category: </span>
          <span>{targetLabel}</span>
        </div>
        <div>
          <span className="text-[var(--text-tertiary)]">AI assistance: </span>
          <span>{aiAssisted ? "Yes" : "No"}</span>
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
          <ul className="space-y-0.5 text-[var(--text-secondary)]">
            {analysis.fields.slice(0, 8).map((f) => (
              <li key={f.predicate_id} className="truncate">
                <span className="capitalize">{friendlyFieldName(f.predicate_id)}</span>: {String(f.value)}
                {f.extractor === "ai" ? (
                  <span className="ml-1 rounded bg-purple-100 px-1 text-[10px] text-purple-700">AI</span>
                ) : null}
              </li>
            ))}
            {analysis.fields.length > 8 && (
              <li className="text-[var(--text-tertiary)]">+{analysis.fields.length - 8} more</li>
            )}
          </ul>
        </div>
      )}

      {/* Records created */}
      {created.length > 0 && (
        <div className="text-[var(--text-secondary)]">
          <span className="text-[var(--text-tertiary)]">Records created: </span>
          {created.length}
          <span className="ml-1 text-[var(--text-tertiary)]">
            ({created.map((r) => MODULE_LABELS[r.module] ?? r.module).join(", ")})
          </span>
        </div>
      )}

      {/* Duplicates */}
      {duplicates.length > 0 && (
        <div className="text-emerald-700 bg-emerald-50 rounded px-2 py-1 text-xs">
          ✓ Matched existing record — no duplicate created.
        </div>
      )}

      {/* Conflicts */}
      {analysis.conflicts && analysis.conflicts.length > 0 && (
        <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs">
          <div className="font-medium text-red-800 mb-1">Conflicting information found:</div>
          {analysis.conflicts.map((c, i) => (
            <div key={i} className="text-red-700">
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
