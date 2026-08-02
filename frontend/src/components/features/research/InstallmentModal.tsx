"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { addInstallment } from "@/lib/api/research";
import { INSTALLMENT_STATUSES } from "@/lib/research/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import type { GrantInstallment, InstallmentStatus } from "@/types";

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

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Add a release installment to a grant. The server enforces the PART 7 budget
 * guard (cumulative released ≤ sanctioned amount) and answers 422 when it is
 * violated — the message is surfaced verbatim in the dialog.
 */
export function InstallmentModal({
  open,
  grantId,
  onClose,
  onSaved,
}: {
  open: boolean;
  grantId: string;
  onClose: () => void;
  onSaved: (installment: GrantInstallment) => void;
}) {
  const [number, setNumber] = useState("1");
  const [date, setDate] = useState("");
  const [amount, setAmount] = useState("");
  const [status, setStatus] = useState<InstallmentStatus>("released");
  const [notes, setNotes] = useState("");
  const [uploadedBy, setUploadedBy] = useState("faculty:ui");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setNumber("1");
    setDate("");
    setAmount("");
    setStatus("released");
    setNotes("");
    setFormError(null);
    setSubmitting(false);
    submittingRef.current = false;
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

    const installmentNo = Number(number.trim());
    if (!Number.isInteger(installmentNo) || installmentNo < 1) {
      setFormError("Installment number must be a whole number ≥ 1.");
      return;
    }
    if (!DATE_RE.test(date.trim())) {
      setFormError("Release date is required (YYYY-MM-DD).");
      return;
    }
    const value = Number(amount.trim().replace(/,/g, ""));
    if (!amount.trim() || !Number.isFinite(value) || value <= 0) {
      setFormError("Amount must be a positive number.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    try {
      const saved = await addInstallment(grantId, {
        installment_no: installmentNo,
        date: date.trim(),
        amount: value,
        status,
        notes: notes.trim() || null,
        uploaded_by: uploadedBy.trim() || "faculty:ui",
      });
      submittingRef.current = false;
      setSubmitting(false);
      onSaved(saved);
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
        aria-labelledby="installment-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="installment-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            Add installment
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
          {formError ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Installment no.">
              <input
                ref={firstFieldRef}
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                value={number}
                onChange={(event) => setNumber(event.target.value)}
                className={FIELD_CLASS}
                aria-label="Installment number"
                required
              />
            </Field>
            <Field label="Release date" hint="YYYY-MM-DD.">
              <input
                value={date}
                onChange={(event) => setDate(event.target.value)}
                className={FIELD_CLASS}
                placeholder="2026-04-15"
                required
              />
            </Field>
            <Field label="Amount (₹)">
              <input
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className={FIELD_CLASS}
                placeholder="1500000"
                required
              />
            </Field>
            <Field label="Status">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as InstallmentStatus)}
                className={FIELD_CLASS}
                aria-label="Installment status"
              >
                {INSTALLMENT_STATUSES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Notes">
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className={FIELD_CLASS}
              rows={2}
              placeholder="First release against sanction order"
            />
          </Field>
          <Field label="Added by">
            <input
              value={uploadedBy}
              onChange={(event) => setUploadedBy(event.target.value)}
              className={FIELD_CLASS}
            />
          </Field>
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
            Add installment
          </button>
        </div>
      </form>
    </div>
  );
}
