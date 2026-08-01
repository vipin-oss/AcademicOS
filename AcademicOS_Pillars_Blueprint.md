# AcademicOS — Four Pillars Extension (Object-Centric, v2)

> **Builds on:** `AcademicOS_ObjectCentric_Blueprint.md` (the Universal Object Model, 14 capabilities, Digital Brain).
> **Adds:** four pillars — (1) Workspace Architecture, (2) AI Memory, (3) Automation Engine, (4) Proactive AI.
> **Phase:** Product Architecture (pre-code). **No code, no database, no API, no implementation — architecture only.**
> **Roles:** Chief Product Officer · Principal UX Architect · Enterprise Information Architect · Knowledge Management Expert · AI Workflow Designer.

**Design rule for this document:** every new concept below is expressed as either (a) a new **Object type** (so it inherits the 14 universal capabilities), (b) a **graph behaviour** over existing Objects, or (c) a **Lens/Frame** — never a separate silo. This keeps the "Digital Brain" coherent.

---

# PILLAR 1 — WORKSPACE ARCHITECTURE

## 1.1 The key distinction: Space vs Workspace vs Lens
- **Space** = *who you belong to* (tenancy, permission boundary, members/roles). Defined in the Object Blueprint.
- **Workspace** = *what you are focused on right now* (a task/role context that aggregates Objects and sets AI context). **A Workspace is itself an Object** (type = `Workspace`) with the 14 capabilities.
- **Lens** = a saved filter + frame *inside* a Workspace (e.g. "my tasks" within the Research Workspace).

A user belongs to one or more Spaces and operates across many Workspaces. Switching Workspace changes the AI's context automatically — no manual "set context" needed.

## 1.2 Workspace as an Object
A `Workspace` Object carries:
- **type** (Teaching / Research / Grant / Committee / Event / Student / Personal / Custom)
- **membership rule** — which Objects belong (explicit links + optional auto-rule, e.g. "all Courses I teach")
- **default frame** (Board / Graph / Calendar / Detail)
- **attached automations** (WorkflowTemplates, see Pillar 3)
- **attached monitors** (Proactive detectors, see Pillar 4)
- **AI context profile** — domain vocabulary, role assumptions, scoped sources
- its own **Timeline, Activity Log, Comments, Tasks, Permissions** (uniform capabilities)

## 1.3 The seven Workspace types

| Workspace | Auto-member Objects | Default frame | Primary automations | AI context |
|---|---|---|---|---|
| **Teaching** | Courses, Students, Faculty, Syllabi(Doc), Assignments(Task), Meetings, Resources | Board (by course/stage) | "New Course", "Quiz Gen" | pedagogy, syllabus, cohort |
| **Research** | Projects, Publications, Datasets, Grants, Labs, Hypotheses, Literature | Graph | "Research Paper", "Literature Monitor" | methods, fields, citations |
| **Grant** | Grants, Budgets, Projects, Reports(Task), Agencies, Compliance | Timeline | "Grant" workflow | funding, milestones, compliance |
| **Committee** | Committee, Members(Faculty), Meetings, Minutes(Doc), Tasks, Policies, Accreditation | Board | "Meeting" workflow | governance, policy |
| **Event** | Event, Agenda(Doc), Registrations, Proceedings(Pub), Resources, Tasks | Calendar | "Conference"/"Workshop"/"Seminar" | programme, logistics |
| **Student** | (the student's own) Enrollments, Submissions, Advising(Notes), Progress, Tasks | List | "PhD Seminar", reminders | learner progress, deadlines |
| **Personal** | User's private Notes, Tasks, Inbox, Bookmarks, Drafts | List | user-defined | the individual |

Workspaces can be **auto-proposed** ("You created Course X — open a Teaching Workspace?"), **joined** (shared by a Space), **custom-composed**, and **archived** (retaining all Objects — they live on in the graph).

## 1.4 Automatic Workspace Context (how AI "understands" context)
When a user is inside a Workspace, the AI session is automatically injected with a **Context Model** derived by reading the Workspace Object — never typed by the user:

```
Context Model =
    workspace.type            → domain vocabulary + persona
  + workspace.memberObjects    → their summaries + relationships (the neighbourhood)
  + user.roleInWorkspace       → permissions + perspective (PI vs student vs registrar)
  + recent activity (Timeline) → what's hot right now
  + relevant long-term memory  → Pillar 2
```

This context **auto-scopes** every AI behaviour:
- **Search** defaults to the Workspace's Objects (user can expand to "all").
- **AI Chat** grounds in Workspace sources first; citations stay in-scope.
- **Summaries** are framed for the Workspace (a Grant Workspace summary emphasises milestones/budget; a Teaching Workspace summary emphasises cohort progress).
- **Suggestions** are Workspace-relevant (grant opportunities in Grant WS; teaching suggestions in Teaching WS).
Cross-Workspace operation remains possible via Universal Search / ⌘K — context is a *default*, not a cage.

---

# PILLAR 2 — AI MEMORY (Long-Term Institutional Memory)

**Principle:** Memory is not a separate store bolted on — *memory is the Knowledge Graph plus derived Memory Artifacts.* Everything the institution has ever done is already an Object with Timeline, Activity Log, Version History, and Comments. AI Memory makes that persistent structure *retrievable and surfaced* across time.

## 2.1 What the institution must remember (mapped to the model)

| Required memory | Stored as |
|---|---|
| Previous **events** | `Event` Objects + their Timelines + Minutes(Doc) + outcomes |
| Previous **proposals** | `Document`/Proposal Objects + version history + decision Comments |
| Past **reviewer comments** | Comments on `Publication` Objects + aggregated **Memory Artifact** ("reviewer patterns") |
| Past **purchases** | `Purchase` Objects + linked `Budget` + receipts(Doc) + approval Activity |
| Past **meetings** | `Meeting` Objects + transcripts + minutes + action Tasks |
| Past **budgets** | `Budget` Objects + line-items + spend history + `Purchase` links |
| Past **publications** | `Publication` Objects + citations + reviews + impact |
| Past **teaching material** | Syllabi/Lectures(Doc) on `Course` Objects + iterations(versions) |

## 2.2 Memory types
- **Episodic** — what happened when: events, meetings, decisions (the Timeline + Activity Log).
- **Procedural** — how things were done: past proposals, workflow runs, templates, playbooks (WorkflowInstance Objects + their artifacts).
- **Semantic** — facts & judgements: reviewer comments, policies, budget norms, teaching content (structured metadata + Comments + Memory Artifacts).
- **Institutional** — the accumulated graph itself: who collaborated with whom, what funded what, what contradicted what.

## 2.3 How memory is STORED
1. **Primary store = the Object Graph.** No memory is lost because no Object is ever hard-deleted (soft-delete + archive; Object Blueprint §2/§4).
2. **Memory Artifacts (derived, attributed Objects).** The AI periodically distils raw history into reusable summaries — e.g. a `MemoryArtifact` "Reviewer patterns for Journal X" attached to that Journal, or "Budget history for Dept Y" attached to the Space. Each artifact is **versioned, cited to source Objects, and human-correctable** (FR-MET-009 spirit).
3. **The five-index substrate** (Lexical · Vector · Graph · Structured · ACL) from the AI Architecture indexes all of it: vector embeddings make memory semantically retrievable; the graph makes it relationally retrievable; Structured powers "show me 2023 purchases over ₹5L."
4. **Retention & decay.** Hot memory (recent, frequently accessed) stays in fast indexes; cold memory is compressed/quantised but never deleted; retention policies (per Space / compliance) auto-archive, never purge without override.

## 2.4 How memory is RETRIEVED
- **By Object:** open any Object → its full Timeline + Activity + prior versions = its memory.
- **By relationship:** traverse the graph ("everything this Grant funded, ever").
- **By time:** Universal Timeline filtered to a type/entity ("all committee meetings, 2020–2024").
- **By query (memory-augmented retrieval):** a question expands with the active Workspace context + relevant neighbourhoods + time filters, retrieves from all five indexes, reranks, and injects into generation **with citations to the source Objects**.
- **Recall features:** "What did we decide last time?", "Show me past proposals to this funder", "How did we run the conference in 2023?" — each resolves to Objects + Memory Artifacts.

## 2.5 How memory is SURFACED
- **Brain Briefing (Dashboard):** the AI narrative is memory-grounded — "Last year's ML Day had 400 attendees; here's the 2023 runbook."
- **Proactive surfacing (Pillar 4):** when starting a new workflow, the AI recalls the last run and pre-fills from memory.
- **"Remember when" cards** in Object detail: a Course shows "past syllabi & what changed."
- **Context injection:** every Workspace/chat automatically carries the relevant long-term memory (§1.4).
- **Privacy:** memory inherits ACL; *institutional* memory (shared) vs *personal* memory (private Workspace) are segregated; cross-Space memory never leaks (R1).

---

# PILLAR 3 — AUTOMATION ENGINE (Reusable Workflows)

## 3.1 Workflows are first-class Objects
- **`WorkflowTemplate`** — a reusable, versioned recipe (e.g. "Conference", "Grant"). Authored once, instantiated many times.
- **`WorkflowInstance`** — a running execution; **itself an Object** with Timeline, Tasks, Activity Log, Attachments, Permissions. You can open a workflow instance and watch it like any other Object.

## 3.2 Workflow anatomy
A `WorkflowTemplate` defines:
- **Trigger:** manual · scheduled (e.g. annually for "National Mathematics Day") · event-based (Object created, status changed) · form-submitted.
- **Stages**, each producing automatically:
  - **Tasks** (with assignee role, due-offset from trigger/Timeline)
  - **Documents** (agenda, proposal, report, call-for-papers — pre-created as Document Objects, often from templates)
  - **Reminders** (Timeline entries + Inbox items at due-offsets)
  - **Timelines** (the instance's own chronological plan)
  - **Relationships** (links the created Objects to the triggering Object and to each other)
  - **Approval gates** (destructive/committal steps require human approval — A8)
  - **Conditions/branches** (if budget > X, add a Finance approval)
- **Role bindings:** who gets which Task (resolved from Space roles / Object relationships).
- **Integrations:** invite emails, calendar sync, external submits (all through approved connectors, FR-AIT-007).

## 3.3 Runtime
- Durable execution (the Agent Runtime / Temporal model from AI Architecture A8): long-running, resumable, heartbeated, auditable. A step failure hands back a partial result + resume point; nothing silently stalls.
- Every instance writes to the **Activity Log**; every committal action is approval-gated and undoable ≥ 30 days.

## 3.4 The seven reference workflows (what they auto-create)

| Workflow | Auto-created Objects |
|---|---|
| **Conference** | Event + Agenda(Doc) + CfP Task + Review Tasks + Registration Tasks + Proceedings(Publication placeholder) + Budget lines + Reminders |
| **Workshop** | Event + Agenda(Doc) + Materials(Doc) + Feedback Task + Reminders |
| **National Mathematics Day** | Event(annual) + Schedule(Doc) + Sessions + Speakers(Faculty/Student links) + Tasks + Report(Doc) + Reminders |
| **Research Paper** | Publication + Tasks (literature→draft→internal review→submission) + co-author links + Compliance check + Timeline + Reminders |
| **Purchase** | Purchase Object + Approval Tasks (per threshold) + Budget link + Vendor + Receipt(Doc) + Audit entry |
| **Grant** | Grant + Proposal(Doc) + Budget + Report Tasks (milestones) + Compliance checklist + Timeline + Reminders |
| **PhD Seminar** | Event + Presenter(Student link) + Abstract(Doc) + Feedback Tasks + Attendance + Reminders |

## 3.5 Library, composition, reuse
- A **Workflow Library** (per Space, with institutional shared templates) — versioned, ratable, forkable.
- Workflows compose: a "Conference" may trigger a "Proceedings Publication" (Research Paper workflow) on acceptance.
- Starting a workflow **recalls memory** (Pillar 2): the AI pre-fills from the last run of the same template.
- Custom workflows are visual, no-code compositions of the same primitives (Trigger → Stages → Artifacts → Gates).

---

# PILLAR 4 — PROACTIVE AI (The Brain that doesn't wait)

## 4.1 The monitoring layer
A continuous, scheduled **detector** layer (extending the Literature Monitor / Compliance Scan agents of AI Architecture F18/F21) runs over the graph + memory + workflow instances. Each detector emits **Proactive Insights** — *not* actions, but *suggestions with evidence*. The brain watches so the human doesn't have to.

## 4.2 The Proactive Insight Object
A `ProactiveInsight` is an Object (uniform capabilities) with:
- **type** (one of the detections below)
- **severity** (info / suggestion / warning / critical)
- **evidence** — links to the source Objects + quotes (always citeable)
- **suggested action** — a proposal card (editable, approval-gated if committal)
- **routing** — who should see it (role/Workspace)
- its own **Timeline + Activity Log** (when raised, when resolved)

## 4.3 Detector catalogue (the nine required detections)

| Detection | Signals used | Produces |
|---|---|---|
| **Upcoming deadlines** | Tasks/Events/Milestones with near due-offsets; Timeline | Insight → "3 grants close in 14 days" + prep Tasks |
| **Missing approvals** | Approval Tasks older than SLA; blocked workflow gates | Insight → "Purchase P12 awaiting HoD > 5 days" |
| **Missing documents** | Workflow required-doc checklist incomplete; accreditation `belongs_to` gaps | Insight → "NAAC Criterion 3 missing 2 evidence docs" |
| **Duplicate work** | Near-duplicate Objects (F11); overlapping Tasks/workflows | Insight → "Two 'ML Day' events scheduled" + merge proposal |
| **Policy violations** | Budget overruns; undeclared conflicts; compliance breaches | Insight → "Budget B over by 12%; ethics disclosure missing" |
| **Possible improvements** | Memory patterns (slow approvals, repeated rework) | Insight → "Grant reports always late; pre-draft 30 days earlier?" |
| **Research opportunities** | New Publications/Calls matching Research Areas/faculty interests | Insight → "New CFP matches your lab's method" |
| **Teaching suggestions** | Stale syllabi; at-risk students; new resources | Insight → "Update Lecture 4 — paper cited 200× since 2021" |
| **Grant opportunities** | Funding agency Calls vs faculty Research Areas/Grants | Insight → "SERB call aligns with Project RP1" |

## 4.4 Surfacing & calibration (calm, not noisy)
- **Routing:** insights land in the **Universal Inbox** (Flagged/Watchlist channels) and the relevant **Workspace** (a Grant deadline insight appears in the Grant Workspace, not spamming the Personal one).
- **Ranking:** by severity × relevance × user role; low-signal insights are suppressed by default.
- **Tuning:** per-Workspace sensitivity sliders; "mute this detector"; "show me only warnings+".
- **Human-in-the-loop:** every insight is a *suggestion*. Approval/committing actions require human authorisation; the brain never auto-executes committal or external steps.
- **Transparency:** every insight shows its evidence links — the user can verify in one click, honouring "show its work."

---

# SYNTHESIS — How the four pillars compose with the Digital Brain

```
        ┌─────────────────── WORKSPACE (context) ───────────────────┐
        │  sets AI scope automatically from its member Objects       │
        └───────────────┬───────────────────────────┬───────────────┘
                        │                           │
            ┌───────────▼──────────┐     ┌──────────▼──────────┐
            │  AI MEMORY (recall)  │     │  AUTOMATION ENGINE  │
            │  graph + artifacts   │◀───▶│  workflows create   │
            │  stored/retrieved/   │     │  Tasks/Docs/Timeline│
            │  surfaced            │     └──────────┬──────────┘
            └───────────┬──────────┘               │ triggers
                        │                          │
                  ┌─────▼──────────────────────────▼─────┐
                  │   PROACTIVE AI (monitors the graph)   │
                  │   emits ProactiveInsight Objects      │
                  │   → Inbox + Workspace + Dashboard     │
                  └───────────────────┬──────────────────┘
                                      │ suggestions (human disposes)
                                      ▼
                          THE OBJECT GRAPH (single source)
```

**New Object types introduced by this document:** `Workspace`, `WorkflowTemplate`, `WorkflowInstance`, `ProactiveInsight`, `MemoryArtifact` — all inheriting the 14 universal capabilities, so they behave exactly like a Professor or a PDF.

**The loop, now complete:**
1. **Capture** → Objects (Workspace-scoped).
2. **Remember** → Memory (graph + artifacts, retained long-term).
3. **Automate** → Workflows spin up Tasks/Docs/Timelines.
4. **Monitor** → Proactive AI detects risks/opportunities as Insights.
5. **Reason & Act** → human reviews Insights/proposals, disposes; the graph grows.
6. **Reflect** → Dashboard/Brain Briefing, fed by memory + Timeline.

---

## UPDATED NON-NEGOTIABLE PRINCIPLES (add to the eight)

9. **Context-awareness by default** — the AI infers Workspace context from the graph; the user never configures it manually.
10. **Memory-respect** — the AI recalls prior decisions and reuses them; it never asks what it already knows (within ACL).
11. **Automation with consent** — workflows act, but committal/external steps are approval-gated and auditable.
12. **Proactive but calm** — the brain surfaces what matters and stays silent otherwise; insights are ranked, citeable, and tunable, never a flood.

*The File Manager stored your files. The Object Brain connected them. These four pillars give it a place to work, a memory to draw on, hands to act, and eyes to watch — all without waiting to be asked.*

*— End of AcademicOS Four Pillars Extension —*
