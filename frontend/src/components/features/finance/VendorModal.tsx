"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createVendor, updateVendor } from "@/lib/api/finance";
import type { VendorResponse } from "@/types";

const INPUT_CLASS =
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

export interface VendorSaveResult {
  vendor: VendorResponse;
  mode: "create" | "edit";
}

/** Register / edit a Vendor (PART 3 registry record + bank details). */
export function VendorModal({
  open,
  onClose,
  onSaved,
  vendor,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (result: VendorSaveResult) => void;
  vendor?: VendorResponse | null;
}) {
  const mode = vendor ? "edit" : "create";
  const [name, setName] = useState("");
  const [gstNumber, setGstNumber] = useState("");
  const [pan, setPan] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [ifsc, setIfsc] = useState("");
  const [branch, setBranch] = useState("");
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setName(vendor?.name ?? "");
    setGstNumber(vendor?.gst_number ?? "");
    setPan(vendor?.pan ?? "");
    setContactPerson(vendor?.contact_person ?? "");
    setEmail(vendor?.email ?? "");
    setPhone(vendor?.phone ?? "");
    setAddress(vendor?.address ?? "");
    setBankName(vendor?.bank_details?.bank_name ?? "");
    setAccountNumber(vendor?.bank_details?.account_number ?? "");
    setIfsc(vendor?.bank_details?.ifsc ?? "");
    setBranch(vendor?.bank_details?.branch ?? "");
    setNotes(vendor?.notes ?? "");
    setTags((vendor?.tags ?? []).join(", "));
    setFormError(null);
    setTimeout(() => firstFieldRef.current?.focus(), 30);
  }, [open, vendor]);

  if (!open) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;
    if (!name.trim()) {
      setFormError("Vendor name is required.");
      return;
    }
    submittingRef.current = true;
    setSubmitting(true);
    setFormError(null);
    const bankDetails = {
      bank_name: bankName.trim() || undefined,
      account_number: accountNumber.trim() || undefined,
      ifsc: ifsc.trim().toUpperCase() || undefined,
      branch: branch.trim() || undefined,
    };
    const payload = {
      name: name.trim(),
      uploaded_by: "finance:ui",
      gst_number: gstNumber.trim().toUpperCase() || null,
      pan: pan.trim().toUpperCase() || null,
      contact_person: contactPerson.trim() || null,
      email: email.trim() || null,
      phone: phone.trim() || null,
      address: address.trim() || null,
      bank_details: bankDetails,
      notes: notes.trim() || null,
      tags: tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    };
    try {
      const saved =
        mode === "edit" && vendor
          ? await updateVendor(vendor.id, payload)
          : await createVendor(payload);
      onSaved({ vendor: saved, mode });
    } catch (err) {
      setFormError(toErrorMessage(err));
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:items-center"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-label={mode === "edit" ? "Edit vendor" : "New vendor"}
        onSubmit={handleSubmit}
        className="w-full max-w-2xl rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-5 py-4">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            {mode === "edit" ? "Edit Vendor" : "New Vendor"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="grid max-h-[70vh] grid-cols-1 gap-4 overflow-y-auto px-5 py-4 sm:grid-cols-2">
          <Field label="Vendor name *">
            <input
              ref={firstFieldRef}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Acme Scientific Supplies"
              className={INPUT_CLASS}
            />
          </Field>
          <Field label="GST Number" hint="Unique when provided (409 on duplicates).">
            <input
              value={gstNumber}
              onChange={(event) => setGstNumber(event.target.value)}
              placeholder="07AABCS1429B1Z5"
              className={`${INPUT_CLASS} font-mono`}
            />
          </Field>
          <Field label="PAN">
            <input
              value={pan}
              onChange={(event) => setPan(event.target.value)}
              placeholder="AABCS1429B"
              className={`${INPUT_CLASS} font-mono`}
            />
          </Field>
          <Field label="Contact person">
            <input
              value={contactPerson}
              onChange={(event) => setContactPerson(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field label="Phone">
            <input
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Address">
              <textarea
                value={address}
                onChange={(event) => setAddress(event.target.value)}
                rows={2}
                className={INPUT_CLASS}
              />
            </Field>
          </div>

          <div className="sm:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Bank Details
            </p>
          </div>
          <Field label="Bank name">
            <input
              value={bankName}
              onChange={(event) => setBankName(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field label="Account number">
            <input
              value={accountNumber}
              onChange={(event) => setAccountNumber(event.target.value)}
              className={`${INPUT_CLASS} font-mono`}
            />
          </Field>
          <Field label="IFSC">
            <input
              value={ifsc}
              onChange={(event) => setIfsc(event.target.value)}
              placeholder="SBIN0001234"
              className={`${INPUT_CLASS} font-mono`}
            />
          </Field>
          <Field label="Branch">
            <input
              value={branch}
              onChange={(event) => setBranch(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>

          <div className="sm:col-span-2">
            <Field label="Notes">
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows={2}
                className={INPUT_CLASS}
              />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Tags" hint="Comma-separated.">
              <input
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="lab, preferred"
                className={INPUT_CLASS}
              />
            </Field>
          </div>

          {formError ? (
            <div className="sm:col-span-2">
              <p
                role="alert"
                className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
              >
                {formError}
              </p>
            </div>
          ) : null}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[var(--border-subtle)] px-5 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Saving…" : mode === "edit" ? "Save changes" : "Create vendor"}
          </button>
        </div>
      </form>
    </div>
  );
}
