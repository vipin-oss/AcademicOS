"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createAgency, updateAgency } from "@/lib/api/research";
import { COMMON_AGENCIES } from "@/lib/research/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { AgencyResponse, ResearchObjectStatus } from "@/types";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

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

export interface AgencySaveResult {
  agency: AgencyResponse;
  mode: "create" | "edit";
}

/**
 * Register / edit a Funding Agency (PART 2 registry). The name is unique
 * (case-insensitive) — the backend answers 409 on duplicates and the message
 * is surfaced inline. The name input offers the well-known Indian agencies as
 * quick-add suggestions (free text allowed).
 */
export function AgencyModal({
  open,
  onClose,
  onSaved,
  agency,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: AgencySaveResult) => void;
  agency?: AgencyResponse | null;
}) {
  const mode = agency ? "edit" : "create";
  const [name, setName] = useState("");
  const [scheme, setScheme] = useState("");
  const [website, setWebsite] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [status, setStatus] = useState<ResearchObjectStatus>("active");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setName(agency?.name ?? "");
    setScheme(agency?.scheme ?? "");
    setWebsite(agency?.website ?? "");
    setContactPerson(agency?.contact_person ?? "");
    setContactEmail(agency?.contact_email ?? "");
    setContactPhone(agency?.contact_phone ?? "");
    setAddress(agency?.address ?? "");
    setNotes(agency?.notes ?? "");
    setStatus(agency?.status ?? "active");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
  }, [open, agency]);

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

    if (!name.trim()) {
      setFormError("Agency name must not be empty.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    const payload = {
      name: name.trim(),
      uploaded_by: uploadedBy.trim() || "faculty:ui",
      status,
      website: website.trim() || null,
      scheme: scheme.trim() || null,
      contact_person: contactPerson.trim() || null,
      contact_email: contactEmail.trim() || null,
      contact_phone: contactPhone.trim() || null,
      address: address.trim() || null,
      notes: notes.trim() || null,
    };

    try {
      const saved = agency
        ? await updateAgency(agency.id, payload)
        : await createAgency(payload);
      submittingRef.current = false;
      setSubmitting(false);
      onSaved({ agency: saved, mode });
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
        aria-labelledby="agency-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="agency-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {mode === "edit" ? "Edit funding agency" : "New funding agency"}
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
            <Field
              label="Agency name"
              hint="Unique per institution — duplicates are rejected."
            >
              <input
                ref={firstFieldRef}
                value={name}
                onChange={(event) => setName(event.target.value)}
                className={FIELD_CLASS}
                placeholder="DST — Department of Science & Technology"
                list="common-agencies"
                required
              />
              <datalist id="common-agencies">
                {COMMON_AGENCIES.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Scheme" hint='E.g. "Core Research Grant", "Major Research Project".'>
                <input
                  value={scheme}
                  onChange={(event) => setScheme(event.target.value)}
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Website">
                <input
                  value={website}
                  onChange={(event) => setWebsite(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="https://dst.gov.in"
                />
              </Field>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Contact
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Contact person">
                <input
                  value={contactPerson}
                  onChange={(event) => setContactPerson(event.target.value)}
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Email">
                <input
                  type="email"
                  value={contactEmail}
                  onChange={(event) => setContactEmail(event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="scheme@agency.gov.in"
                />
              </Field>
              <Field label="Phone">
                <input
                  value={contactPhone}
                  onChange={(event) => setContactPhone(event.target.value)}
                  className={FIELD_CLASS}
                />
              </Field>
            </div>
            <Field label="Address">
              <textarea
                value={address}
                onChange={(event) => setAddress(event.target.value)}
                className={FIELD_CLASS}
                rows={2}
              />
            </Field>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Notes &amp; administration
            </legend>
            <Field label="Notes">
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                className={FIELD_CLASS}
                rows={2}
              />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
              <Field label="Uploaded by">
                <input
                  value={uploadedBy}
                  onChange={(event) => setUploadedBy(event.target.value)}
                  className={FIELD_CLASS}
                />
              </Field>
            </div>
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
            {mode === "edit" ? "Save changes" : "Register agency"}
          </button>
        </div>
      </form>
    </div>
  );
}
