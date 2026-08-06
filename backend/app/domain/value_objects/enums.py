"""Domain enumerations for the Universal Object model.

Frozen reference: Object-Centric Knowledge Graph Blueprint §1–§2.

These are the only enums the Domain Foundation needs. They are plain
``str``/``int`` enums (standard library only) so the domain layer has zero
external dependencies and compiles independently of any framework.
"""
from __future__ import annotations

from enum import Enum


class ObjectType(str, Enum):
    """Every kind of thing in the Knowledge Graph (Blueprint §2).

    A Workspace, a Grant, a Publication, a Person — all are Objects. New
    institution-specific types can be appended here over the product's life.
    """

    # People & roles
    FACULTY = "faculty"
    STUDENT = "student"
    # Teaching & research
    COURSE = "course"
    RESEARCH_PROJECT = "research_project"
    PUBLICATION = "publication"
    GRANT = "grant"
    # Teaching & student management (appended — the catalogue grows over the
    # product's life; no existing member changed)
    ASSIGNMENT = "assignment"
    SUBMISSION = "submission"
    ATTENDANCE_SESSION = "attendance_session"
    # Research projects & grants management (appended — same doctrine)
    FUNDING_AGENCY = "funding_agency"
    PROJECT_MILESTONE = "project_milestone"
    GRANT_INSTALLMENT = "grant_installment"
    GRANT_EXPENDITURE = "grant_expenditure"
    # Operations & governance
    MEETING = "meeting"
    COMMITTEE = "committee"
    EVENT = "event"
    TASK = "task"
    PURCHASE = "purchase"
    BUDGET = "budget"
    # Finance & procurement management (appended — same doctrine: the
    # catalogue grows over the product's life; no existing member changed)
    VENDOR = "vendor"
    # Productivity Hub (appended — same doctrine; no existing member changed)
    NOTIFICATION = "notification"
    CALENDAR_ENTRY = "calendar_entry"
    # Settings & Preferences (appended — same doctrine; no existing member changed)
    SETTINGS = "settings"
    # Identity & Access (appended — Sprint-1 auth foundation; same doctrine:
    # one USER object per account, username as the Object title, credentials
    # as system-layer metadata. RBAC/roles land in a later milestone.)
    USER = "user"
    # Academic Intelligence Assistant (appended — same doctrine; no existing
    # member changed). One aggregate per conversation; messages embedded as
    # numbered metadata entries (see application/use_cases/assistant).
    AI_CONVERSATION = "ai_conversation"
    # Intake Foundations — v2 (appended — same doctrine: the catalogue grows
    # over the product's life; no existing member changed)
    INTAKE_SESSION = "intake_session"
    INTAKE_ITEM = "intake_item"
    # Scholarly artefacts
    DOCUMENT = "document"
    JOURNAL = "journal"
    CONFERENCE = "conference"
    DATASET = "dataset"
    SOFTWARE = "software"
    LABORATORY = "laboratory"
    RESEARCH_AREA = "research_area"
    # System / structural
    SPACE = "space"
    NOTE = "note"
    MESSAGE = "message"
    INTEGRATION = "integration"
    # Four-Pillars extensions (Blueprint §3 / §4)
    WORKSPACE = "workspace"
    WORKFLOW_TEMPLATE = "workflow_template"
    WORKFLOW_INSTANCE = "workflow_instance"
    PROACTIVE_INSIGHT = "proactive_insight"
    MEMORY_ARTIFACT = "memory_artifact"


class ObjectStatus(str, Enum):
    """Base lifecycle states (Blueprint §1.4).

    Type-specific states (e.g. a Publication's ``under_review``) are expressed
    as metadata on top of this universal lifecycle, never as a separate model.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class Provenance(str, Enum):
    """Where a value or link came from (Blueprint §3.1)."""

    ASSERTED = "asserted"  # set by a human
    INFERRED = "inferred"  # proposed/derived by AI (e.g. Smart Link)
    SYSTEM = "system"  # produced automatically by the platform


class MetadataLayer(int, Enum):
    """The seven-layer metadata model (AI Architecture F7 / SRS §16).

    L6 (human-asserted) is immutable to AI writes — see ``Metadata.with_entry``.
    """

    L1_SYSTEM = 1
    L2_FILESYSTEM = 2
    L3_FORMAT = 3
    L4_UNDERSTANDING = 4
    L5_INFERRED = 5
    L6_HUMAN_ASSERTED = 6
    L7_COLLABORATIVE = 7


class RelationshipKind(str, Enum):
    """Typed, directed edges of the Knowledge Graph (Blueprint §3.1, §4).

    The verb encodes direction: ``AUTHORED_BY`` points from a Publication to a
    Faculty member; ``AUTHORS`` is the reverse. ``SMART_LINK`` marks an
    AI-proposed candidate that must be reviewed before it is trusted.
    """

    # structural / membership
    BELONGS_TO = "belongs_to"
    PART_OF = "part_of"
    ATTACHED_TO = "attached_to"
    MEMBER_OF = "member_of"
    RELATED_TO = "related_to"
    CONTAINS = "contains"
    TAGGED = "tagged"
    # scholarly
    AUTHORED_BY = "authored_by"
    AUTHORS = "authors"
    CITES = "cites"
    CITED_BY = "cited_by"
    CONTRADICTS = "contradicts"
    SUPPLEMENTS = "supplements"
    PREREQUISITE_OF = "prerequisite_of"
    PRIOR_ART = "prior_art"
    EXTENDS = "extends"
    REPLICATES = "replicates"
    VERSION_OF = "version_of"
    # organisational / people
    SUPERVISES = "supervises"
    SUPERVISED_BY = "supervised_by"
    TEACHES = "teaches"
    TAUGHT_BY = "taught_by"
    LEADS = "leads"
    # Research projects & grants: the Co-PI edge (faculty CO_LEADS project),
    # appended like every catalogue member before it
    CO_LEADS = "co_leads"
    WORKS_IN = "works_in"
    ENROLLED_IN = "enrolled_in"
    ADVISED_BY = "advised_by"
    FUNDS = "funds"
    FUNDED_BY = "funded_by"
    PRODUCES = "produces"
    PRESENTED_AT = "presented_at"
    ASSIGNED_TO = "assigned_to"
    ASSIGNED_IN = "assigned_in"
    DISCUSSED_IN = "discussed_in"
    BLOCKS = "blocks"
    BLOCKED_BY = "blocked_by"
    # governance / operations
    GOVERNS = "governs"
    HOSTED_BY = "hosted_by"
    REQUIRES = "requires"
    REPORTS = "reports"
    ALLOCATED_TO = "allocated_to"
    # AI-proposed
    SMART_LINK = "smart_link"


class PermissionAction(str, Enum):
    """Permission actions (R4 — permission planning seam).

    Vocabulary derived from the SRS §3.3 capability matrix: view-class
    capabilities (view, read, export) map to READ; create/edit/upload/
    delete capabilities map to WRITE; administrative/approval/configure
    capabilities map to MANAGE. The permission evaluator consumes these
    actions; enforcement itself lands in S2 (edge ACL) and S5 (search
    pre-filtering) on top of this seam.
    """

    READ = "read"
    WRITE = "write"
    MANAGE = "manage"
