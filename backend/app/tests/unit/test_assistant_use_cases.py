"""Unit tests for the Academic Intelligence Assistant (no framework deps).

Mirrors ``test_productivity_use_cases.py``: an in-memory ``ObjectRepository``
fabricates a small cross-module world and the assistant provider + use cases
run against it — proving PART 3 reuse (answers are computed from the frozen
modules' own builders), the conversation lifecycle, and the provider seam.

All fixture dates are derived from the REAL today so the suite is
deterministic on any day it runs.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from app.application.assistant.providers import PROVIDER_NAME, RuleBasedAssistantProvider
from app.application.commands.ask_question import AskQuestionCommand
from app.application.commands.create_conversation import CreateConversationCommand
from app.application.commands.delete_conversation import DeleteConversationCommand
from app.application.commands.update_conversation import UpdateConversationCommand
from app.application.dtos import assistant as dto
from app.application.dtos.assistant import (
    AskQuestionInput,
    CreateConversationInput,
    DeleteConversationInput,
    UpdateConversationInput,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.queries.get_assistant_home import GetAssistantHomeQuery
from app.application.queries.get_conversation import GetConversationQuery
from app.application.queries.list_conversations import ListConversationsQuery
from app.application.use_cases.assistant.ask_question import AskQuestionUseCase
from app.application.use_cases.assistant.create_conversation import CreateConversationUseCase
from app.application.use_cases.assistant.delete_conversation import DeleteConversationUseCase
from app.application.use_cases.assistant.get_conversation import GetConversationUseCase
from app.application.use_cases.assistant.get_home import GetAssistantHomeUseCase
from app.application.use_cases.assistant.helpers import read_messages
from app.application.use_cases.assistant.list_conversations import ListConversationsUseCase
from app.application.use_cases.assistant.update_conversation import UpdateConversationUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry

_TODAY = dt.date.today()
YEAR = str(_TODAY.year)


def d(offset: int) -> str:
    return (_TODAY + dt.timedelta(days=offset)).isoformat()


class InMemoryObjectRepository(ObjectRepository):
    def __init__(self) -> None:
        self._store: dict[str, UniversalObject] = {}

    def save(self, entity: UniversalObject) -> None:
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
        sort_by: str = "id",
        order: str = "asc",
    ) -> list[UniversalObject]:
        items = [
            o
            for o in self._store.values()
            if (object_type is None or o.object_type == object_type)
            and (status is None or o.status == status)
            and (
                metadata_key is None
                or (
                    o.metadata.get_value(metadata_key) is not None
                    and (
                        metadata_value is None
                        or o.metadata.get_value(metadata_key) == metadata_value
                    )
                )
            )
        ]
        reverse = order == "desc"
        if sort_by == "id":
            items.sort(key=lambda o: str(o.id), reverse=reverse)
        elif sort_by == "object_type":
            items.sort(key=lambda o: o.object_type.value, reverse=reverse)
        elif sort_by == "title":
            items.sort(key=lambda o: o.title, reverse=reverse)
        elif sort_by == "status":
            items.sort(key=lambda o: o.status.value, reverse=reverse)
        elif sort_by == "version":
            items.sort(key=lambda o: o.version, reverse=reverse)
        else:
            raise ValueError(f"Unsupported sort_by: {sort_by!r}")
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


def _meta_entries(**pairs: str) -> tuple:
    return tuple(
        MetadataEntry(k, v, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
        for k, v in pairs.items()
    )


def _make(
    repo: InMemoryObjectRepository,
    kind: ObjectType,
    title: str,
    links: list[tuple] | None = None,
    **meta: str,
) -> UniversalObject:
    obj = UniversalObject.create(
        object_type=kind,
        title=title,
        created_by="faculty:ui",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=_meta_entries(**meta)),
    )
    for target, rel_kind in links or []:
        obj.add_relationship(target, rel_kind, actor="faculty:ui")
    repo.save(obj)
    obj.pop_domain_events()
    return obj


@pytest.fixture()
def world() -> dict:
    """Frozen-module world the assistant must answer from (no duplication)."""
    repo = InMemoryObjectRepository()

    agency = _make(repo, ObjectType.FUNDING_AGENCY, "HSRF Foundation")
    project = _make(
        repo, ObjectType.RESEARCH_PROJECT, "Smart Campus Sensor Grid",
        lifecycle_status="active",
        links=[(agency.id, RelationshipKind.FUNDED_BY)],
    )
    _make(repo, ObjectType.RESEARCH_PROJECT, "Legacy Survey", lifecycle_status="completed")
    _make(
        repo, ObjectType.GRANT, "Edge AI Grant",
        grant_number="HSRF/2026/07", amount="500000",
        links=[(project.id, RelationshipKind.FUNDS), (agency.id, RelationshipKind.FUNDED_BY)],
    )
    _make(
        repo, ObjectType.PUBLICATION, "Graph Kernels Survey",
        publication_type="journal", year=YEAR, date=d(0),
    )
    _make(
        repo, ObjectType.PUBLICATION, "Edge Inference Workshop Paper",
        publication_type="conference", conference="ICML 2025",
        year=str(_TODAY.year - 1), date=d(-300),
    )
    _make(
        repo, ObjectType.DOCUMENT, "HSRF Application Form",
        document_type="form", tags="hsrf, grant",
    )
    course = _make(repo, ObjectType.COURSE, "MA201 Linear Algebra")
    asha = _make(
        repo, ObjectType.STUDENT, "Asha Rao", roll_number="MA201",
        links=[(course.id, RelationshipKind.ENROLLED_IN)],
    )
    bilal = _make(
        repo, ObjectType.STUDENT, "Bilal Khan", roll_number="MA202",
        links=[(course.id, RelationshipKind.ENROLLED_IN)],
    )
    for i, states in enumerate([
        {str(asha.id): "present", str(bilal.id): "present"},
        {str(asha.id): "present", str(bilal.id): "absent"},
        {str(asha.id): "present", str(bilal.id): "absent"},
        {str(asha.id): "late", str(bilal.id): "absent"},
    ]):
        _make(
            repo, ObjectType.ATTENDANCE_SESSION, f"Lecture {i + 1}",
            session_date=d(-(3 - i)), attendance_records=json.dumps(states),
            links=[(course.id, RelationshipKind.BELONGS_TO)],
        )
    assignment = _make(
        repo, ObjectType.ASSIGNMENT, "Assignment 1 — Eigenvalues",
        due_date=d(5),
        links=[(course.id, RelationshipKind.BELONGS_TO)],
    )
    _make(
        repo, ObjectType.SUBMISSION, "Bilal's submission",
        submitted_at=d(0), graded_at="",
        links=[(assignment.id, RelationshipKind.BELONGS_TO)],
    )
    committee = _make(repo, ObjectType.COMMITTEE, "IQAC", committee_type="Internal")
    meeting = _make(
        repo, ObjectType.MEETING, "IQAC August Meet", meeting_date=d(2),
        decisions=json.dumps(["Approved AQAR timeline", "Ratified seminar series"]),
        links=[(committee.id, RelationshipKind.BELONGS_TO)],
    )
    _make(
        repo, ObjectType.TASK, "Prepare AQAR annexures",
        due_date=d(3), action_status="pending", priority="high",
        links=[(meeting.id, RelationshipKind.BELONGS_TO)],
    )
    _make(
        repo, ObjectType.TASK, "Buy notebook", task_scope="personal",
        due_date=d(0), action_status="pending",
    )
    _make(
        repo, ObjectType.EVENT, "AI Workshop", event_type="workshop",
        event_status="planned", start_date=d(3), end_date=d(4),
        participation=json.dumps([
            {"role": "participant", "certificate_document_id": "doc-cert-1"},
        ]),
        registration=json.dumps({"certificates_issued": 1}),
    )
    _make(
        repo, ObjectType.EVENT, "Tech Fest 2025", event_type="fest",
        event_status="completed", start_date=d(-40), end_date=d(-39),
        participation=json.dumps([{"role": "organizer"}]),
    )
    _make(
        repo, ObjectType.PURCHASE, "Lab Microscope Proposal",
        proposal_status="submitted", estimated_cost="120000",
        purchase_orders=json.dumps([{"status": "ordered"}]),
        bills=json.dumps([{"payment_status": "paid", "amount": "10000"}]),
    )
    _make(
        repo, ObjectType.PURCHASE, "Stationery Procurement",
        proposal_status="completed", estimated_cost="5000",
        purchase_orders=json.dumps([{"status": "delivered"}]),
        bills=json.dumps([]),
    )
    return {"repo": repo, "course": course, "asha": asha, "bilal": bilal,
            "project": project, "agency": agency}


@pytest.fixture()
def provider(world) -> RuleBasedAssistantProvider:
    return RuleBasedAssistantProvider(world["repo"])


def _ask(repo, provider, question: str, conversation_id: str | None = None):
    return AskQuestionUseCase(repo, provider).execute(
        AskQuestionCommand(
            input=AskQuestionInput(
                question=question, conversation_id=conversation_id, asked_by="faculty:ui"
            )
        )
    )


# ---------------------------------------------------------------------------
# Provider — cross-module answers (PARTS 3..12), computed not duplicated
# ---------------------------------------------------------------------------
def test_provider_identity(provider):
    assert provider.name == PROVIDER_NAME == "rules-v1"


def test_attendance_below_world(provider, world):
    answer = provider.answer("Show students below 75% attendance", "faculty:ui")
    assert answer.intent == dto.INTENT_ATTENDANCE_BELOW
    assert answer.metrics["Below threshold"] == "1"
    assert answer.cards[0].title == "Bilal Khan"
    assert answer.cards[0].href.startswith("/students/")
    assert answer.sources == ["teaching", "students"]


def test_publication_intents_world(provider):
    mine = provider.answer("Show my publications", "faculty:ui")
    assert mine.metrics["Publications"] == "2"
    latest = provider.answer("My latest publication", "faculty:ui")
    assert "Graph Kernels Survey" in latest.summary
    assert latest.cards[0].href.startswith("/publications/")
    this_year = provider.answer("Publications this year", "faculty:ui")
    assert this_year.metrics[f"Publications {YEAR}"] == "1"
    conf = provider.answer("Conference papers", "faculty:ui")
    assert conf.metrics["Conference papers"] == "1"
    assert conf.cards[0].title == "Edge Inference Workshop Paper"


def test_project_intents_world(provider):
    active = provider.answer("Show active research projects", "faculty:ui")
    assert active.metrics["Active projects"] == "1"
    assert "funded by HSRF Foundation" in active.cards[0].subtitle
    completed = provider.answer("Completed projects", "faculty:ui")
    assert completed.metrics["Completed projects"] == "1"
    funded = provider.answer("projects funded by HSRF", "faculty:ui")
    assert funded.metrics["Projects"] == "1"
    assert funded.cards[0].title == "Smart Campus Sensor Grid"
    grants = provider.answer("Research grants", "faculty:ui")
    assert grants.metrics["Grants"] == "1"
    assert grants.metrics["Sanctioned"] == "₹5,00,000"


def test_documents_by_keyword_world(provider):
    answer = provider.answer("Show HSRF documents", "faculty:ui")
    assert answer.metrics["Documents"] == "1"
    assert answer.cards[0].title == "HSRF Application Form"
    assert answer.cards[0].href.startswith("/documents/")


def test_event_intents_world(provider):
    upcoming = provider.answer("Upcoming workshops", "faculty:ui")
    assert upcoming.intent == dto.INTENT_UPCOMING_EVENTS
    assert upcoming.cards and upcoming.cards[0].title == "AI Workshop"
    attended = provider.answer("Events attended", "faculty:ui")
    assert attended.metrics["Attended"] == "1"
    organized = provider.answer("Events organized", "faculty:ui")
    assert organized.metrics["Organized"] == "1"
    certificates = provider.answer("Certificates", "faculty:ui")
    assert certificates.metrics["Certificates"] == "1"


def test_committee_intents_world(provider):
    meetings = provider.answer("Show upcoming committee meetings", "faculty:ui")
    assert meetings.metrics["Next 30 days"] == "1"
    assert meetings.cards[0].title == "IQAC August Meet"
    actions = provider.answer("Show pending committee actions", "faculty:ui")
    assert actions.metrics["Open actions"] == "1"
    assert actions.cards[0].title == "Prepare AQAR annexures"
    decisions = provider.answer("Recent decisions", "faculty:ui")
    assert decisions.metrics["Meetings with decisions"] == "1"
    assert any("AQAR" in item["title"] for item in decisions.items)


def test_finance_intents_world(provider):
    pending = provider.answer("Show pending purchases", "faculty:ui")
    assert pending.metrics["Active proposals"] == "1"
    assert pending.metrics["Open POs"] == "1"
    recent = provider.answer("Recent procurements", "faculty:ui")
    assert recent.metrics["Completed procurements"] == "1"
    assert recent.metrics["Paid bills"] == "1"
    summary = provider.answer("Budget summary", "faculty:ui")
    assert set(summary.metrics) >= {"Approved", "Utilized", "Remaining"}
    assert summary.sources == ["reports", "finance", "research"]


def test_dashboard_intents_world(provider):
    today = provider.answer("What should I do today?", "faculty:ui")
    assert today.intent == dto.INTENT_TODAY_PLAN
    assert "Tasks due today" in today.metrics  # the Excel/DB-free computed frame
    meetings = provider.answer("Show today's meetings", "faculty:ui")
    assert meetings.intent == dto.INTENT_UPCOMING_MEETINGS
    reports = provider.answer("Pending reports", "faculty:ui")
    assert reports.intent == dto.INTENT_PENDING_REPORTS


def test_report_intents_world(provider):
    catalogue = provider.answer("What reports can I see?", "faculty:ui")
    assert catalogue.metrics["Report kinds"] == "9"
    assert catalogue.cards[0].href.startswith("/reports/")
    pubs = provider.answer("Summarize the publications report", "faculty:ui")
    assert pubs.intent == dto.INTENT_MODULE_REPORT_SUMMARY
    assert pubs.metrics.get("Total Publications") == "2"
    assert any(action.href == "/reports/publications" for action in pubs.actions)


def test_search_and_meta_intents_world(provider):
    hits = provider.answer("search for kernels", "faculty:ui")
    assert hits.intent == dto.INTENT_KNOWLEDGE_SEARCH
    assert hits.metrics["Matches"] == "1"
    assert hits.cards[0].title == "Graph Kernels Survey"
    hello = provider.answer("hello", "faculty:ui")
    assert hello.intent == dto.INTENT_GREETING
    help_answer = provider.answer("help", "faculty:ui")
    assert help_answer.intent == dto.INTENT_HELP
    assert "AcademicOS Intelligence" in help_answer.summary
    odd = provider.answer("zqx wvut", "faculty:ui")  # never an error
    assert odd.intent == dto.INTENT_KNOWLEDGE_SEARCH


def test_knowledge_search_skips_conversations_and_settings(world, provider):
    _ask(world["repo"], provider, "hello")  # creates an AI_CONVERSATION
    again = provider.answer("hello", "faculty:ui")
    assert again.intent == dto.INTENT_GREETING
    search = provider.answer("search for conversation", "faculty:ui")
    assert all(card.object_type != "ai_conversation" for card in search.cards)


# ---------------------------------------------------------------------------
# Ask / conversation use cases — the PART 1 workspace
# ---------------------------------------------------------------------------
def test_ask_creates_conversation_and_persists_pair(world, provider):
    out = _ask(world["repo"], provider, "What should I do today?")
    assert out.conversation.title == "What should I do today?"
    assert out.user_message.role == "user"
    assert out.assistant_message.role == "assistant"
    assert out.answer.intent == dto.INTENT_TODAY_PLAN
    assert out.conversation.message_count == 2
    # reloaded through the query use case: answer fully rehydrated
    detail = GetConversationUseCase(world["repo"]).execute(
        GetConversationQuery(conversation_id=out.conversation.id)
    )
    assert len(detail.messages) == 2
    assert detail.messages[1].answer is not None
    assert detail.messages[1].answer.intent == dto.INTENT_TODAY_PLAN
    assert detail.messages[1].answer.cards or detail.messages[1].answer.metrics


def test_second_question_does_not_retitle_auto_titled_thread(world, provider):
    """Regression (E2E): auto-title derives from the FIRST question only —
    later asks must not drift the conversation title."""
    first = _ask(world["repo"], provider, "What should I do today?").conversation
    assert first.title == "What should I do today?"
    second = _ask(
        world["repo"], provider, "upcoming deadlines", conversation_id=first.id
    ).conversation
    assert second.title == "What should I do today?"  # unchanged
    assert second.message_count == 4


def test_ask_appends_and_never_retitles_explicit_title(world, provider):
    created = CreateConversationUseCase(world["repo"]).execute(
        CreateConversationCommand(
            input=CreateConversationInput(title="Deep dive", created_by="faculty:ui")
        )
    )
    out = _ask(world["repo"], provider, "conference papers", conversation_id=created.id)
    assert out.conversation.title == "Deep dive"  # explicit title wins
    assert out.conversation.message_count == 2
    out2 = _ask(world["repo"], provider, "upcoming events", conversation_id=created.id)
    assert out2.conversation.message_count == 4
    assert out2.user_message.seq == 3


def test_ask_unknown_conversation_raises_not_found(world, provider):
    with pytest.raises(ObjectNotFoundError):
        _ask(world["repo"], provider, "hello", conversation_id="missing-id")


def test_ask_validation_errors(world, provider):
    with pytest.raises(ValidationError):
        _ask(world["repo"], provider, "   ")
    with pytest.raises(ValidationError):
        _ask(world["repo"], provider, "x" * 501)
    with pytest.raises(ValidationError):
        _ask(world["repo"], provider, "hi", conversation_id="   ")


def test_provider_seam_is_injectable(world):
    """The future-LLM seam: ANY object honouring the protocol plugs into the
    use case untouched (integration proves the same at the route layer)."""

    class StubProvider:
        @property
        def name(self) -> str:
            return "stub-v0"

        def answer(self, question: str, asked_by: str) -> dto.AssistantAnswerOutput:
            return dto.AssistantAnswerOutput(
                intent="stub", intent_label="Stub", question=question,
                summary=f"canned:{question}", sources=["stub"],
            )

    out = AskQuestionUseCase(world["repo"], StubProvider()).execute(
        AskQuestionCommand(input=AskQuestionInput(question="anything", asked_by="faculty:ui"))
    )
    assert out.answer.summary == "canned:anything"


def test_update_rename_pin_reset_and_validation(world, provider):
    out = _ask(world["repo"], provider, "what can you do")
    update = UpdateConversationUseCase(world["repo"])
    renamed = update.execute(
        UpdateConversationCommand(
            input=UpdateConversationInput(conversation_id=out.conversation.id, title="My thread")
        )
    )
    assert renamed.title == "My thread"
    pinned = update.execute(
        UpdateConversationCommand(
            input=UpdateConversationInput(conversation_id=out.conversation.id, pinned=True)
        )
    )
    assert pinned.pinned is True
    reset = update.execute(
        UpdateConversationCommand(
            input=UpdateConversationInput(conversation_id=out.conversation.id, title="")
        )
    )
    assert reset.title == "what can you do"  # re-derived from the first question
    with pytest.raises(ValidationError):
        update.execute(
            UpdateConversationCommand(input=UpdateConversationInput(conversation_id=out.conversation.id))
        )
    with pytest.raises(ValidationError):
        update.execute(
            UpdateConversationCommand(
                input=UpdateConversationInput(conversation_id=out.conversation.id, title="x" * 121)
            )
        )
    with pytest.raises(ObjectNotFoundError):
        update.execute(
            UpdateConversationCommand(
                input=UpdateConversationInput(conversation_id="nope", pinned=True)
            )
        )


def test_list_orders_pinned_first_then_recent(world, provider):
    first = _ask(world["repo"], provider, "hello").conversation
    second = _ask(world["repo"], provider, "upcoming deadlines").conversation
    listing = ListConversationsUseCase(world["repo"]).execute(ListConversationsQuery())
    assert listing.total_count == 2
    assert {c.id for c in listing.items} == {first.id, second.id}
    UpdateConversationUseCase(world["repo"]).execute(
        UpdateConversationCommand(
            input=UpdateConversationInput(conversation_id=first.id, pinned=True)
        )
    )
    listing = ListConversationsUseCase(world["repo"]).execute(ListConversationsQuery())
    assert listing.items[0].id == first.id  # pinned floats to the top
    page = ListConversationsUseCase(world["repo"]).execute(
        ListConversationsQuery(page=2, page_size=1)
    )
    assert page.page == 2 and page.page_size == 1 and len(page.items) == 1


def test_delete_conversation(world, provider):
    out = _ask(world["repo"], provider, "hello")
    DeleteConversationUseCase(world["repo"]).execute(
        DeleteConversationCommand(input=DeleteConversationInput(conversation_id=out.conversation.id))
    )
    assert ListConversationsUseCase(world["repo"]).execute(
        ListConversationsQuery()
    ).total_count == 0
    with pytest.raises(ObjectNotFoundError):
        DeleteConversationUseCase(world["repo"]).execute(
            DeleteConversationCommand(input=DeleteConversationInput(conversation_id=out.conversation.id))
        )
    with pytest.raises(ValidationError):
        DeleteConversationUseCase(world["repo"]).execute(
            DeleteConversationCommand(input=DeleteConversationInput(conversation_id=" "))
        )


def test_message_cap_trims_oldest(world, provider):
    conv = _ask(world["repo"], provider, "hello").conversation
    asks = (dto.MAX_MESSAGES_PER_CONVERSATION // 2) + 5  # push past the cap
    for _ in range(asks - 1):
        _ask(world["repo"], provider, "help", conversation_id=conv.id)
    detail = GetConversationUseCase(world["repo"]).execute(
        GetConversationQuery(conversation_id=conv.id)
    )
    assert len(detail.messages) <= dto.MAX_MESSAGES_PER_CONVERSATION
    assert detail.messages[0].seq > 1  # oldest pairs were trimmed
    assert detail.messages[-1].role == "assistant"


def test_home_payload(world, provider):
    home = GetAssistantHomeUseCase(world["repo"], provider).execute(GetAssistantHomeQuery())
    assert len(home.suggested) == len(dto.SUGGESTED_QUESTIONS)
    assert home.suggested[0].group and home.suggested[0].intent
    assert home.conversation_count == 0
    out = _ask(world["repo"], provider, "what reports can I see?")
    UpdateConversationUseCase(world["repo"]).execute(
        UpdateConversationCommand(
            input=UpdateConversationInput(conversation_id=out.conversation.id, pinned=True)
        )
    )
    home = GetAssistantHomeUseCase(world["repo"], provider).execute(GetAssistantHomeQuery())
    assert home.conversation_count == 1
    assert [c.id for c in home.pinned] == [out.conversation.id]
    assert [c.id for c in home.recent] == [out.conversation.id]


def test_messages_are_capped_records(world, provider):
    out = _ask(world["repo"], provider, "hello")
    obj = world["repo"].get_by_id(out.conversation.id)
    pairs = read_messages(obj)
    assert [seq for seq, _p in pairs] == [1, 2]
    assert pairs[1][1]["answer"]["intent"] == dto.INTENT_GREETING
    assert pairs[0][1]["role"] == "user"
