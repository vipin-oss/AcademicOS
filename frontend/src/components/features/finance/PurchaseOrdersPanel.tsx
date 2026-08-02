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
import { PoStatusBadge } from "./FinanceBadges";
import { PO_STATUSES } from "@/lib/finance/constants";
import { formatDate } from "@/lib/utils";
import type { ProposalResponse, PurchaseOrderRow, PurchaseOrderStatus } from "@/types";

export interface PurchaseOrderEditRow {
  po_number: string;
  po_date: string;
  vendor_id: string;
  amount: string;
  status: string;
  delivery_date: string;
  document_ids: string[];
  remarks: string;
}

function toEditRow(row: PurchaseOrderRow): PurchaseOrderEditRow {
  return {
    po_number: row.po_number ?? "",
    po_date: row.po_date ?? "",
    vendor_id: row.vendor_id ?? "",
    amount: row.amount ?? "",
    status: row.status ?? "",
    delivery_date: row.delivery_date ?? "",
    document_ids: row.document_ids ?? [],
    remarks: row.remarks ?? "",
  };
}

function blankRow(): PurchaseOrderEditRow {
  return {
    po_number: "",
    po_date: "",
    vendor_id: "",
    amount: "",
    status: "issued",
    delivery_date: "",
    document_ids: [],
    remarks: "",
  };
}

function isFilled(row: PurchaseOrderEditRow): boolean {
  return Boolean(
    clean(row.po_number) ||
      clean(row.po_date) ||
      row.vendor_id ||
      clean(row.amount) ||
      clean(row.delivery_date) ||
      clean(row.remarks) ||
      row.document_ids.length > 0,
  );
}

/**
 * PART 6 purchase orders. `po_number` is required and unique within the
 * proposal (the backend 422s otherwise) — the client mirrors that check.
 */
export function PurchaseOrdersPanel({
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
  const [rows, setRows] = useState<PurchaseOrderEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(proposal.purchase_orders.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<PurchaseOrderEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !clean(row.po_number))) {
      setError("Every purchase order needs a PO number (or remove the row).");
      return;
    }
    const seen = new Set<string>();
    for (const row of filled) {
      const number = clean(row.po_number) ?? "";
      if (seen.has(number)) {
        setError(`Duplicate PO number "${number}" — PO numbers must be unique per proposal.`);
        return;
      }
      seen.add(number);
    }
    if (filled.some((row) => !row.vendor_id)) {
      setError("Every purchase order needs a vendor (or remove the row).");
      return;
    }
    if (filled.some((row) => clean(row.amount) && Number.isNaN(Number(clean(row.amount))))) {
      setError("Purchase order amounts must be non-negative numbers.");
      return;
    }

    setSaving(true);
    const payload = filled.map((row) => ({
      po_number: clean(row.po_number),
      po_date: clean(row.po_date),
      vendor_id: row.vendor_id,
      amount: clean(row.amount),
      status: (row.status || undefined) as PurchaseOrderStatus | undefined,
      delivery_date: clean(row.delivery_date),
      document_ids: row.document_ids,
      remarks: clean(row.remarks),
    }));
    try {
      const updated = await updateProposal(proposal.id, { purchase_orders: payload });
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
      {proposal.purchase_orders.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No purchase orders issued yet — record POs once the order is placed.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-3 font-medium">PO Number</th>
                <th className="py-2 pr-3 font-medium">Vendor</th>
                <th className="py-2 pr-3 font-medium">Date</th>
                <th className="py-2 pr-3 font-medium">Amount</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 font-medium">Delivery</th>
              </tr>
            </thead>
            <tbody>
              {proposal.purchase_orders.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2 pr-3 font-mono text-xs">{row.po_number || "—"}</td>
                  <td className="py-2 pr-3">{row.vendor_name || "—"}</td>
                  <td className="py-2 pr-3">{row.po_date ? formatDate(row.po_date) : "—"}</td>
                  <td className="py-2 pr-3">{moneyOf(row.amount)}</td>
                  <td className="py-2 pr-3">
                    {row.status ? <PoStatusBadge status={row.status} /> : "—"}
                  </td>
                  <td className="py-2">
                    {row.delivery_date ? formatDate(row.delivery_date) : "—"}
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
          <RowField label="PO number *">
            <RowTextInput
              value={row.po_number}
              onChange={(value) => patchRow(index, { po_number: value })}
              ariaLabel={`Purchase order ${index + 1} po number`}
              placeholder="e.g. PO-2026-001"
            />
          </RowField>
          <RowField label="Vendor *">
            <RowSelect
              value={row.vendor_id}
              onChange={(value) => patchRow(index, { vendor_id: value })}
              ariaLabel={`Purchase order ${index + 1} vendor`}
              options={vendors.map((vendor) => ({ value: vendor.id, label: vendor.label }))}
              emptyLabel="— Select vendor —"
            />
          </RowField>
          <RowField label="PO date">
            <RowTextInput
              type="date"
              value={row.po_date}
              onChange={(value) => patchRow(index, { po_date: value })}
              ariaLabel={`Purchase order ${index + 1} date`}
            />
          </RowField>
          <RowField label="Amount (₹)">
            <RowTextInput
              type="number"
              value={row.amount}
              onChange={(value) => patchRow(index, { amount: value })}
              ariaLabel={`Purchase order ${index + 1} amount`}
            />
          </RowField>
          <RowField label="Status">
            <RowSelect
              value={row.status}
              onChange={(value) => patchRow(index, { status: value })}
              ariaLabel={`Purchase order ${index + 1} status`}
              options={PO_STATUSES.map((option) => ({
                value: option.value as string,
                label: option.label,
              }))}
              emptyLabel="— Select —"
            />
          </RowField>
          <RowField label="Delivery date">
            <RowTextInput
              type="date"
              value={row.delivery_date}
              onChange={(value) => patchRow(index, { delivery_date: value })}
              ariaLabel={`Purchase order ${index + 1} delivery date`}
            />
          </RowField>
          <RowField label="Documents">
            <RowDocumentsSelect
              value={row.document_ids}
              onChange={(ids) => patchRow(index, { document_ids: ids })}
              ariaLabel={`Purchase order ${index + 1} documents`}
              options={documents}
            />
          </RowField>
          <RowField label="Remarks">
            <RowTextInput
              value={row.remarks}
              onChange={(value) => patchRow(index, { remarks: value })}
              ariaLabel={`Purchase order ${index + 1} remarks`}
              placeholder="Optional"
            />
          </RowField>
          <RemoveRowButton
            onClick={() =>
              setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
            }
            ariaLabel={`Remove purchase order ${index + 1}`}
          />
        </RowGrid>
      ))}
    </ul>
  );

  return (
    <SectionPanel
      title="Purchase Orders"
      count={proposal.purchase_orders.length}
      ariaLabel="Purchase orders"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add purchase order"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}
