"""DTOs for the Academic Intelligence Assistant module.

LEGACY / TRANSITIONAL (L0 freeze). The ``INTENT_*`` catalogue is
transitional. Do not add intent codes. New capabilities go in
``application/capabilities/registry.py``.

Mirrors ``dtos/settings.py`` / ``dtos/productivity.py``: option catalogues as
tuples, per-operation input dataclasses (``None`` = untouched), and outputs.
Conversations are ``ObjectType.AI_CONVERSATION`` objects; messages live inside
the conversation object as numbered ``msg.<seq>`` JSON metadata entries (V1
caps them at :data:`MAX_MESSAGES_PER_CONVERSATION`).

Version 1 is entirely local and deterministic: the rule-based intent parser
and answer builders below are the single source of truth shared by the
provider, use cases, mappers and tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Conversation storage conventions
# ---------------------------------------------------------------------------
CONVERSATION_TITLE_MAX = 120
QUESTION_MAX = 500
MAX_MESSAGES_PER_CONVERSATION = 100
HOME_RECENT_LIMIT = 5
ANSWER_CARD_LIMIT = 12
KEY_PINNED = "assistant.pinned"
KEY_TITLE_AUTO = "assistant.title_auto"  # "true" while the title is the auto-derived one
MSG_KEY_PREFIX = "msg."

# ---------------------------------------------------------------------------
# Intent catalogue (code, label) — the assistant's capability list.
# ---------------------------------------------------------------------------
INTENT_TODAY_PLAN = "today_plan"
INTENT_PENDING_ITEMS = "pending_items"
INTENT_UPCOMING_DEADLINES = "upcoming_deadlines"
INTENT_UPCOMING_MEETINGS = "upcoming_meetings"
INTENT_PENDING_REPORTS = "pending_reports"
INTENT_BUDGET_REMAINING = "budget_remaining"
INTENT_MY_PUBLICATIONS = "my_publications"
INTENT_LATEST_PUBLICATION = "latest_publication"
INTENT_PUBLICATIONS_THIS_YEAR = "publications_this_year"
INTENT_CONFERENCE_PAPERS = "conference_papers"
INTENT_ACTIVE_PROJECTS = "active_projects"
INTENT_COMPLETED_PROJECTS = "completed_projects"
INTENT_PROJECTS_BY_FUNDER = "projects_by_funder"
INTENT_RESEARCH_GRANTS = "research_grants"
INTENT_DOCUMENTS_BY_KEYWORD = "documents_by_keyword"
INTENT_ATTENDANCE_BELOW = "attendance_below"
INTENT_PENDING_GRADING = "pending_grading"
INTENT_UPCOMING_CLASSES = "upcoming_classes"
INTENT_PENDING_ASSIGNMENTS = "pending_assignments"
INTENT_BUDGET_SUMMARY = "budget_summary"
INTENT_PENDING_PURCHASES = "pending_purchases"
INTENT_RECENT_PROCUREMENTS = "recent_procurements"
INTENT_UPCOMING_EVENTS = "upcoming_events"
INTENT_EVENTS_ATTENDED = "events_attended"
INTENT_EVENTS_ORGANIZED = "events_organized"
INTENT_CERTIFICATES = "certificates"
INTENT_COMMITTEE_MEETINGS = "committee_meetings"
INTENT_PENDING_ACTIONS = "pending_actions"
INTENT_RECENT_DECISIONS = "recent_decisions"
INTENT_REPORT_CATALOGUE = "report_catalogue"
INTENT_MODULE_REPORT_SUMMARY = "module_report_summary"
INTENT_KNOWLEDGE_SEARCH = "knowledge_search"
INTENT_HELP = "help"
INTENT_GREETING = "greeting"

INTENT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Dashboard", (
        INTENT_TODAY_PLAN, INTENT_PENDING_ITEMS, INTENT_UPCOMING_DEADLINES,
        INTENT_UPCOMING_MEETINGS, INTENT_PENDING_REPORTS, INTENT_BUDGET_REMAINING,
    )),
    ("Research", (
        INTENT_MY_PUBLICATIONS, INTENT_LATEST_PUBLICATION, INTENT_PUBLICATIONS_THIS_YEAR,
        INTENT_CONFERENCE_PAPERS, INTENT_ACTIVE_PROJECTS, INTENT_COMPLETED_PROJECTS,
        INTENT_PROJECTS_BY_FUNDER, INTENT_RESEARCH_GRANTS, INTENT_DOCUMENTS_BY_KEYWORD,
    )),
    ("Teaching", (
        INTENT_ATTENDANCE_BELOW, INTENT_PENDING_GRADING,
        INTENT_UPCOMING_CLASSES, INTENT_PENDING_ASSIGNMENTS,
    )),
    ("Finance", (
        INTENT_BUDGET_SUMMARY, INTENT_PENDING_PURCHASES, INTENT_RECENT_PROCUREMENTS,
    )),
    ("Events", (
        INTENT_UPCOMING_EVENTS, INTENT_EVENTS_ATTENDED,
        INTENT_EVENTS_ORGANIZED, INTENT_CERTIFICATES,
    )),
    ("Committees", (
        INTENT_COMMITTEE_MEETINGS, INTENT_PENDING_ACTIONS, INTENT_RECENT_DECISIONS,
    )),
    ("Reports", (INTENT_REPORT_CATALOGUE, INTENT_MODULE_REPORT_SUMMARY)),
    ("Search", (INTENT_KNOWLEDGE_SEARCH, INTENT_HELP, INTENT_GREETING)),
)

INTENT_LABELS: dict[str, str] = {
    INTENT_TODAY_PLAN: "Today’s plan",
    INTENT_PENDING_ITEMS: "Pending items",
    INTENT_UPCOMING_DEADLINES: "Upcoming deadlines",
    INTENT_UPCOMING_MEETINGS: "Upcoming meetings",
    INTENT_PENDING_REPORTS: "Pending reports",
    INTENT_BUDGET_REMAINING: "Budget remaining",
    INTENT_MY_PUBLICATIONS: "My publications",
    INTENT_LATEST_PUBLICATION: "Latest publication",
    INTENT_PUBLICATIONS_THIS_YEAR: "Publications this year",
    INTENT_CONFERENCE_PAPERS: "Conference papers",
    INTENT_ACTIVE_PROJECTS: "Active research projects",
    INTENT_COMPLETED_PROJECTS: "Completed projects",
    INTENT_PROJECTS_BY_FUNDER: "Projects by funder",
    INTENT_RESEARCH_GRANTS: "Research grants",
    INTENT_DOCUMENTS_BY_KEYWORD: "Documents by keyword",
    INTENT_ATTENDANCE_BELOW: "Students below attendance threshold",
    INTENT_PENDING_GRADING: "Pending grading",
    INTENT_UPCOMING_CLASSES: "Upcoming classes",
    INTENT_PENDING_ASSIGNMENTS: "Pending assignments",
    INTENT_BUDGET_SUMMARY: "Budget summary",
    INTENT_PENDING_PURCHASES: "Pending purchases",
    INTENT_RECENT_PROCUREMENTS: "Recent procurements",
    INTENT_UPCOMING_EVENTS: "Upcoming events",
    INTENT_EVENTS_ATTENDED: "Events attended",
    INTENT_EVENTS_ORGANIZED: "Events organized",
    INTENT_CERTIFICATES: "Certificates",
    INTENT_COMMITTEE_MEETINGS: "Committee meetings",
    INTENT_PENDING_ACTIONS: "Pending committee actions",
    INTENT_RECENT_DECISIONS: "Recent decisions",
    INTENT_REPORT_CATALOGUE: "Report catalogue",
    INTENT_MODULE_REPORT_SUMMARY: "Report summary",
    INTENT_KNOWLEDGE_SEARCH: "Knowledge-graph search",
    INTENT_HELP: "What I can do",
    INTENT_GREETING: "Greeting",
}
INTENT_CODES: tuple[str, ...] = tuple(code for _, codes in INTENT_GROUPS for code in codes)

# ---------------------------------------------------------------------------
# Suggested questions (AI Home). (group, question, intent) — the /assistant
# home renders these verbatim; ``intent`` is attached so the UI can badge them.
# ---------------------------------------------------------------------------
SUGGESTED_QUESTIONS: tuple[tuple[str, str, str], ...] = (
    ("Dashboard", "What should I do today?", INTENT_TODAY_PLAN),
    ("Dashboard", "What is pending?", INTENT_PENDING_ITEMS),
    ("Dashboard", "Upcoming deadlines", INTENT_UPCOMING_DEADLINES),
    ("Dashboard", "Upcoming meetings", INTENT_UPCOMING_MEETINGS),
    ("Dashboard", "Pending reports", INTENT_PENDING_REPORTS),
    ("Dashboard", "Budget remaining", INTENT_BUDGET_REMAINING),
    ("Research", "My latest publication", INTENT_LATEST_PUBLICATION),
    ("Research", "Publications this year", INTENT_PUBLICATIONS_THIS_YEAR),
    ("Research", "Conference papers", INTENT_CONFERENCE_PAPERS),
    ("Research", "Show active research projects", INTENT_ACTIVE_PROJECTS),
    ("Research", "Show HSRF documents", INTENT_DOCUMENTS_BY_KEYWORD),
    ("Research", "Completed projects", INTENT_COMPLETED_PROJECTS),
    ("Research", "Research grants", INTENT_RESEARCH_GRANTS),
    ("Teaching", "Show students below 75% attendance", INTENT_ATTENDANCE_BELOW),
    ("Teaching", "Pending grading", INTENT_PENDING_GRADING),
    ("Teaching", "Upcoming classes", INTENT_UPCOMING_CLASSES),
    ("Teaching", "Assignments pending", INTENT_PENDING_ASSIGNMENTS),
    ("Finance", "Budget summary", INTENT_BUDGET_SUMMARY),
    ("Finance", "Show pending purchases", INTENT_PENDING_PURCHASES),
    ("Finance", "Recent procurements", INTENT_RECENT_PROCUREMENTS),
    ("Events", "Show upcoming events", INTENT_UPCOMING_EVENTS),
    ("Events", "Upcoming workshops", INTENT_UPCOMING_EVENTS),
    ("Events", "Events attended", INTENT_EVENTS_ATTENDED),
    ("Events", "Events organized", INTENT_EVENTS_ORGANIZED),
    ("Events", "Certificates", INTENT_CERTIFICATES),
    ("Committees", "Show pending committee actions", INTENT_PENDING_ACTIONS),
    ("Committees", "Show upcoming committee meetings", INTENT_COMMITTEE_MEETINGS),
    ("Committees", "Recent decisions", INTENT_RECENT_DECISIONS),
    ("Reports", "What reports can I see?", INTENT_REPORT_CATALOGUE),
    ("Reports", "Summarize the publications report", INTENT_MODULE_REPORT_SUMMARY),
    ("Search", "Show my publications", INTENT_MY_PUBLICATIONS),
    ("Search", "Show today's meetings", INTENT_UPCOMING_MEETINGS),
)
# Report kinds the assistant can summarize — EXACTLY the Reports module
# catalogue (``dtos/reports.py`` ``REPORT_TITLES`` / frontend ``REPORT_KINDS``),
# so every action href ``/reports/<kind>`` lands on a real report page.
REPORT_MODULES: tuple[str, ...] = (
    "analytics", "committees", "events", "faculty", "finance",
    "publications", "research", "students", "teaching",
)

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
@dataclass
class AskQuestionInput:
    question: str
    conversation_id: str | None = None
    asked_by: str = "system"
    provider_id: str | None = None  # M11.3.1: the selection key (a provider_id)
    model_id: str | None = None  # DEPRECATED alias for provider_id (legacy API)

    def __post_init__(self) -> None:
        # Resolve the legacy alias so the selection key is unambiguous
        # regardless of how the input is constructed (mapper or directly).
        if not self.provider_id and self.model_id:
            self.provider_id = self.model_id


@dataclass
class CreateConversationInput:
    title: str | None = None
    created_by: str = "system"


@dataclass
class UpdateConversationInput:
    conversation_id: str = ""
    title: str | None = None      # None = untouched; "" clears to auto
    pinned: bool | None = None    # None = untouched
    updated_by: str = "system"


@dataclass
class DeleteConversationInput:
    conversation_id: str = ""


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
@dataclass
class AssistantActionOutput:
    label: str
    href: str
    kind: str = "link"  # link | module (UI renders module actions as buttons)


@dataclass
class AssistantCardOutput:
    object_id: str
    object_type: str
    title: str
    subtitle: str | None = None
    href: str = "/"
    badge: str | None = None
    stats: dict[str, str] = field(default_factory=dict)


@dataclass
class AssistantAnswerOutput:
    intent: str
    intent_label: str
    question: str
    summary: str
    metrics: dict[str, str] = field(default_factory=dict)
    items: list[dict] = field(default_factory=list)  # raw rows (title/subtitle/href) for lists
    cards: list[AssistantCardOutput] = field(default_factory=list)
    actions: list[AssistantActionOutput] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # modules consulted
    citations: list[AssistantCitation] = field(default_factory=list)  # S6 M3 evidence


@dataclass
class AssistantMessageOutput:
    seq: int
    role: str  # user | assistant
    content: str
    created_at: str
    answer: AssistantAnswerOutput | None = None


@dataclass
class AssistantConversationOutput:
    id: str
    title: str
    pinned: bool
    message_count: int
    last_message_at: str | None
    created_at: str | None
    version: int = 1


@dataclass
class ConversationDetailOutput:
    conversation: AssistantConversationOutput
    messages: list[AssistantMessageOutput] = field(default_factory=list)


@dataclass
class ConversationListResult:
    items: list[AssistantConversationOutput]
    total_count: int
    page: int
    page_size: int


@dataclass
class SuggestedPrompt:
    group: str
    question: str
    intent: str


@dataclass
class AssistantHomeOutput:
    suggested: list[SuggestedPrompt]
    recent: list[AssistantConversationOutput]
    pinned: list[AssistantConversationOutput]
    conversation_count: int


@dataclass
class AskOutput:
    conversation: AssistantConversationOutput
    user_message: AssistantMessageOutput
    assistant_message: AssistantMessageOutput
    answer: AssistantAnswerOutput


# ---------------------------------------------------------------------------
# Retrieval & context (Sprint-6 M1 — Assistant Retrieval Service)
# ---------------------------------------------------------------------------

# Deterministic budget for the assistant context envelope (characters).
# No tokenizer dependency: a stable, CI-safe approximation of the
# token budget; trimming always drops the OLDEST content first.
CONTEXT_CHAR_BUDGET = 6000
CONTEXT_HISTORY_CHAR_BUDGET = 2000
# Sprint-8 M2 — retrieved memories (prior conversations + the graph-
# discovered knowledge objects) get their own budget, mirroring the
# history doctrine: the current retrieval keeps its context budget, and
# the prompt builder's hard cap remains the final guard.
CONTEXT_MEMORY_CHAR_BUDGET = 2000


@dataclass(frozen=True)
class RetrievedItem:
    """One merged retrieval result (search and/or graph provenance)."""

    object_id: str
    object_type: str
    title: str
    version: int
    sources: tuple[str, ...]  # ("search",) | ("graph",) | ("search", "graph")
    score: float  # deterministic RRF score (0.0 for graph-only items)
    # P0-2: the deterministic ``key: value`` metadata text of the object —
    # LLM evidence beyond title. Populated from the search projection for
    # search hits and from the object's metadata for graph-only items.
    # Additive: empty for legacy callers.
    metadata_text: str = ""


@dataclass(frozen=True)
class AssistantRetrievalResult:
    """Merged, deduplicated, deterministically ordered retrieval.

    P0 evidence contract: when ``document_reference`` is set, the query
    named a specific document (filename/title). ``document_reference_resolved``
    is True only when that exact document survived into ``items``; the
    evidence gate in grounded QA refuses to answer otherwise.
    """

    items: tuple[RetrievedItem, ...]
    search_count: int
    graph_count: int
    document_reference: str | None = None
    document_reference_resolved: bool = False
    resolved_document_id: str | None = None


@dataclass(frozen=True)
class AssistantContext:
    """Provider-agnostic assistant context envelope (Sprint-6 M1).

    ``history`` is the conversation thread trimmed oldest-first to the
    history budget; ``retrieved`` is the merged retrieval (search + graph)
    trimmed to the remaining context budget. ``memories`` / ``knowledge``
    (Sprint-8 M2 — memory-augmented asks) are the automatically recalled
    prior conversations and their graph-discovered related objects,
    trimmed to the memory budget. ``truncated`` reports whether any
    trimming occurred. Pure data — the provider renders it.
    """

    question: str
    history: tuple[tuple[str, str], ...]  # (role, content) pairs, oldest first
    retrieved: tuple[RetrievedItem, ...]
    truncated: bool
    memories: tuple[MemoryItem, ...] = ()
    knowledge: tuple[KnowledgeItem, ...] = ()


@dataclass(frozen=True)
class MemoryItem:
    """One recalled conversation (Sprint-8 M1 — assistant memory).

    The memory projection of a conversation: its title, the latest
    question/answer pair (the full thread stays available through the
    existing conversation endpoints), the CITATIONS preserved from the
    stored answer payload, the review status (a pending or rejected
    answer is recalled with empty content and no citations — the review
    gate), and the retrieval provenance/score.
    """

    conversation_id: str
    title: str
    question: str
    answer: str
    citations: tuple[AssistantCitation, ...] = ()
    review_status: str = ""  # "" | pending | approved | rejected
    score: float = 0.0
    # Sprint-8 M3 — the review-feedback ranking contribution (in [-1, 1];
    # 0.0 when neutral). The recalled ORDER reflects score + review_score.
    review_score: float = 0.0
    sources: tuple[str, ...] = ()
    version: int = 1
    last_message_at: str | None = None


@dataclass(frozen=True)
class KnowledgeItem:
    """One non-conversation object recalled alongside conversations
    (Sprint-8 M1 — the graph-aware knowledge leg of memory recall)."""

    object_id: str
    object_type: str
    title: str
    score: float = 0.0
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryRecall:
    """The deterministic memory recall for one question.

    ``conversations`` are the recalled conversation memories (search +
    graph provenance, review-gated); ``knowledge`` are the related
    objects the graph leg discovered from the conversation anchors.
    """

    conversations: tuple[MemoryItem, ...]
    knowledge: tuple[KnowledgeItem, ...]
    search_count: int
    graph_count: int


@dataclass(frozen=True)
class AssistantPrompt:
    """The deterministic prompt envelope built by the Prompt Builder.

    ``system`` carries the standing instructions (role, grounding rules,
    injection-safety); ``user`` carries the conversation history, the
    permission-filtered retrieval provenance, and the question. Providers
    map this onto their transport format — prompt construction lives ONLY
    in the Prompt Builder service.
    """

    system: str
    user: str
    citations: tuple[AssistantCitation, ...] = ()  # S6 M3: evidence exposed separately
    # S7 M1: which registered prompt (id + version) produced this prompt —
    # makes prompt versions identifiable end to end.
    prompt_id: str = "assistant.default"
    prompt_version: int = 1


@dataclass(frozen=True)
class AssistantCitation:
    """One verifiable evidence item attached to an answer (Sprint-6 M3).

    Carries ONLY facts already present on the retrieval item — the
    deterministic citation ``number``, the object identity and type, the
    title, the provenance ``sources``, and the version/score — so no
    metadata is duplicated. ``object_id`` is the stable identifier.
    """

    number: int
    object_id: str
    object_type: str
    title: str
    sources: tuple[str, ...]
    version: int
    score: float


# ---------------------------------------------------------------------------
# Review workflow (Sprint-6 M5)
# ---------------------------------------------------------------------------
# Human review before publication: the conversation carries its review state
# as L1/SYSTEM metadata; the LAST assistant answer is visible only after
# approval. Three states, nothing more.
KEY_REVIEW_STATUS = "assistant.review_status"
# Sprint-7 M2: the model this conversation uses (registry model id). Stored
# as L1/SYSTEM metadata like assistant.pinned.
KEY_PROVIDER_ID = "assistant.provider_id"  # M11.3.1: the selected provider id
KEY_MODEL_ID = "assistant.model_id"  # DEPRECATED legacy key (still read for old conversations)

REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"
