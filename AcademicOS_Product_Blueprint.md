# AcademicOS — Master Product Blueprint

**The world's best AI-powered Academic Operating System for universities.**
**Horizon: useful and architecturally sound for at least 15 years.**

> **Phase:** Product Architecture (pre-code). This document is the master plan.
> **Status:** No code, no database schema, no API, no implementation. Architecture only.
> **Companion documents:** `AcademicOS_SRS.md` (requirements), `AcademicOS_UI_Spec.md` (interface design), `AcademicOS_AI_Architecture.md` (AI/ML design). This blueprint is the umbrella that those three serve.
>
> **Roles authoring this document:** Chief Product Officer · Principal UX Architect · Enterprise Information Architect · Knowledge Management Expert · AI Workflow Designer.

---

## 0. Framing Principles (15-Year Test)

Before the eight parts, the blueprint is anchored by five longevity tests. Any feature that fails these is reconsidered:

1. **Data outlives software.** The system must be a *vessel for the university's knowledge*, not a silo. Open, exportable, standards-aligned. If AcademicOS is replaced in year 10, the knowledge must leave cleanly.
2. **AI-agnostic core.** Models change yearly; the *knowledge substrate* (documents, entities, graph, metadata) must persist independent of any vendor model. Today's frontier model is a plugin, not a foundation.
3. **Entity-centric, not folder-centric.** Folders are a *view*, not a prison. Knowledge is organised by what it *is about* (entities), not where it was dropped.
4. **Calm, trustworthy, auditable.** The system earns trust by being transparent about what it knows, what it inferred, and what it does not know. No silent actions; no silent failures.
5. **Composable for every role.** One student, one professor, one registrar, one NAAC evaluator — all live in the same substrate with role-appropriate lenses.

---

# PART 1 — COMPLETE NAVIGATION HIERARCHY

## 1.1 The Application Shell

Desktop-first (Fluent + Notion simplicity). Every screen shares one shell:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Topbar: [Spaces ▾] [Breadcrumb] … [Global Search ⌘K] [AI ⚡] [🔔] [@] │
├──────────┬───────────────────────────────────────────┬──────────────┤
│ Sidebar  │                 Workspace                   │ Right Panel  │
│ (modules)│  (contextual page: list / board / canvas)   │ (inspector / │
│          │                                             │  AI / activity)│
│          │                                             │              │
├──────────┴───────────────────────────────────────────┴──────────────┤
│ Statusbar: [sync ●] [index lag ⏱] [degradation ⚠] [storage] [help]  │
└──────────────────────────────────────────────────────────────────────┘
```

Global, always-present surfaces:
- **Command Palette (⌘K / Ctrl+K):** jump anywhere, run any action, natural-language search, "ask AI".
- **Global Search (Part 4):** the ⌘K entry doubles as universal search.
- **Right Panel:** contextual inspector (metadata, relationships, activity) + collapsible AI panel.
- **Statusbar:** sync health, index-lag chip, degradation banner, storage usage — the transparency layer from the AI Architecture (UI Spec §F11 / §12.18).

## 1.2 Primary Sidebar (Grouped Navigation)

```
ACADEMIC
  ├─ Dashboard (Home)
  ├─ Documents (the universal library)
  ├─ AI Assistant
  ├─ Teaching
  ├─ Research
  ├─ Projects
  └─ Publications

PEOPLE
  ├─ Faculty
  └─ Students

OPERATIONS
  ├─ Administration
  │    ├─ Committees
  │    ├─ Purchases & Budget
  │    ├─ Grants
  │    ├─ NAAC
  │    ├─ NBA
  │    └─ SAR
  ├─ Meetings
  ├─ Events
  ├─ Library
  └─ Resources

PERSONAL
  ├─ Calendar
  └─ Notifications

SYSTEM
  ├─ Search
  └─ Settings
```

The sidebar is collapsible to icons; module order is user-customisable; "Spaces" switch context (a Space = a department / lab / project / class — the tenancy and permission boundary).

## 1.3 Every Screen, Submenu, Dialog, Popup, and Menu

Below, each primary destination is enumerated. Conventions:
- **Page** = a full workspace view.
- **Submenu** = secondary navigation inside the module (left rail or tab strip).
- **Dialog** = modal requiring a decision.
- **Popup** = non-modal (hover card, toast, quick-peek, popover).
- **Right-click menu** = context menu on a *node/item* in a list or canvas.
- **Context menu** = action menu invoked *in place* (empty canvas, selected text, inline).

### 1.3.1 Dashboard (Home)
- **Pages:** Personal Briefing (AI digest), Institutional Overview (for admins), My Tasks.
- **Popups:** "AI Briefing" card (generated summary of what changed), widget hover-detail, "Snooze / Dismiss" toast.
- **Right-click menu (on a widget):** Configure · Refresh · Remove · Add to Space.
- **Context menu (empty area):** Add Widget · Reset Layout.
- **Dialogs:** Widget Library, Briefing Preferences.

### 1.3.2 Documents (Universal Library)
- **Submenus:** All Documents · Recent · Shared with Me · Favorites · Archived · Recycle Bin · By Entity · By Type.
- **Pages:** List view · Board (by category/tag) · Gallery (covers) · Graph view · Reader (the document viewer).
- **Dialogs:** Upload (drag-drop, with auto-classify preview) · Move/Assign to Entity · Version History · Link Manager · Properties (metadata editor) · Duplicate Review · Bulk Edit · Export.
- **Popups:** Quick-peek (hover shows summary + snippet) · Index-lag chip · "Related" hover card · Share popover.
- **Right-click menu (on a document):** Open · Open in Reader · Summarize · Ask AI · Link To… · Assign to Entity · Tag · Version History · Duplicate Check · Archive · Move to Recycle Bin · Properties · Copy Link.
- **Context menu (empty canvas):** New Document · Upload · New Folder/View · Paste Link.
- **Reader context menu (selected text):** Ask AI about selection · Cite · Add to Note · Create Task · Translate · Explain.

### 1.3.3 AI Assistant (Chat over all documents)
- **Submenus:** Conversations · Agents · Templates (research/teaching/etc.).
- **Pages:** Chat workspace (scope selector, message stream, source panel, citation cards, proposal cards, agent console).
- **Dialogs:** New Conversation (scope picker) · Agent Configuration · Export Conversation · Proposal Review.
- **Popups:** Source citation card (hover expands quote) · "Thinking / Retrieving" indicator · Suggestion chips.
- **Right-click menu (on a message):** Copy · Regenerate · Explain · Add to Note · Report Wrong.
- **Context menu (input box):** Attach Document · Set Scope · Insert Citation · Toggle Agent Mode.

### 1.3.4 Teaching
- **Submenus:** Courses · Syllabi · Lectures · Assignments · Quizzes · Student Feedback · Materials.
- **Pages:** Course home (timeline + materials) · Lecture builder · Quiz generator review · Feedback drafts.
- **Dialogs:** New Course · Import Syllabus · Generate Quiz (review) · Publish Feedback · Academic-integrity Settings.
- **Popups:** Lesson-plan hover · "AI-drafted, review needed" badge.
- **Right-click menu (on a course item):** Open · Summarize · Generate Quiz · Ask AI · Link Materials.
- **Context menu:** New Lecture · New Assignment.

### 1.3.5 Research
- **Submenus:** Projects · Literature · Hypotheses · Lab Notes · Collaborations · Funding.
- **Pages:** Research home (active projects + literature map) · Literature Review (cited graph) · Gap Analysis memo · Hypothesis board.
- **Dialogs:** New Research Project · Literature Monitor setup · Hypothesis Draft review · Citation Manager.
- **Popups:** Co-citation hover · "New paper on your topic" toast (from monitor).
- **Right-click menu (on a paper):** Open · Cite · Add to Project · Contradiction Check · Summarize.
- **Context menu:** New Note · New Hypothesis.

### 1.3.6 Projects
- **Submenus:** Active · Archived · By Sponsor · By Lab · Timelines · Milestones · Deliverables.
- **Pages:** Project board (Kanban by stage) · Gantt/timeline · Deliverables register · Documents.
- **Dialogs:** New Project · Milestone Editor · Risk Register · Link Publication/Outcome.
- **Popups:** Milestone hover · overdue toast.
- **Right-click menu (on a project):** Open · Dashboard · Link Docs · Link Publications · Generate Report.
- **Context menu:** New Milestone · New Task.

### 1.3.7 Publications
- **Submenus:** Mine · Co-authored · Under Review · Accepted · Published · Preprints · Citations · Journal Templates.
- **Pages:** Publication pipeline (stage board) · Citation network · Manuscript editor (with compliance panel).
- **Dialogs:** New Manuscript · Format to Journal · Reference Manager · Compliance & Ethics Check · Plagiarism Report review.
- **Popups:** Citation hover · "Originality verified / unverified" badge.
- **Right-click menu (on a manuscript):** Open · Format · Check Compliance · Generate Caption · Submit.
- **Context menu:** New Manuscript · Import from arXiv/DOI.

### 1.3.8 Administration
- **Submenus:** Overview · Committees · Purchases & Budget · Grants · NAAC · NBA · SAR · Policies · Audit Log.
- **Pages:** Admin dashboard (compliance heatmap) · Committee register · Purchase requisitions · Budget tracker · Accreditation workspace.
- **Dialogs:** New Committee · Purchase Requisition · Budget Transfer · Grant Report (draft review) · Accreditation Self-Assessment · Policy Editor · Audit Viewer.
- **Popups:** Compliance risk hover · approval-required toast.
- **Right-click menu (on a record):** Open · Approve · Reject · Assign · Export · Audit Trail.
- **Context menu:** New Record · Bulk Import.

### 1.3.9 NAAC / NBA / SAR (Accreditation)
- **Submenus (NAAC):** Criteria 1–7 · Evidence Repository · SSR Draft · AQAR · Data Quality Indicator.
- **Submenus (NBA):** Program Outcomes · Course Outcomes · Attainment · NBA Self-Report.
- **Submenus (SAR):** Annual Report Sections · Statistical Annex · Sign-off.
- **Pages:** Criterion workspace (with auto-pulled evidence from the substrate) · Attainment calculator (review) · Report preview.
- **Dialogs:** Map Evidence · Generate SSR Section (review) · Attainment Compute · Submit for Sign-off.
- **Popups:** "Evidence found / missing" indicator per criterion.
- **Right-click menu (on criterion):** Open · Auto-collect Evidence · Review Draft · Link Documents.
- **Context menu:** Add Criterion Note.

### 1.3.10 Faculty
- **Submenus:** Directory · My Profile · Loads · Supervisions · Committees · Achievements.
- **Pages:** Faculty profile (auto-CV) · Teaching load matrix · Supervision board · Contribution graph.
- **Dialogs:** Edit Profile · Generate CV (review) · Assign Load · Conflict-of-Interest declaration.
- **Popups:** Contribution hover · "Auto-updated" badge.
- **Right-click menu (on a faculty):** Open Profile · Generate CV · View Publications · Link to Project.
- **Context menu:** New Faculty · Import from HR.

### 1.3.11 Students
- **Submenus:** Directory · My Record · Enrollments · Submissions · Advising · Progress.
- **Pages:** Student profile · Enrollment timeline · Submission inbox · Advising notes · Cohort analytics.
- **Dialogs:** Enroll · Record Submission · Add Advising Note · Generate Progress Report (review).
- **Popups:** Risk/at-risk hover · deadline toast.
- **Right-click menu (on a student):** Open · View Submissions · Advise · Link to Project.
- **Context menu:** New Student · Bulk Import.

### 1.3.12 Meetings
- **Submenus:** My Meetings · Committees · Minutes · Action Items · Recordings.
- **Pages:** Meeting list · Minutes editor (auto-transcript + summary) · Action-item tracker.
- **Dialogs:** Schedule Meeting · Upload Recording (transcribe) · Approve Minutes · Assign Action Item.
- **Popups:** Action-item hover · "Minutes ready" toast.
- **Right-click menu (on a meeting):** Open · Summarize · Action Items · Link to Committee.
- **Context menu:** New Meeting.

### 1.3.13 Events
- **Submenus:** Conferences · Seminars · Workshops · Public Lectures · Registrations.
- **Pages:** Event calendar overlay · Event page (agenda + materials) · Registration list.
- **Dialogs:** New Event · Publish Agenda · Send Invite · Link Proceedings.
- **Popups:** Event hover · registration toast.
- **Right-click menu (on an event):** Open · Agenda · Materials · Link Publication.
- **Context menu:** New Event.

### 1.3.14 Library
- **Submenus:** Catalogue · E-Resources · Journals · Databases · Loans · Acquisitions.
- **Pages:** Catalogue search · Resource page (holdings + access) · Acquisition queue.
- **Dialogs:** Add Resource · Request Acquisition · Link to Course (reading list).
- **Popups:** Availability hover · "Full text" badge.
- **Right-click menu (on a resource):** Open · Full Text · Add to Reading List · Cite.
- **Context menu:** New Resource.

### 1.3.15 Resources
- **Submenus:** Software · Datasets · Laboratories · Equipment · Templates · Shared Assets.
- **Pages:** Resource catalogue · Dataset page (provenance + access) · Lab/equipment booking.
- **Dialogs:** Register Resource · Request Access · Book Equipment · Provenance Editor.
- **Popups:** Access hover · booking toast.
- **Right-click menu (on a resource):** Open · Request Access · Link to Project · Cite.
- **Context menu:** New Resource.

### 1.3.16 Calendar
- **Submenus:** My Calendar · Space Calendar · Resource Bookings · Academic Timeline.
- **Pages:** Month/Week/Day/Agenda views · Booking overlay.
- **Dialogs:** New Event · Book Resource · Conflict Resolver.
- **Popups:** Event hover · conflict toast.
- **Right-click menu (on an event):** Open · Reschedule · Link to Meeting/Doc.
- **Context menu:** New Event · New Booking.

### 1.3.17 Notifications
- **Submenus:** All · Mentions · Approvals · AI Digests · Deadlines · Watchlist.
- **Pages:** Notification feed · Digest archive · Watchlist manager.
- **Dialogs:** Notification Preferences · Manage Digests.
- **Popups:** Toast (transient) · badge counts.
- **Right-click menu (on an item):** Mark Read · Snooze · Open Source · Unsubscribe.
- **Context menu:** Mark All Read · Filter.

### 1.3.18 Search (Part 4 dedicated)
- **Submenus:** All · Documents · People · Projects · Publications · Events.
- **Pages:** Results (list / gallery / graph) · Advanced Filters · Saved Searches · Search Analytics (admin).
- **Dialogs:** Save Search · Manage Filters · Natural-Language Query builder.
- **Popups:** Suggested queries · facet popover · result hover-peek.
- **Right-click menu (on a result):** Open · Summarize · Ask AI · Link · Save to List.
- **Context menu:** New Saved Search.

### 1.3.19 Settings
- **Submenus:** Personal · Space · Members & Roles · Integrations (Drive/OneDrive) · AI & Models · Storage · Compliance & Retention · Appearance · Notifications · API & Webhooks · Billing.
- **Pages:** each submenu is a settings page.
- **Dialogs:** Invite Member · Connect Integration · Model/Routing Preferences · Retention Policy Editor · Export Data · Delete Space.
- **Popups:** Save confirmation toast · danger confirmation.
- **Right-click menu (on a member):** Role · Suspend · Remove.
- **Context menu:** Add Integration · New Role.

---

# PART 2 — DOCUMENT PHILOSOPHY

The central doctrine: **documents are citizens of a knowledge substrate, not files in a drawer.** Folders exist, but they are views, not containers.

## 2.1 How documents are organised
- **Primary organisation is by Entity (Part 6), not folder.** A paper "belongs to" a Research Project, a Course, and a Faculty member simultaneously. Organisation is many-to-many.
- **Folders = saved views.** A folder is a reusable filter (entity = X AND type = paper AND year = 2025). Nested folders are allowed for human comfort, but the system never *requires* a folder — every document is findable without one.
- **Spaces** are the top boundary (department / lab / class). A document lives in exactly one Space but can reference entities across Spaces it has access to.
- **Automatic placement.** On ingest, the AI proposes entity assignments and category (AI Architecture F7/F9); the human confirms or overrides. Nothing is orphaned — unclassified docs sit in a visible "Uncategorised" queue.

## 2.2 How folders work
- Folders are **non-destructive and overlapping** — the same document appears in many folders; moving it does not "relocate" the underlying knowledge.
- Folder membership can be manual (drag) or rule-based (auto-file new papers tagged "ML" into "Reading/ML").
- Renaming/restructuring a folder never breaks links, citations, or version history, because those bind to the document identity, not its folder path.

## 2.3 How metadata works
Seven layers (from AI Architecture / SRS §16), with a hard rule: **AI never overwrites a human-asserted value (FR-MET-009).**
- **L1 System:** hash, size, timestamps — automatic, always present.
- **L2 Filesystem:** Space, folder view, ACL root.
- **L3 Format:** page/row/slide counts, author from properties, creation date.
- **L4 Understanding:** structure, language, entity mentions, document type.
- **L5 Inferred:** discipline, audience, reading level, draft/final/preprint.
- **L6 Human-asserted:** any field a user sets — immutable to AI.
- **L7 Collaborative:** owner, sharees, last opened, comments.
Metadata drives every filter, facet, and saved view. It is the reason search and navigation work without folders.

## 2.4 How tags work
- **Controlled vocabulary** (curated per Space: subjects, methods, resource types) for precision + **open tags** (AI-suggested free-form) for discovery.
- Tags form a **tag graph** (synonyms, broader/narrower, co-occurrence). "ML" auto-normalises to "machine learning."
- Tags are many-to-many and explainable; suggested tags route through the Review Queue before applying (AI Architecture F8).

## 2.5 How relationships work
- **Typed, explicit links** between documents and entities (AI Architecture F10): `cites`, `supplements`, `contradicts`, `prerequisite_of`, `prior_art`, `follow_up`, `duplicate_of`, `version_of`.
- Every link carries a **rationale, shared entities, and evidence quotes** so a human can audit it in one glance.
- `contradicts` and `follow_up` links are **always suggested, never auto-applied** (reputational weight).
- Relationships are bidirectional in the graph and power Related Files (F16), literature maps, and impact analysis.

## 2.6 How version history works
- Versions are **evolution links**, not duplicates (AI Architecture F12). The system detects v1→v2→final via filename, timestamp, provenance, and embedding drift.
- A **version graph** records parent→child with a human-readable **change summary** ("added Methods, removed Appendix B").
- One **current version** is suggested by AI but **set by the human**. Superseded versions remain readable, dimmed, and auditable — never auto-deleted.
- Full provenance supports academic audit (who changed what, when).

## 2.7 How archives work
- **Archive** = retain, remove from active views, keep fully searchable and linkable. Used for completed projects, graduated cohorts, past accreditation cycles.
- Retention policies (per Space / compliance regime) auto-archive after N years, with a warning and a human override.
- Archived knowledge stays in the graph — it can still be cited and discovered, just out of the daily noise.

## 2.8 How deleted files work
- **Soft delete only.** Deletion moves a document to the **Recycle Bin** with a guaranteed **undo window ≥ 30 days** (AI Architecture A8).
- Permanent purge is a separate, approval-gated, audited action — never one-click.
- Any document referenced by a link, citation, or version chain cannot be purged until references are resolved (the system proposes re-pointing or archival).
- All deletions write to the **audit log** with actor, time, and reason.

---

# PART 3 — KNOWLEDGE GRAPH

The Knowledge Graph is the connective tissue that makes a flat file store into an institution's memory.

## 3.1 Node Types
Documents · Projects · Publications · Faculty · Students · Committees · Events · Courses · Meetings · Purchases · Budgets · Grants · Research Areas · Laboratories · Software · Datasets · Journals · Conferences · Spaces · Tags.

## 3.2 Edge Types (typed, weighted, attributed)
- **Authorship / membership:** `authored_by`, `supervised_by`, `member_of`, `enrolled_in`.
- **Temporal / lineage:** `version_of`, `prerequisite_of`, `preceded_by`, `part_of`.
- **Scholarly:** `cites`, `cited_by`, `prior_art`, `replicates`, `extends`, `contradicts`.
- **Organisational:** `belongs_to` (entity), `reports_to`, `funded_by`, `allocated_to`.
- **Activity:** `presented_at`, `discussed_in` (meeting), `assigned_in` (task), `linked_to`.
- Every edge stores **provenance** (inferred-by-AI vs asserted-by-human) and **confidence**, and is subject to ACL.

## 3.3 How each core entity links
| Entity | Primary links |
|---|---|
| **Documents** | `belongs_to` Projects/Courses/Committees; `cites` Publications; `version_of` prior docs; `contradicts`/`supplements` other docs |
| **Projects** | `funded_by` Grant; `produces` Publications/Datasets; `involves` Faculty/Students; `part_of` Research Area; `uses` Labs/Software |
| **Publications** | `authored_by` Faculty/Students; `cites` other Publications/Documents; `presented_at` Conference/Event; `reports` Project/Grant |
| **Faculty** | `member_of` Committees; `supervised_by`/`supervises` Students; `teaches` Courses; `authored` Publications; `leads` Projects/Labs |
| **Students** | `enrolled_in` Courses; `advised_by` Faculty; `contributes_to` Projects; `authored` (student) Publications; `member_of` Cohort |
| **Events** | `hosted_by` Space/Committee; `presents` Publications; `scheduled_in` Calendar; `linked_to` Resources |
| **Committees** | `member_of` Faculty; `governs` Policies/Accreditation; `minutes_in` Meetings; `allocated` Budget |
| **Meetings** | `of` Committee; `discussed_in` Documents; `assigned` Action Items; `recorded_as` Transcript |

## 3.4 What the graph enables
- **Discovery:** "show me everything connected to this grant" → publications, datasets, students, meetings, budget.
- **Impact & collaboration analysis:** co-authorship networks, mentorship trees, research-area clusters.
- **Compliance:** NAAC/NBA evidence auto-collected by traversing `belongs_to` / `produces` / `authored_by`.
- **Contradiction surfacing:** `contradicts` edges flag conflicting findings across the corpus.
- **Provenance & audit:** every claim traceable to its source node and edge.

## 3.5 Privacy & integrity of the graph
- Edges inherit the stricter ACL of their endpoints (AI Architecture R1). No cross-Space edge is ever created without permission.
- Inferred edges are clearly marked and removable; asserted edges are protected like L6 metadata.

---

# PART 4 — SEARCH ARCHITECTURE (Google-level)

A single, unified search that blends ten capabilities behind one box. Built on the five-index substrate (Lexical · Vector · Graph · Structured · ACL) from the AI Architecture.

## 4.1 Keyword Search
- BM25F over tokens + facets. Exact-match, phrase, boolean (`AND/OR/NOT`), field-scoped (`title:`, `author:`, `type:`).
- Instant-as-you-type with typo tolerance and synonym expansion.

## 4.2 Semantic Search
- Vector ANN over multi-representation embeddings (chunk + doc-summary + hypothetical-question + entity).
- Understands intent: "the paper that argues attention is all you need" finds the Transformer paper without the phrase.

## 4.3 AI Search
- Natural-language question answered with **grounded, cited responses** (RAG). Returns an answer + citation cards + source panel; **refuses** when the corpus lacks the answer (hallucination ≤ 1.5%, citation accuracy ≥ 97%).
- Clarifying questions when intent is ambiguous.

## 4.4 Filters
- Faceted: type, entity, discipline, author, date, sensitivity, language, tag, category, Space.
- Filter chips are composable; the active filter set is shareable (becomes a Saved Search).

## 4.5 Saved Searches
- Any query + filter combination saved with a name, scope, and refresh cadence.
- Surfaced as a sidebar item, a Command-Palette entry, and an optional notification ("3 new results for 'grant deadline Q3'").

## 4.6 Natural Language Search
- The query box accepts full sentences ("show me unpublished manuscripts supervised by me with a missed ethics disclosure"). Parsed into structured filters + semantic intent, then executed across indexes.

## 4.7 OCR Search
- Full-text search over text extracted from scanned PDFs, images, and slides (AI Architecture F2/F6). A scan of a printed paper is as searchable as a born-digital one.

## 4.8 Image Search
- Visual + textual: find images/figures/diagrams by caption, by contained text (OCR), or by visual similarity (multimodal embedding). "Find figures like this chart" returns visually similar plots.

## 4.9 Duplicate Search
- Detects exact and near-duplicates across formats/filenames (AI Architecture F11). Surfaces a "Duplicate of X?" proposal; consolidates links to a canonical copy without deleting.

## 4.10 Version Search
- "Show all versions of this manuscript" returns the version graph ordered by time with change summaries; lets you jump to any historical edition or set a new current version.

## 4.11 Ranking, Freshness & Trust
- **Fusion:** lexical + vector + graph merged via Reciprocal Rank Fusion, then a cross-encoder reranker.
- **Personalisation:** role + recency lightly bias results (researcher sees prior-art; teacher sees methods).
- **Freshness:** an **index-lag chip** shows how current the index is (ingest is asynchronous) — users never think a just-uploaded doc is "missing."
- **Explainability:** every result shows *why* it matched (matched entity, snippet, score).
- **Safety:** ACL pre-filtering guarantees zero cross-Space leakage (hard invariant).

---

# PART 5 — ACADEMIC MODULES

Each module is a **lens** over the same substrate, not a separate database. Modules add role-appropriate workflows on top of documents, entities, and the graph.

| Module | Purpose (lens over the substrate) |
|---|---|
| **Teaching** | Courses, syllabi, lectures, assignments, quizzes — AI drafts, instructor reviews. Academic-integrity guard prevents completing student work. |
| **Research** | Projects, literature, hypotheses, lab notes — literature maps, gap analysis, monitors. Citations always verifiable. |
| **Projects** | Timelines, milestones, deliverables, risks — linked to publications, grants, datasets produced. |
| **Publications** | Pipeline from draft → review → published; journal formatting, reference management, compliance/ethics & plagiarism checks. |
| **Administration** | Committees, purchases, budgets, policies, audit — approval-gated, auditable actions only. |
| **NAAC** | Criteria 1–7, evidence auto-pulled from substrate, SSR/AQAR drafting, data-quality indicators. |
| **NBA** | Program/Course outcomes, attainment computation (review), self-report. |
| **SAR** | Annual report sections, statistical annex, sign-off workflow. |
| **Students** | Directory, enrollments, submissions, advising, progress analytics, at-risk signals. |
| **Faculty** | Directory, loads, supervisions, contributions, auto-CV. |
| **Meetings** | Scheduling, recordings → transcript → minutes → action items, all linked to committees. |
| **Events** | Conferences/seminars/workshops, agendas, registrations, linked proceedings. |
| **Library** | Catalogue, e-resources, journals, databases, loans, acquisitions, reading-list linking. |
| **Resources** | Software, datasets, labs, equipment, templates — provenance, access, booking. |
| **AI Assistant** | Conversational, scoped, cited, proposal-driven; optional agent mode for multi-step tasks. |
| **Calendar** | Personal/space/resource views, bookings, academic timeline, conflict resolution. |
| **Notifications** | Mentions, approvals, AI digests, deadlines, watchlist — the calm, trustworthy signal layer. |

Every module reuses the same document reader, the same search, the same graph, the same AI. Nothing is rebuilt per module — that is what makes the system coherent and 15-year sustainable.

---

# PART 6 — ENTITY DESIGN (Folders replaced by Entities)

The foundational shift: **stop organising by where a file sits; organise by what it is about.** Every document belongs to one or more entities.

## 6.1 Core Entity Catalogue
| Entity | Key attributes (illustrative) | Lifecycle |
|---|---|---|
| **Faculty** | name, designation, department, expertise[], ORCID, loads | hired → active → emeritus |
| **Student** | id, program, cohort, enrollment[], advisor | admitted → active → graduated/alumni |
| **Research Project** | title, PI, sponsor, period, milestones[], status | proposed → active → completed/archived |
| **Publication** | title, authors[], venue, DOI, status, citations | draft → review → published/preprint |
| **Committee** | name, mandate, members[], minutes[] | constituted → active → dissolved |
| **Event** | type, date, venue, agenda[], registrations[] | planned → held → archived |
| **Course** | code, title, term, instructor[], syllabus | designed → offered → completed |
| **Meeting** | committee, date, attendees[], minutes, actions[] | scheduled → held → minutes approved |
| **Purchase** | item, vendor, cost, approver, status | requested → approved → procured |
| **Budget** | period, head, allocated, spent, line-items[] | drafted → approved → closed |
| **Research Grant** | agency, amount, period, PI, reports[] | applied → awarded → active → closed |
| **Research Area** | name, parent, related[] | evolving taxonomy |
| **Laboratory** | name, PI, equipment[], members[] | active/legacy |
| **Software** | name, license, owner, access[] | registered/retired |
| **Dataset** | title, provenance, license, access[], citations[] | created → published → cited |
| **Journal** | name, ISSN, template, IF | reference |
| **Conference** | name, periodicity, proceedings[] | reference |
| **Document** | identity, type, entities[], metadata (L1–L7), links[], versions[] | living |
| **Space** | name, members, roles, ACL root | tenancy boundary |
| **Tag** | label, synonyms, broader/narrower | governed vocabulary |

(Plus: Department, Program, Thesis, Patent, Funding Agency, Vendor, Cohort, Reading List — as needed.)

## 6.2 The "belongs to" rule
- Every Document has ≥ 1 entity association (`belongs_to`). If none, it sits in "Uncategorised" until a human or AI assigns one.
- Associations are **typed**: a document is `syllabus_of` a Course, `report_of` a Project, `manuscript_of` a Publication, `minutes_of` a Meeting.
- Entities can nest (Research Area → sub-area; Department → Lab) enabling roll-up views ("all documents in the ML research area").

## 6.3 Why this outlasts folders
- A document attached to three entities is found from all three — no "wrong folder" problem.
- When a committee dissolves or a course ends, its documents persist, re-pointed, never orphaned.
- New entity types (a new accreditation framework, a new funding scheme) are added as nodes, not as a refactoring of the whole tree.
- The graph makes implicit structure explicit: a folder can never show you "everything citing this grant," an entity link can.

---

# PART 7 — AI FEATURES

AI is the default collaborator, always grounded, always citeable, always reviewable. (Mapped to the 21-feature AI Architecture.)

| Capability | What it does | Guardrail |
|---|---|---|
| **Auto Classification** (F9) | Places docs in the category tree (navigation/ACL). | Confident → auto; else Review Queue. |
| **Auto Tagging** (F8) | Controlled + open tags via tag graph. | Synonym-normalised; suggested tags reviewed. |
| **Auto Linking** (F10) | Typed doc/doc and doc/entity links + contradiction detection. | `contradicts`/`follow_up` always suggested, never auto. |
| **Auto Summaries** (F15) | Abstractive / structured / extractive, faithful to source. | Faithfulness verifier; coverage map shows gaps. |
| **Auto Metadata** (F7) | Fills L1–L5; proposes L6 diffs only. | Never overwrites human-asserted (FR-MET-009). |
| **Auto Timeline** | Builds event/version/milestone timelines from docs. | Dates inferred only when present; never fabricated. |
| **Auto CV** | Generates a faculty CV from publications, grants, supervision. | Clearly labelled draft; human owns the signature. |
| **Auto API Score** | Computes academic performance indices (h-index, attainment, NAAC metrics). | Transparent formula; inputs citeable. |
| **Auto Research Timeline** | Visualises a project's evolution: papers→grants→datasets→impact. | Sourced from graph edges. |
| **Reviewer Assistant** | Checks manuscripts for scope/fit, missing citations, ethical flags. | Flags only; never rejects on behalf of a human. |
| **Proposal Assistant** | Drafts research/grant/project proposals from prior docs. | Grounded in supplied content; citations attached. |
| **Grant Assistant** | Compiles progress reports, budget narratives, compliance from linked records. | Unverified figures omitted + flagged. |
| **Teaching Assistant** (F19) | Lesson plans, explanations, quizzes, feedback — corpus-grounded, level-adapted. | Academic-integrity guard; instructor approval before release. |
| **(Also)** QA, Semantic Search, AI Chat, Related Files, Duplicate/Version detection, Research/Publication/Administrative assistants | see AI Architecture. | same grounding/refusal/ACL invariants. |

**Universal AI invariants (non-negotiable):**
1. Every AI claim is citeable to a source chunk.
2. The system refuses rather than hallucinates when the corpus lacks the answer.
3. AI proposes; humans dispose. Destructive/approval-gated actions never auto-execute.
4. AI never overwrites a human-asserted value.
5. No cross-Space leakage, ever (R1).

---

# PART 8 — PRODUCT PHILOSOPHY

## 8.1 How the software should behave
- **It remembers so you don't have to.** The substrate is the university's externalised memory; the product's job is to make any piece retrievable in seconds.
- **It is proactive but calm.** AI surfaces what matters (a contradiction, a deadline, a new relevant paper) without nagging. Notifications are signals, not noise.
- **It shows its work.** Every answer, tag, and link is explainable and auditable. Trust comes from transparency, not mystique.
- **It defers to humans on judgement.** The system drafts, ranks, and warns; people decide, sign, and own.
- **It degrades gracefully.** If AI is unavailable, sources and search remain; the user is told the current state (degradation banner), never left guessing.

## 8.2 How users should think while using it
- "This is where my knowledge lives" — not "this is where my files sit."
- "Ask it anything; it will show me the source" — not "I hope the search finds it."
- "The AI did a draft; I'll review" — not "the AI decided."
- "Everything is connected" — a paper, a grant, a student, a committee are one graph, not separate apps.

## 8.3 How information should flow
```
Capture (any format) → Understand (CDM) → Enrich (metadata/tags/links/versions)
        → Connect (graph) → Retrieve (search) → Reason (AI, grounded)
        → Act (human-reviewed proposal) → Record (audit + new knowledge)
```
The loop is continuous: every human action becomes new structured knowledge feeding the next retrieval.

## 8.4 Principles that must never be violated
1. **Data sovereignty.** The university owns its knowledge; export is always possible in open formats.
2. **Privacy by structure.** ACL is enforced at the infrastructure layer, independent of models (R1). Degradation never relaxes isolation.
3. **No silent actions.** Every AI write, link, or classification is visible and reversible.
4. **No fabricated authority.** AI never asserts authorship, novelty, grades, compliance sign-off, or references it cannot verify.
5. **Human accountability.** The system proposes; the professional remains responsible.
6. **Longevity over novelty.** We optimise for the knowledge surviving us, not for this quarter's model.
7. **One substrate, many lenses.** No module is an island; duplication of truth is a defect.

---

## Closing Note (to engineering, when the time comes)

This blueprint is the contract. When code begins, it must honour:
- Entities over folders (Part 6) → the data model starts from entities, not a path tree.
- The five-index substrate and the 21-feature AI architecture already specified.
- The navigation hierarchy (Part 1) as the source of truth for screens and menus.
- The non-negotiable principles (8.4) as acceptance criteria.

Until then: architecture only.

*— End of AcademicOS Master Product Blueprint —*
