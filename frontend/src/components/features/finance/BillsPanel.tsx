"use client";

import { useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { updateProposal } from "@/lib/api/finance";
import {
  SectionPanel,
  RowDocumentsSelect,
  RowField,
  RowGrid,
  RowSelect,
  RowTextInput,
  RemoveRowButton,
  clean,
  moneyOf,
  type PickerOption,
} from "./SectionPanel";
import { PaymentStatusBadge } from "./FinanceBadges";
import { PAYMENT_STATUSES } from "@/lib/finance/constants";
import { formatDate } from "@/lib/utils";
import type { BillRow, PaymentStatus, ProposalResponse } from "@/types";

export interface BillEditRow {
  bill_number: string;
  invoice_number: string;
  vendor_id: string;
  bill_date: string;
  amount: string;
  gst_amount: string;
  payment_status: string;
  paid_date: string;
  po_number: string;
  document_ids: string[];
  remarks: string;
}

function toEditRow(row: BillRow): BillEditRow {
  return {
    bill_number: row.bill_number ?? "",
    invoice_number: row.invoice_number ?? "",
    vendor_id: row.vendor_id ?? "",
    bill_date: row.bill_date ?? "",
    amount: row.amount ?? "",
    gst_amount: row.gst_amount ?? "",
    payment_status: row.payment_status ?? "",
    paid_date: row.paid_date ?? "",
    po_number: row.po_number ?? "",
    document_ids: row.document_ids ?? [],
    remarks: row.remarks ?? "",
  };
}

function blankRow(): BillEditRow {
  return {
    bill_number: "",
    invoice_number: "",
    vendor_id: "",
    bill_date: "",
    amount: "",
    gst_amount: "",
    payment_status: "pending",
    paid_date: "",
    po_number: "",
    document_ids: [],
    remarks: "",
  };
}

function isFilled(row: BillEditRow): boolean {
  return Boolean(
    clean(row.bill_number) ||
      clean(row.invoice_number) ||
      row.vendor_id ||
      clean(row.bill_date) ||
      clean(row.amount) ||
      clean(row.gst_amount) ||
      clean(row.paid_date) ||
      clean(row.po_number) ||
      clean(row.remarks) ||
      row.document_ids.length > 0,
  );
}

/** Bill total = amount + GST (GST rides as its own column, like the backend). */
function billTotal(row: BillRow): string {
  const amount = Number(row.amount ?? 0);
  const gst = Number(row.gst_amount ?? 0);
  if (Number.isNaN(amount) || Number.isNaN(gst)) return moneyOf(row.amount);
  if (!row.amount && !row.gst_amount) return "—";
  return moneyOf(amount + gst);
}

/**
 * PART 7 bills & invoices. `bill_number` is required and unique within the
 * proposal; spend analytics derive from PAID bill totals server-side.
 */
export function BillsPanel({
  proposal,
  vendors,
  documents,
  onUpdated,
}: {
  proposal: ProposalResponse;
  vendors: PickerOption[];
  documents: PickerOption[];
  onUpdated: (proposal: ProposalResponse) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<BillEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(proposal.bills.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<BillEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !clean(row.bill_number))) {
      setError("Every bill needs a bill number (or remove the row).");
      return;
    }
    const seen = new Set<string>();
    for (const row of filled) {
      const number = clean(row.bill_number) ?? "";
      if (seen.has(number)) {
        setError(`Duplicate bill number "${number}" — bill numbers must be unique per proposal.`);
        return;
      }
      seen.add(number);
    }
    if (filled.some((row) => !row.vendor_id)) {
      setError("Every bill needs a vendor (or remove the row).");
      return;
    }
    if (
      filled.some(
        (row) =>
          (clean(row.amount) && Number.isNaN(Number(clean(row.amount)))) ||
          (clean(row.gst_amount) && Number.isNaN(Number(clean(row.gst_amount)))),
      )
    ) {
      setError("Bill amounts and GST must be non-negative numbers.");
      return;
    }

    setSaving(true);
    const payload = filled.map((row) => ({
      bill_number: clean(row.bill_number),
      invoice_number: clean(row.invoice_number),
      vendor_id: row.vendor_id,
      bill_date: clean(row.bill_date),
      amount: clean(row.amount),
      gst_amount: clean(row.gst_amount),
      payment_status: (row.payment_status || undefined) as PaymentStatus | undefined,
      paid_date: clean(row.paid_date),
      po_number: clean(row.po_number),
      document_ids: row.document_ids,
      remarks: clean(row.remarks),
    }));
    try {
      const updated = await updateProposal(proposal.id, { bills: payload });
      onUpdated(updated);
      setSaving(false);
      setEditing(false);
    } catch (err) {
      setSaving(false);
      setError(toErrorMessage(err));
    }
  };

  const view = (
    <>
      {proposal.bills.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No bills recorded yet — log invoices and their payment status here.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-3 font-medium">Bill No.</th>
                <th className="py-2 pr-3 font-medium">Invoice No.</th>
                <th className="py-2 pr-3 font-medium">Vendor</th>
                <th className="py-2 pr-3 font-medium">Date</th>
                <th className="py-2 pr-3 font-medium">Total (incl. GST)</th>
                <th className="py-2 font-medium">Payment</th>
              </tr>
            </thead>
            <tbody>
              {proposal.bills.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2 pr-3 font-mono text-xs">{row.bill_number || "—"}</td>
                  <td className="py-2 pr-3 font-mono text-xs">{row.invoice_number || "—"}</td>
                  <td className="py-2 pr-3">{row.vendor_name || "—"}</td>
                  <td className="py-2 pr-3">{row.bill_date ? formatDate(row.bill_date) : "—"}</td>
                  <td className="py-2 pr-3">{billTotal(row)}</td>
                  <td className="py-2">
                    {row.payment_status ? (
                      <PaymentStatusBadge status={row.payment_status} />
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  const editor = (
    <ul className="space-y-2">
      {rows.map((row, index) => (
        <RowGrid key={index}>
          <RowField label="Bill number *">
            <RowTextInput
              value={row.bill_number}
              onChange={(value) => patchRow(index, { bill_number: value })}
              ariaLabel={`Bill ${index + 1} bill number`}
              placeholder="e.g. BILL-2026-001"
            />
          </RowField>
          <RowField label="Invoice number">
            <RowTextInput
              value={row.invoice_number}
              onChange={(value) => patchRow(index, { invoice_number: value })}
              ariaLabel={`Bill ${index + 1} invoice number`}
              placeholder="Vendor invoice no."
            />
          </RowField>
          <RowField label="Vendor *">
            <RowSelect
              value={row.vendor_id}
              onChange={(value) => patchRow(index, { vendor_id: value })}
              ariaLabel={`Bill ${index + 1} vendor`}
              options={vendors.map((vendor) => ({ value: vendor.id, label: vendor.label }))}
              emptyLabel="— Select vendor —"
            />
          </RowField>
          <RowField label="Bill date">
            <RowTextInput
              type="date"
              value={row.bill_date}
              onChange={(value) => patchRow(index, { bill_date: value })}
              ariaLabel={`Bill ${index + 1} date`}
            />
          </RowField>
          <RowField label="Amount (₹)">
            <RowTextInput
              type="number"
              value={row.amount}
              onChange={(value) => patchRow(index, { amount: value })}
              ariaLabel={`Bill ${index + 1} amount`}
            />
          </RowField>
          <RowField label="GST (₹)">
            <RowTextInput
              type="number"
              value={row.gst_amount}
              onChange={(value) => patchRow(index, { gst_amount: value })}
              ariaLabel={`Bill ${index + 1} gst amount`}
            />
          </RowField>
          <RowField label="Payment status">
            <RowSelect
              value={row.payment_status}
              onChange={(value) => patchRow(index, { payment_status: value })}
              ariaLabel={`Bill ${index + 1} payment status`}
              options={PAYMENT_STATUSES.map((option) => ({
                value: option.value as string,
                label: option.label,
              }))}
              emptyLabel="— Select —"
            />
          </RowField>
          <RowField label="Paid date">
            <RowTextInput
              type="date"
              value={row.paid_date}
              onChange={(value) => patchRow(index, { paid_date: value })}
              ariaLabel={`Bill ${index + 1} paid date`}
            />
          </RowField>
          <RowField label="PO number">
            <RowTextInput
              value={row.po_number}
              onChange={(value) => patchRow(index, { po_number: value })}
              ariaLabel={`Bill ${index + 1} po number`}
              placeholder="Link to a PO"
            />
          </RowField>
          <RowField label="Documents">
            <RowDocumentsSelect
              value={row.document_ids}
              onChange={(ids) => patchRow(index, { document_ids: ids })}
              ariaLabel={`Bill ${index + 1} documents`}
              options={documents}
            />
          </RowField>
          <RowField label="Remarks">
            <RowTextInput
              value={row.remarks}
              onChange={(value) => patchRow(index, { remarks: value })}
              ariaLabel={`Bill ${index + 1} remarks`}
              placeholder="Optional"
            />
          </RowField>
          <RemoveRowButton
            onClick={() =>
              setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
            }
            ariaLabel={`Remove bill ${index + 1}`}
          />
        </RowGrid>
      ))}
    </ul>
  );

  return (
    <SectionPanel
      title="Bills & Invoices"
      count={proposal.bills.length}
      ariaLabel="Bills and invoices"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add bill"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}
