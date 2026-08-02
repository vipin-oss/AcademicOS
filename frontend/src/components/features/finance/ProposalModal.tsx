"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createProposal, updateProposal } from "@/lib/api/finance";
import type { CreateProposalPayload } from "@/lib/api/finance";
import { listFaculty } from "@/lib/api/faculty";
import { listGrants, listProjects } from "@/lib/api/research";
import { getCommittee, listCommittees } from "@/lib/api/committees";
import {
  PROPOSAL_PRIORITIES,
  PROPOSAL_STATUSES,
} from "@/lib/finance/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type {
  CommitteeMeetingSummary,
  ProposalLinkGroup,
  ProposalPriority,
  ProposalResponse,
  ProposalStatus,
  ResearchObjectStatus,
} from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

const MULTI_SELECT_CLASS = `${FIELD_CLASS} h-28`;

function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string | null;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {error ? (
        <p role="alert" className="mt-1 text-xs text-[var(--danger)]">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</p>
      ) : null}
    </label>
  );
}

interface PickerOption {
  id: string;
  label: string;
}

function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: PickerOption[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  return (
    <select
      multiple
      value={selected}
      onChange={(event) =>
        onChange(Array.from(event.target.selectedOptions).map((option) => option.value))
      }
      className={MULTI_SELECT_CLASS}
      aria-label={label}
    >
      {options.map((option) => (
        <option key={option.id} value={option.id}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export interface ProposalSaveResult {
  proposal: ProposalResponse;
  mode: "create" | "edit";
}

/**
 * Register / edit a Purchase Proposal (PART 1 record + PART 2 procurement
 * committee + research/governance links). Quotations, comparative statement,
 * purchase orders, bills and assets are maintained on the workspace sections
 * after the record exists (same contract as committee meetings).
 */
export function ProposalModal({
  open,
  onClose,
  onSaved,
  proposal,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: ProposalSaveResult) => void;
  proposal?: ProposalResponse | null;
}) {
  const mode = proposal ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [proposalNumber, setProposalNumber] = useState("");
  const [department, setDepartment] = useState("");
  const [requestedBy, setRequestedBy] = useState("");
  const [proposalDate, setProposalDate] = useState("");
  const [purpose, setPurpose] = useState("");
  const [budgetHead, setBudgetHead] = useState("");
  const [estimatedCost, setEstimatedCost] = useState("");
  const [proposalStatus, setProposalStatus] = useState<ProposalStatus>("draft");
  const [priority, setPriority] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const [minutes, setMinutes] = useState("");
  const [recommendations, setRecommendations] = useState("");
  const [approvalMeetingId, setApprovalMeetingId] = useState("");
  const [projectIds, setProjectIds] = useState<string[]>([]);
  const [grantIds, setGrantIds] = useState<string[]>([]);
  const [committeeIds, setCommitteeIds] = useState<string[]>([]);
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [status, setStatus] = useState<ResearchObjectStatus>("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  // Picker option lists (typed pickers, like CommitteeModal's link groups).
  const [facultyOptions, setFacultyOptions] = useState<PickerOption[]>([]);
  const [projectOptions, setProjectOptions] = useState<PickerOption[]>([]);
  const [grantOptions, setGrantOptions] = useState<PickerOption[]>([]);
  const [committeeOptions, setCommitteeOptions] = useState<PickerOption[]>([]);
  const [meetingOptions, setMeetingOptions] = useState<PickerOption[]>([]);

  useEffect(() => {
    if (!open) return;
    setTitle(proposal?.title ?? "");
    setProposalNumber(proposal?.proposal_number ?? "");
    setDepartment(proposal?.department ?? "");
    setRequestedBy(proposal?.requested_by ?? "");
    setProposalDate(proposal?.proposal_date ?? "");
    setPurpose(proposal?.purpose ?? "");
    setBudgetHead(proposal?.budget_head ?? "");
    setEstimatedCost(
      proposal?.estimated_cost !== null && proposal?.estimated_cost !== undefined
        ? String(proposal.estimated_cost)
        : "",
    );
    setProposalStatus(proposal?.proposal_status ?? "draft");
    setPriority(proposal?.priority ?? "");
    setNotes(proposal?.notes ?? "");
    setTags((proposal?.tags ?? []).join(", "));
    setMinutes(proposal?.minutes ?? "");
    setRecommendations(proposal?.recommendations ?? "");
    setApprovalMeetingId(proposal?.approval_meeting_id ?? "");
    setProjectIds((proposal?.links?.projects ?? []).map((link) => link.id));
    setGrantIds((proposal?.links?.grants ?? []).map((link) => link.id));
    setCommitteeIds((proposal?.links?.committees ?? []).map((link) => link.id));
    setUploadedBy(proposal?.uploaded_by ?? "faculty:ui");
    setStatus(proposal?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open, proposal]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    listFaculty({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setFacultyOptions(
          response.items.map((person) => ({ id: person.id, label: person.name })),
        ),
      )
      .catch(() => setFacultyOptions([]));
    listProjects({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setProjectOptions(
          response.items.map((project) => ({ id: project.id, label: project.title })),
        ),
      )
      .catch(() => setProjectOptions([]));
    listGrants({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setGrantOptions(response.items.map((grant) => ({ id: grant.id, label: grant.title }))),
      )
      .catch(() => setGrantOptions([]));
    listCommittees({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setCommitteeOptions(
          response.items.map((committee) => ({ id: committee.id, label: committee.name })),
        ),
      )
      .catch(() => setCommitteeOptions([]));
    return () => controller.abort();
  }, [open]);

  // PART 2: the approval-meeting picker offers the meetings of every selected
  // purchase committee (lazy one-shot fetch per selection; failures tolerated —
  // a committee that fails to load simply contributes no meetings).
  useEffect(() => {
    if (!open) return;
    if (committeeIds.length === 0) {
      setMeetingOptions([]);
      return;
    }
    const controller = new AbortController();
    Promise.all(
      committeeIds.map((id) =>
        getCommittee(id, { signal: controller.signal }).catch(() => null),
      ),
    )
      .then((committees) => {
        const options: PickerOption[] = [];
        for (const committee of committees) {
          if (!committee) continue;
          for (const meeting of committee.meetings ?? []) {
            options.push({
              id: meeting.id,
              label: meetingOptionLabel(meeting, committee.name),
            });
          }
        }
        setMeetingOptions(options);
      })
      .catch(() => setMeetingOptions([]));
    return () => controller.abort();
  }, [open, committeeIds]);

  useEffect(() => {
    if (open) firstFieldRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const handleClose = () => {
    if (submittingRef.current) return;
    onClose();
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    setFormError(null);

    if (!title.trim()) {
      setFormError("Proposal title must not be empty.");
      return;
    }
    let costValue: number | null = null;
    if (estimatedCost.trim()) {
      const parsed = Number(estimatedCost.trim());
      if (Number.isNaN(parsed) || parsed < 0) {
        setFormError("Estimated cost must be a non-negative number.");
        return;
      }
      costValue = parsed;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const splitList = (raw: string) =>
      raw
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);

    const payload: CreateProposalPayload = {
      title: title.trim(),
      uploaded_by: uploadedBy.trim() || "faculty:ui",
      status,
      proposal_number: proposalNumber.trim() || null,
      department: department.trim() || null,
      requested_by: requestedBy || null,
      proposal_date: proposalDate.trim() || null,
      purpose: purpose.trim() || null,
      budget_head: budgetHead.trim() || null,
      estimated_cost: costValue,
      proposal_status: proposalStatus,
      priority: (priority || null) as ProposalPriority | null,
      notes: notes.trim() || null,
      tags: splitList(tags),
      approval_meeting_id: approvalMeetingId || null,
      minutes: minutes.trim() || null,
      recommendations: recommendations.trim() || null,
      links: {
        projects: projectIds,
        grants: grantIds,
        committees: committeeIds,
      } as Partial<Record<ProposalLinkGroup, string[]>>,
    };

    try {
      const saved = proposal
        ? await updateProposal(proposal.id, payload)
        : await createProposal(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ proposal: saved, mode });
    } catch (err) {
      submittingRef.current = false;
      setSubmitting(false);
      setFormError(toErrorMessage(err));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) handleClose();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="proposal-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-3xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="proposal-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {mode === "edit" ? "Edit proposal" : "New purchase proposal"}
          </h2>
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Proposal title *">
              <input
                ref={firstFieldRef}
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Procurement of Laboratory Equipment"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Proposal number" hint="Unique when provided (409 on duplicates).">
              <input
                type="text"
                value={proposalNumber}
                onChange={(event) => setProposalNumber(event.target.value)}
                placeholder="e.g. PP-2026-001"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Department">
              <input
                type="text"
                value={department}
                onChange={(event) => setDepartment(event.target.value)}
                placeholder="e.g. Computer Science"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Requested by">
              <select
                value={requestedBy}
                onChange={(event) => setRequestedBy(event.target.value)}
                aria-label="Requested by"
                className={FIELD_CLASS}
              >
                <option value="">— Select faculty —</option>
                {facultyOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Proposal date">
              <input
                type="date"
                value={proposalDate}
                onChange={(event) => setProposalDate(event.target.value)}
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Estimated cost (₹)">
              <input
                type="number"
                inputMode="decimal"
                min="0"
                step="0.01"
                value={estimatedCost}
                onChange={(event) => setEstimatedCost(event.target.value)}
                placeholder="e.g. 250000"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Proposal status">
              <select
                value={proposalStatus}
                onChange={(event) => setProposalStatus(event.target.value as ProposalStatus)}
                aria-label="Proposal status"
                className={FIELD_CLASS}
              >
                {PROPOSAL_STATUSES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Priority">
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value)}
                aria-label="Priority"
                className={FIELD_CLASS}
              >
                <option value="">— None —</option>
                {PROPOSAL_PRIORITIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Budget head">
              <input
                type="text"
                value={budgetHead}
                onChange={(event) => setBudgetHead(event.target.value)}
                placeholder="e.g. Capital Equipment"
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Lifecycle status">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as ResearchObjectStatus)}
                className={FIELD_CLASS}
              >
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </select>
            </Field>
          </div>

          <Field label="Purpose">
            <textarea
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              rows={2}
              placeholder="Why is this procurement needed?"
              className={FIELD_CLASS}
            />
          </Field>

          {/* PART 2 procurement committee (reuses the Committees module) */}
          <div className="rounded-xl border border-[var(--border-subtle)] p-3">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Procurement Committee
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Purchase committees">
                <MultiSelect
                  label="Purchase committees"
                  options={committeeOptions}
                  selected={committeeIds}
                  onChange={setCommitteeIds}
                />
              </Field>
              <Field
                label="Approval meeting"
                hint="Meetings of the selected committees (422 if not a meeting)."
              >
                <select
                  value={approvalMeetingId}
                  onChange={(event) => setApprovalMeetingId(event.target.value)}
                  aria-label="Approval meeting"
                  className={FIELD_CLASS}
                >
                  <option value="">— None —</option>
                  {meetingOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Minutes">
                <textarea
                  value={minutes}
                  onChange={(event) => setMinutes(event.target.value)}
                  rows={3}
                  placeholder="Meeting minutes relevant to this procurement…"
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Recommendations">
                <textarea
                  value={recommendations}
                  onChange={(event) => setRecommendations(event.target.value)}
                  rows={3}
                  placeholder="Committee recommendations…"
                  className={FIELD_CLASS}
                />
              </Field>
            </div>
          </div>

          {/* Research & governance links (whole-group replace, like committees) */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Linked research projects">
              <MultiSelect
                label="Linked research projects"
                options={projectOptions}
                selected={projectIds}
                onChange={setProjectIds}
              />
            </Field>
            <Field label="Linked grants">
              <MultiSelect
                label="Linked grants"
                options={grantOptions}
                selected={grantIds}
                onChange={setGrantIds}
              />
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Notes">
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows={2}
                className={FIELD_CLASS}
              />
            </Field>
            <Field label="Tags" hint="Comma-separated.">
              <input
                type="text"
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="procurement, 2026"
                className={FIELD_CLASS}
              />
            </Field>
          </div>

          <Field label="Recorded by" hint="Audit attribution (the wire key is uploaded_by).">
            <input
              type="text"
              value={uploadedBy}
              onChange={(event) => setUploadedBy(event.target.value)}
              className={FIELD_CLASS}
            />
          </Field>

          {formError ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[var(--border-subtle)] px-5 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? <Spinner /> : null}
            {submitting
              ? mode === "edit"
                ? "Saving…"
                : "Creating…"
              : mode === "edit"
                ? "Save changes"
                : "Create proposal"}
          </button>
        </div>
      </form>
    </div>
  );
}

/** Human label for one approval-meeting option (committee name + date). */
function meetingOptionLabel(meeting: CommitteeMeetingSummary, committeeName: string): string {
  const parts = [
    meeting.title || "Meeting",
    meeting.meeting_number ? `No. ${meeting.meeting_number}` : null,
    meeting.meeting_date ?? null,
    committeeName,
  ].filter(Boolean);
  return parts.join(" · ");
}
