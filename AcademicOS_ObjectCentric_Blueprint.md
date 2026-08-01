# AcademicOS — Object-Centric Knowledge Graph Blueprint
### The Digital Brain, not the File Manager

> **Supersedes** the module-based navigation of `AcademicOS_Product_Blueprint.md` (Part 1). This document is the new master product architecture.
> **Phase:** Product Architecture (pre-code). **No code, no database, no API, no implementation — architecture only.**
> **Roles:** Chief Product Officer · Principal UX Architect · Enterprise Information Architect · Knowledge Management Expert · AI Workflow Designer.

---

## 0. The Paradigm Shift

| Old model (File Manager) | New model (Digital Brain) |
|---|---|
| Software is organised into **modules** (Teaching, Research, Projects…) | Software is organised around **Objects** — every thing is one |
| Documents live in **folders** | Documents are **Objects** linked to other Objects |
| Each module has its own UI, data, and logic | Every Object has the **same 14 universal capabilities** |
| Navigation is a menu of modules | Navigation is **jumping to an Object** and choosing a **view frame** |
| Search finds files | Search finds **any Object** and answers across the graph |
| The app *stores* your files | The app *is* your institution's externalised memory |

**The core thesis:** a university does not think in "modules." It thinks in *things* — a professor, a paper, a grant, a meeting, a student — and how those things connect. AcademicOS models exactly that. A "module" is just a **saved lens** (a filter + view frame) over the Object Graph. There is no Teaching Module; there are Course Objects, Student Objects, and Assignment Objects, all of which are Objects like any other.

The system behaves like a **Digital Brain**:
- **Perception** — anything captured becomes an Object.
- **Memory** — Objects and their Relationships form a persistent Knowledge Graph.
- **Reasoning** — AI reasons over the graph, always grounded in Objects.
- **Action** — Tasks, approvals, and proposals are themselves Objects or live on Objects.
- **Reflection** — Timeline, Dashboard, and Contradiction detection let the brain examine itself.

---

## 1. THE UNIVERSAL OBJECT MODEL

### 1.1 What is an Object?

An **Object** is the single atomic unit of the system. Every Faculty member, Student, Course, Publication, Grant, Meeting, Document, Budget — everything — is an Object. An Object is defined by:

```
        ┌──────────────────────────────────────────┐
        │                 OBJECT                    │
        │  type: Course        id: obj:course:8F2K… │
        │  label: "ML 2025"    slug: /o/course/8F2K │
        ├──────────────────────────────────────────┤
        │  1. Unique ID       8. Tasks              │
        │  2. Metadata         9. AI Summary         │
        │  3. Timeline        10. AI Chat           │
        │  4. Relationships   11. Permissions        │
        │  5. Attachments     12. Activity Log       │
        │  6. Version History 13. Smart Links        │
        │  7. Comments        14. Knowledge Graph    │
        └──────────────────────────────────────────┘
```

**Uniformity is the product.** Because every Object carries the same 14 capabilities, the user learns the system once. Opening a Grant feels like opening a Student feels like opening a Meeting — same verbs, same panels, different content.

### 1.2 The 14 Universal Capabilities (detailed)

| # | Capability | What it is | How AI uses it |
|---|---|---|---|
| 1 | **Unique ID** | Type-prefixed, immutable, resolvable handle (e.g. `obj:publication:9QX…`). Never reused. | Lets any reference, citation, or link resolve forever; powers "jump to object" and graph edges. |
| 2 | **Metadata** | 7-layer record (L1–L7). AI infers L1–L5; L6 human-asserted is **never overwritten** (FR-MET-009). | Drives facets, filters, saved lenses, and retrieval. |
| 3 | **Timeline** | The object's chronological life: created, status changes, versions, scheduled events, related activity. | Powers Universal Timeline; "what changed," "what's next." |
| 4 | **Relationships** | Explicit, typed, directed edges to other Objects (`funds`, `authors`, `teaches`, `member_of`…). | The graph itself; enables discovery, impact, compliance roll-ups. |
| 5 | **Attachments** | Files or other Objects attached (a syllabus Document on a Course; a Dataset on a Project). | Enriches context for AI Chat and summarisation. |
| 6 | **Version History** | Version graph with change summaries; one human-set current version. | Lets the brain show evolution, not just the latest. |
| 7 | **Comments** | Threaded discussion anchored to the Object (or to a passage/field). | Feeds activity; AI can summarise threads. |
| 8 | **Tasks** | Action items living on the Object: assignee, due, state, subtasks. | Tasks are first-class; power Universal Inbox. |
| 9 | **AI Summary** | Faithful, refreshable abstract of the Object and its attachments. | Always citeable; coverage map shows gaps. |
| 10 | **AI Chat** | Scoped conversation over this Object + its neighbourhood. | Grounded RAG; refuses when the graph lacks the answer. |
| 11 | **Permissions** | ACL on the Object; inherits from Space/parent; supports sharing & roles. | Enforced at infrastructure layer (R1, no leakage). |
| 12 | **Activity Log** | Append-only audit of every operation on the Object. | Proves "who did what, when"; supports compliance. |
| 13 | **Smart Links** | AI-suggested candidate Relationships with evidence, routed to review. | Turns implicit structure into explicit edges (F10). |
| 14 | **Knowledge Graph** | The Object's **ego-graph** — its neighbourhood rendered and traversable. | The brain's "you are here"; one click to any neighbour. |

### 1.3 Universal Object Operations (the brain's "muscles")

Because capabilities are uniform, every Object supports the same verbs:
**Open · Link · Attach · Comment · Task · Version · Summarize · Chat · Share/Permission · Audit · Smart-Link · Relate · Archive · Delete (soft).**
There is no feature you can do to one Object that you cannot do to another. This uniformity is what makes the system feel like one brain rather than a toolbox.

### 1.4 Object Lifecycle (base + type extension)

- **Base states:** `Draft → Active → Archived/Superseded`. Every Object has these.
- **Type extensions** layer on top (e.g. Publication: `draft → under_review → published/preprint`; Grant: `applied → awarded → active → closed`; Meeting: `scheduled → held → minutes_approved`). Type-specific states are metadata on the universal lifecycle, never a separate data model.

---

## 2. OBJECT TYPE CATALOGUE

All examples from the brief are Objects. The table shows each type's **signature relationships** and whether it is **versionable**. (The 14 capabilities above apply to every row.)

| Object Type | Represents | Signature Relationships | Versionable |
|---|---|---|---|
| **Faculty** | A staff member | `teaches` Course, `supervises` Student, `leads` Project/Lab, `authored` Publication, `member_of` Committee | profile drafts |
| **Student** | A learner | `enrolled_in` Course, `advised_by` Faculty, `contributes_to` Project, `authored` (student) Publication | record revisions |
| **Course** | A class/offering | `has` Syllabus(Document), `enrolls` Students, `taught_by` Faculty, `uses` Resources | syllabi |
| **Research Project** | A research effort | `funded_by` Grant, `produces` Publication/Dataset, `involves` Faculty/Student, `uses` Lab/Software, `part_of` Research Area | proposals/reports |
| **Publication** | A paper/manuscript | `authored_by` Faculty/Student, `cites` Publication/Document, `presented_at` Conference/Event, `reports` Project/Grant | manuscripts |
| **Grant** | Funding award | `funds` Project, `awarded_to` Faculty, `requires` Reports(Task), `under` Agency | proposals |
| **Meeting** | A gathering | `of` Committee, `discussed_in` Document, `assigned` Task, `recorded_as` Transcript | minutes |
| **Committee** | A governing body | `member_of` Faculty, `governs` Policy/Accreditation, `holds` Meeting, `allocates` Budget | charters |
| **Event** | Conference/seminar/etc. | `hosted_by` Space/Committee, `presents` Publication, `scheduled_in` Calendar | agendas |
| **Task** | An action item | `assigned_to` Person, `on` (any Object), `blocks`/`blocked_by` Task, `due` Date | — |
| **Document** | Any file/artefact | `belongs_to` (any Object), `cites`/`version_of`/`contradicts` other Docs, `attached_to` Object | yes (F12) |
| **Purchase** | Procurement | `requested_by` Person, `against` Budget, `for` Lab/Project, `approved_by` | requisitions |
| **Budget** | A fund | `allocated_to` Project/Committee, `spent_on` Purchase, `period` | line-items |
| **Journal** | A venue | `publishes` Publication, `has` Template | — |
| **Conference** | A venue (event series) | `proceedings` Publication, `hosts` Event | — |
| **Dataset** | A data artefact | `produced_by` Project, `cited_by` Publication, `licensed` | schema/versions |
| **Software** | A tool/code | `owned_by` Lab/Faculty, `used_in` Project, `licensed` | releases |
| **Laboratory** | A facility | `led_by` Faculty, `houses` Equipment, `member_of` (people), `runs` Project | — |
| **Research Area** | A field/topic | `parent`/`child` Area, `contains` Project/Publication, `tagged` | taxonomy |
| *(system)* **Space** | Tenancy/team boundary | `contains` Objects, `has` Members/Roles | — |
| *(system)* **Note / Message** | Free capture | `attached_to` any Object | — |
| *(system)* **Integration** | Drive/OneDrive/etc. | `syncs` Documents | — |

**Key insight:** "Teaching" is not a module — it is the *lens* you get when you open a Course Object and see its Students, Faculty, Syllabus, Assignments (Tasks), and Meetings. The module dissolves into Objects + a view frame.

---

## 3. HOW OBJECTS INTERACT

### 3.1 The Relationship Edge
Every connection is a **typed, directed, attributed edge**:

```
(Faculty:DrA) ──[supervises, since=2023, confidence=1.0, provenance=asserted]──▶ (Student:Bob)
(Publication:P1) ──[cites, page=4, evidence="Fig 2", provenance=inferred]──▶ (Publication:P2)
(Grant:G1) ──[funds, amount=$, period=…]──▶ (ResearchProject:RP1)
```
Attributes: **verb, direction, provenance (asserted vs inferred), confidence, ACL, timestamp, evidence.** Inferred edges are visibly marked and removable; asserted edges are protected like L6 metadata.

### 3.2 Interaction Rules
1. **Everything connects through Objects, not folders.** A Document is attached to a Course and a Project simultaneously — no "wrong place."
2. **Events propagate.** When an Object changes state (Grant awarded, Paper published, Meeting held), related Objects' **Timelines** receive an entry and the relevant people get **Inbox** items.
3. **Aggregation by traversal.** "Everything connected to Grant G1" = graph traversal, not a query across modules.
4. **No orphan knowledge.** Every Document must have ≥1 Relationship (`belongs_to`); unlinked Objects sit in a visible "Unlinked" queue for human/AI resolution.
5. **ACL inherits and never leaks.** An edge inherits the stricter permission of its endpoints (R1). Cross-Space edges require explicit permission.

### 3.3 Canonical Interaction Flows (illustrative)
- **Grant → Research → Publication → Impact:** `Grant` funds `ResearchProject` → Project `produces` `Publication` (authored_by `Faculty`/`Student`) → Publication `cites` prior work and `presented_at` `Conference` → all visible in each Object's **Knowledge Graph** and **Timeline**.
- **Course → Learning:** `Course` `enrolls` `Students`, `taught_by` `Faculty`, `has` `Syllabus` (Document) and `Assignments` (Tasks) → opening the Course shows the whole learning context.
- **Committee → Compliance:** `Committee` `holds` `Meeting` (minutes Document, `assigned` Tasks) → `governs` accreditation evidence → NAAC/SAR lenses traverse `belongs_to` to auto-collect proof.
- **Contradiction surfacing:** two Publications `contradicts` each other (Smart Link) → both Timelines flag it; the brain reflects the conflict instead of hiding it.

---

## 4. HOW DOCUMENTS ARE LINKED

Documents are Objects (type = Document) and therefore participate fully in the graph.

- **Structural links (asserted):** a Document is `attached_to` or `belongs_to` one or more Objects (a syllabus `belongs_to` a Course; a report `belongs_to` a Project). These are explicit and human-set.
- **Scholarly links (asserted/inferred):** `cites`, `cited_by`, `prior_art`, `replicates`, `extends`, `contradicts` — parsed from references (DOI resolution) and from Smart Links (AI-detected semantic relationships with evidence).
- **Evolution links:** `version_of` builds the version graph (F12) with change summaries.
- **Duplicate links:** `duplicate_of` consolidates to a canonical Object without deletion (F11).
- **Smart Links (the differentiator):** the AI continuously scans for *implicit* relationships — "slide deck B quietly contradicts paper A," "dataset D underpins publication P" — and proposes them as **Smart Links** with rationale + evidence quotes. `contradicts`/`follow_up` are *always suggested, never auto-applied* (reputational weight).
- **Resolution is by Object ID, not path.** Links bind to the immutable `obj:…` handle, so renaming, moving, or versioning a Document never breaks a link, citation, or the graph.

Result: the document is no longer "a file in a folder" but **a node in the brain** — findable from every Object it touches, citeable forever, and self-describing through its links.

---

## 5. UNIVERSAL TIMELINE

The Timeline is a **first-class view frame**, not a per-module afterthought.

### 5.1 Two levels
- **Object Timeline:** every Object's own chronological life — creation, edits, status changes, versions, comments, tasks, scheduled events, and related activity (e.g. a Publication's Timeline shows when it was cited).
- **Universal Timeline:** the merged, permission-filtered stream of Timeline entries across **all Objects the user can see**, sorted by time, with **past (history)** and **future (scheduled/deadlines)** modes.

### 5.2 What it shows
- "What happened this week" — Grant awarded, Paper published, Meeting held, Document uploaded.
- "What's next" — Task due, Event scheduled, Grant closing, Milestone approaching.
- Filterable by Object type, Space, person, Research Area, or free query ("show me everything about the ML area in Q3").
- Each entry is a **link to its Object**; clicking jumps there.

### 5.3 Why it matters for a Digital Brain
The Timeline is the brain's **memory stream** — a single, trustworthy chronology of the institution's intellectual and operational life, replacing the scattered "recent items" lists that live inside separate modules.

---

## 6. UNIVERSAL INBOX

One inbox for the person, aggregating signals from **every Object**, not from modules.

### 6.1 Channels (all unified)
- **Assigned Tasks** — anything `assigned_to` you, across all Objects.
- **Approvals** — actions requiring your sign-off (purchase, budget transfer, compliance, member role).
- **Mentions** — `@you` in any Comment or Chat.
- **Shared with Me** — Objects/Attachments others shared.
- **AI Digests** — "3 new papers on your topic," "contradiction detected in your area."
- **Deadlines** — approaching Tasks/Events/Milestone dates.
- **Watchlist** — changes to Objects you follow.
- **Flagged** — contradictions, compliance gaps, unverified references.

### 6.2 Triage model
Each item links to its **source Object** and supports universal actions: **Complete · Approve/Reject · Snooze · Delegate · Convert to Task · Comment · Open.** Goal: a calm, zero-noise signal layer where nothing important is buried in a module the user forgot to check.

---

## 7. UNIVERSAL SEARCH

Search returns **any Object of any type**, not just documents.

- **Heterogeneous results:** a query may return a Faculty, a Grant, a Meeting, and a Document — each rendered in its Object card with type badge.
- **Object-type facets:** filter by type, relationship, metadata, date, sensitivity, Space.
- **Ten modes (from the Search Architecture):** Keyword · Semantic · AI (grounded RAG answer + citations) · Filters · Saved Searches · Natural Language · OCR · Image · Duplicate · Version — now operating over the whole Object space.
- **Relationship/NL queries:** "show me everything connected to Grant G1," "who supervises students working on the ML area," "unpublished manuscripts I advise with a missed ethics disclosure."
- **Jump-to-Object:** by ID, name, or `@` mention in the command palette.
- **Trust:** ACL pre-filter (zero leakage), freshness/index-lag chip, and explainability ("matched because it cites X").

---

## 8. UNIVERSAL WORKSPACE

The working surface is **Object-centric and frame-based**, replacing module pages.

### 8.1 Two contexts
- **Global Workspace (the Brain at a glance):** recent Objects, Inbox peek, Universal Timeline, and a Graph overview of your Spaces.
- **Object Workspace (contextual):** open *any* Object → you see its detail with the 14 capabilities + its **Knowledge Graph** (neighbourhood) + **Timeline** + **Activity Log**. This is the same screen whether the Object is a Professor or a PDF.

### 8.2 View Frames (switch without leaving the brain)
| Frame | Use |
|---|---|
| **Detail** | The 14-capability inspector for one Object. |
| **List** | A saved lens (filter + sort) over many Objects. |
| **Board** | Objects grouped by state/type/relationship (Kanban). |
| **Graph** | The Knowledge Graph — traverse relationships visually. |
| **Canvas** | Free-form assembly of Objects (a research map, a lesson plan). |
| **Calendar** | Time-based view of Objects with dates/Tasks/Events. |
| **Map** | Geographic, when Objects have location. |

### 8.3 Command Palette (⌘K)
Universal jump + universal operation: "Open Grant G1," "Summarize this Course," "Link Document D to Project P," "New Task on Meeting M." One entry point to the entire brain.

### 8.4 Lenses (the "modules" reborn)
A **Lens** = a saved filter + default frame + role. "Teaching" lens = `type:Course OR (Task on Course) …` shown as Board. Lenses are cheap, composable, and never duplicate data — they are views over the graph.

---

## 9. UNIVERSAL DASHBOARD

The Dashboard is the brain's **self-reflection** surface.

- **Brain Briefing:** an AI narrative — "Here's what changed in your world this week" — generated across all your Objects (not one module).
- **Widgets are saved Object-queries**, not module widgets:
  - "Tasks due this week across all my Objects"
  - "Grants closing in 30 days"
  - "New contradictions in my Research Area"
  - "Committee meetings this month"
  - "Students at risk (missed submissions)"
  - "Publications cited this quarter"
- **Role-adaptive:** a Faculty brain shows research/teaching signals; an Admin brain shows compliance/approvals; a Student brain shows deadlines/advising.
- **Persistent vs focused:** a default briefing plus drill-down dashboards per Lens.

---

## 10. DIGITAL BRAIN BEHAVIOUR

| Brain function | System behaviour |
|---|---|
| **Perception** | Capture anything (upload, paste, integrate Drive/OneDrive, record a meeting) → it becomes an Object + Attachments. |
| **Memory** | Objects + Relationships persist as the Knowledge Graph; nothing is lost; versions retain history. |
| **Reasoning** | AI reasons over the graph, grounded in Objects, citing them; refuses rather than hallucinates; proposes, never decides. |
| **Action** | Tasks, approvals, and proposals are Objects or live on Objects; destructive/approval-gated actions never auto-execute. |
| **Reflection** | Timeline, Dashboard, contradiction detection, and audit let the brain examine and improve itself. |

**Calm, trustworthy, proactive.** The brain surfaces what matters (a contradiction, a deadline, a new relevant paper) without noise. It shows its work: every AI claim cites an Object; every inferred link is marked; every action is in the Activity Log. It degrades gracefully — if AI is unavailable, the graph, search, and Objects remain, and the user is told the current state.

---

## 11. FROM MODULES TO OBJECTS — MAPPING

| Former "Module" | Now an Object+Lens |
|---|---|
| Teaching | Course / Student / Task Objects + "Teaching" Lens (Board frame) |
| Research | ResearchProject / Publication / Dataset Objects + "Research" Lens |
| Projects | ResearchProject / Task / Milestone Objects + "Projects" Lens |
| Publications | Publication Object + pipeline Board (by status) |
| Administration | Committee / Purchase / Budget / Grant Objects + "Admin" Lens |
| NAAC / NBA / SAR | Lenses that traverse `belongs_to` to auto-collect evidence from Objects |
| Students / Faculty | Student / Faculty Objects (their detail = the module UI) |
| Meetings / Events | Meeting / Event Objects |
| Library / Resources | Document / Dataset / Software / Journal Objects + "Library" Lens |
| Calendar | Calendar frame over all date-bearing Objects |
| Notifications | Universal Inbox |
| Search | Universal Search |
| Dashboard | Universal Dashboard (Brain Briefing) |

---

## 12. NON-NEGOTIABLE PRINCIPLES (carried forward)

1. **Data sovereignty** — the university owns its Objects; export is always possible in open formats.
2. **Privacy by structure** — ACL enforced at the infrastructure layer; degradation never relaxes isolation (R1).
3. **No silent actions** — every link, classification, or change is visible and reversible.
4. **No fabricated authority** — AI never asserts authorship, grades, compliance sign-off, or references it cannot verify.
5. **Human accountability** — the brain proposes; the person decides and owns.
6. **Longevity over novelty** — optimise for the knowledge surviving us, not this quarter's model.
7. **One graph, many lenses** — duplication of truth is a defect; modules are views, not silos.
8. **Uniformity** — every Object has the same 14 capabilities; learning the system once unlocks all of it.

---

*The File Manager asks "where did I put it?" The Digital Brain answers "here is everything connected to it, and why." AcademicOS is the latter.*

*— End of AcademicOS Object-Centric Knowledge Graph Blueprint —*
