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
import { formatDate } from "@/lib/utils";
import type { ProposalResponse, QuotationRow } from "@/types";

export interface QuotationEditRow {
  vendor_id: string;
  quotation_date: string;
  amount: string;
  validity_date: string;
  document_ids: string[];
  remarks: string;
}

function toEditRow(row: QuotationRow): QuotationEditRow {
  return {
    vendor_id: row.vendor_id ?? "",
    quotation_date: row.quotation_date ?? "",
    amount: row.amount ?? "",
    validity_date: row.validity_date ?? "",
    document_ids: row.document_ids ?? [],
    remarks: row.remarks ?? "",
  };
}

function blankRow(): QuotationEditRow {
  return {
    vendor_id: "",
    quotation_date: "",
    amount: "",
    validity_date: "",
    document_ids: [],
    remarks: "",
  };
}

function isFilled(row: QuotationEditRow): boolean {
  return Boolean(
    row.vendor_id ||
      clean(row.quotation_date) ||
      clean(row.amount) ||
      clean(row.validity_date) ||
      clean(row.remarks) ||
      row.document_ids.length > 0,
  );
}

/**
 * PART 4 quotations (multiple vendors can quote for one proposal). Rows are
 * stored in proposal metadata; saving PUTs only the quotations key.
 */
export function QuotationsPanel({
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
  const [rows, setRows] = useState<QuotationEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(proposal.quotations.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<QuotationEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !row.vendor_id)) {
      setError("Every quotation row needs a vendor (or remove the row).");
      return;
    }
    if (filled.some((row) => clean(row.amount) && Number.isNaN(Number(clean(row.amount))))) {
      setError("Quotation amounts must be non-negative numbers.");
      return;
    }

    setSaving(true);
    const payload = filled.map((row) => ({
      vendor_id: row.vendor_id,
      quotation_date: clean(row.quotation_date),
      amount: clean(row.amount),
      validity_date: clean(row.validity_date),
      document_ids: row.document_ids,
      remarks: clean(row.remarks),
    }));
    try {
      const updated = await updateProposal(proposal.id, { quotations: payload });
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
      {proposal.quotations.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No quotations recorded yet — edit to add the vendors&apos; quotes.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-3 font-medium">Vendor</th>
                <th className="py-2 pr-3 font-medium">Date</th>
                <th className="py-2 pr-3 font-medium">Amount</th>
                <th className="py-2 pr-3 font-medium">Validity</th>
                <th className="py-2 pr-3 font-medium">Documents</th>
                <th className="py-2 font-medium">Remarks</th>
              </tr>
            </thead>
            <tbody>
              {proposal.quotations.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2 pr-3">{row.vendor_name || "—"}</td>
                  <td className="py-2 pr-3">
                    {row.quotation_date ? formatDate(row.quotation_date) : "—"}
                  </td>
                  <td className="py-2 pr-3">{moneyOf(row.amount)}</td>
                  <td className="py-2 pr-3">
                    {row.validity_date ? formatDate(row.validity_date) : "—"}
                  </td>
                  <td className="py-2 pr-3">
                    {(row.supporting_documents ?? []).length > 0
                      ? (row.supporting_documents ?? []).map((doc) => doc.title).join(", ")
                      : "—"}
                  </td>
                  <td className="py-2">{row.remarks || "—"}</td>
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
          <RowField label="Vendor *">
            <RowSelect
              value={row.vendor_id}
              onChange={(value) => patchRow(index, { vendor_id: value })}
              ariaLabel={`Quotation ${index + 1} vendor`}
              options={vendors.map((vendor) => ({ value: vendor.id, label: vendor.label }))}
              emptyLabel="— Select vendor —"
            />
          </RowField>
          <RowField label="Date">
            <RowTextInput
              type="date"
              value={row.quotation_date}
              onChange={(value) => patchRow(index, { quotation_date: value })}
              ariaLabel={`Quotation ${index + 1} date`}
            />
          </RowField>
          <RowField label="Amount (₹)">
            <RowTextInput
              type="number"
              value={row.amount}
              onChange={(value) => patchRow(index, { amount: value })}
              ariaLabel={`Quotation ${index + 1} amount`}
              placeholder="e.g. 245000"
            />
          </RowField>
          <RowField label="Validity date">
            <RowTextInput
              type="date"
              value={row.validity_date}
              onChange={(value) => patchRow(index, { validity_date: value })}
              ariaLabel={`Quotation ${index + 1} validity`}
            />
          </RowField>
          <RowField label="Documents">
            <RowDocumentsSelect
              value={row.document_ids}
              onChange={(ids) => patchRow(index, { document_ids: ids })}
              ariaLabel={`Quotation ${index + 1} documents`}
              options={documents}
            />
          </RowField>
          <RowField label="Remarks">
            <RowTextInput
              value={row.remarks}
              onChange={(value) => patchRow(index, { remarks: value })}
              ariaLabel={`Quotation ${index + 1} remarks`}
              placeholder="Optional"
            />
          </RowField>
          <RemoveRowButton
            onClick={() =>
              setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
            }
            ariaLabel={`Remove quotation ${index + 1}`}
          />
        </RowGrid>
      ))}
    </ul>
  );

  return (
    <SectionPanel
      title="Quotations"
      count={proposal.quotations.length}
      ariaLabel="Quotations"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add quotation"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}
