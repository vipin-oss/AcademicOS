"""Use case: Finance report (PART 7).

Budget utilization (per project — the Finance PART 9 composition,
``budget_line_for_project``), vendor summary (``vendor_stats``), purchase
summary (``proposal_stats`` per proposal) and asset summary
(``asset_register_rows`` + category rollup). All reuse the frozen Finance
module's helpers — computed read, nothing stored, no duplicate logic.
"""
from __future__ import annotations

from app.application.dtos.finance import (
    KEY_DEPARTMENT,
    KEY_ESTIMATED_COST,
    KEY_GST_NUMBER,
    KEY_PROPOSAL_DATE,
    KEY_PROPOSAL_NUMBER,
    KEY_PROPOSAL_STATUS,
)
from app.application.dtos.reports import (
    CHART_BAR,
    ReportChart,
    ReportChartSeries,
    ReportView,
)
from app.application.queries.get_finance_report import GetFinanceReportQuery
from app.application.use_cases.finance.helpers import (
    asset_register_rows,
    budget_line_for_project,
    proposal_stats,
    vendor_stats,
)
from app.application.use_cases.reports.helpers import (
    Snapshot,
    bar_chart,
    count_by,
    department_matches,
    fmt_int,
    fmt_money,
    href_for,
    in_filter_window,
    kpi,
    linked_ids,
    meta_of,
    now_iso,
    parse_amount,
    sorted_buckets,
    table,
    title_case,
)
from app.application.validators.reports import (
    applied_filter_strings,
    assert_valid_filters,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository

KIND = "finance"
REPORT_TITLE = "Finance Report"


def _filtered_proposals(snapshot: Snapshot, filters) -> list[UniversalObject]:
    out: list[UniversalObject] = []
    for proposal in snapshot["proposals"]:
        meta = meta_of(proposal)
        if not in_filter_window(meta.get(KEY_PROPOSAL_DATE), filters):
            continue
        if not department_matches(meta.get(KEY_DEPARTMENT), filters.department):
            continue
        ids = linked_ids(proposal)
        if filters.project_id and filters.project_id not in ids:
            continue
        if filters.grant_id and filters.grant_id not in ids:
            continue
        out.append(proposal)
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def build_finance_report(repository: ObjectRepository, snapshot: Snapshot, filters) -> ReportView:
    filters = assert_valid_filters(filters, KIND)

    # Budget utilization — per project (narrowed by project filter).
    projects = [
        p for p in snapshot["projects"]
        if not filters.project_id or str(p.id) == filters.project_id
    ]
    projects.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    budget_rows: list[list[str]] = []
    budget_hrefs: list[list[str | None]] = []
    budget_lines: list[dict] = []
    total_approved = total_utilized = total_remaining = 0.0
    for project in projects:
        line = budget_line_for_project(repository, project)
        budget_lines.append(line)
        total_approved += line["approved"] or 0.0
        total_utilized += line["utilized"] or 0.0
        total_remaining += line["remaining"] if line["remaining"] is not None else 0.0
        budget_rows.append([
            project.title,
            fmt_money(line["approved"]),
            fmt_money(line["released"]),
            fmt_money(line["utilized"]),
            fmt_money(line["remaining"]),
        ])
        budget_hrefs.append([href_for(project), None, None, None, None])

    # Vendor summary.
    vendor_rows: list[list[str]] = []
    total_vendor_spend = 0.0
    for vendor in sorted(snapshot["vendors"], key=lambda o: (o.title.casefold(), str(o.id))):
        stats = vendor_stats(repository, str(vendor.id))
        total_vendor_spend += stats["spent"]
        vendor_rows.append([
            vendor.title,
            meta_of(vendor).get(KEY_GST_NUMBER) or "—",
            fmt_int(stats["proposals"]),
            fmt_int(stats["purchase_orders"]),
            fmt_int(stats["pending_bills"]),
            fmt_money(stats["spent"]),
        ])

    # Purchase summary (filtered proposals).
    proposals = _filtered_proposals(snapshot, filters)
    purchase_rows: list[list[str]] = []
    purchase_hrefs: list[list[str | None]] = []
    committed_total = 0.0
    total_spent = 0.0
    pending_bills = 0
    for proposal in proposals:
        meta = meta_of(proposal)
        stats = proposal_stats(meta)
        committed_total += stats["committed"] or 0.0
        total_spent += stats["spent"]
        pending_bills += stats["pending_bills"]
        purchase_rows.append([
            meta.get(KEY_PROPOSAL_NUMBER) or "—",
            proposal.title,
            title_case(meta.get(KEY_PROPOSAL_STATUS) or "draft"),
            meta.get(KEY_DEPARTMENT) or "—",
            fmt_money(parse_amount(meta.get(KEY_ESTIMATED_COST))),
            fmt_int(stats["quotations"]),
            fmt_int(stats["purchase_orders"]),
            fmt_money(stats["committed"]),
            fmt_money(stats["spent"]),
            fmt_int(stats["pending_bills"]),
        ])
        purchase_hrefs.append([None, href_for(proposal), None, None, None, None, None, None, None, None])

    # Asset summary.
    assets = list(asset_register_rows(repository))
    asset_rows: list[list[str]] = []
    asset_hrefs: list[list[str | None]] = []
    total_asset_cost = 0.0
    for entry in assets:
        row = entry.row
        total_asset_cost += parse_amount(row.get("cost")) or 0.0
        asset_rows.append([
            str(row.get("asset_id") or "—"),
            title_case(row.get("category")),
            str(row.get("item_name") or "—"),
            str(row.get("serial_number") or "—"),
            str(row.get("location") or "—"),
            str(row.get("assigned_to") or "—"),
            fmt_money(parse_amount(row.get("cost"))),
            title_case(row.get("status")),
            entry.proposal_title,
        ])
        asset_hrefs.append([None, None, None, None, None, None, None, None,
                            f"/finance/{entry.proposal_id}"])
    categories = sorted_buckets(count_by([title_case(r.row.get("category")) for r in assets]))
    statuses = sorted_buckets(count_by([title_case(r.row.get("status")) for r in assets]))

    tables = [
        table("budget_utilization", "Budget Utilization (per project)",
              ("Project", "Approved", "Grants Released", "Utilized", "Remaining"),
              budget_rows, budget_hrefs),
        table("vendor_summary", "Vendor Summary",
              ("Vendor", "GST Number", "Proposals", "Purchase Orders", "Pending Bills", "Paid Spend"),
              vendor_rows, [[None] * 6 for _ in vendor_rows]),
        table("purchase_summary", "Purchase Summary",
              ("Number", "Title", "Status", "Department", "Estimated Cost",
               "Quotations", "POs", "Committed", "Spent", "Pending Bills"),
              purchase_rows, purchase_hrefs),
        table("asset_summary", "Asset Summary",
              ("Asset ID", "Category", "Item", "Serial", "Location",
               "Assigned To", "Cost", "Status", "Proposal"),
              asset_rows, asset_hrefs),
        table("assets_by_category", "Assets by Category", ("Category", "Assets"),
              [[c, fmt_int(n)] for c, n in categories]),
        table("assets_by_status", "Assets by Status", ("Status", "Assets"),
              [[s, fmt_int(n)] for s, n in statuses]),
    ]
    charts = [
        ReportChart(
            key="budget_by_project",
            title="Budget by Project (₹)",
            kind=CHART_BAR,
            labels=[p.title for p in projects],
            series=[
                ReportChartSeries(name="Approved",
                                  data=[float(line["approved"] or 0.0) for line in budget_lines]),
                ReportChartSeries(name="Utilized",
                                  data=[float(line["utilized"] or 0.0) for line in budget_lines]),
            ],
        ),
        bar_chart("assets_by_category", "Assets by Category",
                  [c for c, _ in categories], [float(n) for _, n in categories],
                  name="Assets"),
    ]
    kpis = [
        kpi("Budget Approved", fmt_money(total_approved)),
        kpi("Budget Utilized", fmt_money(total_utilized)),
        kpi("Budget Remaining", fmt_money(total_remaining)),
        kpi("Vendors", fmt_int(len(snapshot["vendors"]))),
        kpi("Proposals", fmt_int(len(proposals))),
        kpi("Committed (POs)", fmt_money(committed_total)),
        kpi("Pending Bills", fmt_int(pending_bills)),
        kpi("Assets", fmt_int(len(assets))),
        kpi("Asset Cost", fmt_money(total_asset_cost)),
    ]
    return ReportView(
        kind=KIND,
        title=REPORT_TITLE,
        generated_at=now_iso(),
        applied_filters=applied_filter_strings(filters),
        kpis=kpis,
        tables=tables,
        charts=charts,
    )


class GetFinanceReportUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetFinanceReportQuery) -> ReportView:
        return build_finance_report(
            self._repository, Snapshot(self._repository), query.filters
        )
