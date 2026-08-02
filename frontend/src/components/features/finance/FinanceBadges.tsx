import { Badge } from "@/components/features/documents/DocumentBadge";
import { labelFor } from "@/lib/finance/constants";
import { titleCase } from "@/lib/utils";
import type {
  AssetStatus,
  ComplianceValue,
  PaymentStatus,
  ProposalPriority,
  ProposalStatus,
  PurchaseOrderStatus,
  ResearchObjectStatus,
} from "@/types";

/**
 * Finance badges. The badge shell (`Badge`) is REUSED from the Documents
 * module (single implementation); the status styles follow the frozen
 * vocabulary (same mapping as Committees/Research/Publications).
 */

const UNIVERSAL_STATUS_STYLES: Record<ResearchObjectStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--success-subtle)] text-[var(--success)]",
  archived: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function UniversalStatusBadge({ status }: { status: ResearchObjectStatus }) {
  return (
    <Badge className={UNIVERSAL_STATUS_STYLES[status] ?? UNIVERSAL_STATUS_STYLES.draft}>
      <span className="sr-only">Status: </span>
      {titleCase(status)}
    </Badge>
  );
}

const PROPOSAL_STATUS_STYLES: Record<string, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  submitted: "bg-[var(--info-subtle)] text-[var(--info)]",
  under_review: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  approved: "bg-[var(--success-subtle)] text-[var(--success)]",
  rejected: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  ordered: "bg-[var(--accent-subtle)] text-[var(--accent)]",
  completed: "bg-[var(--success-subtle)] text-[var(--success)]",
  cancelled: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function ProposalStatusBadge({ status }: { status: ProposalStatus }) {
  return (
    <Badge className={PROPOSAL_STATUS_STYLES[status] ?? PROPOSAL_STATUS_STYLES.draft}>
      <span className="sr-only">Proposal status: </span>
      {labelFor(status)}
    </Badge>
  );
}

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  medium: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  low: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function PriorityBadge({ priority }: { priority: ProposalPriority }) {
  return (
    <Badge className={PRIORITY_STYLES[priority] ?? PRIORITY_STYLES.low}>
      <span className="sr-only">Priority: </span>
      {titleCase(priority)}
    </Badge>
  );
}

const PO_STATUS_STYLES: Record<string, string> = {
  issued: "bg-[var(--info-subtle)] text-[var(--info)]",
  acknowledged: "bg-[var(--info-subtle)] text-[var(--info)]",
  partially_received: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  delivered: "bg-[var(--success-subtle)] text-[var(--success)]",
  closed: "bg-[var(--success-subtle)] text-[var(--success)]",
  cancelled: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function PoStatusBadge({ status }: { status: PurchaseOrderStatus }) {
  return (
    <Badge className={PO_STATUS_STYLES[status] ?? PO_STATUS_STYLES.issued}>
      <span className="sr-only">PO status: </span>
      {labelFor(status)}
    </Badge>
  );
}

const PAYMENT_STYLES: Record<string, string> = {
  pending: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  partial: "bg-[var(--info-subtle)] text-[var(--info)]",
  paid: "bg-[var(--success-subtle)] text-[var(--success)]",
};

export function PaymentStatusBadge({ status }: { status: PaymentStatus }) {
  return (
    <Badge className={PAYMENT_STYLES[status] ?? PAYMENT_STYLES.pending}>
      <span className="sr-only">Payment: </span>
      {titleCase(status)}
    </Badge>
  );
}

const COMPLIANCE_STYLES: Record<string, string> = {
  compliant: "bg-[var(--success-subtle)] text-[var(--success)]",
  non_compliant: "bg-[var(--danger-subtle)] text-[var(--danger)]",
  conditional: "bg-[var(--warning-subtle)] text-[var(--warning)]",
};

export function ComplianceBadge({ value }: { value: ComplianceValue }) {
  return (
    <Badge className={COMPLIANCE_STYLES[value] ?? COMPLIANCE_STYLES.conditional}>
      {labelFor(value)}
    </Badge>
  );
}

const ASSET_STYLES: Record<string, string> = {
  in_service: "bg-[var(--success-subtle)] text-[var(--success)]",
  in_store: "bg-[var(--info-subtle)] text-[var(--info)]",
  under_maintenance: "bg-[var(--warning-subtle)] text-[var(--warning)]",
  retired: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
};

export function AssetStatusBadge({ status }: { status: AssetStatus }) {
  return (
    <Badge className={ASSET_STYLES[status] ?? ASSET_STYLES.in_service}>
      <span className="sr-only">Asset status: </span>
      {labelFor(status)}
    </Badge>
  );
}
