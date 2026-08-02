import type {
  AssetCategory,
  AssetStatus,
  ComplianceValue,
  PaymentStatus,
  ProposalPriority,
  ProposalStatus,
  PurchaseOrderStatus,
} from "@/types";

/**
 * Finance & Procurement constants. The vocabularies mirror the backend
 * (`app/application/dtos/finance.py`) one-to-one — keep them in sync.
 */

/** PART 1 proposal business lifecycle (metadata vocabulary). */
export const PROPOSAL_STATUSES: { value: ProposalStatus; label: string }[] = [
  { value: "draft", label: "Draft" },
  { value: "submitted", label: "Submitted" },
  { value: "under_review", label: "Under Review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "ordered", label: "Ordered" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

export const PROPOSAL_PRIORITIES: { value: ProposalPriority; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export const PO_STATUSES: { value: PurchaseOrderStatus; label: string }[] = [
  { value: "issued", label: "Issued" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "partially_received", label: "Partially Received" },
  { value: "delivered", label: "Delivered" },
  { value: "closed", label: "Closed" },
  { value: "cancelled", label: "Cancelled" },
];

export const PAYMENT_STATUSES: { value: PaymentStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "partial", label: "Partial" },
  { value: "paid", label: "Paid" },
];

export const COMPLIANCE_VALUES: { value: ComplianceValue; label: string }[] = [
  { value: "compliant", label: "Compliant" },
  { value: "non_compliant", label: "Non-Compliant" },
  { value: "conditional", label: "Conditional" },
];

export const ASSET_STATUSES: { value: AssetStatus; label: string }[] = [
  { value: "in_service", label: "In Service" },
  { value: "in_store", label: "In Store" },
  { value: "under_maintenance", label: "Under Maintenance" },
  { value: "retired", label: "Retired" },
];

export const ASSET_CATEGORIES: { value: AssetCategory; label: string }[] = [
  { value: "equipment", label: "Equipment" },
  { value: "furniture", label: "Furniture" },
  { value: "computer", label: "Computer" },
  { value: "laboratory", label: "Laboratory" },
  { value: "library", label: "Library" },
  { value: "vehicle", label: "Vehicle" },
  { value: "software", label: "Software" },
  { value: "other", label: "Other" },
];

/** snake_case -> Title Case fallback (name fields that allow free text). */
export function labelFor(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/** PART 12 financial-year options (Indian FY, April-March), newest first. */
export function financialYearOptions(span = 5): { value: string; label: string }[] {
  const now = new Date();
  const start = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  const options: { value: string; label: string }[] = [];
  for (let i = 0; i < span; i += 1) {
    const year = start - i;
    const value = `${year}-${String((year + 1) % 100).padStart(2, "0")}`;
    options.push({ value, label: `FY ${value}` });
  }
  return options;
}

/** The FY (April-March) an ISO date falls into, e.g. "2026-02-10" -> "2025-26". */
export function financialYearOf(isoDate: string | null | undefined): string | null {
  if (!isoDate || isoDate.length < 7) return null;
  const year = Number(isoDate.slice(0, 4));
  const month = Number(isoDate.slice(5, 7));
  if (Number.isNaN(year) || Number.isNaN(month)) return null;
  const start = month >= 4 ? year : year - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

/** ₹ money formatting for card/list displays (integer-paisa values). */
export function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export const DEFAULT_PROPOSAL_PAGE_SIZE = 10;
export const DEFAULT_VENDOR_PAGE_SIZE = 10;
export const DEFAULT_ASSET_PAGE_SIZE = 20;
