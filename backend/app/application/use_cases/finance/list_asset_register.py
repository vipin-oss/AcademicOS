"""Use case: PART 8 asset register — every asset row across proposals.

Computed aggregate (the dashboard precedent): assets ride as proposal
metadata sections; this lens flattens them into a register with proposal
context. q over item/asset/serial/location + category + status filters,
paginated.
"""
from __future__ import annotations

from app.application.dtos.finance import ASSET_CATEGORIES, ASSET_STATUSES, ListAssetsResult
from app.application.queries.list_asset_register import ListAssetRegisterQuery
from app.application.use_cases.finance.helpers import (
    asset_register_rows,
    resolve_vendors,
)
from app.application.validators.finance import assert_choice, assert_valid_list_query
from app.domain.repositories.object_repository import ObjectRepository


class ListAssetRegisterUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListAssetRegisterQuery) -> ListAssetsResult:
        assert_valid_list_query(query.page, query.page_size)
        assert_choice(query.category, ASSET_CATEGORIES, "category")
        assert_choice(query.status, ASSET_STATUSES, "status")

        rows = asset_register_rows(self._repository)
        names = resolve_vendors(self._repository, [item.row for item in rows])
        for item in rows:
            name = names.get(str(item.row.get("vendor_id") or ""))
            if name is not None:
                item.row["vendor_name"] = name

        tokens = (query.q or "").strip().casefold().split()
        wanted_category = (query.category or "").strip()
        wanted_status = (query.status or "").strip()

        def matches(item) -> bool:
            row = item.row
            if wanted_category and (row.get("category") or "") != wanted_category:
                return False
            if wanted_status and (row.get("status") or "in_service") != wanted_status:
                return False
            if tokens:
                haystack = " ".join(
                    part
                    for part in (
                        str(row.get("item_name") or ""),
                        str(row.get("asset_id") or ""),
                        str(row.get("serial_number") or ""),
                        str(row.get("location") or ""),
                        str(row.get("assigned_to") or ""),
                        str(item.proposal_number or ""),
                        item.proposal_title,
                    )
                    if part
                ).casefold()
                if any(token not in haystack for token in tokens):
                    return False
            return True

        matched = [item for item in rows if matches(item)]
        total = len(matched)
        start = (query.page - 1) * query.page_size
        items = matched[start:start + query.page_size]
        return ListAssetsResult(
            items=items, total_count=total, page=query.page, page_size=query.page_size
        )
