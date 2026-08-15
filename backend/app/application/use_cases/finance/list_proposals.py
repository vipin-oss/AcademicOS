"""Use case: List Purchase Proposals — PART 12 search + filters + pagination.

Mirrors ``ListCommitteesUseCase``: token-AND ``q`` over an own-metadata
haystack PLUS vendor names (the member-name haystack precedent), vendor /
project / grant / status / department / financial_year filters (Indian FY,
April-March), title-ordered pagination. List rows go through the ONE shared
enrichment (``enrich_proposal_output``) — resolved vendor names, the PART 2
approval meeting, normalised link groups and the computed stats block — so a
directory row carries exactly the workspace payload's denormalised shape.
"""
from __future__ import annotations

from app.application.dtos.finance import (
    KEY_DEPARTMENT,
    KEY_PROPOSAL_DATE,
    KEY_PROPOSAL_STATUS,
    ListProposalsResult,
    ProposalOutput,
)
from app.application.queries.list_proposals import ListProposalsQuery
from app.application.use_cases.finance.helpers import (
    enrich_proposal_output,
    financial_year_bounds,
    resolve_vendors,
)
from app.application.validators.finance import (
    assert_optional_financial_year,
    assert_valid_list_query,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


def _meta(obj) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


class ListProposalsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListProposalsQuery) -> ListProposalsResult:
        assert_valid_list_query(query.page, query.page_size)
        assert_optional_financial_year(query.financial_year)

        # M27 fast path: an unfiltered directory listing pages directly in SQL
        # (count + find, title_ci — the registry's name order) instead of
        # loading every PURCHASE row and hydrating all JSONB metadata before
        # slicing. The slow path below is preserved for queries with criteria
        # the SQL projection cannot express (q tokens, vendor/project/grant/
        # status/department/financial-year filters).
        plain = (
            not (query.q or "").strip()
            and not (query.vendor or "").strip()
            and not (query.project or "").strip()
            and not (query.grant or "").strip()
            and not (query.status or "").strip()
            and not (query.department or "").strip()
            and not (query.financial_year or "").strip()
        )
        if plain:
            total_count = self._repository.count(object_type=ObjectType.PURCHASE)
            page = self._repository.find(
                object_type=ObjectType.PURCHASE,
                page=query.page,
                page_size=query.page_size,
                sort_by="title_ci",
                order="asc",
            )
            items: list[ProposalOutput] = []
            for obj in page:
                link_ids = [
                    rel.target
                    for rel in obj.relationships
                    if rel.kind is RelationshipKind.RELATED_TO
                ]
                linked_by_id = {
                    str(o.id): o for o in self._repository.find_by_ids(link_ids)
                }
                out = ProposalOutput.from_domain(obj, [], linked_by_id=linked_by_id)
                enrich_proposal_output(self._repository, obj, out)
                items.append(out)
            return ListProposalsResult(
                items=items,
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
            )

        objects = self._repository.find_by_type(ObjectType.PURCHASE)

        tokens = (query.q or "").strip().casefold().split()
        vendor_tokens = (query.vendor or "").strip().casefold().split()
        wanted_dept = (query.department or "").strip().casefold()
        wanted_project = (query.project or "").strip()
        wanted_grant = (query.grant or "").strip()
        fy_window = (
            financial_year_bounds(query.financial_year.strip())
            if (query.financial_year or "").strip()
            else None
        )

        matched: list[ProposalOutput] = []
        for obj in objects:
            meta = _meta(obj)
            if query.status and (meta.get(KEY_PROPOSAL_STATUS) or "draft") != query.status:
                continue
            if wanted_dept and wanted_dept not in (meta.get(KEY_DEPARTMENT) or "").strip().casefold():
                continue
            if fy_window is not None:
                date = (meta.get(KEY_PROPOSAL_DATE) or "").strip()
                if not (fy_window[0] <= date <= fy_window[1]):
                    continue
            if wanted_project and not any(
                str(rel.target) == wanted_project for rel in obj.relationships
            ):
                continue
            if wanted_grant and not any(
                str(rel.target) == wanted_grant for rel in obj.relationships
            ):
                continue

            link_ids = [
                rel.target for rel in obj.relationships
                if rel.kind is RelationshipKind.RELATED_TO
            ]
            linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(link_ids)}
            out = ProposalOutput.from_domain(obj, [], linked_by_id=linked_by_id)
            enrich_proposal_output(self._repository, obj, out)

            vendor_names = " ".join(
                resolve_vendors(
                    self._repository,
                    out.quotations + out.comparative + out.purchase_orders + out.bills,
                ).values()
            ).casefold()
            if vendor_tokens and any(token not in vendor_names for token in vendor_tokens):
                continue
            if tokens:
                haystack = " ".join(
                    part
                    for part in (
                        out.title,
                        out.proposal_number,
                        out.department,
                        out.budget_head,
                        out.purpose,
                        out.notes,
                        vendor_names,
                        out.requested_name,
                    )
                    if part
                ).casefold()
                if any(token not in haystack for token in tokens):
                    continue
            matched.append(out)

        matched.sort(key=lambda item: (item.title.casefold(), item.id))
        total = len(matched)
        start = (query.page - 1) * query.page_size
        items = matched[start:start + query.page_size]
        return ListProposalsResult(
            items=items, total_count=total, page=query.page, page_size=query.page_size
        )
