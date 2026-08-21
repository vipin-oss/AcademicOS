"use client";

/**
 * PendingReviewSection — shows pending review fields grouped by entity.
 *
 * Instead of showing 10 individual claims, groups them into entity cards:
 * - "Conference: Workshop on AI" → Confirm All (1 click)
 * - "Publication: Paper Title" → Confirm All (1 click)
 *
 * Low-confidence items (<80%) are highlighted for individual review.
 * High-confidence items can be confirmed in bulk.
 */

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  XCircle,
  Edit3,
  Loader2,
  ChevronDown,
  ChevronRight,
  Sparkles,
  Calendar,
  BookOpen,
  FlaskConical,
  Users,
  FileText,
} from "lucide-react";
import { api } from "@/lib/api/client";
import type { PendingReviewItemResponse } from "@/lib/api/documentIntake";
import { friendlyFieldName } from "@/lib/fieldLabels";
import { cn } from "@/lib/utils";

function confidenceDot(c: number | null): { color: string; label: string } {
  if (c === null) return { color: "bg-gray-300", label: "" };
  if (c >= 0.9) return { color: "bg-emerald-500", label: "High" };
  if (c >= 0.75) return { color: "bg-amber-500", label: "Medium" };
  return { color: "bg-red-500", label: "Low" };
}

// Map predicate_ids to entity groups
const ENTITY_GROUPS: Record<string, { label: string; icon: typeof FileText; color: string }> = {
  conference_name: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  event_title: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  start_date: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  end_date: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  venue: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  city: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  country: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  organizer: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  participation_type: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  presentation_title: { label: "Conference / Event", icon: Calendar, color: "text-purple-600 bg-purple-50 border-purple-200" },
  publication_title: { label: "Publication", icon: BookOpen, color: "text-blue-600 bg-blue-50 border-blue-200" },
  journal_name: { label: "Publication", icon: BookOpen, color: "text-blue-600 bg-blue-50 border-blue-200" },
  publication_year: { label: "Publication", icon: BookOpen, color: "text-blue-600 bg-blue-50 border-blue-200" },
  authors: { label: "Publication", icon: BookOpen, color: "text-blue-600 bg-blue-50 border-blue-200" },
  doi: { label: "Publication", icon: BookOpen, color: "text-blue-600 bg-blue-50 border-blue-200" },
  project_title: { label: "Research / Grant", icon: FlaskConical, color: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  funding_agency: { label: "Research / Grant", icon: FlaskConical, color: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  sanctioned_amount: { label: "Research / Grant", icon: FlaskConical, color: "text-emerald-600 bg-emerald-50 border-emerald-200" },
  committee_name: { label: "Committee", icon: Users, color: "text-amber-600 bg-amber-50 border-amber-200" },
  committee_role: { label: "Committee", icon: Users, color: "text-amber-600 bg-amber-50 border-amber-200" },
};

function getEntityGroup(predicateId: string): { label: string; icon: typeof FileText; color: string } {
  return ENTITY_GROUPS[predicateId] ?? { label: "Other Details", icon: FileText, color: "text-gray-600 bg-gray-50 border-gray-200" };
}

interface EntityGroup {
  key: string;
  label: string;
  icon: typeof FileText;
  color: string;
  items: PendingReviewItemResponse[];
  allHighConfidence: boolean;
}

function ReviewItemRow({
  item,
  onResolved,
}: {
  item: PendingReviewItemResponse;
  onResolved: (claimId: string) => void;
}) {
  const [acting, setActing] = useState(false);
  const [resolved, setResolved] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(item.display_value);

  const conf = confidenceDot(item.confidence);
  const hasValue = item.display_value && item.display_value.trim() !== "";
  const fieldName = friendlyFieldName(item.predicate_id);
  const isLowConfidence = (item.confidence ?? 1) < 0.8;

  const handleConfirm = useCallback(async () => {
    setActing(true);
    try {
      await api.post(`/confirmations/${item.claim_id}/approve`, {});
      setResolved(true);
      onResolved(item.claim_id);
    } catch { /* ignore */ } finally { setActing(false); }
  }, [item.claim_id, onResolved]);

  const handleReject = useCallback(async () => {
    setActing(true);
    try {
      await api.post(`/confirmations/${item.claim_id}/reject`, {});
      setResolved(true);
      onResolved(item.claim_id);
    } catch { /* ignore */ } finally { setActing(false); }
  }, [item.claim_id, onResolved]);

  const handleEditSave = useCallback(async () => {
    if (!editValue.trim()) return;
    setActing(true);
    try {
      await api.post(`/confirmations/${item.claim_id}/correct`, {
        raw_value: editValue.trim(),
        notes: "Manual correction",
      });
      setEditing(false);
      setResolved(true);
      onResolved(item.claim_id);
    } catch { /* ignore */ } finally { setActing(false); }
  }, [item.claim_id, editValue, onResolved]);

  if (resolved) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-emerald-700">
        <CheckCircle2 className="h-3 w-3" />
        <span>{fieldName} saved</span>
      </div>
    );
  }

  return (
    <div className={cn(
      "group flex items-center gap-3 px-3 py-2 transition-colors hover:bg-[var(--bg-hover)]",
      isLowConfidence && "bg-red-50/50",
    )}>
      {/* Confidence + Field name */}
      <div className="flex items-center gap-1.5 min-w-[140px]">
        <span className={cn("h-2 w-2 rounded-full", conf.color)} title={`${conf.label} confidence`} />
        <span className="text-sm font-medium text-[var(--text-primary)]">{fieldName}</span>
        {item.status === "auto_suggested" && <Sparkles className="h-3 w-3 text-blue-400" />}
      </div>

      {/* Value */}
      <div className="flex-1 min-w-0">
        {editing ? (
          <div className="flex gap-1.5">
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="flex-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleEditSave();
                if (e.key === "Escape") { setEditing(false); setEditValue(item.display_value); }
              }}
              autoFocus
            />
            <button type="button" onClick={() => void handleEditSave()} disabled={acting}
              className="rounded bg-[var(--accent)] px-2 py-1 text-xs text-white disabled:opacity-50">Save</button>
            <button type="button" onClick={() => { setEditing(false); setEditValue(item.display_value); }}
              className="rounded border border-[var(--border-subtle)] px-2 py-1 text-xs">Cancel</button>
          </div>
        ) : hasValue ? (
          <span className="text-sm text-[var(--text-primary)] truncate block">{item.display_value}</span>
        ) : (
          <span className="text-sm text-[var(--text-tertiary)] italic">Not found</span>
        )}
      </div>

      {/* Source evidence */}
      {hasValue && item.source_text && item.source_text.trim() !== "" && !editing && (
        <span className="text-[11px] text-blue-600 font-mono truncate max-w-[150px] hidden sm:block" title={item.source_text}>
          &ldquo;{item.source_text.length > 40 ? item.source_text.slice(0, 40) + "..." : item.source_text}&rdquo;
        </span>
      )}

      {/* Actions */}
      {!editing && (
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button type="button" onClick={() => void handleConfirm()} disabled={acting}
            className="rounded-md bg-emerald-100 p-1.5 text-emerald-700 hover:bg-emerald-200 disabled:opacity-50" title="Confirm">
            <CheckCircle2 className="h-3.5 w-3.5" />
          </button>
          <button type="button" onClick={() => { setEditing(true); setEditValue(item.display_value); }} disabled={acting}
            className="rounded-md bg-[var(--bg-hover)] p-1.5 text-[var(--text-secondary)] hover:bg-[var(--border-subtle)] disabled:opacity-50" title="Edit">
            <Edit3 className="h-3.5 w-3.5" />
          </button>
          <button type="button" onClick={() => void handleReject()} disabled={acting}
            className="rounded-md bg-red-50 p-1.5 text-red-600 hover:bg-red-100 disabled:opacity-50" title="Not applicable">
            <XCircle className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

function EntityGroupCard({
  group,
  onResolved,
}: {
  group: EntityGroup;
  onResolved: (claimId: string) => void;
}) {
  // Expand groups that have low-confidence items (need review), collapse high-confidence groups
  const [expanded, setExpanded] = useState(!group.allHighConfidence);
  const [confirmingGroup, setConfirmingGroup] = useState(false);
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());

  const pendingInGroup = group.items.filter((item) => !resolvedIds.has(item.claim_id));
  if (pendingInGroup.length === 0) return null;

  const Icon = group.icon;
  const lowConfCount = pendingInGroup.filter((i) => (i.confidence ?? 1) < 0.8).length;

  const handleConfirmGroup = useCallback(async () => {
    setConfirmingGroup(true);
    try {
      const ids = pendingInGroup.map((i) => i.claim_id);
      await Promise.all(ids.map((id) => api.post(`/confirmations/${id}/approve`, {})));
      setResolvedIds((prev) => {
        const next = new Set(prev);
        ids.forEach((id) => next.add(id));
        return next;
      });
      ids.forEach((id) => onResolved(id));
    } catch { /* ignore */ } finally { setConfirmingGroup(false); }
  }, [pendingInGroup, onResolved]);

  return (
    <div className={cn("rounded-lg border", group.color.split(" ").slice(1).join(" "))}>
      {/* Entity group header */}
      <div className="flex items-center justify-between px-4 py-3">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 min-w-0 flex-1 text-left"
        >
          <Icon className={cn("h-4 w-4 shrink-0", group.color.split(" ")[0])} />
          <span className="text-sm font-semibold text-[var(--text-primary)]">{group.label}</span>
          <span className="rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-tertiary)]">
            {pendingInGroup.length} {pendingInGroup.length === 1 ? "field" : "fields"}
          </span>
          {lowConfCount > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-700">
              {lowConfCount} needs review
            </span>
          )}
          {expanded ? <ChevronDown className="h-4 w-4 text-[var(--text-tertiary)]" /> : <ChevronRight className="h-4 w-4 text-[var(--text-tertiary)]" />}
        </button>
        <button
          type="button"
          onClick={() => void handleConfirmGroup()}
          disabled={confirmingGroup}
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50 shrink-0 ml-2"
        >
          {confirmingGroup ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
          {confirmingGroup ? "Confirming..." : "Confirm All"}
        </button>
      </div>

      {/* Items */}
      {expanded && (
        <div className="border-t border-inherit divide-y divide-inherit">
          {pendingInGroup.map((item) => (
            <ReviewItemRow key={item.claim_id} item={item} onResolved={(id) => { setResolvedIds((prev) => new Set(prev).add(id)); onResolved(id); }} />
          ))}
        </div>
      )}
    </div>
  );
}

export interface PendingReviewSectionProps {
  documentId: string;
  documentTitle: string;
  items: PendingReviewItemResponse[];
  loading: boolean;
  onItemResolved: () => void;
}

export function PendingReviewSection({
  documentId,
  documentTitle,
  items,
  loading,
  onItemResolved,
}: PendingReviewSectionProps) {
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
  const [confirmingAll, setConfirmingAll] = useState(false);
  const [createdRecords, setCreatedRecords] = useState<Array<{ id: string; type: string; title: string }>>([]);

  const handleResolved = useCallback(
    (claimId: string) => {
      setResolvedIds((prev) => new Set(prev).add(claimId));
      onItemResolved();
    },
    [onItemResolved],
  );

  const pendingItems = items.filter((item) => !resolvedIds.has(item.claim_id));

  // Group items by entity type
  const entityGroups = useMemo(() => {
    const groupMap = new Map<string, EntityGroup>();
    for (const item of pendingItems) {
      const groupInfo = getEntityGroup(item.predicate_id);
      let group = groupMap.get(groupInfo.label);
      if (!group) {
        group = {
          key: groupInfo.label,
          label: groupInfo.label,
          icon: groupInfo.icon,
          color: groupInfo.color,
          items: [],
          allHighConfidence: true,
        };
        groupMap.set(groupInfo.label, group);
      }
      group.items.push(item);
      if ((item.confidence ?? 1) < 0.8) group.allHighConfidence = false;
    }
    return Array.from(groupMap.values());
  }, [pendingItems]);

  const handleConfirmAll = useCallback(async () => {
    setConfirmingAll(true);
    try {
      const result: any = await api.post(`/documents/${documentId}/confirm-all-high-confidence`, undefined, {
        query: { min_confidence: 0.9 },
      });
      const highConfIds = pendingItems
        .filter((item) => (item.confidence ?? 0) >= 0.9)
        .map((item) => item.claim_id);
      setResolvedIds((prev) => {
        const next = new Set(prev);
        highConfIds.forEach((id) => next.add(id));
        return next;
      });
      if (result?.records_created?.length > 0) {
        setCreatedRecords(result.records_created);
      }
      onItemResolved();
    } catch { /* silent */ } finally { setConfirmingAll(false); }
  }, [documentId, pendingItems, onItemResolved]);

  if (loading) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-amber-600" />
          <span className="text-sm text-amber-800">Loading review items...</span>
        </div>
      </div>
    );
  }

  if (pendingItems.length === 0) {
    if (resolvedIds.size > 0) {
      const TYPE_LABELS: Record<string, string> = {
        event: "Event", publication: "Publication", project: "Research Project", committee: "Committee",
      };
      const TYPE_LINKS: Record<string, string> = {
        event: "/events/", publication: "/publications/", project: "/research/projects/", committee: "/committees/",
      };
      return (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <div>
              <p className="text-sm font-semibold text-emerald-900">All reviewed</p>
              {createdRecords.length > 0 ? (
                <div className="mt-1 space-y-1">
                  {createdRecords.map((rec) => (
                    <p key={rec.id} className="text-xs text-emerald-700">
                      Recorded as {TYPE_LABELS[rec.type] ?? rec.type}:{" "}
                      <Link href={`${TYPE_LINKS[rec.type] ?? "/records/"}${encodeURIComponent(rec.id)}`}
                        className="font-semibold underline hover:text-emerald-900">
                        {rec.title || "View"}
                      </Link>
                    </p>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-emerald-700">
                  Information saved.{" "}
                  <Link href={`/documents/${encodeURIComponent(documentId)}`} className="underline hover:text-emerald-900">
                    View document
                  </Link>
                </p>
              )}
            </div>
          </div>
        </div>
      );
    }
    return null;
  }

  const highConfCount = pendingItems.filter((i) => (i.confidence ?? 0) >= 0.9).length;

  return (
    <div className="space-y-3" id="review-section">
      {/* Header */}
      <div className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <h2 className="text-sm font-semibold text-amber-900">
            {pendingItems.length} {pendingItems.length === 1 ? "field" : "fields"} need your review
          </h2>
        </div>
        {highConfCount > 0 && (
          <button type="button" onClick={() => void handleConfirmAll()} disabled={confirmingAll}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50">
            {confirmingAll ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            {confirmingAll ? "Confirming..." : `Confirm All High-Confidence (${highConfCount})`}
          </button>
        )}
      </div>

      {/* Entity group cards */}
      <div className="space-y-2">
        {entityGroups.map((group) => (
          <EntityGroupCard key={group.key} group={group} onResolved={handleResolved} />
        ))}
      </div>
    </div>
  );
}
