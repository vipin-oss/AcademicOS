"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createGrant, listAgencies, listProjects, updateGrant } from "@/lib/api/research";
import { RELEASE_SCHEDULES } from "@/lib/research/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { GrantResponse, ResearchObjectStatus } from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

const MULTI_SELECT_CLASS = `${FIELD_CLASS} h-28`;

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {hint ? <p className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</p> : null}
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

export interface GrantSaveResult {
  grant: GrantResponse;
  mode: "create" | "edit";
}

/**
 * Register / edit a Grant (PART 3). The grant_number is unique per institution
 * — the backend answers 409 on duplicates and the message is surfaced inline.
 * `defaultProjectIds` pre-selects funded projects (used by the project
 * workspace's "New grant" button); edit mode always derives links from the
 * grant itself.
 */
export function GrantModal({
  open,
  onClose,
  onSaved,
  grant,
  defaultProjectIds,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: GrantSaveResult) => void;
  grant?: GrantResponse | null;
  defaultProjectIds?: string[];
}) {
  const mode = grant ? "edit" : "create";
  const [title, setTitle] = useState("");
  const [grantNumber, setGrantNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [releaseSchedule, setReleaseSchedule] = useState("");
  const [notes, setNotes] = useState("");
  const [projectIds, setProjectIds] = useState<string[]>([]);
  const [agencyIds, setAgencyIds] = useState<string[]>([]);
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [status, setStatus] = useState<ResearchObjectStatus>("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  const [projectOptions, setProjectOptions] = useState<PickerOption[]>([]);
  const [agencyOptions, setAgencyOptions] = useState<PickerOption[]>([]);
  // Pages pass `defaultProjectIds={[project.id]}` — a fresh array every render.
  // Keep it in a ref so the reset effect below depends only on [open, grant]
  // (a changed array identity must NOT wipe in-progress form edits).
  const defaultProjectIdsRef = useRef<string[] | undefined>(defaultProjectIds);
  defaultProjectIdsRef.current = defaultProjectIds;

  useEffect(() => {
    if (!open) return;
    setTitle(grant?.title ?? "");
    setGrantNumber(grant?.grant_number ?? "");
    setAmount(grant?.amount != null ? String(grant.amount) : "");
    setReleaseSchedule(grant?.release_schedule ?? "");
    setNotes(grant?.notes ?? "");
    setProjectIds(
      grant
        ? (grant.links?.projects ?? []).map((link) => link.id)
        : (defaultProjectIdsRef.current ?? []),
    );
    setAgencyIds((grant?.links?.funding_agencies ?? []).map((link) => link.id));
    setStatus(grant?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, grant]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    listProjects({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setProjectOptions(
          response.items.map((project) => ({ id: project.id, label: project.title })),
        ),
      )
      .catch(() => setProjectOptions([]));
    listAgencies({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setAgencyOptions(response.items.map((agency) => ({ id: agency.id, label: agency.name }))),
      )
      .catch(() => setAgencyOptions([]));
    return () => controller.abort();
  }, [open]);

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
      setFormError("Grant title must not be empty.");
      return;
    }
    if (!grantNumber.trim()) {
      setFormError("Grant number must not be empty.");
      return;
    }
    const parsed = amount.trim() ? Number(amount.trim().replace(/,/g, "")) : null;
    if (amount.trim() && (parsed == null || !Number.isFinite(parsed) || parsed < 0)) {
      setFormError("Sanctioned amount must be a non-negative number.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const payload = {
      title: title.trim(),
      grant_number: grantNumber.trim(),
      uploaded_by: uploadedBy.trim() || "faculty:ui",
      status,
      amount: parsed,
      release_schedule: releaseSchedule.trim() || null,
      notes: notes.trim() || null,
      links: { projects: projectIds, funding_agencies: agencyIds },
    };

    try {
      const saved = grant
        ? await updateGrant(grant.id, payload)
        : await createGrant(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ grant: saved, mode });
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
        aria-labelledby="grant-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="grant-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {mode === "edit" ? "Edit grant" : "New grant"}
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

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {formError ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Identity
            </legend>
            <Field label="Grant title">
              <input
                ref={firstFieldRef}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className={FIELD_CLASS}
                placeholder="SERB Core Research Grant — Perovskite thin films"
                required
              />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Grant number" hint="Unique per institution — duplicates are rejected.">
                <input
                  value={grantNumber}
                  onChange={(event) => setGrantNumber(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="CRG/2025/004321"
                  required
                />
              </Field>
              <Field label="Sanctioned amount (₹)">
                <input
                  inputMode="decimal"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="4500000"
                />
              </Field>
              <Field label="Release schedule">
                <input
                  value={releaseSchedule}
                  onChange={(event) => setReleaseSchedule(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="annual"
                  list="release-schedules"
                />
                <datalist id="release-schedules">
                  {RELEASE_SCHEDULES.map((option) => (
                    <option key={option} value={option} />
                  ))}
                </datalist>
              </Field>
              <Field label="Status">
                <select
                  value={status}
                  onChange={(event) => setStatus(event.target.value as ResearchObjectStatus)}
                  className={FIELD_CLASS}
                  aria-label="Status"
                >
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="archived">Archived</option>
                </select>
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Funding
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Funding agency" hint="Ctrl/Cmd-click for multiple;">
                <MultiSelect
                  label="Linked funding agencies"
                  options={agencyOptions}
                  selected={agencyIds}
                  onChange={setAgencyIds}
                />
              </Field>
              <Field label="Funded projects" hint="Ctrl/Cmd-click for multiple;">
                <MultiSelect
                  label="Linked projects"
                  options={projectOptions}
                  selected={projectIds}
                  onChange={setProjectIds}
                />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Notes &amp; administration
            </legend>
            <Field label="Notes" hint="Utilisation certificates and sanction letters are attached as Documents on the grant page.">
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                className={FIELD_CLASS}
                rows={2}
              />
            </Field>
            <Field label="Uploaded by">
              <input
                value={uploadedBy}
                onChange={(event) => setUploadedBy(event.target.value)}
                className={FIELD_CLASS}
              />
            </Field>
          </fieldset>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--border-subtle)] px-5 py-4">
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            {submitting ? <Spinner className="h-4 w-4" /> : null}
            {mode === "edit" ? "Save changes" : "Register grant"}
          </button>
        </div>
      </form>
    </div>
  );
}
