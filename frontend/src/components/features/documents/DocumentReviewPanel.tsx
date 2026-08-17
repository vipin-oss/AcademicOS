"use client";

/**
 * DocumentReviewPanel — unified, document-centric review experience.
 *
 * Shows what AcademicOS understood about a document, grouped into:
 *   - Already confirmed (no action needed)
 *   - Needs your confirmation (proposed / review_required)
 *   - Conflicts (different from existing)
 *   - Missing (not found, can add)
 *   - Entity matches (possible related documents)
 *
 * Professor can Confirm / Edit / Not applicable for each field.
 */

import { useCallback, useMemo, useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  HelpCircle,
  FileText,
  Link2,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import type {
  DocumentAnalysisResponse,
  FieldConfidence,
} from "@/lib/api/documentIntake";
import {
  ReviewItem,
  type ReviewItemField,
} from "./ReviewItem";
import { EntityMatchReview } from "./EntityMatchReview";
import { ConflictResolution } from "./ConflictResolution";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface DocumentReviewPanelProps {
  analysis: DocumentAnalysisResponse;
  documentId: string;
  documentTitle?: string;
  /** Called when any review action completes */
  onReviewChanged?: () => void;
}

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const MODULE_LABELS: Record<string, string> = {
  research: "Research Project",
  publications: "Publication",
  faculty: "Faculty",
  teaching: "Teaching",
  committees: "Committee",
  events: "Event",
  students: "Student",
  finance: "Finance",
  general_document: "Document",
};

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
    start_date: "Start Date",
    end_date: "End Date",
    organizer: "Organizer",
  };
  return map[predicateId] ?? predicateId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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

function sourceFriendly(source: string): string {
  switch (source) {
    case "label": return "Found near a label";
    case "regex": return "Matched a known pattern";
    case "prose": return "Extracted from text";
    case "ai": return "AI suggestion";
    case "agreement": return "Previously confirmed";
    default: return source;
  }
}

/* ------------------------------------------------------------------ */
/* Collapsible Section                                                 */
/* ------------------------------------------------------------------ */

function Section({
  title,
  count,
  icon,
  defaultOpen = true,
  children,
}: {
  title: string;
  count: number;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (count === 0) return null;
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left hover:bg-[var(--bg-hover)] transition-colors"
      >
        {icon}
        <span className="text-sm font-semibold text-[var(--text-primary)]">{title}</span>
        <span className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
          {count}
        </span>
        <span className="ml-auto">
          {open ? <ChevronDown className="h-4 w-4 text-[var(--text-tertiary)]" /> : <ChevronRight className="h-4 w-4 text-[var(--text-tertiary)]" />}
        </span>
      </button>
      {open && <div className="border-t border-[var(--border-subtle)] p-3 space-y-3">{children}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export function DocumentReviewPanel({
  analysis,
  documentId,
  documentTitle,
  onReviewChanged,
}: DocumentReviewPanelProps) {
  const [resolvedFields, setResolvedFields] = useState<Set<string>>(new Set());

  const handleResolved = useCallback(
    (predicateId: string, _action: string) => {
      setResolvedFields((prev) => new Set(prev).add(predicateId));
      onReviewChanged?.();
    },
    [onReviewChanged],
  );

  // Categorize fields
  const categorized = useMemo(() => {
    const fields = analysis.field_confidence ?? [];
    const conflictPreds = new Set(analysis.conflicts?.map((c) => c.predicate_id) ?? []);
    const conflictMap = new Map(
      (analysis.conflicts ?? []).map((c) => [c.predicate_id, c]),
    );

    const confirmed: ReviewItemField[] = [];
    const needsReview: ReviewItemField[] = [];
    const conflicts: { field: ReviewItemField; existing: string; extracted: string }[] = [];

    for (const f of fields) {
      if (resolvedFields.has(f.predicate_id)) continue;
      if (f.status === "auto_applied") {
        confirmed.push(f);
      } else if (conflictPreds.has(f.predicate_id)) {
        const c = conflictMap.get(f.predicate_id)!;
        conflicts.push({
          field: f,
          existing: String(c.existing_value),
          extracted: String(c.extracted_value),
        });
      } else {
        needsReview.push(f);
      }
    }
    return { confirmed, needsReview, conflicts };
  }, [analysis, resolvedFields]);

  const targetLabel = analysis.target_record_label
    || MODULE_LABELS[analysis.target_module]
    || analysis.target_module;

  // Review complete?
  const isReviewComplete =
    categorized.needsReview.length === 0 && categorized.conflicts.length === 0;

  // Build routing outcome message
  const created = analysis.routing?.filter((r) => r.kind === "created") ?? [];
  const duplicates = analysis.routing?.filter((r) => r.kind === "duplicate") ?? [];

  return (
    <div className="space-y-4">
      {/* Document understanding summary */}
      <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="h-5 w-5 text-[var(--accent)]" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              What AcademicOS understood
            </h3>
            {documentTitle && (
              <p className="text-xs text-[var(--text-tertiary)]">{documentTitle}</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <div>
            <span className="text-[var(--text-tertiary)]">Document type: </span>
            <span className="font-medium capitalize">
              {(analysis.document_type_id ?? "unknown").replace(/_/g, " ")}
            </span>
          </div>
          <div>
            <span className="text-[var(--text-tertiary)]">Confidence: </span>
            <span className={`font-medium ${confidenceColor(analysis.confidence)}`}>
              {confidenceLabel(analysis.confidence)}
            </span>
          </div>
          <div>
            <span className="text-[var(--text-tertiary)]">Category: </span>
            <span className="font-medium">
              {MODULE_LABELS[analysis.target_module] ?? analysis.target_module}
            </span>
          </div>
          {targetLabel && (
            <div>
              <span className="text-[var(--text-tertiary)]">Will become: </span>
              <span className="font-medium text-[var(--accent)]">{targetLabel}</span>
            </div>
          )}
          {analysis.extraction_mode === "ai_assisted" && (
            <div className="col-span-2 flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-purple-500" />
              <span className="text-xs text-purple-700">AI-assisted extraction</span>
            </div>
          )}
        </div>

        {/* Routing outcome */}
        {created.length > 0 && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            {targetLabel} created from this document.
          </div>
        )}
        {duplicates.length > 0 && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800">
            <CheckCircle2 className="h-4 w-4 text-blue-600 shrink-0" />
            Matched an existing record — no duplicate created.
          </div>
        )}
      </div>

      {/* Review complete message */}
      {isReviewComplete && (categorized.confirmed.length > 0 || resolvedFields.size > 0) && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <div>
              <p className="text-sm font-semibold text-emerald-900">Review complete</p>
              <p className="text-xs text-emerald-700">
                Your document information has been saved.
                {created.length > 0 && ` ${targetLabel} has been created.`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Needs your confirmation */}
      <Section
        title="Needs your confirmation"
        count={categorized.needsReview.length}
        icon={<AlertCircle className="h-4 w-4 text-amber-600" />}
        defaultOpen={true}
      >
        {categorized.needsReview.map((f) => (
          <ReviewItem
            key={f.predicate_id}
            field={f}
            showActions={true}
            targetRecordLabel={targetLabel}
            onResolved={handleResolved}
          />
        ))}
      </Section>

      {/* Conflicts */}
      {categorized.conflicts.length > 0 && (
        <Section
          title="Conflicting information"
          count={categorized.conflicts.length}
          icon={<AlertTriangle className="h-4 w-4 text-red-600" />}
          defaultOpen={true}
        >
          <ConflictResolution
            conflicts={categorized.conflicts.map((c) => ({
              predicate_id: c.field.predicate_id,
              existing_claim_id: "", // Will be resolved by the component
              existing_value: c.existing,
              extracted_value: c.extracted,
            }))}
            documentId={documentId}
            onResolved={onReviewChanged}
          />
        </Section>
      )}

      {/* Already confirmed — collapsed by default */}
      <Section
        title="Already confirmed"
        count={categorized.confirmed.length}
        icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />}
        defaultOpen={false}
      >
        <div className="divide-y divide-[var(--border-subtle)]">
          {categorized.confirmed.map((f) => (
            <div key={f.predicate_id} className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2 min-w-0">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                <span className="text-xs text-[var(--text-primary)] truncate">
                  {friendlyFieldName(f.predicate_id)}
                </span>
                <span className="text-xs text-[var(--text-tertiary)]">
                  {sourceFriendly(f.source)}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-xs text-[var(--text-secondary)] truncate max-w-[200px]">
                  {f.value}
                </span>
                <span className="text-[10px] font-medium text-emerald-600">Auto-applied</span>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Entity matches */}
      {analysis.entity_matches && analysis.entity_matches.length > 0 && (
        <EntityMatchReview
          documentId={documentId}
          documentTitle={documentTitle}
          onMatchResolved={onReviewChanged}
        />
      )}
    </div>
  );
}
