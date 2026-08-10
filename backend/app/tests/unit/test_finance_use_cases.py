"""Unit tests for the Finance & Procurement use cases (no framework deps).

Mirrors ``test_committee_use_cases.py``: an in-memory ``ObjectRepository``
exercises the slice without any database, filesystem, network, or HTTP.
"""
from __future__ import annotations

import pytest

from app.application.commands.create_proposal import CreateProposalCommand
from app.application.commands.create_vendor import CreateVendorCommand
from app.application.commands.delete_proposal import DeleteProposalCommand
from app.application.commands.delete_vendor import DeleteVendorCommand
from app.application.commands.update_proposal import UpdateProposalCommand
from app.application.commands.update_vendor import UpdateVendorCommand
from app.application.dtos.finance import (
    CreateProposalInput,
    CreateVendorInput,
    UpdateProposalInput,
    UpdateVendorInput,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_finance_dashboard import GetFinanceDashboardQuery
from app.application.queries.get_proposal import GetProposalQuery
from app.application.queries.get_vendor import GetVendorQuery
from app.application.queries.list_asset_register import ListAssetRegisterQuery
from app.application.queries.list_budget_lines import ListBudgetLinesQuery
from app.application.queries.list_proposals import ListProposalsQuery
from app.application.queries.list_vendors import ListVendorsQuery
from app.application.use_cases.finance.create_proposal import CreateProposalUseCase
from app.application.use_cases.finance.create_vendor import CreateVendorUseCase
from app.application.use_cases.finance.delete_proposal import DeleteProposalUseCase
from app.application.use_cases.finance.delete_vendor import DeleteVendorUseCase
from app.application.use_cases.finance.get_finance_dashboard import (
    GetFinanceDashboardUseCase,
)
from app.application.use_cases.finance.get_proposal import GetProposalUseCase
from app.application.use_cases.finance.get_vendor import GetVendorUseCase
from app.application.use_cases.finance.list_asset_register import ListAssetRegisterUseCase
from app.application.use_cases.finance.list_budget_lines import ListBudgetLinesUseCase
from app.application.use_cases.finance.list_proposals import ListProposalsUseCase
from app.application.use_cases.finance.list_vendors import ListVendorsUseCase
from app.application.use_cases.finance.update_proposal import UpdateProposalUseCase
from app.application.use_cases.finance.update_vendor import UpdateVendorUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry


class InMemoryObjectRepository(ObjectRepository):
    # String-keyed store — accepts ObjectId and wire strings alike, exactly
    # like the production SQLAlchemy adapter (which stringifies ids).
    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}

    def save(self, entity: UniversalObject, *, outbox_events=()) -> None:
        self._store[str(entity.id)] = entity

    def get_by_id(self, id) -> UniversalObject | None:
        return self._store.get(str(id))

    def find_by_ids(self, ids: list) -> list[UniversalObject]:
        return [self._store[str(i)] for i in ids if str(i) in self._store]

    def exists(self, id) -> bool:
        return str(id) in self._store

    def delete(self, id) -> None:
        self._store.pop(str(id), None)

    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.object_type == object_type]

    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        return [o for o in self._store.values() if o.status == status]

    def find_related(self, object_id, kind=None) -> list:
        obj = self._store.get(str(object_id))
        return [] if obj is None else obj.related_ids(kind)
    def find_inbound(
        self, object_id: ObjectId, kind=None
    ) -> list[ObjectId]:
        return [
            o.id
            for o in self._store.values()
            if any(r.target == object_id and (kind is None or r.kind == kind) for r in o.relationships)
        ]

    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        out: list[UniversalObject] = []
        for o in self._store.values():
            v = o.metadata.get_value(key)
            if v is not None and (value is None or v == value):
                out.append(o)
    def find(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
        page: int = 1,
        page_size: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> list[UniversalObject]:
        if page < 1:
            raise ValueError("page must be >= 1.")
        if page_size < 0:
            raise ValueError("page_size must be >= 0.")
        if sort_by is not None and sort_by not in (
            "id", "object_type", "title", "title_ci", "status", "version",
        ):
            raise ValueError(f"Unsupported sort_by: {sort_by!r}")
        if order not in ("asc", "desc"):
            raise ValueError(f"Unsupported order: {order!r}")

        items = [
            o
            for o in self._store.values()
            if (object_type is None or o.object_type == object_type)
            and (status is None or o.status == status)
            and (
                metadata_key is None
                or (
                    (value := o.metadata.get_value(metadata_key)) is not None
                    and (metadata_value is None or value == metadata_value)
                )
            )
        ]
        effective_sort = sort_by if sort_by is not None else ("id" if page_size > 0 else None)
        if effective_sort is not None:
            reverse = order == "desc"
            if effective_sort == "id":
                items.sort(key=lambda o: str(o.id), reverse=reverse)
            elif effective_sort == "object_type":
                items.sort(key=lambda o: o.object_type.value, reverse=reverse)
            elif effective_sort in ("title", "title_ci"):
                items.sort(key=lambda o: o.title, reverse=reverse)
            elif effective_sort == "status":
                items.sort(key=lambda o: o.status.value, reverse=reverse)
            elif effective_sort == "version":
                items.sort(key=lambda o: o.version, reverse=reverse)
        if page_size > 0:
            start = (page - 1) * page_size
            items = items[start : start + page_size]
        return items

    def count(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> int:
        return len(
            self.find(
                object_type=object_type,
                status=status,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
            )
        )


    def list(self) -> list[UniversalObject]:
        return list(self._store.values())


# ---------------------------------------------------------------------------
# Fabrication helpers (mirror the other suites' style)
# ---------------------------------------------------------------------------
def _meta_entries(**pairs: str) -> tuple:
    return tuple(
        MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
        for key, value in pairs.items()
    )


def _faculty(repo: InMemoryObjectRepository, title: str) -> UniversalObject:
    obj = UniversalObject.create(
        object_type=ObjectType.FACULTY, title=title, created_by="registrar:1",
        status=ObjectStatus.ACTIVE,
    )
    repo.save(obj)
    obj.pop_domain_events()
    return obj


def _document(repo: InMemoryObjectRepository, title: str) -> UniversalObject:
    obj = UniversalObject.create(
        object_type=ObjectType.DOCUMENT, title=title, created_by="registrar:1",
        status=ObjectStatus.ACTIVE,
    )
    repo.save(obj)
    obj.pop_domain_events()
    return obj


def _meeting(repo: InMemoryObjectRepository, title: str) -> UniversalObject:
    from app.domain.value_objects.metadata import Metadata

    obj = UniversalObject.create(
        object_type=ObjectType.MEETING, title=title, created_by="registrar:1",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=_meta_entries(meeting_number="3", meeting_date="2026-07-28", mode="hybrid")),
    )
    repo.save(obj)
    obj.pop_domain_events()
    return obj


def _vendor_input(**overrides) -> CreateVendorInput:
    data = {
        "name": "Acme Scientific Supplies",
        "created_by": "finance:1",
        "status": ObjectStatus.ACTIVE,
        "gst_number": "07AABCS1429B1Z5",
        "pan": "AABCS1429B",
        "contact_person": "Ravi Kumar",
        "email": "sales@acme.example",
        "phone": "9810012345",
        "address": "Okhla, New Delhi",
        "bank_details": {"bank_name": "SBI", "account_number": "12345678901", "ifsc": "SBIN0001234"},
        "notes": "Preferred lab supplier.",
        "tags": ["lab"],
    }
    data.update(overrides)
    return CreateVendorInput(**data)


def _make_vendor(repo: InMemoryObjectRepository, **overrides) -> UniversalObject:
    out = CreateVendorUseCase(repo).execute(CreateVendorCommand(input=_vendor_input(**overrides)))
    return repo.get_by_id(out.id)


def _quotation(vendor_id: str, amount: str = "440000", **extra) -> dict:
    row = {"vendor_id": vendor_id, "quotation_date": "2026-07-10", "amount": amount}
    row.update(extra)
    return row


def _proposal_input(vendor_id: str, **overrides) -> CreateProposalInput:
    data = {
        "title": "HPC Nodes Purchase",
        "created_by": "finance:1",
        "status": ObjectStatus.DRAFT,
        "proposal_number": "PP-2026-001",
        "department": "Physics",
        "proposal_date": "2026-07-15",
        "purpose": "Compute expansion",
        "budget_head": "Capital",
        "estimated_cost": "450000",
        "proposal_status": "submitted",
        "priority": "high",
        "tags": ["it"],
        "quotations": [_quotation(vendor_id)],
        "purchase_orders": [
            {"po_number": "PO-1", "po_date": "2026-07-20", "vendor_id": vendor_id,
             "amount": "440000", "status": "issued", "delivery_date": "2026-08-30"}
        ],
        "bills": [
            {"bill_number": "B-1", "invoice_number": "INV-1", "vendor_id": vendor_id,
             "bill_date": "2026-08-01", "amount": "440000", "gst_amount": "79200",
             "payment_status": "paid", "paid_date": "2026-08-02"}
        ],
        "assets": [
            {"asset_id": "AST-1", "category": "computer", "item_name": "HPC Node",
             "serial_number": "SN123", "location": "Server Room",
             "purchase_date": "2026-08-01", "cost": "440000", "status": "in_service"}
        ],
    }
    data.update(overrides)
    return CreateProposalInput(**data)


def _make_proposal(repo: InMemoryObjectRepository, vendor_id: str, **overrides):
    return CreateProposalUseCase(repo).execute(
        CreateProposalCommand(input=_proposal_input(vendor_id, **overrides))
    )


# ---------------------------------------------------------------------------
# Vendor slice (PART 3)
# ---------------------------------------------------------------------------
def test_create_vendor_persists_core_fields_and_bank_details() -> None:
    repo = InMemoryObjectRepository()
    out = CreateVendorUseCase(repo).execute(CreateVendorCommand(input=_vendor_input()))
    stored = repo.get_by_id(out.id)
    assert stored is not None and stored.object_type is ObjectType.VENDOR
    assert stored.title == "Acme Scientific Supplies"
    assert out.gst_number == "07AABCS1429B1Z5"
    assert out.bank_details["ifsc"] == "SBIN0001234"
    assert out.tags == ["lab"]
    assert any("Created" in event for event in out.events)


def test_create_vendor_rejects_duplicate_gst_and_name_and_bad_codes() -> None:
    repo = InMemoryObjectRepository()
    _make_vendor(repo)
    with pytest.raises(ObjectAlreadyExistsError):
        CreateVendorUseCase(repo).execute(
            CreateVendorCommand(input=_vendor_input(name="Other Co"))
        )  # same GST
    with pytest.raises(ObjectAlreadyExistsError):
        CreateVendorUseCase(repo).execute(
            CreateVendorCommand(input=_vendor_input(gst_number=None, pan=None))
        )  # same name
    with pytest.raises(ValidationError):
        CreateVendorUseCase(repo).execute(
            CreateVendorCommand(input=_vendor_input(name="Zed Traders", gst_number="not-a-gst"))
        )
    with pytest.raises(ValidationError):
        CreateVendorUseCase(repo).execute(
            CreateVendorCommand(input=_vendor_input(name="Zed Traders", email="not-an-email"))
        )


def test_update_vendor_merges_and_rechecks_duplicates() -> None:
    repo = InMemoryObjectRepository()
    first = _make_vendor(repo)
    _make_vendor(repo, name="Beta Instruments", gst_number="07BBCSI9999C1Z2", pan=None)
    out = UpdateVendorUseCase(repo).execute(
        UpdateVendorCommand(
            object_id=str(first.id),
            input=UpdateVendorInput(actor="finance:2", phone="9999999999"),
        )
    )
    assert out.phone == "9999999999"
    assert out.gst_number == "07AABCS1429B1Z5"  # untouched
    with pytest.raises(ObjectAlreadyExistsError):
        UpdateVendorUseCase(repo).execute(
            UpdateVendorCommand(
                object_id=str(first.id),
                input=UpdateVendorInput(actor="finance:2", gst_number="07BBCSI9999C1Z2"),
            )
        )
    with pytest.raises(ObjectNotFoundError):
        UpdateVendorUseCase(repo).execute(
            UpdateVendorCommand(
                object_id="obj:vendor:NOPE", input=UpdateVendorInput(actor="finance:2", phone="1")
            )
        )


def test_list_vendors_search_and_delete() -> None:
    repo = InMemoryObjectRepository()
    _make_vendor(repo)
    _make_vendor(repo, name="Beta Instruments", gst_number="07BBCSI9999C1Z2", pan=None)
    listed = ListVendorsUseCase(repo).execute(ListVendorsQuery(q="acme 07aabcs"))
    assert listed.total_count == 1
    assert listed.items[0].name == "Acme Scientific Supplies"
    assert listed.items[0].stats["proposals"] == 0
    with pytest.raises(ValidationError):
        ListVendorsUseCase(repo).execute(ListVendorsQuery(page=0))
    gone = DeleteVendorUseCase(repo)
    with pytest.raises(ObjectNotFoundError):
        gone.execute(DeleteVendorCommand(object_id="obj:vendor:NOPE"))
    acme = ListVendorsUseCase(repo).execute(ListVendorsQuery(q="acme")).items[0]
    gone.execute(DeleteVendorCommand(object_id=acme.id))
    assert ListVendorsUseCase(repo).execute(ListVendorsQuery()).total_count == 1


# ---------------------------------------------------------------------------
# Proposal slice (PARTS 1/2/4-8)
# ---------------------------------------------------------------------------
def test_create_proposal_full_enriched_round_trip() -> None:
    repo = InMemoryObjectRepository()
    vendor = _make_vendor(repo)
    requester = _faculty(repo, "Dr. Nandini Rao")
    meeting = _meeting(repo, "7th Purchase Committee Meeting")
    document = _document(repo, "Quote A.pdf")
    project = UniversalObject.create(
        object_type=ObjectType.RESEARCH_PROJECT, title="Quantum Sensors",
        created_by="registrar:1", status=ObjectStatus.ACTIVE,
    )
    repo.save(project)
    project.pop_domain_events()

    out = _make_proposal(
        repo,
        str(vendor.id),
        requested_by=str(requester.id),
        approval_meeting_id=str(meeting.id),
        quotations=[_quotation(str(vendor.id), document_ids=[str(document.id)])],
        comparative=[
            {"vendor_id": str(vendor.id), "amount": "440000",
             "technical_compliance": "compliant", "financial_compliance": "compliant",
             "recommended": True}
        ],
        minutes="Approved by the purchase committee.",
        recommendations="Award to the L1 vendor.",
        projects=[str(project.id)],
    )
    assert out.requested_name == "Dr. Nandini Rao"
    assert out.quotations[0]["vendor_name"] == "Acme Scientific Supplies"
    assert out.quotations[0]["supporting_documents"] == [
        {"id": str(document.id), "title": "Quote A.pdf"}
    ]
    assert out.comparative[0]["recommended"] is True
    assert out.approval_meeting is not None
    assert out.approval_meeting.meeting_number == "3"
    assert out.links["projects"][0]["title"] == "Quantum Sensors"
    # spent = 440000 + 79200 GST on the PAID bill
    assert out.stats["spent"] == 519200.0
    assert out.stats["purchase_orders"] == 1
    stored = repo.get_by_id(out.id)
    assert stored is not None and stored.object_type is ObjectType.PURCHASE


def test_create_proposal_duplicate_number_and_triple_conflict() -> None:
    repo = InMemoryObjectRepository()
    vendor = _make_vendor(repo)
    _make_proposal(repo, str(vendor.id))
    with pytest.raises(ObjectAlreadyExistsError):
        _make_proposal(repo, str(vendor.id), title="Another Title")  # same number
    with pytest.raises(ObjectAlreadyExistsError):
        _make_proposal(
            repo, str(vendor.id), proposal_number=None
        )  # same title+department+date
    # A different date clears the triple.
    ok = _make_proposal(repo, str(vendor.id), proposal_number=None, proposal_date="2026-07-16")
    assert ok.proposal_number is None


def test_create_proposal_reference_and_shape_validation() -> None:
    repo = InMemoryObjectRepository()
    vendor = _make_vendor(repo)
    requester = _faculty(repo, "Dr. X")
    # Section vendor must be a VENDOR object.
    with pytest.raises(ValidationError):
        _make_proposal(
            repo, str(vendor.id), title="Bad Ref",
            quotations=[_quotation(str(requester.id))],
        )
    # requested_by must be FACULTY.
    with pytest.raises(ValidationError):
        _make_proposal(repo, str(vendor.id), title="Bad Requester", requested_by=str(vendor.id))
    # Link targets must carry the group's type.
    with pytest.raises(ValidationError):
        _make_proposal(repo, str(vendor.id), title="Bad Link", projects=[str(vendor.id)])
    # Unknown section keys are rejected by the validator.
    with pytest.raises(ValidationError):
        _make_proposal(
            repo, str(vendor.id), title="Bad Keys",
            quotations=[_quotation(str(vendor.id), bogus="x")],
        )
    # Only one comparative row may be recommended.
    other = _make_vendor(repo, name="Beta Instruments", gst_number=None, pan=None)
    with pytest.raises(ValidationError):
        _make_proposal(
            repo, str(vendor.id), title="Two Recommended",
            comparative=[
                {"vendor_id": str(vendor.id), "amount": "1", "recommended": True},
                {"vendor_id": str(other.id), "amount": "2", "recommended": True},
            ],
        )
    # Duplicate po_number inside one proposal is rejected; bad amounts too.
    with pytest.raises(ValidationError):
        _make_proposal(
            repo, str(vendor.id), title="Dup PO",
            purchase_orders=[
                {"po_number": "PO-1", "vendor_id": str(vendor.id), "amount": "10"},
                {"po_number": "po-1", "vendor_id": str(vendor.id), "amount": "20"},
            ],
        )
    with pytest.raises(ValidationError):
        _make_proposal(
            repo, str(vendor.id), title="Bad Amount",
            quotations=[_quotation(str(vendor.id), amount="-5")],
        )


def test_list_proposals_filters_and_pagination() -> None:
    repo = InMemoryObjectRepository()
    vendor = _make_vendor(repo)
    _make_proposal(repo, str(vendor.id))
    _make_proposal(
        repo, str(vendor.id), title="Library Furniture Purchase",
        proposal_number="PP-2026-002", department="Library",
        proposal_date="2026-02-10", proposal_status="approved", quotations=[],
    )
    listed = ListProposalsUseCase(repo).execute(ListProposalsQuery())
    assert listed.total_count == 2
    by_q = ListProposalsUseCase(repo).execute(ListProposalsQuery(q="hpc physics"))
    assert by_q.total_count == 1
    by_fy = ListProposalsUseCase(repo).execute(ListProposalsQuery(financial_year="2025-26"))
    assert by_fy.total_count == 1 and by_fy.items[0].department == "Library"
    by_vendor = ListProposalsUseCase(repo).execute(ListProposalsQuery(vendor="acme"))
    assert by_vendor.total_count == 2
    by_vendor_miss = ListProposalsUseCase(repo).execute(ListProposalsQuery(vendor="unknown"))
    assert by_vendor_miss.total_count == 0
    by_status = ListProposalsUseCase(repo).execute(ListProposalsQuery(status="approved"))
    assert by_status.total_count == 1
    with pytest.raises(ValidationError):
        ListProposalsUseCase(repo).execute(ListProposalsQuery(financial_year="2026-26"))
    assert ListProposalsUseCase(repo).execute(
        ListProposalsQuery(page=2, page_size=1)
    ).total_count == 2


def test_update_proposal_merge_and_section_replace() -> None:
    repo = InMemoryObjectRepository()
    vendor = _make_vendor(repo)
    out = _make_proposal(repo, str(vendor.id))
    # Scalar merge: sections ride through untouched.
    merged = UpdateProposalUseCase(repo).execute(
        UpdateProposalCommand(
            object_id=out.id,
            input=UpdateProposalInput(actor="finance:2", proposal_status="approved"),
        )
    )
    assert merged.proposal_status == "approved"
    assert merged.quotations[0]["vendor_name"] == "Acme Scientific Supplies"
    assert merged.stats["spent"] == 519200.0
    # Section group-replace with a new row set.
    replaced = UpdateProposalUseCase(repo).execute(
        UpdateProposalCommand(
            object_id=out.id,
            input=UpdateProposalInput(
                actor="finance:2",
                quotations=[_quotation(str(vendor.id), amount="445000", remarks="Revised quote")],
            ),
        )
    )
    assert len(replaced.quotations) == 1
    assert replaced.quotations[0]["remarks"] == "Revised quote"
    # Duplicate re-check bumps into nothing (number kept by merge).
    with pytest.raises(ObjectAlreadyExistsError):
        _make_proposal(repo, str(vendor.id), title="Clash", proposal_number="PP-2026-001")
    with pytest.raises(ObjectNotFoundError):
        UpdateProposalUseCase(repo).execute(
            UpdateProposalCommand(
                object_id="obj:purchase:NOPE",
                input=UpdateProposalInput(actor="finance:2", notes="x"),
            )
        )


def test_get_and_delete_proposal() -> None:
    repo = InMemoryObjectRepository()
    vendor = _make_vendor(repo)
    out = _make_proposal(repo, str(vendor.id))
    fetched = GetProposalUseCase(repo).execute(GetProposalQuery(object_id=out.id))
    assert fetched.stats["assets"] == 1
    with pytest.raises(ObjectNotFoundError):
        GetProposalUseCase(repo).execute(GetProposalQuery(object_id=out.id + "X"))
    DeleteProposalUseCase(repo).execute(DeleteProposalCommand(object_id=out.id))
    with pytest.raises(ObjectNotFoundError):
        GetProposalUseCase(repo).execute(GetProposalQuery(object_id=out.id))
    # The vendor itself survives (institutional record on another Object).
    assert GetVendorUseCase(repo).execute(GetVendorQuery(object_id=str(vendor.id))) is not None


# ---------------------------------------------------------------------------
# Dashboard, budget lens, asset register (PARTS 8/9/11)
# ---------------------------------------------------------------------------
def test_finance_dashboard_cards_and_asset_register() -> None:
    repo = InMemoryObjectRepository()
    vendor = _make_vendor(repo)
    _make_proposal(repo, str(vendor.id))
    _make_proposal(
        repo, str(vendor.id), title="Pending Only", proposal_number="PP-2026-009",
        proposal_date="2026-06-01", proposal_status="under_review",
        quotations=[], purchase_orders=[],
        bills=[{"bill_number": "B-9", "vendor_id": str(vendor.id), "amount": "1000",
                "gst_amount": "180", "payment_status": "pending"}],
        assets=[],
    )
    dash = GetFinanceDashboardUseCase(repo).execute(GetFinanceDashboardQuery())
    assert dash.active_procurements == 2
    assert dash.pending_approvals == 2
    assert dash.total_vendors == 1
    assert dash.total_purchase_orders == 1
    assert dash.pending_bills == 1
    assert dash.budget_utilized == 519200.0
    assert dash.budget_remaining is None  # no research project budgets yet

    register = ListAssetRegisterUseCase(repo).execute(ListAssetRegisterQuery())
    assert register.total_count == 1
    row = register.items[0]
    assert row.row["item_name"] == "HPC Node"
    assert row.proposal_number == "PP-2026-001"
    filtered = ListAssetRegisterUseCase(repo).execute(ListAssetRegisterQuery(category="furniture"))
    assert filtered.total_count == 0
    searched = ListAssetRegisterUseCase(repo).execute(ListAssetRegisterQuery(q="hpc server"))
    assert searched.total_count == 1


def test_budget_lines_compose_research_budget_with_procurement_spend() -> None:
    from app.domain.value_objects.metadata import Metadata

    repo = InMemoryObjectRepository()
    vendor = _make_vendor(repo)
    project = UniversalObject.create(
        object_type=ObjectType.RESEARCH_PROJECT, title="Quantum Sensors",
        created_by="registrar:1", status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=_meta_entries(budget_approved="1000000", budget_utilized="50000")),
    )
    repo.save(project)
    project.pop_domain_events()
    grant = UniversalObject.create(
        object_type=ObjectType.GRANT, title="SERB Grant", created_by="registrar:1",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=_meta_entries(amount="800000")),
    )
    grant.add_relationship(project.id, RelationshipKind.FUNDS, Provenance.ASSERTED, actor="registrar:1")
    repo.save(grant)
    grant.pop_domain_events()
    installment = UniversalObject.create(
        object_type=ObjectType.GRANT_INSTALLMENT, title="Installment 1", created_by="registrar:1",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=_meta_entries(
                installment_no="1", amount="400000", installment_status="released"
            )
        ),
    )
    installment.add_relationship(
        grant.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor="registrar:1"
    )
    repo.save(installment)
    installment.pop_domain_events()

    _make_proposal(repo, str(vendor.id), projects=[str(project.id)])
    lines = ListBudgetLinesUseCase(repo).execute(ListBudgetLinesQuery()).items
    assert len(lines) == 1
    line = lines[0]
    assert line.approved == 1000000.0
    assert line.released == 400000.0
    # utilized = frozen research utilization (50 000) + procurement paid bills
    assert line.utilized == 569200.0
    assert line.remaining == 430800.0
    assert line.spent == 519200.0
    assert line.proposals == 1
