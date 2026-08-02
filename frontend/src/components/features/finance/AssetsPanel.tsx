"use client";

import { useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { updateProposal } from "@/lib/api/finance";
import {
  SectionPanel,
  RowField,
  RowGrid,
  RowSelect,
  RowTextInput,
  RemoveRowButton,
  clean,
  moneyOf,
  type PickerOption,
} from "./SectionPanel";
import { AssetStatusBadge } from "./FinanceBadges";
import { ASSET_CATEGORIES, ASSET_STATUSES, labelFor } from "@/lib/finance/constants";
import { formatDate } from "@/lib/utils";
import type { AssetCategory, AssetRow, AssetStatus, ProposalResponse } from "@/types";

export interface AssetEditRow {
  asset_id: string;
  category: string;
  item_name: string;
  serial_number: string;
  location: string;
  assigned_to: string;
  warranty_expiry: string;
  purchase_date: string;
  cost: string;
  status: string;
  po_number: string;
  remarks: string;
}

function toEditRow(row: AssetRow): AssetEditRow {
  return {
    asset_id: row.asset_id ?? "",
    category: row.category ?? "",
    item_name: row.item_name ?? "",
    serial_number: row.serial_number ?? "",
    location: row.location ?? "",
    assigned_to: row.assigned_to ?? "",
    warranty_expiry: row.warranty_expiry ?? "",
    purchase_date: row.purchase_date ?? "",
    cost: row.cost ?? "",
    status: row.status ?? "",
    po_number: row.po_number ?? "",
    remarks: row.remarks ?? "",
  };
}

function blankRow(): AssetEditRow {
  return {
    asset_id: "",
    category: "",
    item_name: "",
    serial_number: "",
    location: "",
    assigned_to: "",
    warranty_expiry: "",
    purchase_date: "",
    cost: "",
    status: "in_service",
    po_number: "",
    remarks: "",
  };
}

function isFilled(row: AssetEditRow): boolean {
  return Boolean(
    clean(row.asset_id) ||
      row.category ||
      clean(row.item_name) ||
      clean(row.serial_number) ||
      clean(row.location) ||
      clean(row.assigned_to) ||
      clean(row.warranty_expiry) ||
      clean(row.purchase_date) ||
      clean(row.cost) ||
      clean(row.po_number) ||
      clean(row.remarks),
  );
}

/**
 * PART 8 assets acquired through this proposal. The same rows feed the
 * cross-proposal Asset Register (`/finance/assets`) server-side.
 */
export function AssetsPanel({
  proposal,
  onUpdated,
}: {
  proposal: ProposalResponse;
  onUpdated: (proposal: ProposalResponse) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<AssetEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(proposal.assets.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<AssetEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !clean(row.asset_id))) {
      setError("Every asset needs an asset ID (or remove the row).");
      return;
    }
    const seen = new Set<string>();
    for (const row of filled) {
      const identifier = clean(row.asset_id) ?? "";
      if (seen.has(identifier)) {
        setError(`Duplicate asset ID "${identifier}" — asset IDs must be unique per proposal.`);
        return;
      }
      seen.add(identifier);
    }
    if (filled.some((row) => clean(row.cost) && Number.isNaN(Number(clean(row.cost))))) {
      setError("Asset costs must be non-negative numbers.");
      return;
    }

    setSaving(true);
    const payload = filled.map((row) => ({
      asset_id: clean(row.asset_id),
      category: (row.category || undefined) as AssetCategory | undefined,
      item_name: clean(row.item_name),
      serial_number: clean(row.serial_number),
      location: clean(row.location),
      assigned_to: clean(row.assigned_to),
      warranty_expiry: clean(row.warranty_expiry),
      purchase_date: clean(row.purchase_date),
      cost: clean(row.cost),
      status: (row.status || undefined) as AssetStatus | undefined,
      po_number: clean(row.po_number),
      remarks: clean(row.remarks),
    }));
    try {
      const updated = await updateProposal(proposal.id, { assets: payload });
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
      {proposal.assets.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No assets registered for this proposal yet — add delivered items with their IDs.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-3 font-medium">Asset ID</th>
                <th className="py-2 pr-3 font-medium">Item</th>
                <th className="py-2 pr-3 font-medium">Category</th>
                <th className="py-2 pr-3 font-medium">Location</th>
                <th className="py-2 pr-3 font-medium">Cost</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {proposal.assets.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2 pr-3 font-mono text-xs">{row.asset_id || "—"}</td>
                  <td className="py-2 pr-3">{row.item_name || "—"}</td>
                  <td className="py-2 pr-3">{labelFor(row.category)}</td>
                  <td className="py-2 pr-3">{row.location || "—"}</td>
                  <td className="py-2 pr-3">{moneyOf(row.cost)}</td>
                  <td className="py-2">
                    {row.status ? <AssetStatusBadge status={row.status} /> : "—"}
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
          <RowField label="Asset ID *">
            <RowTextInput
              value={row.asset_id}
              onChange={(value) => patchRow(index, { asset_id: value })}
              ariaLabel={`Asset ${index + 1} asset id`}
              placeholder="e.g. AST-2026-001"
            />
          </RowField>
          <RowField label="Item name">
            <RowTextInput
              value={row.item_name}
              onChange={(value) => patchRow(index, { item_name: value })}
              ariaLabel={`Asset ${index + 1} item name`}
              placeholder="e.g. Oscilloscope"
            />
          </RowField>
          <RowField label="Category">
            <RowSelect
              value={row.category}
              onChange={(value) => patchRow(index, { category: value })}
              ariaLabel={`Asset ${index + 1} category`}
              options={ASSET_CATEGORIES.map((option) => ({
                value: option.value as string,
                label: option.label,
              }))}
              emptyLabel="— Select —"
            />
          </RowField>
          <RowField label="Serial number">
            <RowTextInput
              value={row.serial_number}
              onChange={(value) => patchRow(index, { serial_number: value })}
              ariaLabel={`Asset ${index + 1} serial number`}
            />
          </RowField>
          <RowField label="Location">
            <RowTextInput
              value={row.location}
              onChange={(value) => patchRow(index, { location: value })}
              ariaLabel={`Asset ${index + 1} location`}
              placeholder="e.g. Lab 2"
            />
          </RowField>
          <RowField label="Assigned to">
            <RowTextInput
              value={row.assigned_to}
              onChange={(value) => patchRow(index, { assigned_to: value })}
              ariaLabel={`Asset ${index + 1} assigned to`}
              placeholder="Custodian"
            />
          </RowField>
          <RowField label="Warranty expiry">
            <RowTextInput
              type="date"
              value={row.warranty_expiry}
              onChange={(value) => patchRow(index, { warranty_expiry: value })}
              ariaLabel={`Asset ${index + 1} warranty expiry`}
            />
          </RowField>
          <RowField label="Purchase date">
            <RowTextInput
              type="date"
              value={row.purchase_date}
              onChange={(value) => patchRow(index, { purchase_date: value })}
              ariaLabel={`Asset ${index + 1} purchase date`}
            />
          </RowField>
          <RowField label="Cost (₹)">
            <RowTextInput
              type="number"
              value={row.cost}
              onChange={(value) => patchRow(index, { cost: value })}
              ariaLabel={`Asset ${index + 1} cost`}
            />
          </RowField>
          <RowField label="Status">
            <RowSelect
              value={row.status}
              onChange={(value) => patchRow(index, { status: value })}
              ariaLabel={`Asset ${index + 1} status`}
              options={ASSET_STATUSES.map((option) => ({
                value: option.value as string,
                label: option.label,
              }))}
              emptyLabel="— Select —"
            />
          </RowField>
          <RowField label="PO number">
            <RowTextInput
              value={row.po_number}
              onChange={(value) => patchRow(index, { po_number: value })}
              ariaLabel={`Asset ${index + 1} po number`}
              placeholder="Link to a PO"
            />
          </RowField>
          <RowField label="Remarks">
            <RowTextInput
              value={row.remarks}
              onChange={(value) => patchRow(index, { remarks: value })}
              ariaLabel={`Asset ${index + 1} remarks`}
              placeholder="Optional"
            />
          </RowField>
          <RemoveRowButton
            onClick={() =>
              setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
            }
            ariaLabel={`Remove asset ${index + 1}`}
          />
        </RowGrid>
      ))}
    </ul>
  );

  return (
    <SectionPanel
      title="Assets"
      count={proposal.assets.length}
      ariaLabel="Proposal assets"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add asset"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}
