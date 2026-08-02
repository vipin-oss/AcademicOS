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
import { ComplianceBadge } from "./FinanceBadges";
import { COMPLIANCE_VALUES } from "@/lib/finance/constants";
import type { ComparativeRow, ComplianceValue, ProposalResponse } from "@/types";

export interface ComparativeEditRow {
  vendor_id: string;
  amount: string;
  technical_compliance: string;
  financial_compliance: string;
  recommended: boolean;
  remarks: string;
}

function toEditRow(row: ComparativeRow): ComparativeEditRow {
  return {
    vendor_id: row.vendor_id ?? "",
    amount: row.amount ?? "",
    technical_compliance: row.technical_compliance ?? "",
    financial_compliance: row.financial_compliance ?? "",
    recommended: Boolean(row.recommended),
    remarks: row.remarks ?? "",
  };
}

function blankRow(): ComparativeEditRow {
  return {
    vendor_id: "",
    amount: "",
    technical_compliance: "",
    financial_compliance: "",
    recommended: false,
    remarks: "",
  };
}

function isFilled(row: ComparativeEditRow): boolean {
  return Boolean(
    row.vendor_id ||
      clean(row.amount) ||
      row.technical_compliance ||
      row.financial_compliance ||
      row.recommended ||
      clean(row.remarks),
  );
}

/**
 * PART 5 comparative statement — one row per bidder with technical/financial
 * compliance and a single recommended vendor (enforced server-side too).
 */
export function ComparativePanel({
  proposal,
  vendors,
  onUpdated,
}: {
  proposal: ProposalResponse;
  vendors: PickerOption[];
  onUpdated: (proposal: ProposalResponse) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<ComparativeEditRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setRows(proposal.comparative.map(toEditRow));
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const patchRow = (index: number, patch: Partial<ComparativeEditRow>) =>
    setRows((current) =>
      current.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );

  /** Prefill one row per recorded quotation (vendor + quoted amount). */
  const generateFromQuotations = () => {
    setRows(
      proposal.quotations.map((quotation) => ({
        vendor_id: quotation.vendor_id ?? "",
        amount: quotation.amount ?? "",
        technical_compliance: "compliant",
        financial_compliance: "compliant",
        recommended: false,
        remarks: "",
      })),
    );
  };

  const save = async () => {
    if (saving) return;
    setError(null);
    const filled = rows.filter(isFilled);
    if (filled.some((row) => !row.vendor_id)) {
      setError("Every comparative row needs a vendor (or remove the row).");
      return;
    }
    if (filled.some((row) => clean(row.amount) && Number.isNaN(Number(clean(row.amount))))) {
      setError("Comparative amounts must be non-negative numbers.");
      return;
    }
    if (filled.filter((row) => row.recommended).length > 1) {
      setError("Only one vendor can be recommended.");
      return;
    }
    if (
      filled.some(
        (row) =>
          (row.technical_compliance &&
            !COMPLIANCE_VALUES.some((option) => option.value === row.technical_compliance)) ||
          (row.financial_compliance &&
            !COMPLIANCE_VALUES.some((option) => option.value === row.financial_compliance)),
      )
    ) {
      setError("Compliance values must come from the vocabulary.");
      return;
    }

    setSaving(true);
    const payload = filled.map((row) => ({
      vendor_id: row.vendor_id,
      amount: clean(row.amount),
      technical_compliance: (row.technical_compliance || undefined) as
        | ComplianceValue
        | undefined,
      financial_compliance: (row.financial_compliance || undefined) as
        | ComplianceValue
        | undefined,
      recommended: row.recommended,
      remarks: clean(row.remarks),
    }));
    try {
      const updated = await updateProposal(proposal.id, { comparative: payload });
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
      {proposal.comparative.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">
          No comparative statement yet — record compliance and mark the recommended vendor.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
                <th className="py-2 pr-3 font-medium">Vendor</th>
                <th className="py-2 pr-3 font-medium">Amount</th>
                <th className="py-2 pr-3 font-medium">Technical</th>
                <th className="py-2 pr-3 font-medium">Financial</th>
                <th className="py-2 pr-3 font-medium">Recommended</th>
                <th className="py-2 font-medium">Remarks</th>
              </tr>
            </thead>
            <tbody>
              {proposal.comparative.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-2 pr-3">{row.vendor_name || "—"}</td>
                  <td className="py-2 pr-3">{moneyOf(row.amount)}</td>
                  <td className="py-2 pr-3">
                    {row.technical_compliance ? (
                      <ComplianceBadge value={row.technical_compliance} />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2 pr-3">
                    {row.financial_compliance ? (
                      <ComplianceBadge value={row.financial_compliance} />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2 pr-3">
                    {row.recommended ? (
                      <span
                        aria-label={`Recommended vendor ${row.vendor_name ?? ""}`}
                        className="inline-flex items-center rounded-full bg-[var(--success-subtle)] px-2 py-0.5 text-xs font-medium text-[var(--success)]"
                      >
                        Recommended
                      </span>
                    ) : (
                      "—"
                    )}
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

  const complianceOptions = COMPLIANCE_VALUES.map((option) => ({
    value: option.value as string,
    label: option.label,
  }));

  const editor = (
    <>
      {proposal.quotations.length > 0 ? (
        <button
          type="button"
          onClick={generateFromQuotations}
          className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2 py-1 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          Generate from quotations ({proposal.quotations.length})
        </button>
      ) : null}
      <ul className="space-y-2">
        {rows.map((row, index) => (
          <RowGrid key={index}>
            <RowField label="Vendor *">
              <RowSelect
                value={row.vendor_id}
                onChange={(value) => patchRow(index, { vendor_id: value })}
                ariaLabel={`Comparative ${index + 1} vendor`}
                options={vendors.map((vendor) => ({ value: vendor.id, label: vendor.label }))}
                emptyLabel="— Select vendor —"
              />
            </RowField>
            <RowField label="Amount (₹)">
              <RowTextInput
                type="number"
                value={row.amount}
                onChange={(value) => patchRow(index, { amount: value })}
                ariaLabel={`Comparative ${index + 1} amount`}
              />
            </RowField>
            <RowField label="Technical compliance">
              <RowSelect
                value={row.technical_compliance}
                onChange={(value) => patchRow(index, { technical_compliance: value })}
                ariaLabel={`Comparative ${index + 1} technical compliance`}
                options={complianceOptions}
                emptyLabel="— Select —"
              />
            </RowField>
            <RowField label="Financial compliance">
              <RowSelect
                value={row.financial_compliance}
                onChange={(value) => patchRow(index, { financial_compliance: value })}
                ariaLabel={`Comparative ${index + 1} financial compliance`}
                options={complianceOptions}
                emptyLabel="— Select —"
              />
            </RowField>
            <RowField label="Recommended">
              <span className="inline-flex items-center gap-2 py-1.5 text-sm text-[var(--text-secondary)]">
                <input
                  type="checkbox"
                  checked={row.recommended}
                  onChange={(event) => patchRow(index, { recommended: event.target.checked })}
                  aria-label={`Comparative ${index + 1} recommended`}
                  className="h-4 w-4 accent-[var(--accent)]"
                />
                Recommend this vendor
              </span>
            </RowField>
            <RowField label="Remarks">
              <RowTextInput
                value={row.remarks}
                onChange={(value) => patchRow(index, { remarks: value })}
                ariaLabel={`Comparative ${index + 1} remarks`}
                placeholder="Optional"
              />
            </RowField>
            <RemoveRowButton
              onClick={() =>
                setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))
              }
              ariaLabel={`Remove comparative ${index + 1}`}
            />
          </RowGrid>
        ))}
      </ul>
    </>
  );

  return (
    <SectionPanel
      title="Comparative Statement"
      count={proposal.comparative.length}
      ariaLabel="Comparative statement"
      editing={editing}
      saving={saving}
      error={error}
      onEdit={startEdit}
      onSave={save}
      onCancel={cancel}
      addLabel="Add row"
      onAdd={() => setRows((current) => [...current, blankRow()])}
      view={view}
      editor={editor}
    />
  );
}
