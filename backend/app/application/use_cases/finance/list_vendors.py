"""Use case: List Vendors — PART 3 registry search + pagination.

Mirrors ``ListCommitteesUseCase``: token-AND ``q`` over the vendor haystack
(name/GST/PAN/contact/email), name-ordered pagination.
"""
from __future__ import annotations

from app.application.dtos.finance import ListVendorsResult, VendorOutput
from app.application.queries.list_vendors import ListVendorsQuery
from app.application.use_cases.finance.helpers import vendor_stats
from app.application.validators.finance import assert_valid_list_query
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def _haystack(output: VendorOutput) -> str:
    meta = output.metadata
    parts = [
        output.name,
        meta.get("gst_number"),
        meta.get("pan"),
        meta.get("contact_person"),
        meta.get("email"),
        meta.get("phone"),
        meta.get("address"),
    ]
    return " ".join(part for part in parts if part).casefold()


class ListVendorsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListVendorsQuery) -> ListVendorsResult:
        assert_valid_list_query(query.page, query.page_size)

        # M27 fast path: an unfiltered directory listing pages directly in SQL
        # (count + find, title_ci — the registry's name order, since
        # VendorOutput.name is the object title) instead of loading every
        # VENDOR row and hydrating all JSONB metadata before slicing. The slow
        # path below is preserved for the q haystack filter.
        plain = not (query.q or "").strip()
        if plain:
            total_count = self._repository.count(object_type=ObjectType.VENDOR)
            page = self._repository.find(
                object_type=ObjectType.VENDOR,
                page=query.page,
                page_size=query.page_size,
                sort_by="title_ci",
                order="asc",
            )
            items: list[VendorOutput] = []
            for obj in page:
                out = VendorOutput.from_domain(obj, [])
                out.stats = vendor_stats(self._repository, str(obj.id))
                items.append(out)
            return ListVendorsResult(
                items=items,
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
            )

        objects = self._repository.find_by_type(ObjectType.VENDOR)

        tokens = (query.q or "").strip().casefold().split()
        matched: list[VendorOutput] = []
        for obj in objects:
            out = VendorOutput.from_domain(obj, [])
            if tokens:
                haystack = _haystack(out)
                if any(token not in haystack for token in tokens):
                    continue
            out.stats = vendor_stats(self._repository, str(obj.id))
            matched.append(out)

        matched.sort(key=lambda item: (item.name.casefold(), item.id))
        total = len(matched)
        start = (query.page - 1) * query.page_size
        items = matched[start:start + query.page_size]
        return ListVendorsResult(
            items=items, total_count=total, page=query.page, page_size=query.page_size
        )
