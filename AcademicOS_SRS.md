# AcademicOS — Software Requirements Specification (SRS)

**The AI-Powered Academic Operating System for Faculty, Researchers, PhD Scholars & Universities**

| Field | Value |
|---|---|
| Document Title | AcademicOS — Software Requirements Specification |
| Version | 1.0 (Baseline) |
| Status | Approved for Architecture Review |
| Date | 31 July 2026 |
| Document Owner | Office of the Chief Architect / Product Management |
| Contributing Roles | Senior Software Architect, AI Engineer, UX Designer, Product Manager |
| Classification | Internal — Engineering & Leadership |
| Intended Audience | Engineering leadership, platform teams, AI/ML teams, design, security & compliance, university CIOs, investors |
| Review Cycle | Quarterly; amendment via Architecture Decision Record (ADR) |

### Revision History

| Ver | Date | Author | Change Summary |
|---|---|---|---|
| 0.1 | — | Product | Problem discovery, persona interviews (n=62 across 9 institutions) |
| 0.5 | — | Architecture | Domain model, module decomposition, AI stack selection |
| 0.9 | — | Design + AI | Journey maps, dashboard specs, RAG/agent specification |
| 1.0 | 31-Jul-2026 | Joint | Baseline SRS covering Sections 1–20 + appendices |

---

## Table of Contents

**Part A — Product Definition**
1. Vision
2. Target Users
3. User Roles
4. Functional Requirements
5. Non-Functional Requirements

**Part B — Experience Architecture**
6. User Journey
7. Navigation Flow
8. Module Breakdown
9. Dashboard Design

**Part C — Technical Architecture**
10. Database Planning
11. AI Features
12. Security
13. Storage Strategy
14. Version Control
15. Search Engine
16. Metadata Design

**Part D — Philosophy & Forward Look**
17. Future Expansion
18. Folder Philosophy
19. Naming Convention
20. UI Philosophy

**Appendices** — A: Glossary · B: Integration Catalogue · C: Risk Register · D: KPI Tree · E: Release Plan · F: Open Questions & ADR Backlog

---

## 0. Preamble — How to Read This Document

### 0.1 Scope of the System

AcademicOS is a **multi-tenant, AI-native system of record and system of work for academic knowledge labour**. It is the single place where a professor's teaching materials, a scholar's thesis chapters, a lab's datasets, a department's accreditation evidence, and a university's research output all live — organised not by where a human happened to drop a file, but by what the artefact *is*, what it *belongs to*, and what it is *for*.

**In scope:** knowledge artefact management, academic entity modelling (courses, students, projects, grants, publications), AI reasoning over the institution's own corpus, workflow and approval, compliance evidence assembly, search and discovery, analytics, and integration with the surrounding academic software estate.

**Explicitly out of scope for v1 (see §17 for horizon planning):** being a Learning Management System (we integrate with Moodle/Canvas/Blackboard rather than replace them), being a Student Information System of record for enrolment/fees, being a journal submission portal, and being a general-purpose office suite (we integrate with Microsoft 365 and Google Workspace editors).

### 0.2 Requirement Notation

- **MUST / SHALL** — mandatory for the stated release.
- **SHOULD** — strongly recommended; deviation requires an ADR.
- **MAY** — optional/desirable.
- Requirement IDs follow `FR-<MODULE>-<NNN>` and `NFR-<CATEGORY>-<NNN>`.
- Priority follows MoSCoW: **M** (Must), **S** (Should), **C** (Could), **W** (Won't, this release).
- Release targets: **R1** (MVP, months 0–9), **R2** (Scale, 10–18), **R3** (Platform, 19–30).

### 0.3 Architectural North Stars

Five decisions constrain everything downstream. They are stated once, here, and are non-negotiable without an ADR:

1. **The graph is the truth; the folder is a rendering.** Every artefact is a node in a typed knowledge graph. Hierarchical folders are one of many *projections* of that graph. This is the single decision that separates AcademicOS from Drive/SharePoint.
2. **Metadata is captured at the moment of least friction — by AI, at ingest.** Humans confirm; they do not type. A system that requires manual metadata entry will be abandoned by week three.
3. **Every AI output is a citation-bearing, traceable, reversible proposal — never a silent mutation.** Academia runs on provenance. An AI that cannot show its sources is worse than no AI.
4. **Permissions are evaluated at the atom, enforced at every projection.** Search, AI answers, exports, dashboards and shares all pass through one authorisation kernel. There is no second path to data.
5. **Multi-tenancy is physical where it matters and logical where it doesn't.** Tenant isolation is enforced in storage keys, database row policies, vector namespaces and index shards — not merely by a `WHERE` clause in application code.

---

# PART A — PRODUCT DEFINITION

---

## 1. Vision

### 1.1 The Problem — Stated Precisely

Academic knowledge work is the most information-dense profession outside of law and medicine, and it is served by the worst tooling of the three. A mid-career Assistant Professor at a research university simultaneously operates as a teacher, a researcher, a grant administrator, a supervisor, a peer reviewer, a committee member, and a compliance respondent. Each of these roles generates artefacts. None of them share a home.

Field research across 62 academics at 9 institutions surfaced a consistent pathology:

| Observed Reality | Consequence |
|---|---|
| The average faculty member maintains **4.7 parallel storage systems** (institutional drive, personal Google Drive, laptop `Desktop/`, email attachments, a USB/external HDD, plus WhatsApp/Telegram for "quick" file sharing) | No single source of truth; the "real" version is wherever the last edit happened |
| Filenames like `Final_v2_FINAL_revised_USE-THIS_ok(1).docx` are the **dominant versioning strategy** | Version anxiety; papers submitted from the wrong draft; irreproducible results |
| **11–17 hours per accreditation cycle** spent hunting for evidence that already exists (NAAC/NBA/ABET/AACSB/REF) | Senior researchers doing clerical archaeology instead of research |
| Institutional memory evaporates on departure — a retiring professor's 30-year corpus leaves in a cardboard box or a dead cloud account | Permanent loss of curricula, question banks, datasets, mentoring history |
| Research data is disconnected from the paper it produced, which is disconnected from the grant that funded it, which is disconnected from the student who did the work | Funder data-management mandates unmeetable; credit disputes; no reproducibility |
| Search means `Ctrl+F` on a filename — content, meaning and relationships are invisible | Knowledge is *stored* but not *available* |
| Supervision of PhD scholars runs on ad-hoc email, undocumented meetings, and memory | Progress disputes, unclear expectations, high attrition |

The root cause is not laziness. It is that **general-purpose file systems have no concept of academic entities**. Windows Explorer does not know what a "semester" is. Google Drive does not know that a dataset produced a figure that appears in a manuscript that satisfies a grant deliverable. Every relationship a professor holds in their head must be re-derived, manually, forever.

### 1.2 Vision Statement

> **AcademicOS is the operating system for academic work — an AI-native workspace where every artefact of teaching, research, supervision and governance is automatically understood, connected, versioned and retrievable, so that scholars spend their hours on scholarship and institutions never lose their memory.**

### 1.3 The Reframe: From Storage to Understanding

| Old World (Explorer / Drive / SharePoint) | AcademicOS |
|---|---|
| You organise files | The system organises artefacts; you correct it |
| Folders are the only structure | Folders are one view; graph, timeline, entity and semantic views coexist |
| Filenames carry meaning | Metadata carries meaning; filenames are generated |
| Search = filename match | Search = hybrid lexical + semantic + graph + permission-aware ranking |
| Versions = copies | Versions = immutable, diffable, attributable lineage |
| Files are inert | Artefacts are agents' working memory; the corpus answers questions |
| Compliance = a frantic manual hunt | Compliance = a continuously maintained, queryable evidence graph |
| Knowledge leaves with the person | Knowledge is institutional, with succession built in |
| Collaboration = attachments | Collaboration = shared entities with roles, provenance and contribution ledger |

### 1.4 Product Principles

1. **Zero-Effort Structure.** If the user must think about *where* something goes, we have failed. Ingest → classify → file → link → notify, with confirmation costing one keystroke.
2. **Cite or Be Silent.** No AI assertion appears without traceable provenance to source artefacts, with confidence surfaced honestly.
3. **The Long Now.** Design for a 30-year artefact lifespan. Formats, exports and identifiers must survive vendor changes, institutional migrations and the user's own career.
4. **Respect the Ritual.** Academia has real rituals — semesters, viva voce, peer review, grant cycles, accreditation. The product models them natively rather than forcing generic "projects and tasks".
5. **Individual First, Institution Second.** Adoption is won one professor at a time. A single scholar must get standalone value on day one, before any institutional rollout exists.
6. **Non-Destructive by Default.** Nothing is ever hard-deleted by AI, by bulk actions, or by accident. Every operation is undoable and audited.
7. **Explainable Automation.** Every automated decision — a classification, a rename, a permission inference — can answer "why did you do that?" in one click.
8. **Sovereign Data.** The institution owns its corpus, its embeddings and its derived intelligence. Full export, any time, no lock-in, no training on tenant data without explicit opt-in.

### 1.5 Positioning

**AcademicOS is to academic work what Figma is to design and what Epic is to clinical practice: a domain-native system of record that replaces a category of generic tools by knowing the domain.**

Competitive landscape and our wedge:

| Category | Examples | Why they fail academia | Our wedge |
|---|---|---|---|
| Generic cloud drives | Google Drive, OneDrive, Dropbox | No domain model, no compliance semantics, no research lineage | Academic entity graph |
| Doc/knowledge workspaces | Notion, Coda, Obsidian | Manual structure; no ingest intelligence; poor with binary/large research data | AI auto-organisation + data-scale storage |
| Reference managers | Zotero, Mendeley, EndNote | Only handle *others'* papers, not your own corpus | Bidirectional: we integrate, then extend |
| Research data platforms | Figshare, Dataverse, OSF | Archival endpoints, not daily workspaces | Daily workspace that *feeds* archives |
| CRIS / RIMS | Pure, Converis, Symplectic | Administrator-facing reporting; researchers hate entering data | Researcher-facing; reporting is a byproduct |
| LMS | Moodle, Canvas, Blackboard | Course delivery only; not the professor's private brain | Integrate; we own the pre- and post-LMS lifecycle |
| ELN | Benchling, LabArchives | Bench-science specific | Discipline-agnostic core, ELN-compatible |

### 1.6 Success Metrics (North Star + Supporting)

**North Star:** *Weekly Active Artefact Interactions per Active Academic* — a composite of files ingested, AI queries resolved, entities linked and workflows advanced. It captures habit formation better than logins.

| Metric | Definition | R1 Target | R3 Target |
|---|---|---|---|
| Time-to-First-Value | Signup → first AI-organised artefact set | < 10 min | < 4 min |
| Auto-classification acceptance | % AI-proposed classifications accepted unedited | ≥ 85% | ≥ 94% |
| Search success rate | Queries ending in an artefact open/action within 60s | ≥ 70% | ≥ 88% |
| Retrieval time saved | Self-reported + instrumented vs. baseline | ≥ 60% | ≥ 80% |
| Accreditation prep time | Hours to assemble a criterion evidence pack | −70% | −92% |
| D30 / D90 retention (individual) | Active academics | 55% / 40% | 75% / 62% |
| Institutional seat expansion | Net revenue retention | 110% | 135% |
| AI trust index | % AI outputs accepted without correction | ≥ 75% | ≥ 90% |
| Corpus completeness | % of a user's academic output present in system | ≥ 50% | ≥ 90% |

### 1.7 Explicit Non-Goals

- We will not build a WYSIWYG word processor or spreadsheet engine.
- We will not become the enrolment/fees system of record.
- We will not act as a plagiarism-detection authority (we integrate with Turnitin/iThenticate).
- We will not gamify scholarship with vanity leaderboards.
- We will not sell, share or train foundation models on tenant content absent written, revocable, tenant-level opt-in.

---

## 2. Target Users

### 2.1 Market Segmentation

| Segment | Global Scale | Entry Motion | Willingness to Pay | Priority |
|---|---|---|---|---|
| Individual academics (Asst./Assoc./Full Professors) | ~13M worldwide | PLG, self-serve | Low–Mid (personal card) | **P0 — wedge** |
| PhD scholars & postdocs | ~7M worldwide | PLG, referral by supervisor | Low (student pricing) | **P0 — volume/virality** |
| Research groups & labs | ~1M+ | Team plan, PI-purchased | Mid | **P1** |
| Departments / Schools | ~200k | Assisted sales | Mid–High | **P1** |
| Universities / Institutes | ~30k globally | Enterprise sales, RFP, tender | High | **P2 — revenue** |
| Research councils, funders, accreditors | ~2k | Partnership | High | **P3 — moat** |

### 2.2 Primary Personas

---

#### Persona 1 — Dr. Ananya Iyer · **Assistant Professor** (the Overloaded Multi-Role Academic)

**Profile.** 34, Assistant Professor of Computer Science, tenure-track, year 3 of 6. Teaches 2 courses/semester (~180 students), supervises 3 PhD + 6 M.Tech scholars, PI on one government grant, Co-PI on one industry project, member of 4 committees, reviews ~20 papers/year.

**A typical week generates:** 3 lecture decks, 2 assignment sets, ~60 graded submissions, 4 student meeting notes, 1 manuscript revision, 2 grant expense claims, 1 committee minute, 9 email threads containing decisions that exist nowhere else.

**Pains (verbatim-flavoured):**
- "I have three versions of the same lecture on three machines and I no longer know which one I actually taught."
- "My tenure dossier is due in 18 months and reconstructing four years of activity terrifies me."
- "The department asked for 'evidence of teaching innovation' — I know it exists, I cannot find it."
- "I re-create material I already made, because finding it takes longer than remaking it."

**Jobs To Be Done:**
- *When* a new semester starts, *I want* last year's course to clone forward with materials, rubrics and question banks intact, *so I can* teach an improved version instead of rebuilding.
- *When* I finish any piece of work, *I want* it filed and connected without thinking, *so that* my future self and my institution can find it.
- *When* my dossier/appraisal is due, *I want* the system to assemble the narrative and evidence, *so that* I spend a day, not a month.

**Success looks like:** opens AcademicOS first thing each morning; the dashboard already knows what today needs.

---

#### Persona 2 — Rahul Menon · **PhD Scholar** (the Anxious Long-Horizon Maker)

**Profile.** 27, 3rd year, materials science. Runs experiments, writes code, reads 15 papers/week, drafts chapters, and reports to a supervisor he sees fortnightly.

**Pains:** literature chaos across Zotero/downloads/inbox; experimental data disconnected from the figures it produced; chapter drafts sprawling across Word, LaTeX and Overleaf; no record of what the supervisor approved three months ago; genuine fear of losing years of work.

**JTBD:**
- *When* I read a paper, *I want* its claims linked to my thesis argument, *so that* my literature review writes itself from my own reading.
- *When* I run an experiment, *I want* raw data, processing scripts, outputs and the resulting figure permanently chained, *so that* reproducibility is automatic.
- *When* I meet my supervisor, *I want* decisions and action items captured as durable records, *so that* progress is undisputed.

**Success looks like:** at submission, the thesis compiles with every figure traceable to raw data, and the viva prep pack generates itself.

---

#### Persona 3 — Prof. Meera Krishnan · **Principal Investigator / Research Lead**

**Profile.** 51, full professor, heads a 22-person lab, ₹6.2 crore of active funding across 5 grants, 14 active manuscripts, industry consultancy, patent portfolio.

**Pains:** cannot see lab-wide status without asking everyone; funder data-management-plan compliance is a liability; authorship and contribution disputes; onboarding a new student takes six weeks of tribal knowledge transfer; when a postdoc leaves, their work becomes unusable.

**JTBD:** portfolio visibility without micromanagement; automatic funder-compliance posture; institutional continuity across people; effortless reporting to funders.

---

#### Persona 4 — Dr. Sanjay Rao · **Head of Department / Dean**

**Profile.** 58, HoD of a 60-faculty department, responsible for accreditation, workload distribution, appraisals, and quality assurance.

**Pains:** accreditation evidence collection is a recurring institutional trauma; no live view of departmental research output or teaching quality; faculty appraisal data arrives in 60 inconsistent spreadsheets; curriculum-outcome mapping is done annually and manually.

**JTBD:** continuous, audit-ready compliance posture; real-time departmental analytics; fair, evidence-based appraisal; one-click regulator submissions.

---

#### Persona 5 — Ms. Fatima Sheikh · **University Administrator / IQAC / Research Office**

**Profile.** 42, Internal Quality Assurance Cell coordinator; owns NAAC/NBA/NIRF submissions, research-office reporting, policy compliance, and the institutional repository.

**Pains:** chases 800 faculty for data annually; duplicate/contradictory records; no lineage on submitted numbers; ranking submissions built on trust rather than evidence.

**JTBD:** institution-wide, verifiable, exportable evidence; policy enforcement that is automatic rather than pleading; defensible audit trails.

---

#### Persona 6 — Arjun Das · **Research Assistant / Junior Contributor**

**Profile.** 23, M.Tech student working part-time in the lab. Needs access to exactly what he is working on, no more; needs onboarding without a human babysitter; needs his contribution recorded for his CV.

---

#### Persona 7 — External Collaborator / Reviewer / Examiner (Guest)

Needs strictly time-boxed, watermarked, revocable access to a defined artefact set, with no account sprawl and full audit of what they viewed.

### 2.3 Secondary & Tertiary Stakeholders

- **Librarians / Repository Managers** — metadata quality, OAI-PMH harvesting, open-access mandate compliance, DOI minting.
- **Grants & Finance Officers** — burn rate, deliverable status, audit evidence.
- **IT / CISO** — SSO, data residency, DLP, incident response, procurement security review.
- **Funding Agencies** — outcome verification, DMP compliance.
- **Accreditation Bodies** — NAAC, NBA, ABET, AACSB, AQAS, REF, TEQSA — standardised evidence packs.
- **Industry Partners** — controlled IP-safe collaboration spaces.

### 2.4 Anti-Personas (whom we deliberately do not optimise for in v1)

- Undergraduate students consuming course content (LMS territory).
- K-12 schools (different compliance and pedagogy model).
- Corporate R&D with no academic entity model (different naming and governance ontology).

---

## 3. User Roles

### 3.1 Authorisation Model Overview

AcademicOS uses a **layered hybrid model**:

```
Identity  →  Tenant Membership  →  Global Role  →  Scoped Roles (per Space/Entity)
                                        ↓
                          Capability Set (fine-grained verbs)
                                        ↓
              ABAC Policy Evaluation (attributes: sensitivity, embargo,
              residency, funder rules, IP class, time window, IP range)
                                        ↓
                          Effective Permission Decision (+ reason)
```

- **RBAC** gives the coarse, understandable layer users can reason about.
- **ABAC** gives the policy layer institutions need (e.g., "embargoed until 2027-03-01", "ITAR/export-controlled", "residency: India only", "no external sharing for grant #X").
- **ReBAC (relationship-based)** derives implicit access: *supervisor-of* → read access to the scholar's thesis workspace; *co-author-on* → access to manuscript lineage. Derived grants are always visible, explainable and revocable.

**Conflict resolution:** explicit DENY > explicit ALLOW > inherited DENY > inherited ALLOW > derived (relationship) ALLOW > default DENY.

### 3.2 Role Catalogue

| # | Role | Scope | Core Purpose | Typical Holder |
|---|---|---|---|---|
| R01 | **Super Administrator** | Platform (vendor) | Platform operations, tenant provisioning. *Cannot read tenant content* — break-glass only, dual-approved, fully audited | Vendor SRE |
| R02 | **Institution Administrator** | Tenant | Org structure, SSO, policies, licences, retention, branding | University CIO / IT head |
| R03 | **Compliance / Quality Officer** | Tenant | Accreditation frameworks, evidence, audits, retention holds | IQAC coordinator |
| R04 | **Research Office Manager** | Tenant | Grants, DMPs, ethics, IP, funder reporting | Research office |
| R05 | **Dean / Faculty Head** | Faculty/School | Cross-department oversight, approvals, analytics | Dean |
| R06 | **Head of Department** | Department | Workload, appraisal, curriculum oversight, dept analytics | HoD |
| R07 | **Principal Investigator** | Lab / Project | Owns research spaces, team, budgets, outputs | Professor / PI |
| R08 | **Faculty / Academic** | Own spaces + assigned | Teaching, research, supervision — the core creator | Asst./Assoc./Full Prof |
| R09 | **Co-Supervisor** | Scholar record | Shared supervision rights, no admin rights | Second supervisor |
| R10 | **PhD Scholar / Researcher** | Own thesis + lab | Long-horizon research, thesis, publications | Doctoral candidate |
| R11 | **Postdoctoral Fellow** | Project spaces | Research execution, mentoring juniors | Postdoc |
| R12 | **Research Assistant / Student Worker** | Assigned artefacts only | Task-scoped contribution | M.Tech/UG assistant |
| R13 | **Teaching Assistant** | Course scope | Grading, material support, no gradebook publish | TA |
| R14 | **Librarian / Repository Manager** | Tenant (metadata) | Metadata QA, DOI, OA compliance, harvesting | Library staff |
| R15 | **Departmental Coordinator** | Department (ops) | Scheduling, minutes, records, logistics | Admin staff |
| R16 | **External Collaborator** | Invited spaces | Bounded co-authoring/data sharing | Partner institution |
| R17 | **External Examiner / Reviewer** | Time-boxed bundle | Read + annotate only, watermarked, expiring | Viva examiner |
| R18 | **Auditor (Read-Only)** | Defined scope | Immutable read + audit-log read; no mutation | Regulator, internal audit |
| R19 | **Service / Integration Account** | Scoped API | Machine access with narrow capabilities | LMS/HRIS connector |
| R20 | **Alumni / Emeritus** | Frozen archive | Read own historical corpus; export | Retired faculty |

### 3.3 Capability Matrix (abridged — full matrix in the permissions appendix)

Legend: ● Full · ◐ Conditional (policy/approval-gated) · ○ None

| Capability | R02 Inst Admin | R03 Compliance | R06 HoD | R07 PI | R08 Faculty | R10 Scholar | R12 RA | R17 Examiner | R18 Auditor |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Create personal space | ● | ● | ● | ● | ● | ● | ○ | ○ | ○ |
| Create department/lab space | ● | ○ | ● | ● | ◐ | ○ | ○ | ○ | ○ |
| Upload / ingest artefacts | ● | ● | ● | ● | ● | ● | ◐ | ○ | ○ |
| Edit own artefacts | ● | ● | ● | ● | ● | ● | ◐ | ○ | ○ |
| Edit others' artefacts | ◐ | ○ | ◐ | ◐ | ○ | ○ | ○ | ○ | ○ |
| Delete (soft) | ● | ◐ | ◐ | ● | ● | ● | ○ | ○ | ○ |
| Purge (hard) | ◐ | ◐ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Restore versions | ● | ● | ● | ● | ● | ● | ○ | ○ | ○ |
| Share externally | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ○ | ○ | ○ |
| View dept analytics | ● | ● | ● | ◐ | ○ | ○ | ○ | ○ | ◐ |
| View institution analytics | ● | ● | ○ | ○ | ○ | ○ | ○ | ○ | ◐ |
| Configure accreditation framework | ● | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Approve workflows | ● | ● | ● | ● | ◐ | ○ | ○ | ○ | ○ |
| Manage grant budget | ● | ○ | ◐ | ● | ◐ | ○ | ○ | ○ | ○ |
| Supervise scholars | ○ | ○ | ● | ● | ● | ○ | ○ | ○ | ○ |
| Use AI on own corpus | ● | ● | ● | ● | ● | ● | ◐ | ○ | ○ |
| Use AI on dept corpus | ● | ● | ● | ◐ | ○ | ○ | ○ | ○ | ○ |
| Read audit logs | ● | ● | ◐ | ◐ | ◐ (own) | ◐ (own) | ○ | ○ | ● |
| Apply legal hold | ● | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Export full tenant data | ● | ◐ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Impersonate user | ◐ (dual-approval, audited, banner shown) | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |

### 3.4 Role Mechanics

**FR-ROLE-001 (M, R1)** — A user MUST be able to hold multiple roles simultaneously across different scopes, with a visible **role context switcher** in the top bar (e.g., "Viewing as: HoD, Dept. of Physics").

**FR-ROLE-002 (M, R1)** — Effective permission on any artefact MUST be explainable: a "Why do I have access?" panel showing the grant chain (e.g., *Direct role: none → Derived: co-author on Manuscript #482 → Inherited: Project Space "NanoCat" → Result: Read+Comment*).

**FR-ROLE-003 (M, R1)** — **Delegation**: any role holder MAY delegate a bounded subset of capabilities for a bounded period (sabbatical, medical leave, conference travel), with automatic expiry and full audit.

**FR-ROLE-004 (M, R2)** — **Succession & Offboarding**: when a person leaves, an Offboarding Workflow MUST transfer ownership of institutional artefacts to a designated successor, convert the individual to Alumni/Emeritus, preserve attribution permanently, and produce a signed handover manifest.

**FR-ROLE-005 (S, R2)** — **Just-in-Time Elevation**: sensitive capabilities (purge, export-all, impersonate) require step-up MFA, a stated business reason, optional second approver, and auto-expire in ≤ 60 minutes.

**FR-ROLE-006 (M, R1)** — **Least-privilege defaults**: new members of any space receive the minimum viable role; escalation is explicit.

**FR-ROLE-007 (S, R2)** — **Access reviews**: quarterly automated attestation campaigns; unreviewed external access auto-expires.

---

## 4. Functional Requirements

> This section is organised by capability domain. Each requirement carries an ID, priority, release and acceptance criteria. Module ownership is defined in §8.

### 4.1 Identity, Onboarding & Tenancy (IDN)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-IDN-001 | Self-serve signup via email, Google, Microsoft, ORCID | M | R1 |
| FR-IDN-002 | Enterprise SSO: SAML 2.0, OIDC, plus federated academic identity (Shibboleth / eduGAIN / InCommon) | M | R1 |
| FR-IDN-003 | SCIM 2.0 user & group provisioning/deprovisioning from institutional IdP/HRIS | M | R2 |
| FR-IDN-004 | ORCID iD linking with bidirectional works sync (opt-in) | M | R1 |
| FR-IDN-005 | MFA: TOTP, WebAuthn/passkeys, push; enforceable per-tenant policy | M | R1 |
| FR-IDN-006 | Multi-tenant membership: one identity may belong to several institutions with clean context separation | M | R2 |
| FR-IDN-007 | Guided onboarding wizard capturing discipline, role, teaching load, research areas, current tools — used to seed the workspace ontology | M | R1 |
| FR-IDN-008 | **Legacy Import**: connectors for Google Drive, OneDrive/SharePoint, Dropbox, local folder upload, email mailbox, Zotero/Mendeley library, Overleaf projects | M | R1 |
| FR-IDN-009 | **Migration Preview**: before committing, show the proposed reorganisation of imported content side-by-side with the original tree, with per-item accept/reject and bulk rules | M | R1 |
| FR-IDN-010 | Personal → institutional account graduation without data loss when a university adopts the platform | S | R2 |
| FR-IDN-011 | Account recovery with identity-proofing; institutional admin-assisted recovery path | M | R1 |

**Acceptance (FR-IDN-008/009):** importing a 25 GB / 40,000-item Drive completes within 6 hours, produces a reviewable classification plan, and achieves ≥ 85% acceptance on a sampled 200-item audit.

### 4.2 Artefact Ingest & Capture (ING)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-ING-001 | Multi-channel ingest: web drag-drop, folder upload, desktop sync agent, mobile camera scan, email-to-workspace address, browser extension, watched cloud folders, API/webhook | M | R1 |
| FR-ING-002 | Support ≥ 120 file types incl. Office, PDF, LaTeX, Jupyter, R Markdown, images, audio, video, CAD, GIS, code, CSV/Parquet, SPSS/Stata/SAS, FASTQ/BAM (large-file path), instrument formats | M | R1–R2 |
| FR-ING-003 | Resumable chunked upload; single-file ceiling 100 GB; per-artefact bundle ceiling 1 TB | M | R1 |
| FR-ING-004 | Content-hash de-duplication with "this already exists here" resolution UX | M | R1 |
| FR-ING-005 | **Mobile scan**: photograph whiteboard/handwritten notes/printed docs → deskew, enhance, OCR (incl. handwriting), auto-file | M | R1 |
| FR-ING-006 | **Meeting capture**: record or upload audio/video → transcribe → diarise speakers → extract decisions and action items → attach to the relevant entity | M | R2 |
| FR-ING-007 | **Email ingest**: forward to a private address; body + attachments become artefacts with thread context preserved | M | R1 |
| FR-ING-008 | **Quick Capture**: global hotkey note/voice-memo pad that AI later routes to the correct entity | S | R1 |
| FR-ING-009 | Virus/malware scanning and content-safety screening prior to indexing | M | R1 |
| FR-ING-010 | Ingest queue with per-item status, retry, and failure diagnostics | M | R1 |
| FR-ING-011 | Instrument/lab-device drop folders (SFTP/S3-compatible endpoint) for automated data capture | C | R3 |

### 4.3 AI Auto-Organisation & Classification (ORG)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-ORG-001 | Every ingested artefact MUST be auto-classified into: artefact type, academic entity linkage, subject taxonomy, semester/time context, sensitivity level, language | M | R1 |
| FR-ORG-002 | Auto-generated metadata: title, abstract/summary, keywords, authors/contributors, dates, institutions, funding mentions, cited references | M | R1 |
| FR-ORG-003 | Auto-linking: propose relationships to existing entities (this figure ← this dataset; this lecture → this course outcome; this manuscript ← this grant) | M | R1 |
| FR-ORG-004 | Confidence scoring per field; items below threshold routed to a **Review Queue** rather than silently filed | M | R1 |
| FR-ORG-005 | One-click accept / edit / reject on every AI proposal, with the correction used as a learning signal | M | R1 |
| FR-ORG-006 | **Rules engine**: user- and admin-defined deterministic rules (if source = instrument-A and type = CSV → Project X / raw-data, apply retention policy R7) that override model output | M | R2 |
| FR-ORG-007 | Bulk reorganisation: select N artefacts → AI proposes a reorganisation plan → preview diff → apply → single-action undo | M | R1 |
| FR-ORG-008 | Duplicate & near-duplicate detection with merge/keep-both/supersede resolution | M | R2 |
| FR-ORG-009 | Auto-tagging against institutional controlled vocabularies and discipline taxonomies | M | R2 |
| FR-ORG-010 | Continuous re-classification: when the ontology or model improves, previously filed items are re-evaluated and improvements proposed (never silently applied) | S | R2 |
| FR-ORG-011 | **Stray-item detection**: periodic sweep for artefacts with weak linkage ("orphans") and prompt for connection | S | R2 |

### 4.4 Teaching & Course Management (TCH)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-TCH-001 | Course entity with code, title, credits, semester, cohort, syllabus, outcomes (COs), delivery mode | M | R1 |
| FR-TCH-002 | **Semester Roll-Forward**: clone a course to the next offering, carrying materials, rubrics, question banks and outcomes, with a diff view of what changed | M | R1 |
| FR-TCH-003 | Lecture/session planner mapping each session → topics → COs → materials → assessments | M | R1 |
| FR-TCH-004 | Question bank with difficulty, Bloom's level, CO mapping, usage history, and reuse-collision warnings | M | R2 |
| FR-TCH-005 | AI-assisted generation of question papers, rubrics, lesson plans, slide outlines and assignment briefs — always as editable drafts | M | R1 |
| FR-TCH-006 | CO–PO/PSO attainment mapping with automatic computation from assessment data | M | R2 |
| FR-TCH-007 | Assignment/submission handling with plagiarism-service integration and rubric-based grading support | S | R2 |
| FR-TCH-008 | Teaching portfolio auto-compilation: materials, innovations, feedback, attainment, peer reviews | M | R2 |
| FR-TCH-009 | Student feedback ingestion and sentiment/theme analysis with longitudinal trend | S | R2 |
| FR-TCH-010 | LMS bidirectional sync (Moodle, Canvas, Blackboard, Google Classroom) via LTI 1.3 + APIs | M | R2 |
| FR-TCH-011 | Curriculum versioning: syllabus changes tracked across academic years with rationale capture | M | R2 |
| FR-TCH-012 | Accessibility checking of teaching materials (alt text, contrast, reading order) with remediation suggestions | S | R2 |

### 4.5 Research Project & Lab Management (RES)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-RES-001 | Research Project entity: objectives, hypotheses, methods, team + roles, milestones, funding link, ethics link, outputs | M | R1 |
| FR-RES-002 | Experiment/Study records with protocol, parameters, execution log, raw data, processed data, results | M | R2 |
| FR-RES-003 | **Provenance chain**: immutable lineage raw data → script/version → processed data → figure/table → manuscript claim | M | R2 |
| FR-RES-004 | Dataset entity with schema description, variable dictionary, licence, access class, DOI readiness | M | R2 |
| FR-RES-005 | Code/notebook linkage with Git integration (GitHub/GitLab) — commit hash bound to result artefacts | M | R2 |
| FR-RES-006 | Lab notebook mode: timestamped, append-only entries, witness/countersign support | S | R2 |
| FR-RES-007 | Equipment/resource booking and consumable logs linked to projects | C | R3 |
| FR-RES-008 | Ethics/IRB application tracking with approval documents, amendments and expiry alerts | M | R2 |
| FR-RES-009 | **Reproducibility Package** export: one action produces data + code + environment manifest + README + licence, ready for OSF/Zenodo/Dataverse | S | R2 |
| FR-RES-010 | Multi-institution collaboration spaces with per-partner data-sharing rules and IP boundaries | M | R2 |
| FR-RES-011 | Field/clinical data collection intake with consent-form binding and PII handling controls | C | R3 |

### 4.6 Publication & Scholarly Output (PUB)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-PUB-001 | Publication entity across the full lifecycle: idea → draft → internal review → submitted → under review → revision → accepted → published → post-publication | M | R1 |
| FR-PUB-002 | Manuscript workspace with version lineage, section-level comments, and co-author contribution tracking | M | R1 |
| FR-PUB-003 | Reference/citation library with Zotero/Mendeley/BibTeX import-export and de-duplication | M | R1 |
| FR-PUB-004 | Journal/venue tracker: target list, scope fit, impact indicators, APC, OA policy, decision history, response times | S | R2 |
| FR-PUB-005 | Reviewer-response builder: point-by-point response scaffold linked to manuscript changes | S | R2 |
| FR-PUB-006 | Automatic ingest of published works via DOI/Crossref/Scopus/Web of Science/PubMed/ORCID | M | R2 |
| FR-PUB-007 | Citation metrics tracking with source attribution and update cadence | S | R2 |
| FR-PUB-008 | **CRediT taxonomy** contributor roles recorded per output | M | R2 |
| FR-PUB-009 | Open-access compliance: licence, embargo, repository deposit status, funder mandate check | M | R2 |
| FR-PUB-010 | Patent/IP disclosure workflow with confidentiality controls and prior-art attachment | S | R3 |
| FR-PUB-011 | Preprint posting assistance and versioning alignment with the journal version | C | R3 |

### 4.7 Grants, Funding & Compliance Finance (GRT)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-GRT-001 | Grant entity: agency, scheme, award number, PI/Co-PIs, period, budget heads, sanctioned vs. utilised | M | R2 |
| FR-GRT-002 | Proposal pipeline: call discovery → intent → drafting → internal approval → submission → outcome | M | R2 |
| FR-GRT-003 | Deliverable & milestone tracker with due-date alerting and evidence attachment | M | R2 |
| FR-GRT-004 | Expenditure logging with document attachment (invoices, sanction letters, UCs) — reconciliation-ready, not a replacement for ERP finance | S | R2 |
| FR-GRT-005 | Utilisation Certificate / progress-report generation from linked evidence | S | R2 |
| FR-GRT-006 | **Data Management Plan (DMP)** authoring, versioning and automatic compliance posture (are the datasets actually where the DMP promised?) | M | R2 |
| FR-GRT-007 | Funder-specific reporting templates (SERB/DST/DBT/ICMR/UGC, NSF, NIH, ERC, Horizon Europe, Wellcome) | S | R3 |
| FR-GRT-008 | Cost-share, overhead and staff-effort allocation views | C | R3 |

### 4.8 Supervision & Scholar Lifecycle (SUP)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-SUP-001 | Scholar record: enrolment, area, supervisor(s), committee, milestones, funding, timeline | M | R1 |
| FR-SUP-002 | Milestone framework configurable per institution (coursework, comprehensive/qualifier, proposal defence, DC meetings, synopsis, submission, viva) | M | R2 |
| FR-SUP-003 | **Meeting log** with agenda, notes, decisions, action items, and dual acknowledgement — creating an undisputed supervision record | M | R1 |
| FR-SUP-004 | Thesis workspace: chapter-level structure, per-chapter status, word counts, supervisor feedback threads | M | R1 |
| FR-SUP-005 | Progress dashboard with early-warning signals (stalled chapters, missed milestones, low activity, overdue feedback) | M | R2 |
| FR-SUP-006 | Doctoral Committee report generation from the accumulated record | S | R2 |
| FR-SUP-007 | Viva/defence preparation pack: thesis, publications, examiner reports, anticipated questions, provenance appendix | S | R2 |
| FR-SUP-008 | Supervisor load view: all scholars, stages, risk flags, feedback SLA adherence | M | R2 |
| FR-SUP-009 | Alumni conversion at completion with permanent attribution and controlled archive access | S | R2 |

### 4.9 Knowledge, Notes & Literature (KNW)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-KNW-001 | Rich block-based notes with bidirectional linking to any entity | M | R1 |
| FR-KNW-002 | PDF reader with highlights, margin notes, and highlight→note extraction | M | R1 |
| FR-KNW-003 | Literature matrix: comparative table across papers (method, sample, findings, limitations, relevance) auto-populated by AI | M | R2 |
| FR-KNW-004 | Concept/knowledge graph visualisation of the personal and lab corpus | S | R2 |
| FR-KNW-005 | Reading list & queue with priority, deadlines and progress | S | R2 |
| FR-KNW-006 | Idea/Research-question backlog with maturity states and evidence attachment | S | R2 |
| FR-KNW-007 | Templates library (institutional + community): syllabi, proposals, protocols, review forms, thesis skeletons | M | R2 |

### 4.10 Search & Retrieval (SRCH)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-SRCH-001 | Unified search across artefacts, entities, metadata, full text, transcripts, OCR, code and comments | M | R1 |
| FR-SRCH-002 | Hybrid retrieval: BM25 lexical + dense vector + graph traversal, fused and re-ranked | M | R1 |
| FR-SRCH-003 | Natural-language querying ("the slide where I explained transformer attention to first-years last year") | M | R1 |
| FR-SRCH-004 | Faceted filtering: type, entity, person, date, semester, course, project, grant, sensitivity, status, file format, size, language | M | R1 |
| FR-SRCH-005 | Permission-aware results — no leakage of existence for unauthorised items | M | R1 |
| FR-SRCH-006 | Saved searches that materialise as **Smart Folders** | M | R1 |
| FR-SRCH-007 | Search-within-artefact incl. page/timestamp deep links (jump to PDF page 14, video 00:23:11) | M | R2 |
| FR-SRCH-008 | Similar-item and "related to this" discovery | M | R2 |
| FR-SRCH-009 | Query autocomplete, spell tolerance, synonym & acronym expansion using academic vocabularies | M | R2 |
| FR-SRCH-010 | Federated search across linked external sources (library catalogue, institutional repository, Scopus) | C | R3 |
| FR-SRCH-011 | Zero-result recovery: explain why nothing matched and offer relaxed queries | S | R2 |

### 4.11 AI Assistant & Agents (AI)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-AI-001 | Conversational assistant grounded in the user's authorised corpus with inline citations to source artefacts | M | R1 |
| FR-AI-002 | Scope selector: ask across *this artefact*, *this entity*, *my workspace*, *my lab*, *my department* (permission-bounded) | M | R1 |
| FR-AI-003 | Document intelligence: summarise, extract, compare, critique, translate, simplify, expand | M | R1 |
| FR-AI-004 | Multi-document synthesis: literature reviews, gap analyses, methodological comparisons | M | R2 |
| FR-AI-005 | Draft generation for academic artefacts (see §11 catalogue), always labelled and editable | M | R1 |
| FR-AI-006 | Agentic workflows: multi-step tasks with a visible plan, step approvals and a full action log | M | R2 |
| FR-AI-007 | Proactive intelligence: deadline risk, missing evidence, unlinked outputs, compliance gaps, stale drafts | M | R2 |
| FR-AI-008 | AI actions on the workspace (reorganise, rename, tag, link, generate) — always previewed, always reversible | M | R1 |
| FR-AI-009 | Per-tenant and per-user AI controls: enable/disable features, model routing, data-boundary settings | M | R1 |
| FR-AI-010 | Explicit AI-generated content labelling and export-time disclosure metadata | M | R1 |
| FR-AI-011 | Feedback capture (thumbs, corrections, "wrong citation") feeding evaluation datasets | M | R1 |
| FR-AI-012 | Voice interaction for hands-free capture and query | C | R3 |

### 4.12 Collaboration & Workflow (COL)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-COL-001 | Threaded comments and @mentions on artefacts, versions, regions (PDF area, video timespan, cell range) | M | R1 |
| FR-COL-002 | Task assignment with due dates, dependencies and entity linkage | M | R1 |
| FR-COL-003 | Configurable approval workflows (syllabus approval, leave for conference, proposal sign-off, data release) with parallel/serial routing, escalation and SLA | M | R2 |
| FR-COL-004 | Shared spaces with role-scoped membership and join requests | M | R1 |
| FR-COL-005 | External sharing: expiring links, watermarking, download control, view analytics, NDA acknowledgement | M | R2 |
| FR-COL-006 | Real-time presence and co-editing for native notes; lock/check-out for binary artefacts | S | R2 |
| FR-COL-007 | Notification centre with digest scheduling, channel routing (in-app, email, mobile push, Teams/Slack) and quiet hours | M | R1 |
| FR-COL-008 | Handover packs: assemble everything a successor needs for a course/project/scholar | S | R2 |

### 4.13 Compliance, Accreditation & Governance (CMP)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-CMP-001 | Framework library with criterion trees: NAAC, NBA, NIRF, ABET, AACSB, AQAS, REF, TEQSA, WASC, plus custom | M | R2 |
| FR-CMP-002 | **Evidence mapping**: link artefacts to criteria manually or via AI suggestion; one artefact may serve many criteria | M | R2 |
| FR-CMP-003 | Live readiness scoring per criterion with gap list and owner assignment | M | R2 |
| FR-CMP-004 | Evidence-pack export: indexed, paginated, hyperlinked PDF/ZIP bundle matching the regulator's required structure | M | R2 |
| FR-CMP-005 | Immutable audit trail of who submitted what evidence and when | M | R2 |
| FR-CMP-006 | Retention policies and legal holds per artefact class | M | R2 |
| FR-CMP-007 | Annual appraisal / API-score / faculty-activity report generation from the live record | M | R2 |
| FR-CMP-008 | Policy engine: institutional rules enforced at action time (e.g., "no external sharing of unpublished datasets") with clear denial reasons | M | R2 |
| FR-CMP-009 | Conflict-of-interest and research-integrity declarations tracking | C | R3 |

### 4.14 Analytics & Reporting (ANL)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-ANL-001 | Personal analytics: output over time, teaching load, supervision load, citation trajectory, time allocation | M | R2 |
| FR-ANL-002 | Lab/project analytics: throughput, milestone adherence, budget burn, member contribution | M | R2 |
| FR-ANL-003 | Departmental analytics: publications, funding, student outcomes, workload equity, quality indicators | M | R2 |
| FR-ANL-004 | Institutional analytics: research profile, collaboration network, ranking-metric readiness, trend forecasting | S | R3 |
| FR-ANL-005 | Report builder with scheduled delivery and multiple export formats | S | R2 |
| FR-ANL-006 | Benchmarking against anonymised, consented cohorts | C | R3 |
| FR-ANL-007 | Every number in every chart MUST be drillable to its source artefacts | M | R2 |

### 4.15 Administration & Platform Operations (ADM)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-ADM-001 | Org-structure management (faculties, departments, centres, labs) with effective-dated changes | M | R2 |
| FR-ADM-002 | Licence/seat management, usage quotas, storage allocation by unit | M | R2 |
| FR-ADM-003 | Tenant branding, custom domain, localisation defaults | S | R2 |
| FR-ADM-004 | Configuration of taxonomies, naming conventions, templates and workflows | M | R2 |
| FR-ADM-005 | Audit-log explorer with export to SIEM | M | R2 |
| FR-ADM-006 | Data residency selection at tenant creation | M | R2 |
| FR-ADM-007 | Full tenant export and verified deletion on offboarding | M | R2 |
| FR-ADM-008 | Sandbox/staging tenant for configuration testing | C | R3 |

### 4.16 Platform, API & Extensibility (PLT)

| ID | Requirement | Pri | Rel |
|---|---|:--:|:--:|
| FR-PLT-001 | Public REST + GraphQL API covering all first-party capabilities | M | R2 |
| FR-PLT-002 | Webhooks and event subscriptions | M | R2 |
| FR-PLT-003 | OAuth 2.1 app authorisation with granular scopes and per-tenant admin approval | M | R2 |
| FR-PLT-004 | Standards support: OAI-PMH, DataCite, Crossref, SWORD, LTI 1.3, RO-Crate | S | R3 |
| FR-PLT-005 | Offline-capable desktop sync client (Windows/macOS/Linux) with selective sync | M | R2 |
| FR-PLT-006 | Mobile apps (iOS/Android) for capture, review, approvals and search | M | R2 |
| FR-PLT-007 | Extension marketplace with review, sandboxing and permission disclosure | C | R3 |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Target |
|---|---|---|
| NFR-PERF-001 | Application shell first contentful paint | ≤ 1.2 s p75 on 10 Mbps |
| NFR-PERF-002 | Dashboard fully interactive | ≤ 2.0 s p95 |
| NFR-PERF-003 | Search results (10M-artefact tenant) | ≤ 300 ms p95, ≤ 800 ms p99 |
| NFR-PERF-004 | Semantic/RAG answer — first token | ≤ 1.5 s p90 |
| NFR-PERF-005 | Complete grounded answer (≤ 8 sources) | ≤ 6 s p90 |
| NFR-PERF-006 | Artefact preview render (≤ 50 MB PDF) | ≤ 1.5 s p90 |
| NFR-PERF-007 | Ingest-to-searchable latency (doc ≤ 20 MB) | ≤ 60 s p90 |
| NFR-PERF-008 | Ingest-to-searchable (video ≤ 2 h) | ≤ 20 min p90 |
| NFR-PERF-009 | Upload throughput per client | ≥ 80% of available bandwidth |
| NFR-PERF-010 | UI interaction feedback | ≤ 100 ms; anything longer shows optimistic state |
| NFR-PERF-011 | Bulk operation on 10,000 artefacts | Queued, progress-tracked, ≤ 15 min |

### 5.2 Scalability

| ID | Requirement | Target |
|---|---|---|
| NFR-SCAL-001 | Concurrent active users | 100,000 platform-wide; 25,000 peak per region |
| NFR-SCAL-002 | Registered users | 5,000,000 |
| NFR-SCAL-003 | Tenants | 10,000 institutions |
| NFR-SCAL-004 | Largest single tenant | 50,000 users, 500 TB, 500M artefacts |
| NFR-SCAL-005 | Artefacts platform-wide | 50 billion |
| NFR-SCAL-006 | Vector index | 100 billion chunks, sharded per tenant |
| NFR-SCAL-007 | Ingest throughput | 10,000 artefacts/minute sustained; 50,000 burst |
| NFR-SCAL-008 | Horizontal scalability | All stateless services scale linearly to 10× with < 15% efficiency loss |
| NFR-SCAL-009 | Noisy-neighbour isolation | Per-tenant rate limits, quotas and queue fairness; no tenant may consume > 5% of shared capacity |
| NFR-SCAL-010 | Elasticity | Autoscale to 3× baseline within 5 minutes |

### 5.3 Availability & Reliability

| ID | Requirement | Target |
|---|---|---|
| NFR-AVL-001 | Core read/search availability | 99.95% monthly (enterprise SLA 99.9% with credits) |
| NFR-AVL-002 | Write/ingest availability | 99.9% monthly |
| NFR-AVL-003 | AI services availability | 99.5% with graceful degradation to non-AI search |
| NFR-AVL-004 | RPO | ≤ 5 minutes |
| NFR-AVL-005 | RTO | ≤ 1 hour (region failure ≤ 4 hours) |
| NFR-AVL-006 | Durability of stored artefacts | 99.999999999% (11 nines) |
| NFR-AVL-007 | Zero-downtime deploys | Blue/green + progressive rollout, automated rollback on SLO burn |
| NFR-AVL-008 | Graceful degradation ladder | AI off → semantic search off → lexical search + browse always available |
| NFR-AVL-009 | Backup verification | Automated monthly restore drills with published results |
| NFR-AVL-010 | Chaos engineering | Quarterly game-days incl. region loss and dependency failure |

### 5.4 Security (summary; full treatment in §12)

| ID | Requirement |
|---|---|
| NFR-SEC-001 | Encryption in transit TLS 1.3; at rest AES-256; per-tenant keys with optional BYOK/HYOK |
| NFR-SEC-002 | Zero-trust service mesh with mTLS between all internal services |
| NFR-SEC-003 | Complete, tamper-evident audit logging of every data access and mutation |
| NFR-SEC-004 | Annual third-party penetration test; continuous automated scanning; public disclosure policy |
| NFR-SEC-005 | Certifications: ISO 27001, SOC 2 Type II, ISO 27701; alignment with GDPR, India DPDP Act 2023, FERPA, HIPAA (where applicable) |
| NFR-SEC-006 | Secrets in a managed vault, rotated ≤ 90 days; no long-lived static credentials |
| NFR-SEC-007 | Supply-chain: SBOM per release, signed artefacts, dependency provenance attestation |

### 5.5 Usability & Accessibility

| ID | Requirement |
|---|---|
| NFR-USE-001 | WCAG 2.2 Level AA across all user-facing surfaces; AAA for text contrast where feasible |
| NFR-USE-002 | Full keyboard operability; every action reachable via command palette |
| NFR-USE-003 | Screen-reader tested (NVDA, JAWS, VoiceOver) each release |
| NFR-USE-004 | New user completes core task (find a specific artefact) without training in ≤ 3 minutes |
| NFR-USE-005 | SUS score ≥ 80 in usability benchmarks |
| NFR-USE-006 | No destructive action without confirmation + undo window ≥ 30 days |
| NFR-USE-007 | Responsive from 320 px to ultrawide; touch targets ≥ 44 px |
| NFR-USE-008 | Reduced-motion, high-contrast and dyslexia-friendly typography options |

### 5.6 Interoperability & Portability

| ID | Requirement |
|---|---|
| NFR-INT-001 | All user data exportable in open formats (original binaries + JSON-LD metadata + relationship graph) |
| NFR-INT-002 | No proprietary lock-in: exports must be re-importable and human-navigable |
| NFR-INT-003 | Standards conformance: Dublin Core, DataCite 4.x, CERIF, schema.org, RO-Crate, BagIt for archival |
| NFR-INT-004 | Cloud-portable architecture (Kubernetes + open datastores); avoid single-vendor lock-in on critical paths |
| NFR-INT-005 | Private/on-prem deployment option for sovereignty-constrained institutions (R3) |

### 5.7 Internationalisation

| ID | Requirement |
|---|---|
| NFR-I18N-001 | UI localisation framework from day one; launch locales: en-GB, en-US, hi-IN, plus 8 more by R3 |
| NFR-I18N-002 | Content processing (OCR, embeddings, summarisation) for ≥ 30 languages |
| NFR-I18N-003 | Full Unicode, RTL layout support, locale-aware dates/numbers, multiple academic-calendar systems |
| NFR-I18N-004 | Transliteration-tolerant search for Indic and CJK scripts |

### 5.8 Maintainability & Observability

| ID | Requirement |
|---|---|
| NFR-MNT-001 | Modular service boundaries; no service > 30k LOC; documented ownership per service |
| NFR-MNT-002 | ≥ 80% automated test coverage on business logic; contract tests on every service boundary |
| NFR-MNT-003 | OpenTelemetry traces, metrics and structured logs on 100% of requests |
| NFR-MNT-004 | SLO-based alerting with error budgets; no alert without a runbook |
| NFR-MNT-005 | Feature flags for all non-trivial changes; kill switch per AI feature |
| NFR-MNT-006 | Deploy frequency ≥ daily; change-failure rate ≤ 10%; MTTR ≤ 30 min (DORA elite) |
| NFR-MNT-007 | All architectural decisions recorded as ADRs in-repo |

### 5.9 AI-Specific Quality

| ID | Requirement | Target |
|---|---|---|
| NFR-AIQ-001 | Grounded-answer citation accuracy | ≥ 97% of citations support the claim |
| NFR-AIQ-002 | Hallucination rate on corpus questions | ≤ 1.5%; unanswerable questions correctly refused ≥ 95% |
| NFR-AIQ-003 | Classification precision / recall | ≥ 0.92 / ≥ 0.88 on the golden set |
| NFR-AIQ-004 | Retrieval Recall@10 | ≥ 0.93 on the evaluation benchmark |
| NFR-AIQ-005 | Cost per active user per month (AI inference) | ≤ $1.80 at R2 scale |
| NFR-AIQ-006 | Regression gate | No model/prompt release may reduce any eval metric > 2% without sign-off |
| NFR-AIQ-007 | Fairness | No significant quality degradation across discipline, language or seniority cohorts |

### 5.10 Compliance, Legal & Ethics

| ID | Requirement |
|---|---|
| NFR-LEG-001 | Data residency honoured absolutely — including embeddings, caches, logs and AI inference |
| NFR-LEG-002 | DSR (access, rectification, erasure, portability) fulfilled ≤ 30 days, ≤ 7 days for institutional escalation |
| NFR-LEG-003 | Records of processing, DPIAs, and sub-processor register maintained and published |
| NFR-LEG-004 | Academic-integrity safeguards: AI drafts labelled; no ghost-authorship affordances; institution-configurable AI usage policy |
| NFR-LEG-005 | Accessibility conformance statements (VPAT) published per release |
| NFR-LEG-006 | Alignment with the EU AI Act transparency obligations for limited-risk systems |

### 5.11 Cost & Efficiency

| ID | Requirement |
|---|---|
| NFR-COST-001 | Infrastructure cost ≤ 22% of revenue at steady state |
| NFR-COST-002 | Storage cost optimised via tiering; ≥ 60% of bytes on warm/cold tiers by month 18 |
| NFR-COST-003 | Model routing must prefer the cheapest model meeting the quality bar for each task class |
| NFR-COST-004 | Per-tenant cost attribution and reporting for pricing accuracy |

---

# PART B — EXPERIENCE ARCHITECTURE

---

## 6. User Journey

### 6.1 Journey Map J1 — Faculty Onboarding & Migration ("The First Hour")

**Goal:** convert 15 years of chaos into a structured workspace with minimum effort and maximum trust.

| Stage | User Action | System Response | Emotion | Design Imperative |
|---|---|---|---|---|
| **1. Arrive** | Lands via colleague referral or institutional email | Value proposition in academic language, not enterprise jargon; 90-second demo with a real professor's workspace | Curious / sceptical | Speak the domain instantly |
| **2. Identify** | Signs in with institutional SSO or ORCID | ORCID pulls publication history; SSO pulls department, courses, role | Pleasantly surprised | Never ask for what we can fetch |
| **3. Declare** | Answers 6 questions: discipline, role, courses taught, research areas, scholars supervised, current tools | Ontology seeded; workspace skeleton pre-built | Invested | ≤ 60 s; every question must visibly change the outcome |
| **4. Connect** | Authorises Google Drive + email + Zotero | Read-only scan begins; live counter: "Found 12,847 items · 3,201 documents · 89 datasets · 412 presentations" | Anticipation | Show progress with meaning, not a spinner |
| **5. **The Reveal**** | Reviews the proposed organisation | Split view: chaotic original tree on the left; proposed structure on the right — Courses (6), Research Projects (4), Publications (37), Scholars (3), Grants (2), Admin (1). Confidence badges. "142 items need your input" | **Awe — the pivotal moment** | This screen decides whether the product succeeds |
| **6. Correct** | Fixes ~20 misclassifications, merges two projects, renames one course | Corrections applied and generalised: "Apply this rule to 47 similar items?" | Control regained | Corrections must feel powerful, not tedious |
| **7. Commit** | Approves the plan | Background migration; user can start working immediately on completed portions | Relief | Never block the user on a batch job |
| **8. First Win** | Asks: "What did I teach in Data Structures last spring?" | Answer with the exact syllabus, 14 lecture decks, 3 assignments, and the question bank — cited | **Conversion** | The first query must be answered perfectly |
| **9. Habituate** | Returns next morning | Dashboard shows today's classes, an overdue review, a scholar awaiting feedback, and a deadline in 6 days | Dependence forming | Give a reason to open it daily |

**Critical failure modes to design against:** the Reveal showing obviously wrong structure (trust collapse); migration silently altering originals (never — source is read-only); asking for manual metadata before delivering value.

### 6.2 Journey Map J2 — PhD Scholar, Year 1 → Viva (the 4-year arc)

| Phase | Duration | Scholar Activity | AcademicOS Role | Key Artefacts |
|---|---|---|---|---|
| **Orientation** | M0–M3 | Enrolment, supervisor allocation, coursework | Thesis workspace auto-created; milestone timeline instantiated from institutional template; supervisor linked | Enrolment record, timeline, agreement |
| **Literature Immersion** | M3–M12 | Reading 15 papers/week, building a mental map | Papers ingested from browser/Zotero; auto-summarised; literature matrix builds itself; concept graph reveals clusters and gaps | Reading library, literature matrix, gap analysis |
| **Proposal** | M9–M15 | Formulating the question, defending the proposal | AI drafts the proposal from the accumulated literature and notes; committee feedback captured as durable records | Proposal, DC minutes, approval |
| **Execution** | M12–M36 | Experiments, code, data, failures, iteration | Every run captured with parameters; provenance chain formed automatically; negative results preserved (they matter) | Datasets, code versions, lab entries, figures |
| **Dissemination** | M18–M42 | Conference and journal papers | Manuscript workspace; co-author contributions logged; submissions tracked; reviewer responses scaffolded | Manuscripts, reviews, publications |
| **Synthesis** | M36–M45 | Writing the thesis | Chapters assemble from existing artefacts; every figure traceable to raw data; consistency checks across chapters; citation completeness audit | Thesis versions, figure provenance |
| **Defence** | M45–M48 | Submission, examiners, viva | Viva pack generated: thesis, publication record, anticipated questions from examiner profiles, provenance appendix | Viva pack, examiner reports |
| **Transition** | M48+ | Graduation | Corpus archived with permanent attribution; converts to Alumni; supervisor retains institutional continuity of the work | Archive, handover, DOI deposits |

**Anxiety-reduction design:** a persistent "Your work is safe" affordance — versions, backups and provenance visible at a glance. This is a genuine emotional requirement for doctoral users.

### 6.3 Journey Map J3 — The Accreditation Sprint (Institutional)

**Before AcademicOS:** 6 months, 40 people, 800 emails, 11,000 files in a shared drive named `NAAC_FINAL_2026_v3`, and a week of collective panic.

| Stage | Actor | With AcademicOS |
|---|---|---|
| Framework setup | Compliance Officer | Selects "NAAC Cycle 4" from the library; criterion tree loads with metrics and expected evidence types |
| Baseline scan | System | AI maps existing corpus to criteria; produces a readiness heatmap in hours, not months |
| Gap assignment | Compliance Officer | Gaps auto-assigned to owning departments with deadlines; owners see only their gaps |
| Evidence contribution | Faculty | Each professor sees a short personal list: "3 items needed"; uploads or confirms existing artefacts inline |
| Verification | HoD → Compliance | Two-stage approval; every item carries provenance and a timestamp |
| Assembly | System | Evidence pack generated: indexed, paginated, hyperlinked, regulator-formatted |
| Submission | Compliance Officer | Export + immutable snapshot retained for audit defence |
| Audit visit | Auditor | Read-only auditor role with direct criterion→evidence navigation |

**Outcome target:** 6 months → 3 weeks; 40 people → 6 people plus lightweight faculty confirmations.

### 6.4 Journey Map J4 — A Day in the Life (Assistant Professor, Tuesday)

| Time | Situation | Interaction |
|---|---|---|
| 07:40 | Commute | Mobile: reviews the Morning Brief — 2 classes, 1 scholar meeting, a grant milestone in 6 days, and one manuscript revision request received overnight |
| 09:00 | Before class | Opens today's session; materials, attendance link and last year's student-confusion notes surfaced together |
| 11:15 | Post-class | Voice memo: "students struggled with the pumping lemma — add worked examples next year" → auto-attached to that session for next roll-forward |
| 12:30 | Scholar meeting | Meeting log opens with last meeting's action items pre-loaded; new decisions captured; both parties acknowledge |
| 14:00 | Deep work | Manuscript revision; AI compares reviewer comments against the current draft and flags two unaddressed points |
| 16:00 | Committee | Uploads minutes by email forward; system files them under the committee entity and extracts action items |
| 17:30 | Admin | Approves two student submissions and a leave request from the notification centre |
| 21:00 | Home | Asks: "Am I on track for my annual appraisal?" → live report with evidence links and three gaps identified |

### 6.5 Emotional Design Requirements

| Emotion | Trigger | Design Response |
|---|---|---|
| Fear of loss | Uploading a life's work to a new system | Visible version history, "safe" indicators, one-click full export, transparent backups |
| Distrust of AI | Automated organisation of precious material | Preview everything; cite everything; undo everything; never auto-delete |
| Overwhelm | Thousands of items needing review | Progressive disclosure; batch rules; "good enough now, refine later" |
| Pride | Career accomplishment | Beautiful portfolio and impact views worth showing to a committee |
| Belonging | Institutional identity | Tenant branding, departmental spaces, shared vocabulary |

---

## 7. Navigation Flow

### 7.1 Information Architecture

```
AcademicOS
│
├── ⌂ Home (role-adaptive dashboard)
│
├── ⚡ Today            — agenda, tasks, approvals, AI briefing
│
├── ◈ Spaces           — the primary workspace container
│   ├── Personal Space
│   ├── Course Spaces        (per course offering)
│   ├── Research Spaces      (per project / lab)
│   ├── Supervision Spaces   (per scholar)
│   ├── Committee Spaces
│   └── Shared / External Spaces
│
├── ▤ Library          — the artefact universe (all views)
│   ├── All Artefacts
│   ├── Smart Folders (saved queries)
│   ├── Recent · Starred · Shared with me
│   ├── Review Queue (low-confidence AI proposals)
│   └── Archive · Trash (30-day recovery)
│
├── ◉ Entities         — the academic domain objects
│   ├── Courses          ├── Publications      ├── Datasets
│   ├── Projects         ├── Grants            ├── People
│   ├── Scholars         ├── Committees        └── Venues
│
├── ✦ Assistant        — conversational AI + agent runs
│
├── ⌕ Search           — universal (also ⌘K from anywhere)
│
├── ▦ Insights         — analytics, portfolio, compliance posture
│
├── ⚙ Admin            — (role-gated) org, policy, users, integrations
│
└── ◐ Profile          — identity, ORCID, preferences, AI settings, storage
```

### 7.2 Navigation Model

Three-zone layout, borrowed from the best of Notion (flexibility), VS Code (density discipline) and Outlook (information rhythm):

| Zone | Width | Contents | Behaviour |
|---|---|---|---|
| **Rail** (L1) | 56 px collapsed / 240 px expanded | Global sections, pinned spaces, workspace switcher | Persistent; collapsible; keyboard `⌘\` |
| **Context Pane** (L2) | 280–360 px, resizable | Tree/list for the active section; filters; smart folders | Contextual; hideable for focus mode |
| **Canvas** (L3) | Remaining | Content: dashboard, artefact viewer, entity detail, table view | Tab support; split view; full-screen mode |
| **Assistant Dock** (L4) | 400 px overlay / docked right | AI conversation scoped to current context | Summonable `⌘J`; remembers per-space threads |
| **Inspector** (L5) | 320 px right | Metadata, versions, links, permissions, activity for selection | Toggle `⌘I`; tabbed |

### 7.3 Primary Navigation Flows

**Flow A — Find something (the most frequent flow)**
```
Any screen → ⌘K → type intent
   ├─ exact-ish match → arrow to result → ↵ opens artefact
   ├─ natural language → Assistant answers with cited artefacts → open source
   └─ ambiguous → Search Results (facets + preview) → refine → open
                        └─ "Save as Smart Folder" → appears in Library
```

**Flow B — Capture something**
```
Ingest (drag / email / scan / sync / API)
  → Processing (virus scan → extract → OCR/ASR → embed → classify)
  → Confidence check
       ├─ high  → auto-filed + toast "Filed to Course X · Undo · Change"
       └─ low   → Review Queue badge → user confirms in a 3-second interaction
  → Linked, indexed, searchable, notified to relevant collaborators
```

**Flow C — Work inside an entity**
```
Spaces → Research Space "NanoCat"
  → Overview (health, timeline, team, recent activity)
  → Tabs: Artefacts · Experiments · Data · Manuscripts · Tasks · Budget · Compliance · Discussion
  → Select artefact → Canvas viewer + Inspector
  → Ask Assistant (scope auto-set to this space)
```

**Flow D — Report/comply**
```
Insights → Compliance → Framework (NAAC C4)
  → Criterion tree with readiness heatmap
  → Criterion 3.2 (68%) → Gap list → Assign owner / Attach evidence
  → Evidence attached from existing corpus via AI suggestion
  → Readiness recalculates live → Export Evidence Pack
```

**Flow E — Supervise**
```
Spaces → Supervision → Scholar "R. Menon"
  → Timeline (milestones, risk flags) → Chapter status board
  → Open Chapter 3 v7 → inline feedback → resolve
  → Log meeting → decisions + actions → dual acknowledgement → notifications
```

### 7.4 URL & Deep-Linking Scheme

Stable, human-readable, shareable, permission-checked:

```
/t/{tenant}/home
/t/{tenant}/today
/t/{tenant}/space/{space-slug}
/t/{tenant}/space/{space-slug}/artefacts?type=slides&sem=2026-odd
/t/{tenant}/artefact/{artefact-id}                 (canonical, immutable)
/t/{tenant}/artefact/{artefact-id}/v/{version}
/t/{tenant}/artefact/{artefact-id}#p=14            (PDF page)
/t/{tenant}/artefact/{artefact-id}#t=00:23:11      (media timestamp)
/t/{tenant}/entity/course/{course-id}
/t/{tenant}/entity/scholar/{scholar-id}/milestones
/t/{tenant}/search?q=...&f[type]=dataset&f[year]=2025
/t/{tenant}/assistant/thread/{thread-id}
/t/{tenant}/insights/compliance/{framework}/{criterion}
/t/{tenant}/admin/policies
/share/{opaque-token}                               (external, expiring)
```

Rules: every artefact has a permanent canonical URL that never breaks even after moves and renames; every view state (filters, sort, layout) is encoded in the URL so it can be shared; all links are permission-checked at render, returning a request-access page rather than a 404 when the item exists but is unauthorised (unless existence itself is confidential, in which case 404).

### 7.5 Command Palette (⌘K / Ctrl-K) — the Power Spine

A single input that unifies six modes, disambiguated by prefix:

| Prefix | Mode | Example |
|---|---|---|
| *(none)* | Universal search | `attention lecture` |
| `>` | Commands | `> create course` |
| `@` | People | `@meera` |
| `#` | Entities/tags | `#NanoCat` |
| `/` | Navigation | `/insights/compliance` |
| `?` | Ask AI | `? what's blocking my grant report` |

Requirements: ≤ 50 ms to open, results stream as you type, recent/frequent items ranked first, fully keyboard-operable, works offline for cached content.

### 7.6 Navigation Principles

1. **Three-click rule, honoured by search.** Any artefact reachable in ≤ 3 clicks *or* one ⌘K.
2. **You are always somewhere.** Persistent breadcrumbs showing entity path, not just folder path (e.g., `Research › NanoCat › Experiments › Run 42 › raw.csv`).
3. **Context follows you.** Opening the Assistant from a space scopes it to that space automatically.
4. **Back always works.** Full browser-history semantics including modal and pane state.
5. **No dead ends.** Every empty state suggests the next action; every error offers a recovery.
6. **Progressive disclosure.** Advanced features (rules engine, provenance graph, policy editor) live one level deeper, never cluttering the primary path.

---

## 8. Module Breakdown

### 8.1 System Context

```
┌────────────────────────────────────────────────────────────────────────┐
│  CLIENTS   Web SPA · Desktop Sync · Mobile (iOS/Android) · Browser Ext │
│            Email Gateway · Public API Consumers · LMS via LTI          │
└───────────────────────────────┬────────────────────────────────────────┘
                                │  HTTPS / WSS
┌───────────────────────────────▼────────────────────────────────────────┐
│  EDGE       CDN · WAF · DDoS · API Gateway · AuthN · Rate Limit · BFF  │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────────┐
│  EXPERIENCE LAYER   GraphQL Federation · REST v1 · WebSocket Hub       │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────────┐
│  DOMAIN SERVICES (M01–M16)                                             │
│  Identity · Artefact · Entity/Graph · Ingest · AI Orchestration ·      │
│  Search · Version · Collaboration · Workflow · Compliance · Analytics· │
│  Notification · Integration · Admin · Billing · Audit                  │
└───────────────────────────────┬────────────────────────────────────────┘
                                │  Kafka / NATS event backbone
┌───────────────────────────────▼────────────────────────────────────────┐
│  PLATFORM   PostgreSQL · Neo4j/Age · OpenSearch · Vector DB · Redis ·  │
│             S3-compatible Object Store · ClickHouse · Temporal         │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────────┐
│  EXTERNAL   LLM providers · ORCID · Crossref · Scopus · LMS · HRIS ·   │
│             Turnitin · Zotero · GitHub · Microsoft 365 · Google        │
└────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Module Catalogue

---

#### **M01 — Identity & Access Management (IAM)**
- **Responsibility:** authentication, session management, tenant membership, role/capability resolution, policy evaluation (RBAC+ABAC+ReBAC), delegation, access reviews.
- **Key components:** Auth Service (OIDC/SAML/passkeys), Policy Decision Point (PDP), Policy Enforcement Points embedded in every service, SCIM Provisioner, Consent Manager.
- **Data owned:** users, identities, tenants, memberships, roles, capabilities, policies, grants, delegations, sessions.
- **Contracts consumed by:** every module (authorisation is a synchronous, cached, sub-5 ms call).
- **Design notes:** PDP decisions cached per (subject, resource-class, action) with event-driven invalidation. Decisions return a *reason object* to power the "Why do I have access?" UI.
- **Scaling:** stateless, regional replicas, decision cache hit rate target ≥ 95%.

---

#### **M02 — Artefact Service (Content Core)**
- **Responsibility:** the lifecycle of every stored object — create, read, update metadata, soft delete, restore, purge, move (re-link), copy, lock, preview generation, thumbnail, format conversion.
- **Key components:** Artefact API, Storage Abstraction Layer (multi-cloud object store), Preview/Render Pipeline, Format Converter, Quota Manager, Retention Enforcer.
- **Data owned:** artefacts, blobs, previews, storage locations, quotas, retention states.
- **Interfaces:** emits `artefact.created|updated|moved|deleted|restored` events.
- **Design notes:** content-addressed storage (SHA-256) enables cross-tenant *conceptual* dedup while keeping per-tenant encryption — dedup happens only within a tenant's key domain to prevent cross-tenant inference attacks.

---

#### **M03 — Entity & Knowledge Graph Service**
- **Responsibility:** the academic domain model — courses, projects, publications, grants, scholars, datasets, committees, venues, people — and the typed relationships between them and artefacts. This is the module that makes AcademicOS more than a drive.
- **Key components:** Entity CRUD, Relationship Engine, Graph Query API, Ontology Registry, Entity Resolution (deduplicating "R. Menon" / "Rahul Menon" / ORCID), Lineage Tracker.
- **Data owned:** entities, relationships, ontology definitions, entity-resolution clusters.
- **Design notes:** graph is the authoritative structure; folder trees are materialised projections rebuilt from graph state. Relationships are first-class objects with their own metadata (created_by, confidence, source: human|ai|rule|import, valid_from/to).

---

#### **M04 — Ingest & Processing Pipeline**
- **Responsibility:** get content in, safely, and make it machine-understandable.
- **Pipeline stages (each independently scalable, retryable, idempotent):**
  1. Receive (chunked upload / connector poll / email / API)
  2. Quarantine + malware scan + content-safety screen
  3. Type detection & validation
  4. Blob persist + hash + dedup check
  5. Text extraction (PDF, Office, LaTeX, code, notebooks)
  6. OCR (printed + handwritten) for images/scans
  7. ASR + diarisation for audio/video
  8. Structure parsing (tables, figures, sections, references, formulas)
  9. Chunking (semantic, structure-aware, overlapping)
  10. Embedding generation (text, and optionally image/table)
  11. Metadata extraction (LLM + specialised extractors)
  12. Classification & entity linking proposal
  13. Index publish (lexical + vector + graph)
  14. Notify + confidence routing (auto-file vs. review queue)
- **Key components:** Orchestrator (Temporal workflows), worker pools per stage, priority queues (interactive > batch > backfill), Dead-Letter handling with human-visible diagnostics.
- **Design notes:** the pipeline must be resumable at any stage and re-runnable when models improve, without re-uploading content.

---

#### **M05 — AI Orchestration Service**
- **Responsibility:** all model interaction — routing, prompting, retrieval, tool use, agent execution, guardrails, evaluation, cost control.
- **Key components:** Model Router, Prompt Registry (versioned, A/B-testable), RAG Engine, Agent Runtime, Tool Registry, Guardrail Filters (input & output), Citation Verifier, Token/Cost Accountant, Eval Harness, Feedback Collector.
- **Design notes:** no other service calls an LLM directly — a single choke point for security, cost, auditability and model portability. Every AI invocation writes an `ai_interaction` record with prompt hash, model, retrieved context IDs, output, latency, cost and user feedback.

---

#### **M06 — Search Service**
- **Responsibility:** query understanding, hybrid retrieval, permission filtering, ranking, facets, suggestions, saved searches.
- **Key components:** Query Parser/Planner, Lexical Index (OpenSearch), Vector Index, Graph Expander, Fusion Ranker, ACL Filter, Personalisation Layer, Result Cache.
- **Design notes:** authorisation is applied as a pre-filter on index shards (per-tenant) and a post-filter on results (per-artefact ACL), never as a UI-level hide.

---

#### **M07 — Version & Provenance Service**
- **Responsibility:** immutable version lineage, diffing, branching for manuscripts, restore, provenance chains, attribution ledger, content integrity.
- **Key components:** Version Store, Diff Engine (text, structured, binary-aware, semantic), Branch/Merge Manager, Lineage Recorder, Integrity Verifier (hash chain).

---

#### **M08 — Collaboration Service**
- **Responsibility:** comments, mentions, presence, real-time co-editing (CRDT for native notes), sharing, external access tokens, activity feeds.

---

#### **M09 — Workflow & Automation Engine**
- **Responsibility:** approvals, tasks, rules, triggers, scheduled jobs, SLA tracking, escalation.
- **Key components:** Workflow Definition Store (declarative, versioned), Temporal-backed execution, Rules Engine (deterministic, evaluated before AI), Task Service, SLA Monitor.

---

#### **M10 — Compliance & Accreditation Service**
- **Responsibility:** framework definitions, criterion trees, evidence mapping, readiness scoring, evidence-pack generation, retention policy, legal holds, integrity attestations.

---

#### **M11 — Analytics & Insights Service**
- **Responsibility:** metric computation, dashboards, report builder, exports, forecasting, benchmarking.
- **Key components:** Event Collector, ClickHouse warehouse, dbt-style transformation layer, Metric Registry (single definition per metric — no duplicate truth), Report Renderer.
- **Design note:** every metric is defined once in the Metric Registry and referenced everywhere, guaranteeing that "publication count" means the same thing on a faculty dashboard, a dean's report and a NAAC submission.

---

#### **M12 — Notification Service**
- **Responsibility:** multi-channel delivery (in-app, email, push, Teams/Slack/webhook), user preferences, digesting, quiet hours, deduplication, escalation.
- **Design note:** aggressive intelligent bundling — academics abandon tools that email them 40 times a day.

---

#### **M13 — Integration Hub**
- **Responsibility:** all external connectors, normalised into internal events. Connector SDK, credential vault, sync scheduler, conflict resolution, backfill, health monitoring.
- **Connector families:** storage (Drive/OneDrive/Dropbox/S3), identity (IdP/HRIS/SIS), academic (ORCID/Crossref/Scopus/WoS/PubMed/DOAJ/Unpaywall), LMS (LTI 1.3), reference (Zotero/Mendeley), code (GitHub/GitLab), repositories (DSpace/Dataverse/Zenodo/Figshare), productivity (M365/Google/Slack/Teams), integrity (Turnitin/iThenticate).

---

#### **M14 — Administration & Configuration Service**
- **Responsibility:** tenant lifecycle, org structure, policy configuration, taxonomies, templates, branding, licences, feature flags per tenant.

---

#### **M15 — Audit & Observability Service**
- **Responsibility:** tamper-evident audit log (append-only, hash-chained), SIEM export, access transparency reports, platform telemetry, SLO tracking.

---

#### **M16 — Billing & Entitlement Service**
- **Responsibility:** plans, seats, usage metering (storage, AI tokens, API calls), invoicing, entitlement checks, cost attribution per tenant.

### 8.3 Cross-Cutting Concerns

| Concern | Implementation Approach |
|---|---|
| Multi-tenancy | Tenant ID in every request context; row-level security in Postgres; per-tenant index and vector namespaces; per-tenant object-store prefixes and keys |
| Idempotency | All mutating APIs accept an idempotency key; all event consumers are idempotent |
| Eventing | Kafka topics per domain with schema registry; outbox pattern for transactional consistency |
| Caching | Redis for session, PDP decisions, hot metadata, search result fragments; explicit invalidation via events |
| Rate limiting | Per tenant, per user, per API key, per AI-cost budget |
| Feature flags | Per tenant / cohort / user; every AI feature independently killable |
| Localisation | Externalised strings; content-language detection in the pipeline |
| Testing | Contract tests at boundaries; golden-set evals for AI; synthetic tenants for load tests |

### 8.4 Module Dependency Map (compressed)

| Module | Depends On |
|---|---|
| M02 Artefact | M01, M15, M16 |
| M03 Entity/Graph | M01, M02, M15 |
| M04 Ingest | M01, M02, M03, M05, M06, M12 |
| M05 AI | M01, M02, M03, M06, M15, M16 |
| M06 Search | M01, M02, M03 |
| M07 Version | M02, M15 |
| M08 Collaboration | M01, M02, M12 |
| M09 Workflow | M01, M02, M03, M12 |
| M10 Compliance | M02, M03, M06, M07, M09, M15 |
| M11 Analytics | all (read-only via events) |
| M13 Integration | M01, M02, M04, M14 |

**Rule:** no cyclic runtime dependencies. Where a cycle appears logically, it is broken with events (asynchronous) rather than synchronous calls.

---

## 9. Dashboard Design

### 9.1 Design Doctrine

A dashboard in AcademicOS is **not a chart wall**. It is an *answer to the question "what deserves my attention right now?"*, followed by *the fastest possible path to acting on it*. Four rules:

1. **Attention before information.** Top of screen = what is at risk, due, or waiting on you. Charts live below the fold.
2. **Every card is actionable.** No card exists that cannot be clicked into a concrete next step.
3. **Every number is drillable.** Clicking any figure reveals its constituent artefacts and its definition.
4. **Role-adaptive, user-customisable.** Ship an opinionated default per role; allow rearrangement, hiding and adding; allow reset.

**Grid:** 12-column responsive; card sizes S (3col), M (4/6col), L (8col), XL (12col). Cards define their own compact/expanded states. Layout persists per user per role context.

### 9.2 Faculty / Assistant Professor Dashboard (default)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Good morning, Dr. Iyer          Tuesday, 4 Aug · Odd Semester, Week 3   ⌘K   │
├──────────────────────────────────────────────────────────────────────────────┤
│ ✦ YOUR AI BRIEFING                                                      [XL] │
│ "3 things need you today: the SERB progress report is due in 6 days and      │
│  2 deliverables lack evidence; Rahul's Chapter 3 has waited 9 days for your   │
│  feedback; and your CS-301 session in 90 minutes has no updated slides.       │
│  I've drafted the progress report from your project records — review?"        │
│              [Review draft]  [Open Chapter 3]  [Prepare CS-301]  [Dismiss]    │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ ⏱ TODAY                   [M] │ ⚠ NEEDS ATTENTION                        [M] │
│ 10:30 CS-301 Lecture 8        │ ● Grant report — 6 days      [Open]          │
│       Automata · Room B204    │ ● Ch.3 feedback — 9 days late [Open]         │
│       ▸ Slides ▸ Attendance   │ ● Ethics renewal — 21 days   [Open]          │
│ 12:30 Meeting: R. Menon       │ ● 14 items in Review Queue   [Triage]        │
│ 15:00 DC Meeting: A. Sharma   │ ● 2 approvals waiting        [Review]        │
├───────────────────────────────┼──────────────────────────────────────────────┤
│ ▤ RECENT & CONTINUE       [M] │ ◈ MY SPACES                              [M] │
│ Ch3_Menon_v7.docx  2h ago     │ CS-301 Automata      ●●●○○  Week 3/16        │
│ NanoCat_results.ipynb 1d      │ CS-540 ML            ●●○○○  Week 3/16        │
│ SERB_Q3_draft.docx  2d        │ NanoCat (Research)   ●●●●○  On track         │
│ Reviewer2_response  3d        │ 3 Scholars           ⚠1 at risk              │
├───────────────────────────────┴──────────────────────────────────────────────┤
│ 👥 SUPERVISION                                                           [L] │
│ Scholar        Stage            Last Contact  Next Milestone   Risk          │
│ R. Menon       Ch.3 writing     14 days       Synopsis Nov     ● Medium      │
│ A. Sharma      Data collection  3 days        DC Meeting today ● Low         │
│ P. Nair        Coursework       31 days       Comprehensive    ● High        │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ 📈 MY OUTPUT (12 mo)      [M] │ 🎯 APPRAISAL READINESS                   [M] │
│ Publications  ▁▂▃▅▃▆  7       │ Teaching     ████████░░  82%                 │
│ Citations     ▁▂▄▅▇█  143     │ Research     ██████░░░░  64%  3 gaps         │
│ Grants active           2      │ Service      █████████░  91%                │
│ Scholars                3      │ Overall      ███████░░░  76%   [View gaps]  │
└───────────────────────────────┴──────────────────────────────────────────────┘
```

**Widget library available to faculty:** AI Briefing · Today's Schedule · Needs Attention · Recent Artefacts · My Spaces · Supervision Board · Output Metrics · Appraisal Readiness · Storage & Quota · Reading Queue · Manuscript Pipeline · Grant Burn · Review Queue · Teaching Feedback Trend · Collaboration Network · Upcoming Deadlines · Quick Capture.

### 9.3 PhD Scholar Dashboard

Emphasis shifts from *breadth management* to *progress reassurance and momentum*.

| Zone | Cards |
|---|---|
| Hero | **Thesis Progress Ring** — chapters complete/in-draft/outlined, overall % against the milestone timeline, months remaining, and a "you are on/behind/ahead of plan" verdict with reasoning |
| Attention | Supervisor feedback awaiting your action · Overdue milestones · Data not backed up · Unfiled items |
| Work | Active chapter with word count and last edit · Today's experiments · Reading queue (3 priority papers) |
| Evidence | Publication pipeline (drafts → submitted → under review → accepted) · Conference deadlines matching your topic |
| Assurance | "Your work is safe": versions retained, last backup, provenance completeness score |
| Growth | Skills/coursework completion · Contribution ledger for CV |

### 9.4 Principal Investigator / Lab Head Dashboard

| Zone | Cards |
|---|---|
| Portfolio | Grants: sanctioned vs. utilised, burn-rate sparkline, months of runway, upcoming deliverables |
| People | Team board: each member's current focus, last activity, blockers, and risk flag |
| Output | Manuscript pipeline by stage with age-in-stage (stale = red) |
| Compliance | DMP posture, ethics approvals expiring, open-access compliance, data-deposit status |
| Science | Experiment throughput, reproducibility-package completeness, dataset growth |
| Risk | Attrition signals, milestone slippage forecast, budget overrun projection |

### 9.5 Head of Department / Dean Dashboard

| Zone | Cards |
|---|---|
| Health | Departmental scorecard: research output, funding, teaching quality, student outcomes — each vs. target and vs. last year |
| Compliance | Accreditation readiness heatmap by criterion; count of open gaps by owner |
| People | Workload distribution (equity view — teaching vs. research vs. service hours per faculty), appraisal cycle status |
| Pipeline | Proposals in flight, expected funding, publications by quartile |
| Risk | Faculty with no output in 12 months (private, sensitive framing), scholars at risk, unstaffed courses next term |
| Actions | Approvals queue, evidence verification queue |

**Sensitivity rule:** individual-performance data visible to a manager is (a) always sourced from verifiable artefacts, (b) never AI-inferred judgement about a person, and (c) logged when accessed. The system informs individuals which of their aggregate metrics are visible to whom.

### 9.6 Institution Administrator / IQAC Dashboard

| Zone | Cards |
|---|---|
| Institutional | Total output, funding, collaborations, rankings-metric readiness (NIRF/THE/QS input fields with completeness) |
| Accreditation | Multi-framework readiness, submission calendar, evidence verification progress |
| Adoption | Platform usage by department, migration completeness, training gaps |
| Governance | Policy violations, external-sharing exceptions, retention compliance, legal holds |
| Storage/Cost | Consumption by unit, AI usage and cost by unit, forecast |
| Integrity | Audit anomalies, access-review status, offboarding backlog |

### 9.7 Common Dashboard Requirements

| ID | Requirement |
|---|---|
| FR-DSH-001 | Role-default layouts with per-user customisation (drag, resize, hide, add, reset) |
| FR-DSH-002 | All cards load progressively; skeletons never block the shell; no card may block another |
| FR-DSH-003 | Data freshness indicator on every card; manual refresh available |
| FR-DSH-004 | Every metric drillable to source artefacts and to its Metric Registry definition |
| FR-DSH-005 | Time-range control global to the dashboard, with per-card override |
| FR-DSH-006 | Empty states are instructive, not blank ("No scholars yet — add one, or import from SIS") |
| FR-DSH-007 | Export any card as image/CSV; export dashboard as a PDF report |
| FR-DSH-008 | Dashboards fully keyboard-navigable and screen-reader labelled with data tables behind every chart |
| FR-DSH-009 | Mobile dashboards are a re-prioritised single-column stack, not a shrunken desktop grid |
| FR-DSH-010 | Widget-level permission checks — a card the user cannot see never renders and never leaks its existence in layout |

---

## 10. Database Planning

### 10.1 Polyglot Persistence Strategy

No single store serves all access patterns. Each store is chosen for a specific job, with clear ownership:

| Store | Technology | Purpose | Why |
|---|---|---|---|
| **Primary OLTP** | PostgreSQL 16+ (Citus/partitioned) | Entities, artefact metadata, users, permissions, workflows | ACID, relational integrity, RLS, JSONB flexibility, mature ops |
| **Graph** | Neo4j (or Apache AGE on Postgres for smaller tenants) | Relationships, lineage, traversals, recommendations | Multi-hop traversal performance the relational model cannot match |
| **Search** | OpenSearch / Elasticsearch | Lexical full-text, facets, aggregations, highlighting | Best-in-class BM25, faceting, and operational tooling |
| **Vector** | Qdrant / Milvus (pgvector for small tenants) | Semantic retrieval over chunk embeddings | Billion-scale ANN with metadata filtering and namespacing |
| **Object** | S3-compatible (AWS S3 / Azure Blob / MinIO on-prem) | Blobs, versions, previews, exports | Durability, tiering, cost |
| **Analytics** | ClickHouse | Events, metrics, dashboards, reports | Columnar aggregation at scale |
| **Cache/Queue** | Redis | Sessions, PDP cache, hot metadata, rate limits, ephemeral locks | Latency |
| **Event Log** | Kafka | Domain events, CDC, pipeline coordination | Durable, replayable backbone |
| **Workflow State** | Temporal (Postgres-backed) | Long-running ingest and approval workflows | Durable execution, retries, visibility |
| **Audit** | Append-only Postgres partition + object-store WORM archive | Tamper-evident audit trail | Compliance defensibility |

### 10.2 Multi-Tenancy Model

**Hybrid, tiered by customer size:**

| Tier | Model | Applies To |
|---|---|---|
| Shared pool | Shared Postgres cluster, `tenant_id` on every row, RLS enforced, shared indices with tenant-scoped shards | Individuals, small teams (< 500 users) |
| Dedicated schema | Own schema within a shared cluster; own vector namespace; own search index | Departments, mid institutions (500–5,000) |
| Dedicated cluster | Own database cluster, own object-store bucket, own vector cluster, optionally own region | Large universities (> 5,000), sovereignty or contractual requirement |

**Non-negotiable isolation controls (all tiers):** `tenant_id` is part of every primary key or a mandatory partition key; Postgres Row-Level Security is enabled and enforced (application role never has BYPASSRLS); object keys are prefixed `tenant/{tenant_id}/…` with per-tenant KMS keys; vector collections are namespaced per tenant; search indices are per-tenant (or per-tenant routing key with alias-level filtering); every query passes through a data-access layer that injects tenant context from the authenticated session, never from client input.

### 10.3 Core Logical Model (Conceptual ER)

```
        ┌──────────┐        ┌───────────┐        ┌──────────┐
        │  TENANT  │───1:N──│   USER    │──M:N───│   ROLE   │
        └────┬─────┘        └─────┬─────┘        └──────────┘
             │                    │
             │ 1:N                │ N:M (membership)
             ▼                    ▼
        ┌──────────┐        ┌───────────┐
        │   ORG    │───────▶│   SPACE   │
        │  UNIT    │  1:N   └─────┬─────┘
        └──────────┘              │ 1:N
                                  ▼
   ┌──────────────┐   M:N   ┌───────────┐   1:N   ┌───────────┐
   │    ENTITY    │◀───────▶│  ARTEFACT │────────▶│  VERSION  │
   │ (course,     │  (via   └─────┬─────┘         └───────────┘
   │  project,    │  RELATION)    │ 1:N
   │  grant,      │               ▼
   │  scholar,    │         ┌───────────┐         ┌───────────┐
   │  publication,│         │   CHUNK   │────────▶│ EMBEDDING │
   │  dataset...) │         └───────────┘         └───────────┘
   └──────┬───────┘
          │ M:N (typed, attributed)
          ▼
   ┌──────────────┐        ┌──────────────┐       ┌──────────────┐
   │ RELATIONSHIP │        │  METADATA    │       │  PERMISSION  │
   └──────────────┘        │  (layered)   │       │    GRANT     │
                           └──────────────┘       └──────────────┘

   Supporting: COMMENT · TASK · WORKFLOW_INSTANCE · NOTIFICATION ·
               AUDIT_EVENT · AI_INTERACTION · EVIDENCE_MAPPING ·
               RETENTION_POLICY · SHARE_LINK · ACTIVITY
```

### 10.4 Key Table Specifications

> Field lists are given as design specifications, not implementation DDL.

**`tenant`** — tenant_id (UUID, PK) · name · slug · type (individual|department|institution) · tier · region · residency_policy · kms_key_ref · plan_id · storage_quota_bytes · ai_budget_monthly · branding (JSONB) · locale_defaults · status · created_at · deleted_at
*Indexes:* slug (unique), status, region.

**`user`** — user_id (UUID, PK) · primary_email (citext, unique) · display_name · given_name · family_name · orcid (unique, nullable) · scopus_id · google_scholar_id · avatar_ref · locale · timezone · status · mfa_enabled · last_active_at · created_at
*Notes:* identity is global; membership is per-tenant, so one human = one account across institutions.

**`tenant_membership`** — membership_id · tenant_id (FK) · user_id (FK) · employee_id · designation · org_unit_id · joined_at · left_at · status · is_primary
*Indexes:* (tenant_id, user_id) unique where active; (tenant_id, org_unit_id).

**`org_unit`** — org_unit_id · tenant_id · parent_id (self-FK) · type (university|faculty|department|centre|lab) · name · code · head_user_id · effective_from · effective_to
*Notes:* effective-dated hierarchy so historical reports remain correct after reorganisations.

**`space`** — space_id · tenant_id · type (personal|course|research|supervision|committee|external|admin) · name · slug · owner_user_id · org_unit_id · primary_entity_id · visibility (private|unit|tenant|external) · settings (JSONB) · archived_at · created_at
*Indexes:* (tenant_id, type), (tenant_id, owner_user_id), slug.

**`artefact`** — artefact_id (UUID v7, PK) · tenant_id · space_id · current_version_id · title · canonical_name · artefact_type (see §16) · mime_type · size_bytes · content_hash · storage_tier · language · sensitivity (public|internal|confidential|restricted) · status (draft|active|superseded|archived|deleted) · created_by · created_at · updated_at · deleted_at · purge_after · legal_hold (bool) · ai_confidence · classification_source (human|ai|rule|import) · checksum_verified_at
*Partitioning:* by tenant_id hash, then by created_at range (monthly) for large tenants.
*Indexes:* (tenant_id, space_id, updated_at DESC) · (tenant_id, artefact_type) · content_hash · GIN on metadata JSONB · partial index on status='active'.

**`artefact_version`** — version_id · artefact_id · version_number (int) · semantic_label (e.g., v2.1-draft) · blob_ref · size_bytes · content_hash · change_summary · change_type (major|minor|patch|metadata) · created_by · created_at · parent_version_id · branch_name · is_current · retention_class · signature (optional)
*Notes:* immutable rows; never updated after write except `is_current` flag flip.

**`entity`** — entity_id · tenant_id · entity_type (course|course_offering|project|grant|publication|dataset|scholar|committee|venue|patent|equipment) · canonical_name · code · status · lifecycle_stage · start_date · end_date · owner_user_id · org_unit_id · attributes (JSONB, type-specific and schema-validated) · external_ids (JSONB: doi, orcid, award_number, isbn…) · created_at · updated_at
*Indexes:* (tenant_id, entity_type, status) · GIN on attributes · GIN on external_ids · trigram on canonical_name.

**`relationship`** — relationship_id · tenant_id · from_type · from_id · to_type · to_id · rel_type (see vocabulary below) · confidence (0–1) · source (human|ai|rule|import|derived) · created_by · created_at · valid_from · valid_to · attributes (JSONB) · verified_by · verified_at
*Indexes:* (tenant_id, from_id, rel_type) · (tenant_id, to_id, rel_type) · unique on (from_id, to_id, rel_type) where valid_to is null.
*Mirrored into the graph store* via CDC for traversal workloads.

**Relationship vocabulary (core, extensible):** `belongs_to` · `authored_by` · `contributed_to` (with CRediT role) · `supervises` · `funded_by` · `derived_from` · `cites` · `supersedes` · `evidences` (artefact → criterion) · `teaches` · `enrolled_in` · `produced` · `used_dataset` · `implements` · `reviews` · `approves` · `member_of` · `collaborates_with` · `mentions`.

**`metadata`** (layered, see §16) — metadata_id · tenant_id · subject_type · subject_id · layer (system|technical|descriptive|academic|administrative|provenance|custom) · key · value (JSONB) · datatype · source (human|ai|extracted|imported|computed) · confidence · vocabulary_ref · created_by · created_at · superseded_by
*Notes:* metadata is append-only and versioned; the current value is a view over the latest non-superseded row. This gives full metadata provenance ("who said this paper was published in 2024, and when?").

**`chunk`** — chunk_id · tenant_id · artefact_id · version_id · sequence · text · token_count · char_start · char_end · page_no · timestamp_start/end (media) · section_path · heading · chunk_type (prose|table|code|caption|formula|transcript) · embedding_model · embedding_version · created_at
*Vector store holds:* chunk_id, tenant_id (namespace), embedding vector, plus filterable metadata (artefact_type, entity_ids, sensitivity, date, language, space_id).

**`permission_grant`** — grant_id · tenant_id · subject_type (user|group|role|link|service) · subject_id · resource_type · resource_id · capability_set · effect (allow|deny) · inherited (bool) · source_grant_id · conditions (JSONB — ABAC predicates) · granted_by · granted_at · expires_at · revoked_at
*Indexes:* (tenant_id, resource_id) · (tenant_id, subject_id) · partial on active grants.

**`audit_event`** — event_id (ULID) · tenant_id · actor_user_id · actor_type (user|service|ai_agent|system) · action · resource_type · resource_id · outcome (success|denied|error) · reason · ip · user_agent · session_id · request_id · before_state_hash · after_state_hash · prev_event_hash · event_hash · occurred_at · metadata (JSONB)
*Notes:* hash-chained per tenant per day; daily root hash written to WORM storage and optionally notarised.

**`ai_interaction`** — interaction_id · tenant_id · user_id · feature · thread_id · scope · prompt_template_id · prompt_version · model_id · input_token_count · output_token_count · retrieved_chunk_ids (array) · retrieval_scores · output_text_ref · citations (JSONB) · guardrail_flags · latency_ms · cost_usd · user_feedback · accepted (bool) · created_at
*Notes:* the backbone of evaluation, cost control, and auditability of AI influence on the record.

**`evidence_mapping`** — mapping_id · tenant_id · framework_id · criterion_id · artefact_id · entity_id · mapped_by · mapping_source (human|ai) · confidence · verification_status · verified_by · verified_at · submission_id · notes

**Other core tables:** `comment`, `task`, `workflow_definition`, `workflow_instance`, `notification`, `share_link`, `retention_policy`, `legal_hold`, `saved_search`, `template`, `taxonomy_term`, `entity_resolution_cluster`, `usage_meter`, `connector_config`, `sync_state`.

### 10.5 Partitioning, Sharding & Growth

| Concern | Strategy |
|---|---|
| Horizontal scale | Shard Postgres by `tenant_id` (Citus distributed tables); co-locate all tenant data on one shard to keep joins local |
| Large-tenant hot tables | Sub-partition `artefact`, `audit_event`, `ai_interaction`, `activity` by time (monthly) |
| Search index | One index per tenant for large tenants; shared index with routing for small tenants; rollover indices by year for time-series-heavy content |
| Vector index | Collection per tenant; HNSW with per-collection tuning; quantisation (scalar/product) for cold tenants |
| Graph | Per-tenant subgraph labelling; large tenants get dedicated graph databases |
| Analytics | ClickHouse partitioned by (tenant_id, month), with pre-aggregated materialised views for dashboard queries |
| Archival | Rows older than the active window move to columnar archive tables; artefact blobs tier down (§13) |

### 10.6 Data Integrity, Consistency & Migration

- **Consistency model:** strong consistency for permissions, versions and financial/compliance records; read-your-writes for user-facing metadata; eventual (target < 60 s) for search, vector and analytics projections, with visible "indexing" status in the UI.
- **Transactional outbox** guarantees that an event is published if and only if the database transaction committed.
- **Referential integrity** enforced in the database for core relations; soft references (graph, search) reconciled by a nightly consistency job that reports drift as an SLO.
- **Schema migrations:** expand → migrate → contract; every migration must be backward-compatible for at least one release; no blocking DDL on tables > 10M rows (use concurrent index builds and batched backfills); all migrations tested against a production-shaped synthetic dataset.
- **Backups:** continuous WAL archiving (PITR to any second within 35 days), daily full snapshots, cross-region replication, quarterly verified restores, per-tenant restore capability (a single university must be restorable without touching others).
- **Data retention:** configurable per artefact class; soft delete → 30-day trash → 90-day recoverable archive → purge, with legal holds overriding all deletion.

### 10.7 Estimated Volumetrics (steady state, R3)

| Entity | Rows | Notes |
|---|---|---|
| Artefacts | 50 B | Across 10k tenants |
| Versions | 200 B | Avg 4 versions per artefact |
| Chunks | 500 B | Avg 10 chunks per artefact version indexed |
| Embeddings | 100 B active | Cold chunks' vectors offloaded/compressed |
| Relationships | 300 B | Avg 6 per artefact |
| Metadata rows | 750 B | Avg 15 fields per artefact, versioned |
| Audit events | 2 T (rolling 7 yr) | Tiered to WORM archive after 90 days hot |
| Blob storage | 500 PB | Tiered per §13 |

---

## 11. AI Features

### 11.1 AI Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI EXPERIENCE SURFACES                           │
│  Assistant Dock · Inline Actions · Review Queue · Proactive Cards ·     │
│  Command Palette (?) · Agent Console · Draft Composer · Smart Filing    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                    AI ORCHESTRATION LAYER (M05)                         │
│  ┌───────────┐ ┌────────────┐ ┌───────────┐ ┌────────────┐ ┌─────────┐ │
│  │  Intent   │ │  Retrieval │ │  Prompt   │ │   Model    │ │ Guard-  │ │
│  │  Router   │→│   Engine   │→│ Assembly  │→│  Router    │→│ rails   │ │
│  └───────────┘ └────────────┘ └───────────┘ └────────────┘ └─────────┘ │
│  ┌───────────┐ ┌────────────┐ ┌───────────┐ ┌────────────┐ ┌─────────┐ │
│  │  Agent    │ │   Tool     │ │ Citation  │ │   Cost     │ │  Eval   │ │
│  │  Runtime  │ │  Registry  │ │ Verifier  │ │ Accountant │ │ Harness │ │
│  └───────────┘ └────────────┘ └───────────┘ └────────────┘ └─────────┘ │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                       KNOWLEDGE SUBSTRATE                               │
│  Vector Index · Lexical Index · Knowledge Graph · Metadata Store ·      │
│  Permission Filter (applied BEFORE retrieval, not after)                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                        MODEL LAYER (pluggable)                          │
│  Frontier LLM (complex reasoning) · Mid LLM (routine generation) ·      │
│  Small/Local LLM (classification, extraction) · Embedding models ·      │
│  Re-ranker (cross-encoder) · OCR/ASR · Domain-tuned classifiers         │
│  Deployment: managed API (with DPA + zero-retention) or VPC/on-prem     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 The RAG Pipeline (specification)

**Indexing path**
1. **Structure-aware chunking** — respect document structure (sections, slides, cells, paragraphs, speaker turns). Target 300–800 tokens with 15% overlap; tables and code kept intact; captions bound to their figures.
2. **Contextual enrichment** — each chunk is stored with a generated context header (document title, section path, entity context, date) prepended at embedding time. This single technique materially improves retrieval on academic corpora where chunks are otherwise context-free.
3. **Multi-representation indexing** — for each artefact store: (a) chunk embeddings, (b) a document-level summary embedding, (c) hypothetical-question embeddings for key sections, (d) lexical tokens, (e) graph node with typed edges.
4. **Metadata attachment** — every vector carries filterable metadata (tenant, space, entity IDs, type, date, sensitivity, language, author) so filtering happens inside ANN search, not after.

**Query path**
1. **Query understanding** — classify intent (lookup / synthesis / action / navigation / analytical), extract entities and temporal expressions ("last spring" → semester resolution), expand acronyms via the tenant vocabulary, detect scope.
2. **Permission pre-filter** — compute the user's accessible partition *before* retrieval. Non-negotiable.
3. **Hybrid retrieval** — parallel BM25 (top 50), dense vector (top 50), and graph expansion (entities within 2 hops of matched nodes).
4. **Fusion** — Reciprocal Rank Fusion, then cross-encoder re-ranking to top 8–12.
5. **Context assembly** — deduplicate, order by relevance and chronology, enforce token budget, always include artefact identity so citations are exact.
6. **Generation** — task-specific prompt template (versioned), with strict instruction to cite chunk IDs and to say "I don't know" when the corpus lacks the answer.
7. **Citation verification** — post-generation check that every claim-bearing sentence maps to a retrieved chunk; unsupported sentences are flagged or removed before display.
8. **Response shaping** — answer + inline citations + source cards + confidence + suggested follow-ups + actions.

**Quality controls:** golden evaluation set of ≥ 2,000 real academic queries per discipline family; nightly regression runs; no prompt or model change ships without passing the gate in NFR-AIQ-006.

### 11.3 AI Feature Catalogue

#### Tier 1 — Organisational Intelligence (the core value)

| Feature | Description | Human Control |
|---|---|---|
| **Auto-Classification** | Determine artefact type, entity linkage, subject, semester, sensitivity at ingest | Confidence-gated; review queue below threshold |
| **Metadata Extraction** | Title, authors, abstract, keywords, dates, funding, references, DOI, methodology | Every field editable; corrections retrain |
| **Auto-Linking** | Propose typed relationships to existing entities | Proposals shown as pending edges until accepted |
| **Smart Renaming** | Generate convention-compliant names (§19) | Preview diff; bulk accept/reject; original name retained forever |
| **Duplicate Resolution** | Detect exact and near-duplicates across the corpus | User chooses merge / supersede / keep both |
| **Auto-Foldering** | Materialise the projection structure | Structure is a view; nothing is physically moved destructively |
| **Orphan Detection** | Find weakly connected artefacts and propose homes | Batch triage UI |
| **Migration Planning** | Analyse an imported legacy drive and propose the whole target structure | The "Reveal" screen (§6.1) |

#### Tier 2 — Comprehension Intelligence

| Feature | Description |
|---|---|
| **Ask Your Corpus** | Grounded conversational Q&A across any authorised scope, with citations |
| **Document Summarisation** | Multi-length summaries (one-line, abstract, executive, detailed) with key-point extraction |
| **Multi-Document Synthesis** | "Summarise everything I know about catalytic degradation" across 60 sources |
| **Literature Matrix** | Auto-built comparison table (method, sample, findings, limitations, gap) |
| **Gap Analysis** | Identify what the corpus does *not* cover relative to a research question |
| **Contradiction Detection** | Surface conflicting findings or inconsistent numbers across documents |
| **Semantic Diff** | "What changed in meaning between v6 and v7?" rather than character diffs |
| **Media Understanding** | Lecture video → chapters, transcript, slide alignment, searchable topics |
| **Table & Figure Q&A** | Query numeric content inside tables and charts |
| **Cross-Lingual** | Ask in English, retrieve from Hindi/German/Chinese sources, answer in the asked language |

#### Tier 3 — Generative Assistance (always labelled, always draft)

| Feature | Notes |
|---|---|
| Lesson plans, session outlines, slide skeletons | Grounded in the professor's own prior material and the syllabus |
| Question papers & rubrics | CO-mapped, Bloom-balanced, difficulty-distributed, reuse-collision-checked |
| Grant proposal sections | Grounded in the PI's prior work; funder-template aware; never fabricates results |
| Progress & utilisation reports | Assembled from actual project records with evidence links |
| Literature review drafts | Every sentence citation-backed to the user's own reading library |
| Reviewer-response letters | Point-by-point scaffold cross-checked against actual manuscript edits |
| Meeting minutes & action items | From recorded or uploaded meetings |
| Annual appraisal narratives | Evidence-linked; gaps flagged rather than filled with invention |
| Accreditation criterion narratives | Assembled from mapped evidence; never asserts unevidenced claims |
| Recommendation-letter drafts | From the documented supervision record; requires heavy human editing by design |

**Integrity guardrails on generation:** the system refuses to fabricate results, data, citations or student assessments. Any generated artefact carries `ai_generated: true`, the model and prompt version, and the human editor's subsequent contribution ratio. Institutions can disable specified generative features by policy.

#### Tier 4 — Agentic Workflows (R2+)

Agents execute multi-step tasks with a **visible plan, step-level approval, and a complete action log**. Every agent action is a normal, audited, reversible system operation — agents have no privileged path.

| Agent | Trigger | Plan (illustrative) |
|---|---|---|
| **Semester Setup Agent** | "Set up CS-301 for Odd 2026" | Clone prior offering → refresh dates → flag outdated content → rebuild question bank pool → map COs → draft session plan → report changes for approval |
| **Compliance Agent** | Framework selected | Scan corpus → map to criteria → score readiness → list gaps → assign owners → schedule reminders |
| **Grant Report Agent** | 30 days before due | Gather deliverable evidence → compute utilisation → draft narrative → flag missing items → route for PI approval |
| **Literature Monitor** | Weekly | Query external sources for new work in your areas → filter by relevance to your active projects → summarise → add to reading queue |
| **Thesis Consistency Agent** | On demand | Check terminology consistency, figure/table numbering, citation completeness, cross-references, undefined acronyms across chapters |
| **Onboarding Agent** | New lab member | Assemble reading list, protocols, access requests, orientation checklist from lab corpus |
| **Data Hygiene Agent** | Continuous | Find unlinked datasets, missing DMP coverage, unbacked-up work, expiring approvals |

**Agent safety rules:** (1) no destructive action without explicit human approval; (2) hard budget and step ceilings; (3) all actions attributed to `actor_type = ai_agent` with the initiating human recorded; (4) a global kill switch per agent per tenant; (5) agents inherit exactly the initiating user's permissions — never more.

#### Tier 5 — Proactive & Predictive Intelligence

- **Morning Brief** — a natural-language digest of what matters today, generated from deadlines, queues, risks and calendar.
- **Deadline risk scoring** — probability of missing a milestone based on artefact activity, historical velocity and remaining scope.
- **Scholar attrition risk** — early warning from meeting cadence, output velocity and feedback latency, framed as *supportive intervention*, never as a punitive score, and visible to the scholar too.
- **Evidence-gap alerts** — "your appraisal claims teaching innovation; no supporting artefact is linked".
- **Reuse suggestions** — "you already made this figure in 2024; reuse or supersede?"
- **Collaboration suggestions** — internal colleagues working on adjacent problems (opt-in, privacy-respecting).

### 11.4 Model Strategy

| Task Class | Model Tier | Rationale |
|---|---|---|
| Classification, tagging, routing, extraction of simple fields | Small model, fine-tuned, self-hosted | Volume is enormous; latency and cost dominate |
| Embeddings | Domain-adapted open embedding model, self-hosted | Cost, data control, re-embedding freedom |
| Re-ranking | Cross-encoder, self-hosted | Latency-sensitive, high volume |
| Summarisation, routine drafting | Mid-tier commercial or open-weight | Quality/cost balance |
| Complex reasoning, synthesis, agent planning | Frontier model via API | Only where quality demands it |
| OCR / handwriting / ASR | Specialised services | Best-of-breed |

**Model portability is mandatory.** All model access is behind an internal abstraction; swapping a provider must be a configuration change plus an eval run, never a code rewrite. Every tenant can be pinned to a specific model set for reproducibility and compliance.

**Cost governance:** per-tenant and per-user AI budgets; semantic caching of repeated queries; aggressive small-model-first routing with escalation only on low confidence; batch processing for non-interactive work; token-budget enforcement at prompt assembly.

### 11.5 Trust, Safety & Transparency Requirements

| ID | Requirement |
|---|---|
| FR-AIT-001 | Every AI output displays: source citations, confidence, model used, and generation timestamp |
| FR-AIT-002 | "Show your work" panel: exact chunks retrieved, their scores, and the reasoning summary |
| FR-AIT-003 | Refusal behaviour: when the corpus cannot answer, say so explicitly and offer to search externally — never fabricate |
| FR-AIT-004 | All AI-suggested mutations are previewable and reversible for ≥ 30 days |
| FR-AIT-005 | Prompt-injection defence: retrieved content is treated as untrusted data; instruction-bearing content in documents cannot alter system behaviour; tool calls are schema-validated and permission-checked |
| FR-AIT-006 | PII/sensitive-data detection with configurable redaction before external model calls |
| FR-AIT-007 | Tenant data is never used to train foundation models without explicit written opt-in; zero-retention agreements with all model providers |
| FR-AIT-008 | Full AI interaction history per user, exportable and deletable |
| FR-AIT-009 | Bias and quality monitoring across disciplines, languages and seniority cohorts, published internally each quarter |
| FR-AIT-010 | Human-in-the-loop mandatory for: student assessment decisions, personnel judgements, compliance submissions, and any irreversible action |

---

## 12. Security

### 12.1 Security Architecture Principles

1. **Zero trust** — no implicit trust between services, networks or users; every request authenticated and authorised.
2. **Defence in depth** — edge, network, application, data and monitoring layers each independently sufficient to detect or stop common attacks.
3. **Least privilege everywhere** — users, services, agents and operators.
4. **Assume breach** — design for containment, detection and rapid recovery; blast radius is bounded by tenant.
5. **Secure by default** — the safest configuration is the default; insecure options require deliberate, logged action.
6. **Verifiable** — security claims are backed by logs, tests, attestations and independent audit.

### 12.2 Threat Model (STRIDE, abridged)

| Threat | Vector | Mitigations |
|---|---|---|
| **Spoofing** | Credential stuffing, phishing, session hijack, SSO assertion forgery | Passkeys/WebAuthn, MFA enforcement, IdP signature validation with clock skew limits, device binding, impossible-travel detection, short-lived tokens with rotation, session pinning |
| **Tampering** | Artefact or metadata alteration, audit log manipulation | Content hashing, immutable versions, hash-chained append-only audit log with WORM archive, signed critical records, DB-level constraints |
| **Repudiation** | "I never approved that" / authorship disputes | Comprehensive attributed audit trail, dual acknowledgement on supervision and approval records, optional cryptographic signing, notarised daily audit roots |
| **Information Disclosure** | **Cross-tenant leakage (the existential risk)**, over-broad sharing, AI answering from unauthorised content, search leakage, metadata inference | Tenant ID in every key and query, RLS with no bypass role, per-tenant KMS keys, per-tenant vector namespaces, permission pre-filter before retrieval, automated cross-tenant isolation tests on every deploy, existence-hiding for confidential resources |
| **Denial of Service** | Upload floods, expensive queries, AI cost exhaustion, ingest bombs | Per-tenant rate limits and quotas, query cost analysis with rejection, AI budget caps, queue fairness, WAF, CDN absorption, autoscaling with circuit breakers |
| **Elevation of Privilege** | Broken object-level authorisation (IDOR), role confusion, agent over-permission, injection | Centralised PDP for every access, deny-by-default, capability checks at the object level, agents bound to initiating user's permissions, parameterised queries, output encoding, mandatory code review on auth paths |

**AI-specific threats:** indirect prompt injection via uploaded documents (mitigated by treating retrieved content as data, structural prompt separation, tool-call validation, and output scanning); training-data leakage (mitigated by zero-retention contracts and no-train clauses); model denial of wallet (mitigated by budgets); embedding inversion (mitigated by encrypted vector storage and per-tenant namespaces); membership inference via search (mitigated by permission pre-filtering and existence hiding).

### 12.3 Authentication & Session Security

| Control | Specification |
|---|---|
| Methods | Passkeys/WebAuthn (preferred), SSO via SAML 2.0 / OIDC, federated academic identity (Shibboleth, eduGAIN), email+password (with breach-corpus checking) |
| MFA | TOTP, WebAuthn, push; tenant-enforceable; mandatory for all privileged roles |
| Passwords | Argon2id hashing, minimum entropy policy, no forced rotation, breach detection |
| Sessions | Short-lived access tokens (15 min), rotating refresh tokens with reuse detection, device inventory with remote revoke, absolute session lifetime, idle timeout policy per tenant |
| Step-up | Re-authentication required for: permission changes, external sharing of restricted content, bulk export, purge, impersonation, billing |
| Service auth | mTLS + short-lived workload identity; no static secrets in code or config |

### 12.4 Authorisation Enforcement

- Single **Policy Decision Point**; every service embeds a **Policy Enforcement Point**. There is no code path to data that bypasses the PDP.
- Object-level checks on every artefact, version, chunk and metadata field.
- **Search and AI are first-class enforcement surfaces**, not afterthoughts: indices are permission-partitioned and results are re-verified at render.
- Automated **authorisation regression suite** runs on every deploy: a matrix of ~4,000 (role × resource × action) assertions plus explicit cross-tenant negative tests. A single failure blocks release.

### 12.5 Data Protection

| Layer | Control |
|---|---|
| In transit | TLS 1.3 everywhere, HSTS preload, certificate pinning on mobile, mTLS internally |
| At rest | AES-256-GCM; envelope encryption; per-tenant data-encryption keys wrapped by tenant KMS keys; BYOK for enterprise, HYOK on request (R3) |
| In use | Field-level encryption for the most sensitive attributes; memory hygiene on secrets; confidential computing evaluated for on-prem high-sensitivity tenants |
| Key management | Managed HSM-backed KMS, annual rotation, split-knowledge for master keys, documented crypto-shredding for tenant deletion |
| Backups | Encrypted with separate keys; immutable/object-lock; isolated credentials; restore testing quarterly |
| Deletion | Soft delete → trash → archive → cryptographic erasure; certificate of deletion issued to the tenant |

### 12.6 Application Security Programme

- Secure SDLC: threat modelling for every new module; security review gate on auth, crypto, ingest, and AI code paths.
- Automated: SAST, DAST, dependency scanning, container scanning, IaC scanning, secret scanning — all blocking in CI.
- Manual: annual third-party penetration test (application + infrastructure + AI red-teaming), quarterly internal red team.
- Bug bounty programme with published safe-harbour policy.
- SBOM published per release; artefacts signed; provenance attested (SLSA level 3 target).
- Input validation on all boundaries; strict Content Security Policy; SSRF protections on all connector fetches; file-type validation and sandboxed preview rendering (untrusted documents never render in a privileged context).

### 12.7 Operational Security

| Control | Specification |
|---|---|
| Vendor access to tenant data | **Default: none.** Break-glass only, requiring documented reason, dual approval, tenant notification, time-boxed session, full session recording |
| Access transparency | Tenants receive a log of every vendor access to their data |
| Admin actions | All privileged operations logged, alerted and reviewed |
| Network | Private subnets, no public database endpoints, egress allow-listing, WAF + DDoS at edge |
| Monitoring | SIEM with correlation rules for: mass download, unusual export, permission escalation, off-hours admin access, cross-tenant query anomalies, AI cost spikes |
| Incident response | Documented IR plan, 24×7 on-call, severity taxonomy, ≤ 72 h regulatory notification, post-incident reports published to affected tenants |
| Business continuity | Multi-AZ by default, multi-region for enterprise, annual DR exercise with published RTO/RPO evidence |

### 12.8 Compliance & Privacy

| Framework | Position |
|---|---|
| ISO/IEC 27001 & 27701 | Certified (target: month 18) |
| SOC 2 Type II | Annual report (target: month 15) |
| GDPR | DPA, SCCs, EU data residency option, DPO appointed, DPIA templates provided to tenants |
| India DPDP Act 2023 | Consent management, notice, data-principal rights workflow, India residency option, significant-data-fiduciary readiness |
| FERPA | Student-record handling controls, directory-information configuration, disclosure logging |
| HIPAA | Available for clinical-research tenants via BAA on qualifying deployments |
| EU AI Act | Transparency obligations for limited-risk AI; documented model inventory and risk classification |
| Accessibility | WCAG 2.2 AA, VPAT per release |
| Sector | Alignment with national research-data policies and funder mandates (FAIR principles) |

**Privacy by design:** data minimisation at collection; purpose limitation enforced in code (analytics cannot read content); user-level privacy dashboard showing what is stored, who accessed it, and what AI did with it; granular consent for optional processing; anonymisation for benchmarking with k-anonymity thresholds.

---

## 13. Storage Strategy

### 13.1 Storage Tiers

| Tier | Media | Access Latency | Content | Cost Index | Transition Rule |
|---|---|---|---|---|---|
| **T0 — Edge Cache** | CDN | < 50 ms | Previews, thumbnails, published static assets | High | Auto, TTL-based |
| **T1 — Hot** | SSD-backed object storage | < 200 ms | Active artefacts, current versions, items touched in 90 days | 1.0× | Default on ingest |
| **T2 — Warm** | Standard object storage (infrequent access) | < 1 s | Untouched 90–365 days; superseded versions | 0.55× | Automatic, policy-driven |
| **T3 — Cold** | Archive-class storage | Minutes | Untouched > 365 days; completed projects; historical versions | 0.20× | Automatic, with user-visible label |
| **T4 — Deep Archive** | Deep archive / tape-class | Hours (12 h retrieval) | Legal-hold and long-retention records, > 3 years untouched | 0.04× | Policy-driven, admin-approved |
| **T5 — Preservation** | External repository (Zenodo/Dataverse/institutional) | External | DOI-minted published datasets and outputs | n/a | Explicit deposit action |

**Rules:** tiering is fully automatic but always transparent — the UI shows the tier and the expected retrieval time before a user requests a cold artefact; metadata, previews, thumbnails, transcripts and embeddings **never** leave T1, so *search always works even when the bytes are cold*. This is the key design decision: the corpus remains fully searchable and AI-answerable at 20% of the storage cost.

### 13.2 Object Layout & Content Addressing

```
s3://acos-{region}-{tier}/
  tenant={tenant_id}/
    blob/{hash[0:2]}/{hash[2:4]}/{sha256}          ← immutable content-addressed blob
    derived/{artefact_id}/preview/{version}.pdf
    derived/{artefact_id}/thumb/{size}.webp
    derived/{artefact_id}/text/{version}.txt
    derived/{artefact_id}/transcript/{version}.vtt
    export/{job_id}/...
    backup/{date}/...
```

- **Content-addressed blobs** give free deduplication and integrity verification. Dedup scope is *within a tenant's key domain* only (cross-tenant dedup is deliberately rejected — it creates a side channel revealing that another tenant holds an identical file).
- **Derived artefacts are reproducible**, so they may be evicted and regenerated; only originals are irreplaceable and get maximum durability guarantees.
- **Immutability:** blobs are write-once. "Editing" always produces a new blob and a new version row.

### 13.3 Storage Requirements

| ID | Requirement |
|---|---|
| FR-STO-001 | Durability 11 nines via erasure coding and cross-AZ replication; cross-region replication for enterprise tiers |
| FR-STO-002 | Data residency enforced at bucket level; a tenant pinned to `in-south` never has bytes, derived data, embeddings, logs or inference traffic leave that region |
| FR-STO-003 | Per-tenant, per-unit and per-user quotas with soft warnings at 80%/90% and configurable hard stops |
| FR-STO-004 | Large-file support: 100 GB single object via multipart; 1 TB logical artefact bundles |
| FR-STO-005 | Resumable uploads surviving network loss and browser restart |
| FR-STO-006 | Integrity verification: checksum on write, periodic background scrubbing, checksum on read, automatic repair from replica |
| FR-STO-007 | Storage analytics: consumption by unit, type, age, tier; growth forecasting; "reclaimable space" recommendations (duplicates, superseded previews, stale exports) |
| FR-STO-008 | Cold-retrieval UX: expected wait shown, background restore, notification on availability, optional expedited retrieval |
| FR-STO-009 | Offline/desktop sync with selective sync, placeholder files (on-demand hydration), and conflict resolution that never destroys either side |
| FR-STO-010 | Bring-Your-Own-Storage: enterprise tenants may attach their own S3/Azure bucket for primary blob storage while metadata remains managed |
| FR-STO-011 | Immutable/object-lock storage for records under legal hold or regulatory retention |
| FR-STO-012 | Full export: complete tenant corpus with folder projection, original filenames, and JSON-LD sidecar metadata, delivered as verifiable BagIt bundles |

### 13.4 Cost Model & Optimisation

Assumptions: an active academic accumulates ~40 GB/year (documents 5%, media 55%, research data 40%). A 5,000-user university reaches ~200 TB in year 1 and ~1 PB by year 5.

Optimisation levers, in order of impact:
1. **Aggressive automatic tiering** (target ≥ 60% of bytes on T2 or colder by month 18).
2. **Version thinning policy** — keep all major versions forever; thin minor versions older than 2 years to daily-last, then weekly-last, with per-class overrides and never for compliance-classified records.
3. **Derived-data eviction** — regenerate previews on demand rather than storing them indefinitely for cold content.
4. **Deduplication** within tenant.
5. **Format optimisation** — lossless recompression of images, modern codecs for lecture video (with originals retained for 12 months, then policy-driven).
6. **Media transcoding ladders** — store one archival master plus adaptive streams; drop unused renditions.
7. **Quota nudges** — surface reclaimable space to users rather than silently absorbing cost.

### 13.5 Data Lifecycle

```
CREATE → ACTIVE (T1) → INACTIVE (T2, 90d) → DORMANT (T3, 365d)
                                                    ↓
                                      ARCHIVED (T4, policy) ── or ── PRESERVED (T5, DOI)
                                                    ↓
                     [Retention expiry AND no legal hold AND owner notified]
                                                    ↓
                        SOFT DELETE (30d trash) → RECOVERABLE ARCHIVE (90d) → PURGE
```

Nothing is purged without: retention expiry, absence of legal hold, absence of citation by another live artefact, and a notification to the owner and the institutional administrator with a 30-day objection window.

---

## 14. Version Control

### 14.1 Philosophy

> Academia's true unit of value is not the file — it is *the intellectual lineage of a claim*. Version control must therefore capture not only "what bytes changed" but "who contributed what thinking, when, and on what basis".

`Final_v2_FINAL_revised.docx` is not a user failure; it is a tooling failure. AcademicOS eliminates the *need* for manual versioning by making version history effortless, visible, navigable and trustworthy.

### 14.2 Versioning Model

| Concept | Definition |
|---|---|
| **Artefact** | The stable identity. Permanent ID, permanent URL, survives renames, moves and format changes. |
| **Version** | An immutable snapshot of content + metadata at a point in time, with attribution and a change summary. |
| **Revision label** | Human-meaningful semantic label: `v1.0-draft`, `v2.3-internal-review`, `v3.0-submitted`, `v3.1-revision-r1`, `v4.0-accepted`, `v4.0-published`. |
| **Branch** | A named parallel line of development (e.g., `journal-a-format`, `student-rewrite`, `thesis-chapter-variant`). |
| **Merge** | Reconciliation of branches with human adjudication on conflicts. |
| **Lineage** | The directed graph of derivation across artefacts (data → analysis → figure → manuscript). |
| **Provenance record** | The signed, immutable statement of how an artefact came to exist. |

### 14.3 Change Semantics

| Change Type | Trigger | Version Increment |
|---|---|---|
| **Major** | Structural rewrite, new results, submission, acceptance, formal milestone | `x.0` |
| **Minor** | Section edits, added content, revised figures | `x.y` |
| **Patch** | Typos, formatting, reference fixes | `x.y.z` |
| **Metadata-only** | Tagging, re-classification, permission change | No content version; recorded in the metadata history |

Classification is AI-proposed from the diff and always human-overridable.

### 14.4 Functional Requirements

| ID | Requirement |
|---|---|
| FR-VER-001 | Every content change creates an immutable version — automatically, with no user action |
| FR-VER-002 | Unlimited version retention for compliance-classified artefacts; policy-based thinning elsewhere (§13.4) with user-visible policy |
| FR-VER-003 | Version timeline UI: chronological, branch-aware, showing author, timestamp, change size, change summary, and stage label |
| FR-VER-004 | Diff support: rich text (word-level), Markdown/LaTeX, code, structured data (row/column-level for CSV), slides (slide-level), images (visual overlay/onion-skin), PDFs (text + visual), notebooks (cell-level) |
| FR-VER-005 | **Semantic diff**: AI-generated natural-language description of what changed and why it matters ("Results section now reports n=412 instead of n=380; conclusion strengthened accordingly") |
| FR-VER-006 | Restore any version to current with a single action, itself recorded as a new version (history is never rewritten) |
| FR-VER-007 | Compare any two arbitrary versions, including across branches |
| FR-VER-008 | Branching for manuscripts and theses with visual branch graph and merge assistance |
| FR-VER-009 | Version-level comments and approvals ("approved by supervisor at v2.3") that remain permanently bound to that version |
| FR-VER-010 | Contribution ledger: per-version and per-artefact attribution of who wrote/edited/reviewed what, aggregated to a contribution profile |
| FR-VER-011 | Provenance chains across artefacts, visualised as a lineage graph, with one-click "show me where this figure's data came from" |
| FR-VER-012 | Integrity: each version's content hash chained to its predecessor; tamper detection on read; optional digital signature for records of consequence (approved theses, submitted evidence, ethics approvals) |
| FR-VER-013 | Concurrent-edit handling: real-time CRDT merge for native notes; check-out/lock plus conflict-copy resolution for binary formats — never silent overwrite |
| FR-VER-014 | External-tool round-trip: edits made in Word/Google Docs/Overleaf/Git flow back as versions with correct attribution |
| FR-VER-015 | Version search: find content that existed in a past version even if removed from the current one ("where did that paragraph about limitations go?") |
| FR-VER-016 | Milestone snapshots: freeze the complete state of an entity (course offering, thesis, project, evidence pack) as a citable, immutable bundle |
| FR-VER-017 | Retention/legal hold overrides all thinning and deletion of versions |

### 14.5 Provenance Chain Example (Research)

```
instrument-run-2026-03-14.raw  (T1, hash a3f…, ingested from instrument drop folder)
        │ derived_from · script: preprocess.py @ commit 8b21c4d (env: conda-lock hash 77e…)
        ▼
cleaned_dataset_v2.parquet     (dataset entity DS-0341, DOI-ready)
        │ used_by · analysis.ipynb @ commit d90f1aa, executed 2026-04-02 14:22 UTC
        ▼
figure_3_selectivity.svg       (figure artefact, generated output)
        │ appears_in · Manuscript MS-0187 §Results, v3.1-revision-r1
        ▼
Publication PUB-0092, DOI 10.xxxx/yyyy, funded_by Grant GR-0014 (SERB CRG/2024/xxxx)
```

Every arrow is a queryable, immutable relationship. A reviewer asking "how was Figure 3 produced?" receives the complete chain, including the exact code commit and environment, in one click. This capability alone justifies the platform for research-intensive institutions.

---

## 15. Search Engine

### 15.1 Search Architecture

```
                             ┌──────────────────┐
   User Query ──────────────▶│ Query Understanding│
                             │ • intent classify  │
                             │ • entity extract   │
                             │ • temporal resolve │
                             │ • acronym expand   │
                             │ • scope detect     │
                             │ • spell correct    │
                             └─────────┬──────────┘
                                       │
                             ┌─────────▼──────────┐
                             │ Permission Planner │  ← accessible partition computed FIRST
                             └─────────┬──────────┘
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
      ┌───────────────┐        ┌──────────────┐         ┌──────────────┐
      │ Lexical (BM25)│        │ Vector (ANN) │         │ Graph Expand │
      │ • fields      │        │ • chunks     │         │ • 2-hop      │
      │ • phrases     │        │ • summaries  │         │ • entity ctx │
      │ • filters     │        │ • hypo-Qs    │         │ • lineage    │
      └───────┬───────┘        └──────┬───────┘         └──────┬───────┘
              └────────────────────────┼────────────────────────┘
                             ┌─────────▼──────────┐
                             │  Fusion (RRF)      │
                             └─────────┬──────────┘
                             ┌─────────▼──────────┐
                             │ Cross-Encoder Rerank│
                             └─────────┬──────────┘
                             ┌─────────▼──────────┐
                             │ Personalisation &  │
                             │ Recency Boosting   │
                             └─────────┬──────────┘
                             ┌─────────▼──────────┐
                             │ ACL Post-Verify +  │
                             │ Snippet Generation │
                             └─────────┬──────────┘
                                       ▼
                     Results · Facets · Answer · Related · Actions
```

### 15.2 What Is Searchable

| Source | Extracted Content |
|---|---|
| Documents | Full text, headings, tables, footnotes, embedded metadata |
| PDFs | Text layer + OCR fallback + figure captions + reference list |
| Slides | Slide text, speaker notes, embedded images (OCR), slide titles |
| Spreadsheets | Cell content, sheet names, headers, formulas, named ranges |
| Images/scans | OCR text (printed and handwritten), AI-generated descriptions, EXIF |
| Audio/video | Transcript with timestamps, speaker labels, on-screen text (OCR of frames), chapters |
| Code/notebooks | Source, comments, docstrings, markdown cells, output text |
| Datasets | Column names, data dictionary, README, sample values, schema |
| LaTeX | Source, compiled text, equations (as LaTeX and as normalised form), bibliography |
| Entities | All attributes, external IDs, aliases |
| Metadata | Every layer (§16) |
| Collaboration | Comments, tasks, meeting notes, decisions |
| Versions | Historical content, change summaries |
| AI outputs | Saved summaries, generated drafts (clearly labelled as such) |

### 15.3 Query Capabilities

| Type | Example | Handling |
|---|---|---|
| Keyword | `pumping lemma` | BM25 with field boosting |
| Phrase | `"catalytic degradation of microplastics"` | Exact phrase, higher weight |
| Boolean/field | `type:dataset AND project:NanoCat NOT status:archived` | Structured query parser |
| Natural language | `the slides where I explained attention to first-years last year` | Intent → entity + temporal + semantic |
| Question | `what were the main limitations in my 2024 papers?` | RAG answer + sources |
| Similarity | `more like this` | Vector nearest-neighbour on the source artefact |
| Provenance | `what produced figure 3 of MS-0187?` | Graph traversal |
| Temporal | `everything from odd semester 2025` | Academic-calendar-aware date resolution |
| Person-scoped | `Rahul's chapter drafts` | Entity resolution + relationship filter |
| Negative/absence | `projects with no data management plan` | Graph anti-join query |
| Aggregate | `how many Q1 publications did the department produce in 2025?` | Analytical query against the metric registry |

### 15.4 Ranking Signals

| Signal | Weight class | Notes |
|---|---|---|
| Lexical relevance (BM25, field-boosted) | High | Title/heading matches boosted ~3× over body |
| Semantic similarity | High | Cross-encoder reranked |
| Entity match precision | High | Exact course code or grant number dominates |
| Recency | Medium | Discipline-tuned decay; a 2019 protocol may be as relevant as a 2026 memo |
| Academic-calendar relevance | Medium | Current semester boosted for teaching artefacts |
| User affinity | Medium | Own artefacts, own spaces, frequent collaborators |
| Interaction history | Medium | Previously opened, starred, recently edited |
| Graph centrality | Low–Med | Artefacts central to a project's lineage rank higher |
| Authority | Low | Approved/published versions above drafts |
| Completeness | Low | Well-described artefacts slightly favoured |
| Duplicate suppression | Filter | Near-duplicates collapsed with an expander |

Learning-to-rank model trained on click, dwell and task-completion signals, with per-tenant personalisation layers and strict privacy boundaries (no cross-tenant signal sharing).

### 15.5 Search Experience Requirements

| ID | Requirement |
|---|---|
| FR-SRE-001 | Instant search-as-you-type with results streaming from the first keystroke (debounced) |
| FR-SRE-002 | Unified result surface: an AI answer card (when the query is a question), then ranked artefacts, then entities, then people, then actions |
| FR-SRE-003 | Rich result cards: type icon, title, snippet with query-term highlighting, entity breadcrumb, date, owner, thumbnail |
| FR-SRE-004 | Inline preview on hover/space without leaving results |
| FR-SRE-005 | Facet panel with live counts; facets adapt to result composition |
| FR-SRE-006 | Deep-link into result location (page, slide, cell, timestamp) |
| FR-SRE-007 | Save any query as a Smart Folder with optional alerting when new matches arrive |
| FR-SRE-008 | Search history, recent searches, and suggested queries |
| FR-SRE-009 | Zero-result handling: explain the constraint that eliminated results and offer relaxations |
| FR-SRE-010 | Search scoping chips: This artefact / This space / My work / My lab / Department / Everything I can access |
| FR-SRE-011 | Bulk actions directly from results (tag, move, share, export, add to evidence pack) |
| FR-SRE-012 | Search analytics for admins: top queries, zero-result queries, low-CTR queries — feeding taxonomy and content improvements |
| FR-SRE-013 | Full keyboard operation; results navigable and openable without the mouse |
| FR-SRE-014 | Offline search over locally synced content in the desktop client |

### 15.6 Indexing Operations

- **Near-real-time:** target ≤ 60 s from ingest completion to searchability; ≤ 5 s for text edits to native notes.
- **Incremental:** only changed chunks are re-embedded; content hashing prevents redundant work.
- **Re-indexing:** full tenant re-index must be possible online, without downtime, with dual-index alias swap; required when embedding models are upgraded.
- **Consistency monitoring:** continuous reconciliation between the primary store and indices; drift reported as an SLO with automatic repair jobs.
- **Index health:** per-tenant index size, query latency and freshness exposed to admins.

---

## 16. Metadata Design

### 16.1 The Seven Metadata Layers

Metadata is not one flat bag of tags; it is layered by origin, authority and lifetime.

| Layer | Owner | Mutability | Examples |
|---|---|---|---|
| **L1 System** | Platform | Immutable | artefact_id, tenant_id, created_at, content_hash, storage_tier |
| **L2 Technical** | Extraction pipeline | Auto-refresh | mime_type, size, page_count, duration, resolution, encoding, language, checksum |
| **L3 Descriptive** | AI + human | Editable | title, subtitle, abstract, summary, keywords, description, alt text |
| **L4 Academic** | AI + human + integrations | Editable | discipline, subject taxonomy, course, semester, project, grant, publication venue, DOI, methodology, CO/PO mapping, contributors + CRediT roles, peer-review status |
| **L5 Administrative** | Policy + admin | Governed | owner, sensitivity, retention class, legal hold, licence, rights, embargo, access class, approval status |
| **L6 Provenance** | System | Immutable | created_by, derived_from, generated_by (tool + version), version lineage, AI involvement, verification records |
| **L7 Custom** | Tenant | Tenant-governed | Institution-defined fields, departmental schemes, funder-specific fields |

Every metadata value carries: `value`, `source` (human / ai / extracted / imported / computed / rule), `confidence`, `asserted_by`, `asserted_at`, `vocabulary_ref`, and `superseded_by`. This makes metadata *auditable* — a requirement most systems ignore and every accreditor eventually asks about.

### 16.2 Core Metadata Schema (universal fields)

| Field | Type | Required | Source | Notes |
|---|---|---|---|---|
| artefact_id | ULID/UUIDv7 | Yes | System | Permanent, never reused |
| title | Text | Yes | AI→Human | Human-readable, distinct from filename |
| artefact_type | Enum | Yes | AI | Controlled vocabulary (§16.3) |
| description | Text | No | AI | 1–3 sentence purpose statement |
| abstract | Text | No | AI/Extracted | For scholarly artefacts |
| keywords | Array | No | AI | 5–10, from controlled + free vocabulary |
| subjects | Array[TermRef] | No | AI | Mapped to discipline taxonomy |
| language | ISO 639-3 | Yes | Detected | Multi-value allowed |
| created_date | Date | Yes | System/Extracted | Original creation, not upload |
| authors/contributors | Array[PersonRef + CRediT role] | No | AI/Extracted | Resolved to identities where possible |
| owner | UserRef | Yes | System | Accountable party |
| entities | Array[EntityRef + rel_type] | Yes | AI | Course, project, grant, scholar, publication links |
| academic_period | Term | No | AI | Semester/term/academic-year resolution |
| sensitivity | Enum | Yes | Policy/AI | public / internal / confidential / restricted |
| licence | SPDX or text | No | Human | Defaults by policy |
| rights_statement | Text | No | Human | |
| status | Enum | Yes | System | draft / in-review / active / superseded / archived |
| version_label | Text | Yes | System | Semantic label |
| retention_class | Ref | Yes | Policy | Determines lifecycle |
| provenance | Object | Yes | System | Derivation chain |
| ai_generated | Bool + detail | Yes | System | Model, prompt version, human edit ratio |
| quality_score | Float | No | Computed | Metadata completeness + verification state |

### 16.3 Artefact Type Vocabulary (extensible; ~90 types across 8 families)

| Family | Types |
|---|---|
| **Teaching** | syllabus · lesson_plan · lecture_slides · lecture_video · lecture_notes · reading_list · assignment · assessment_rubric · question_paper · question_bank_item · answer_key · gradebook · student_submission · course_feedback · attendance_record · lab_manual · tutorial_sheet |
| **Research** | research_proposal · literature_note · protocol · experiment_record · raw_dataset · processed_dataset · analysis_script · notebook · figure · table · model_artefact · simulation_output · survey_instrument · interview_transcript · field_note · codebook |
| **Publication** | manuscript_draft · preprint · submitted_paper · peer_review_report · reviewer_response · published_article · book · book_chapter · conference_paper · poster · presentation · thesis · thesis_chapter · dissertation_abstract · patent_disclosure · technical_report |
| **Funding** | funding_call · proposal · budget · sanction_letter · agreement · progress_report · utilisation_certificate · expense_record · dmp · final_report |
| **Supervision** | scholar_record · supervision_meeting_log · progress_report · committee_report · milestone_record · examiner_report · viva_record · recommendation_letter |
| **Governance** | policy · minutes · circular · committee_document · accreditation_evidence · audit_record · appraisal_document · workload_statement · mou · ethics_approval |
| **Professional** | cv · biosketch · award_record · certificate · invited_talk · outreach_record · service_record · training_record |
| **General** | note · reference_material · image · correspondence · template · scan · miscellaneous |

### 16.4 Standards Alignment (mandatory for interoperability)

| Standard | Use |
|---|---|
| **Dublin Core / DCMI Terms** | Base descriptive metadata; export mapping |
| **DataCite 4.x** | Dataset and DOI deposit metadata |
| **Crossref** | Publication metadata ingest/deposit |
| **CERIF** | Research information exchange with CRIS systems |
| **schema.org (+ Bioschemas)** | Web/SEO and machine-readable exposure |
| **CRediT** | Contributor role taxonomy |
| **ORCID** | Person identifiers |
| **ROR** | Organisation identifiers |
| **Funder Registry / Crossref Open Funder** | Funder identifiers |
| **RO-Crate** | Packaging research objects with context |
| **BagIt** | Archival transfer packaging |
| **PREMIS** | Digital preservation metadata |
| **OAI-PMH / ResourceSync** | Repository harvesting |
| **LTI 1.3 / Caliper** | LMS interop and learning analytics |
| **FAIR principles** | Findable, Accessible, Interoperable, Reusable — measured as a per-artefact FAIRness score |

### 16.5 Metadata Governance

| ID | Requirement |
|---|---|
| FR-MET-001 | Institutions may define required, recommended and optional fields per artefact type, enforced at save or at publish |
| FR-MET-002 | Controlled vocabularies managed by admins/librarians with synonyms, deprecation, and mapping to external authorities |
| FR-MET-003 | **Metadata completeness score** per artefact, entity, space and department, with dashboards and nudges |
| FR-MET-004 | Bulk metadata editing with preview, validation and undo |
| FR-MET-005 | Metadata inheritance: artefacts inherit defaults from their space/entity, with explicit override indication |
| FR-MET-006 | Full metadata version history with attribution ("who changed the publication year, when, and why") |
| FR-MET-007 | Validation rules: format, range, vocabulary membership, cross-field consistency (e.g., published_date ≥ submitted_date) |
| FR-MET-008 | Import/export mappings for all standards in §16.4, round-trip safe |
| FR-MET-009 | AI never overwrites a human-asserted value; it proposes a change with rationale and awaits confirmation |
| FR-MET-010 | Metadata quality reports for librarians: missing fields, low-confidence values, vocabulary drift, unresolved entities |

### 16.6 Entity Resolution

Academic corpora are full of the same thing named differently. The Entity Resolution service clusters variants using name similarity, co-authorship graphs, email/ORCID identity, institutional affiliation and temporal plausibility. Clusters are surfaced for confirmation ("Are *R. Menon*, *Rahul Menon* and *rmenon@univ.edu* the same person?"), with merge and split operations fully reversible and audited. The same applies to venues, funders, courses across renamings, and datasets across duplicates.

---

# PART D — PHILOSOPHY & FORWARD LOOK

---

## 17. Future Expansion

### 17.1 Horizon Model

| Horizon | Window | Theme | Objective |
|---|---|---|---|
| **H1 — Foundation** | Months 0–9 | *Make it indispensable to one professor* | Ingest, auto-organise, search, AI assistant, courses, publications, versions |
| **H2 — Institution** | Months 10–18 | *Make it indispensable to a department* | Supervision, grants, compliance, workflows, analytics, LMS/SIS integration, mobile & desktop |
| **H3 — Platform** | Months 19–30 | *Make it an ecosystem* | Public API, marketplace, agents, cross-institution collaboration, on-prem, discipline packs |
| **H4 — Network** | Months 31–48 | *Make it infrastructure* | Federated research graph, funder/publisher integrations, benchmarking, research-intelligence products |

### 17.2 Expansion Vectors

**1. Vertical depth — Discipline Packs.** The core is discipline-agnostic; value multiplies with domain specialisation. Planned packs: Life Sciences (ELN-grade protocols, sequence data, IACUC/IRB), Engineering (CAD, simulation, testing regimes), Social Sciences (survey instruments, qualitative coding, consent management), Humanities (archival sources, critical editions, non-textual evidence), Medicine (clinical trial records, HIPAA workflows, CRF handling), Law (case corpora, citation systems). Each pack adds artefact types, metadata schemas, workflows, templates and evaluation sets — configuration and content, not forked code.

**2. Horizontal breadth — Adjacent workflows.** Conference and event management; peer-review management for society journals; academic hiring and promotion dossiers; alumni and industry engagement records; student project supervision at UG/PG scale; research-ethics case management.

**3. Platform — Extensibility economy.** Public API and webhook platform (H3); an extension marketplace with sandboxed permissions and vendor review; a template exchange where institutions publish syllabi, rubrics and protocols; community-contributed discipline taxonomies; partner-built connectors for regional systems (Samarth, ERP vendors, national repositories).

**4. Intelligence — From assistant to colleague.** Continuous learning from tenant corrections (privacy-preserving, tenant-isolated); per-tenant retrieval fine-tuning; multi-agent research support (an agent that monitors literature, another that maintains compliance, another that keeps data hygienic, coordinated by a planner); predictive research intelligence (funding-fit scoring, collaborator recommendation, impact forecasting); AI co-reviewer that critiques a manuscript against the venue's standards before submission.

**5. Network effects — The federated research graph.** With consent, participating institutions can expose a metadata-only layer enabling cross-institution expertise discovery, collaboration matchmaking, and shared instrument/resource discovery. Funders can verify outputs against a verifiable record instead of self-reported forms. This is the long-term moat: not features, but the graph.

**6. Geographic & deployment.** Regional data centres (India, EU, US, UK, Australia, Gulf, Southeast Asia); sovereign/on-prem deployments; localisation into major academic languages; compliance packs for national regulators (UGC/AICTE/NAAC/NBA, REF, TEQSA, CHEA).

**7. Commercial expansion.** Individual → lab → department → institution → consortium land-and-expand; research-intelligence analytics as a premium tier for leadership; verified-outcomes services for funders; preservation/archival services; training and change-management services (a real revenue line in higher education).

### 17.3 Architectural Readiness (what we build now to enable later)

| Future Capability | Enabling Decision Taken in v1 |
|---|---|
| Discipline packs | Ontology and artefact types are data, not code; schemas are tenant-configurable |
| Marketplace | All first-party features built on the same public API contracts we will expose |
| On-prem | No proprietary managed-service lock-in on critical paths; Kubernetes + open datastores |
| Federated graph | Global identifiers (ORCID, ROR, DOI) adopted from day one; metadata standards-compliant |
| Model evolution | Model abstraction layer; re-embedding pipeline; versioned prompts; eval harness |
| Multi-region | Tenant-pinned residency from the first line of code, not retrofitted |
| Consortium tenancy | Tenant model supports parent/child relationships and cross-tenant sharing agreements |
| New modalities | Ingest pipeline is stage-pluggable; adding a modality means adding processors, not rewriting |

### 17.4 Deliberate Deferrals (with reasons)

| Deferred | Why | Revisit |
|---|---|---|
| Full LMS replacement | Enormous scope; incumbents entrenched; integration is the better wedge | H4, only if pulled by customers |
| Native document editing | Users are wedded to Word/LaTeX/Docs; we should host and version, not re-create | Never (integrate instead) |
| Student-facing mass product | Different buyer, different economics, support load | H4 |
| Blockchain credentialing | Solution seeking a problem; hash-chained audit already delivers integrity | Only on regulatory demand |
| Public social/network features | Distracts from the core job; academia already has channels | H4, narrowly |

---

## 18. Folder Philosophy

### 18.1 The Core Thesis

> **Folders are a rendering, not a reality.**

In every legacy system, placing a file in a folder is a destructive act of commitment: the file exists in exactly one place, and every other legitimate way of thinking about it is lost. A lecture on graph algorithms belongs to *CS-301*, to *Odd Semester 2026*, to *my teaching portfolio*, to *the algorithms subject cluster*, to *NBA Criterion 1.3 evidence*, and to *things I should update next year*. A hierarchy forces you to choose one and betray the rest.

AcademicOS inverts this. The truth is the **graph**: artefacts, entities and typed relationships. Folders are *projections* of the graph — deterministic, regenerable views. Because they are views, an artefact appears in every place it legitimately belongs, with no copies, no shortcuts, and no divergence.

### 18.2 The Structural Spine

Users still need a stable mental model. We provide one canonical projection — familiar enough to feel like home, principled enough to never rot:

```
◈ MY WORKSPACE
│
├── 🎓 TEACHING
│   └── {Academic Year}/{Term}/{Course Code — Course Title}/
│       ├── 00_Course-Design      (syllabus, outcomes, plan, approvals)
│       ├── 01_Sessions           (per-session: slides, notes, recordings, activities)
│       ├── 02_Assessments        (question papers, rubrics, keys, analysis)
│       ├── 03_Submissions        (student work, grading records)
│       ├── 04_Feedback           (student feedback, peer review, reflection)
│       └── 05_Evidence           (attainment, innovation, accreditation links)
│
├── 🔬 RESEARCH
│   └── {Project Code — Project Name}/
│       ├── 00_Project-Charter    (proposal, objectives, approvals, team, ethics)
│       ├── 01_Literature         (references, notes, matrices, gap analysis)
│       ├── 02_Methods            (protocols, instruments, code, environments)
│       ├── 03_Data
│       │   ├── raw               (immutable, never edited)
│       │   ├── processed         (with lineage to raw)
│       │   └── outputs           (figures, tables, models)
│       ├── 04_Manuscripts        (drafts, submissions, reviews, responses)
│       ├── 05_Dissemination      (talks, posters, media, outreach)
│       └── 06_Administration     (budget, reports, correspondence)
│
├── 👥 SUPERVISION
│   └── {Scholar Name — Programme}/
│       ├── 00_Record             (enrolment, plan, agreements, committee)
│       ├── 01_Milestones         (proposal, comprehensive, DC reports, synopsis)
│       ├── 02_Meetings           (logs, decisions, actions)
│       ├── 03_Thesis             (chapters, versions, feedback)
│       ├── 04_Outputs            (papers, presentations, datasets)
│       └── 05_Examination        (submission, examiners, reports, viva)
│
├── 💰 FUNDING
│   └── {Agency — Award Number}/
│       ├── 00_Proposal · 01_Award · 02_Deliverables
│       ├── 03_Financial · 04_Reports · 05_Closure
│
├── 📄 PUBLICATIONS
│   └── {Year}/{Short-Title}/         (full lifecycle per output)
│
├── 🏛 SERVICE & GOVERNANCE
│   └── Committees/ · Reviews/ · Institutional/ · Outreach/
│
├── 👤 PROFESSIONAL
│   └── CV/ · Appraisals/ · Awards/ · Training/ · Talks/
│
└── 🗄 ARCHIVE
    └── {Year}/  (completed items, retained, searchable, cold-tiered)
```

**Design rules for the spine:**
- **Maximum depth 4.** Beyond four levels, humans lose the map. Depth is replaced by metadata and filtering.
- **Numeric prefixes** on second-level folders (`00_`, `01_`) enforce a *workflow order*, not an alphabetical accident — they teach the process.
- **Consistency across contexts.** Every course looks the same; every project looks the same. Muscle memory transfers.
- **No `Misc`, no `Other`, no `New Folder`.** Unclassifiable items go to the Review Queue where AI and the user resolve them; they never accumulate in a junk drawer.
- **`raw` is sacred.** Raw data folders are write-once by policy; editing raw data requires an explicit, audited override.

### 18.3 The Four Projections

Every artefact is simultaneously visible in four coexisting views, switchable in one click:

| Projection | Organising Logic | Best For |
|---|---|---|
| **Structural** | The canonical spine above | Orientation, onboarding, mental model, export |
| **Entity** | Grouped by course, project, scholar, grant, publication | Doing the actual work |
| **Temporal** | Academic calendar: year → term → week → day | "What was I doing last March?" |
| **Semantic** | AI-clustered by topic, method, theme; concept graph | Discovery, synthesis, finding unexpected connections |

Plus **Smart Folders** — saved queries that behave exactly like folders but are defined by rules ("all datasets from NanoCat without a DMP", "everything I need to review this week", "Q1 publications from 2025"). They update themselves and never go stale.

### 18.4 Folder Requirements

| ID | Requirement |
|---|---|
| FR-FLD-001 | The canonical structure is auto-created on onboarding, seeded from the user's declared role and courses |
| FR-FLD-002 | Artefacts appear in every projection they legitimately belong to, with no duplication of bytes |
| FR-FLD-003 | Moving an artefact changes relationships, never content, and is fully reversible |
| FR-FLD-004 | Users may create custom folders, but the system nudges toward metadata when a folder duplicates an existing filter |
| FR-FLD-005 | Depth beyond 4 levels triggers a gentle restructuring suggestion |
| FR-FLD-006 | Smart Folders are first-class: pinnable, shareable, alertable, exportable |
| FR-FLD-007 | Institutions may define a mandatory structural template for departmental and compliance spaces |
| FR-FLD-008 | Export renders the structural projection as real directories, with sidecar metadata preserving all other relationships — so a user leaving the platform loses nothing |
| FR-FLD-009 | Legacy import maps arbitrary existing trees to the canonical spine with a reviewable plan, and preserves the original path as permanent metadata (`legacy_path`) so nothing about the original organisation is forgotten |
| FR-FLD-010 | "Where does this belong?" — any artefact can ask the system for placement suggestions with reasoning |

### 18.5 What We Refuse to Build

- Unlimited nesting depth (it is how drives die).
- Physical copies as an organisation mechanism (the origin of version chaos).
- Shortcuts, aliases and symlinks visible to users (leaky abstractions, broken links).
- Personal folder anarchy in *institutional* spaces (governed spaces have governed structure).
- A default "Downloads"-equivalent dumping ground.

---

## 19. Naming Convention

### 19.1 Why Naming Still Matters

Even in a metadata-driven system, names matter at three boundaries: when files are **exported** to a filesystem, when they are **shared** with people outside the platform, and when a human **scans a list** and must recognise the right item in under a second. Names must therefore be self-describing without any surrounding context.

But — critically — **users never have to type these names**. The system generates them. The convention is enforced by machine, not by discipline.

### 19.2 The Naming Grammar

```
{SCOPE}_{TYPE}_{DESCRIPTOR}_{QUALIFIER}_{DATE|SEQUENCE}_{VERSION}.{ext}
```

| Token | Rule | Examples |
|---|---|---|
| SCOPE | Entity code — course code, project code, grant number, scholar initials | `CS301`, `NANOCAT`, `SERB-CRG-2024-1187`, `RM` |
| TYPE | Controlled abbreviation from the artefact-type vocabulary | `SYL`, `LEC`, `ASG`, `QP`, `MS`, `DS`, `FIG`, `RPT`, `MIN`, `PROT` |
| DESCRIPTOR | 2–4 words, kebab-case, meaningful | `graph-algorithms`, `catalyst-selectivity` |
| QUALIFIER | Optional context: term, cohort, run, stage | `2026-ODD`, `RUN42`, `SUBMITTED` |
| DATE / SEQ | ISO 8601 `YYYYMMDD` or zero-padded sequence `L08` | `20260804`, `L08` |
| VERSION | `v` + semantic version, or `vFINAL` never (banned) | `v2.1`, `v3.0` |

**Canonical examples**

| Artefact | Generated Name |
|---|---|
| Lecture 8 slides, CS-301, Odd 2026 | `CS301_LEC_graph-algorithms_2026-ODD_L08_v1.2.pptx` |
| Mid-semester question paper | `CS301_QP_midsem_2026-ODD_20260915_v1.0.pdf` |
| Raw instrument data, run 42 | `NANOCAT_DS-RAW_selectivity-assay_RUN42_20260314_v1.0.csv` |
| Figure for manuscript | `NANOCAT_FIG_selectivity-vs-temp_MS0187_20260402_v3.1.svg` |
| Manuscript under revision | `NANOCAT_MS_catalytic-degradation_REV-R1_20260620_v3.1.docx` |
| PhD chapter draft | `RM-PHD_THC_ch03-methodology_20260728_v7.0.docx` |
| Grant progress report | `SERB-CRG-2024-1187_RPT_progress-q3_20260930_v1.0.pdf` |
| Supervision meeting log | `RM-PHD_MTG_chapter3-review_20260804_v1.0.md` |
| Committee minutes | `BOS-CSE_MIN_curriculum-revision_20260712_v1.0.pdf` |

### 19.3 Rules

**Mandatory**
1. ISO 8601 dates only (`YYYYMMDD` or `YYYY-MM-DD`). Never `04-08-26` — it is ambiguous across continents and unsortable.
2. No spaces. Use `_` between tokens and `-` within tokens. This keeps names safe in URLs, shells, scripts, Git and every operating system.
3. ASCII-safe for filenames; the human-readable Unicode title lives in metadata, not in the filesystem name.
4. Lower-case descriptors; upper-case scope and type codes (visual parsing aid).
5. Maximum 120 characters total (safe across Windows path limits when nested).
6. Version tokens are semantic and monotonic. `final`, `FINAL`, `latest`, `new`, `updated`, `old`, `copy`, `(1)` are **banned tokens** — the system rejects and rewrites them.
7. Sequence numbers zero-padded (`L08`, not `L8`) so lexical sort equals logical sort.
8. Sensitive content never carries identifying information in the filename (e.g., no student names on graded submissions in shared contexts) — pseudonymised codes instead.

**Prohibited:** personal shorthand nobody else can decode; emojis in filenames (delightful in the UI, catastrophic in scripts); paths encoding information that belongs in metadata; renaming as a substitute for versioning.

### 19.4 Entity Naming (beyond files)

| Entity | Pattern | Example |
|---|---|---|
| Course offering | `{CODE}-{TITLE}-{YEAR}-{TERM}` | `CS301-Automata-Theory-2026-ODD` |
| Research project | `{ACRONYM}-{Short-Name}` | `NANOCAT-Catalytic-Degradation` |
| Grant | `{AGENCY}-{SCHEME}-{YEAR}-{NUMBER}` | `SERB-CRG-2024-1187` |
| Scholar record | `{INITIALS}-{PROGRAMME}-{ADMIT-YEAR}` | `RM-PHD-2023` |
| Manuscript | `MS{NNNN}-{short-title}` | `MS0187-catalytic-degradation` |
| Dataset | `DS{NNNN}-{short-description}` | `DS0341-selectivity-assays` |
| Space | `{Type}: {Human Name}` | `Research: NanoCat Lab` |
| Smart Folder | Natural language | `Needs my review this week` |

### 19.5 Enforcement Model

| ID | Requirement |
|---|---|
| FR-NAM-001 | Names are auto-generated at ingest from extracted metadata; the user is never asked to name a file |
| FR-NAM-002 | The original uploaded filename is preserved permanently as `original_filename` metadata and remains searchable — we never destroy the user's own reference point |
| FR-NAM-003 | Institutions may customise the naming grammar (token order, separators, codes) per artefact type; the default ships opinionated |
| FR-NAM-004 | Bulk rename with full preview, diff, and one-click undo across thousands of artefacts |
| FR-NAM-005 | Banned-token detection with automatic correction proposals (`Final_v2_FINAL.docx` → suggested compliant name + version assignment) |
| FR-NAM-006 | Collision handling appends a disambiguating token, never a silent `(1)` |
| FR-NAM-007 | Name changes never break links: canonical IDs and URLs are name-independent, and all prior names are retained as aliases resolvable in search |
| FR-NAM-008 | Export honours the naming convention and the structural projection so the exported tree is immediately usable outside the platform |
| FR-NAM-009 | A naming-compliance score per space, visible to admins, with a one-click "bring into compliance" action |

---

## 20. UI Philosophy

### 20.1 Design Thesis

> **Calm, dense, and deferential.** Academics are experts operating under cognitive load. The interface must present a great deal of information without shouting, and must get out of the way the moment the user knows what they want.

We reject three prevailing patterns: the *consumer-app dopamine loop* (badges, streaks, celebration confetti — insulting to a professor); the *enterprise-software wall of grey* (dense but joyless and unlearnable); and the *AI-first chat-only interface* (impressive in a demo, useless when you need to compare 40 documents).

Our reference points: **Linear** for speed and keyboard primacy, **Notion** for flexible structure, **Things** for calm, **VS Code** for professional density, **Stripe Docs** for clarity of explanation.

### 20.2 The Ten Principles

1. **Content is the interface.** Chrome is minimal, monochrome and recedes; the user's own work provides the colour.
2. **Information density with breathing room.** Show more per screen than consumer apps, but with disciplined spacing, alignment and typographic hierarchy. Experts resent being drip-fed.
3. **Keyboard is a first-class citizen.** Every action has a shortcut; ⌘K reaches everything; power users should be able to work without touching the mouse for an entire session.
4. **Progressive disclosure.** Three levels: *glance* (dashboard cards), *scan* (lists and tables), *study* (detail views). Advanced controls live behind a deliberate reveal.
5. **Show, then act.** Preview before commit for every consequential operation, especially AI operations. Diffs, plans and previews are the primary trust mechanism.
6. **Undo over confirm.** Prefer reversibility to interruption. Modal confirmations are reserved for the genuinely irreversible.
7. **Explain everything.** Every AI output, automated decision, permission state and metric offers a "why" affordance in one click.
8. **Consistent spatial memory.** Elements stay where they are. Navigation, inspector and assistant occupy fixed zones. Users build muscle memory in days.
9. **Respect the discipline.** Render LaTeX, chemical structures, code with syntax highlighting, and citations natively. Nothing signals "this tool was not made for you" faster than mangled equations.
10. **Accessible by construction.** WCAG 2.2 AA is a build gate, not a retrofit. Contrast, focus order, ARIA semantics, reduced motion and screen-reader parity are tested every release.

### 20.3 Visual Language

| Element | Specification |
|---|---|
| **Typography** | UI: Inter (variable). Reading/long-form: a humanist serif for document bodies. Code/data: JetBrains Mono. Type scale 12/13/14/16/20/24/32/40 with a 1.25 modular ratio; body line-height 1.6 |
| **Colour** | Near-monochrome foundation (12-step neutral ramp). One primary accent (deep indigo `#4F46E5` family) used sparingly for primary actions and active state. Semantic colours: success green, warning amber, danger red, info blue, AI violet — each with accessible on-colour text pairs |
| **AI identity** | All AI surfaces carry a consistent violet accent and a subtle "sparkle" mark, so users can always tell instantly what came from a model versus a human |
| **Spacing** | 4 px base grid; 8 px rhythm; 16/24 px section separation; content max-width 720 px for reading surfaces |
| **Elevation** | Four levels only: flat, subtle border, card shadow, modal shadow. No decorative depth |
| **Radius** | 6 px controls, 10 px cards, 14 px modals — soft but not playful |
| **Iconography** | Single consistent line-icon set, 1.5 px stroke, 20/24 px sizes; artefact types have distinct, learnable glyphs |
| **Motion** | 150 ms for state changes, 250 ms for panel transitions, spring easing for direct manipulation. Motion communicates causality only. Full `prefers-reduced-motion` support |
| **Dark mode** | First-class, designed independently (not an inverted filter); default follows system |
| **Data visualisation** | Restrained palette, direct labelling over legends, no 3D, no gratuitous animation; every chart has an accessible data-table equivalent |

### 20.4 Interaction Patterns

| Pattern | Application |
|---|---|
| **Command palette** | Universal entry point; six modes (§7.5) |
| **Inspector panel** | Contextual metadata/versions/links/permissions for the current selection — never a separate page |
| **Inline editing** | Click to edit metadata in place; autosave with a subtle saved indicator; no "Edit" mode toggle |
| **Drag and drop** | Files into spaces, artefacts onto entities to link, cards to reorder dashboards — always with a clear drop target and an undo toast |
| **Bulk selection** | Shift/Ctrl-click, select-all-matching-filter, with a persistent action bar showing exactly how many items are affected |
| **Optimistic UI** | Actions appear instantly; failures roll back with a clear, non-blaming explanation |
| **Empty states** | Always instructive: what this is, why it matters, one primary action, one example |
| **Loading** | Skeletons matching final layout; never spinners for > 400 ms; progress with meaning ("Analysing 1,203 of 12,847 items") |
| **Notifications** | Toasts for confirmations with inline undo; the notification centre for anything requiring action; nothing that blocks |
| **AI interaction** | Three modes coexist: *ambient* (proactive cards), *inline* (selection → AI action), *conversational* (assistant dock). Never chat-only |
| **Errors** | Plain language, cause, consequence, and a recovery action. Never an error code alone. Never blame the user |

### 20.5 Responsive & Platform Strategy

| Surface | Strategy |
|---|---|
| **Desktop web (primary)** | Full three-zone layout; density controls (comfortable/compact); multi-pane and split views; the "deep work" surface |
| **Tablet** | Two-zone with collapsible context pane; annotation-optimised (reading and marking PDFs, giving feedback) |
| **Mobile** | *Capture, review, decide* — not deep work. Bottom navigation: Today, Search, Capture, Assistant, Profile. Optimised for scanning documents, approving requests, voice notes, and answering "where is that file?" while walking to class |
| **Desktop client** | Native file-system integration with placeholder/on-demand files; offline access; drag-drop from Explorer/Finder; right-click "Save to AcademicOS" |
| **Browser extension** | Save papers and pages with metadata, capture citations, one-click ingest from journal sites |

### 20.6 AI User Experience Rules

1. **AI is a proposal engine, never an autocrat.** Every AI action is a proposal until a human accepts, except for reversible, low-risk classification within confidence thresholds.
2. **Always visibly labelled.** Violet accent and sparkle mark on every AI-touched surface.
3. **Always cited.** Sources are shown inline and openable in one click.
4. **Always honest about uncertainty.** Confidence is displayed as clear language ("high confidence", "needs your check"), not as false-precision percentages in the primary view.
5. **Always interruptible.** Long AI operations stream, show progress, and can be stopped without losing partial results.
6. **Always improvable.** Every output has correction affordances; every correction teaches the system and the user sees that it did.
7. **Never a dead end.** If the AI cannot help, it says so and offers a manual path.
8. **Never creepy.** No AI commentary on individual performance, no unsolicited judgements about people, no surveillance framing in analytics.

### 20.7 Onboarding & Learnability

- **Progressive onboarding:** teach three features on day one, three more in week one, advanced capabilities when behaviour indicates readiness. Never a 12-step tour.
- **Contextual help:** inline explainers on every non-obvious concept (what a Smart Folder is; why this artefact is here), dismissible permanently.
- **Templates and examples** as the fastest teacher: a new user sees a fully populated example course/project before building their own.
- **In-product academy:** short role-based paths ("Set up your semester in 10 minutes", "Prepare for accreditation").
- **Measurable learnability:** time-to-first-value, feature discovery rate, and help-search terms tracked as product metrics; anything users repeatedly search help for is a design defect.

### 20.8 Design System Governance

A single versioned design system (tokens → primitives → components → patterns → templates) shared by web, desktop and mobile. Tokens are the contract: colour, spacing, typography, radius, elevation, motion and semantic aliases are defined once and consumed everywhere, including by tenant branding overrides (which may change accent, logo and typography within accessibility guardrails, and nothing else). Every component ships with accessibility specifications, keyboard behaviour, empty/loading/error states, and dark-mode variants before it can be used in production.

---

# APPENDICES

---

## Appendix A — Glossary

| Term | Definition |
|---|---|
| **Artefact** | Any stored knowledge object (file, note, record) with identity, metadata, versions and relationships |
| **Entity** | An academic domain object (course, project, grant, scholar, publication, dataset, committee) |
| **Space** | A workspace container grouping artefacts and entities for a purpose and an audience |
| **Projection** | A generated view of the knowledge graph (structural, entity, temporal, semantic) |
| **Smart Folder** | A saved query that behaves like a folder and updates automatically |
| **Chunk** | A retrieval-sized segment of an artefact used for embedding and grounding |
| **Grounding** | Constraining AI output to retrieved, cited content from the authorised corpus |
| **Provenance** | The recorded chain of how an artefact came to exist |
| **Evidence Mapping** | The link between an artefact and an accreditation criterion |
| **Review Queue** | Where low-confidence AI proposals await human confirmation |
| **PDP / PEP** | Policy Decision Point / Policy Enforcement Point — the authorisation kernel |
| **CO / PO / PSO** | Course Outcomes / Programme Outcomes / Programme Specific Outcomes |
| **DMP** | Data Management Plan required by research funders |
| **CRediT** | Contributor Roles Taxonomy for scholarly attribution |
| **RAG** | Retrieval-Augmented Generation |
| **RRF** | Reciprocal Rank Fusion — merging multiple ranked result lists |
| **FAIR** | Findable, Accessible, Interoperable, Reusable |
| **IQAC** | Internal Quality Assurance Cell (Indian higher-education quality body) |

## Appendix B — Integration Catalogue (priority order)

| Priority | Integrations |
|---|---|
| **P0 (R1)** | Google Drive, OneDrive/SharePoint, Dropbox, Gmail/Outlook, ORCID, Crossref, Zotero, Mendeley, Google/Microsoft SSO |
| **P1 (R2)** | Moodle, Canvas, Blackboard (LTI 1.3), Scopus, Web of Science, PubMed, GitHub, GitLab, Overleaf, Turnitin, institutional SAML/Shibboleth, SCIM/HRIS |
| **P2 (R3)** | DSpace, Dataverse, Zenodo, Figshare, OpenAlex, Unpaywall, DOAJ, Slack, Teams, Zoom, national funder portals, Samarth/regional ERPs, DOI minting (DataCite) |
| **P3 (H4)** | Journal submission systems, national research information systems, instrument/LIMS vendors, publisher APIs, benchmarking consortia |

## Appendix C — Risk Register (top risks)

| # | Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R1 | **Cross-tenant data leakage** | Catastrophic (company-ending) | Low | Isolation at every layer; automated cross-tenant tests on every deploy; per-tenant keys; external audit |
| R2 | **AI hallucination in compliance or assessment output** | Severe (institutional and reputational) | Medium | Grounding, citation verification, mandatory human-in-loop on consequential outputs, refusal behaviour |
| R3 | **Adoption failure — faculty ignore the tool** | Existential (commercial) | Medium-High | Individual-first value; 10-minute time-to-value; zero manual metadata; the "Reveal" moment; champion programme |
| R4 | **Migration quality below expectation** | High (trust collapse at first impression) | Medium | Preview-before-commit; per-item review; conservative confidence thresholds; source never modified |
| R5 | **AI cost exceeding unit economics** | High | Medium | Small-model-first routing, caching, budgets, batch processing, continuous cost telemetry |
| R6 | **Scale bottleneck in vector or graph tier** | High | Medium | Per-tenant sharding from day one; load tests at 10× projected volume; quantisation strategy |
| R7 | **Long enterprise sales cycles starve runway** | High | High | PLG bottom-up motion funding the enterprise motion; department-level land points |
| R8 | **Regulatory change (AI/data) invalidating a design** | Medium | Medium | Residency and model abstraction built in; policy configurability; compliance roadmap tracked quarterly |
| R9 | **Incumbent bundles a competing feature (Microsoft/Google)** | High | Medium | Domain depth they will not build; standards-based interop; institutional switching costs via the graph |
| R10 | **Key-person dependency in AI evaluation quality** | Medium | Medium | Golden sets and eval harness as versioned assets, not tribal knowledge |

## Appendix D — KPI Tree

```
NORTH STAR: Weekly Active Artefact Interactions per Active Academic
│
├── ACQUISITION      signups · institution pipeline · referral coefficient
├── ACTIVATION       time-to-first-value · migration completion · first AI success
├── ENGAGEMENT       DAU/WAU/MAU · artefacts ingested · searches · AI queries ·
│                    entities linked · workflows completed
├── RETENTION        D7/D30/D90 · semester-over-semester return · corpus completeness
├── QUALITY          classification acceptance · search success · AI trust index ·
│                    citation accuracy · p95 latency · availability
├── EXPANSION        seats per tenant · module adoption · NRR · department→institution
└── EFFICIENCY       AI cost/user · storage cost/TB · support tickets/user · CAC payback
```

## Appendix E — Indicative Release Plan

| Release | Months | Scope | Exit Criteria |
|---|---|---|---|
| **R0 — Alpha** | 0–4 | Ingest, storage, versioning, basic search, artefact viewer, personal space | 25 design-partner academics using it weekly |
| **R1 — MVP / PLG** | 5–9 | AI classification + metadata, hybrid search, assistant with citations, courses, publications, migration tooling, naming engine | 1,000 active academics; 85% classification acceptance; D30 ≥ 55% |
| **R2 — Institution** | 10–18 | Supervision, grants, compliance frameworks, workflows, analytics, LMS/SSO/SCIM, mobile + desktop clients, agents (first three) | 5 institutional customers; 10,000 users; SOC 2 Type II |
| **R3 — Platform** | 19–30 | Public API, marketplace, discipline packs, on-prem option, multi-region, advanced agents, federated features | 50 institutions; 100,000 users; ISO 27001 |
| **R4 — Network** | 31–48 | Research graph federation, funder integrations, benchmarking, research intelligence | Consortium deals; category leadership |

## Appendix F — Open Questions & ADR Backlog

| # | Question | Owner | Needed By |
|---|---|---|---|
| Q1 | Neo4j vs. Apache AGE for the graph tier — operational cost vs. traversal performance at 300B edges | Architecture | Pre-R1 |
| Q2 | Self-hosted vs. API embeddings — cost, quality and residency trade-off | AI Eng | Pre-R1 |
| Q3 | Pricing architecture: per-seat vs. storage+AI consumption vs. institutional flat fee | Product | Pre-R1 |
| Q4 | Depth of native editing (block editor) vs. pure integration with M365/Google/Overleaf | Product/Design | R2 |
| Q5 | Default retention and version-thinning policy — what is safe and defensible academically? | Compliance | Pre-R2 |
| Q6 | Whether cross-tenant anonymised benchmarking is acceptable to institutions at all | Product/Legal | R3 |
| Q7 | Discipline-pack extensibility model — configuration only, or sandboxed plugin code? | Architecture | R3 |
| Q8 | On-prem deployment scope: full platform or a hybrid metadata-managed model? | Architecture | R3 |

---

## Document Sign-Off

| Role | Responsibility | Status |
|---|---|---|
| Product Management | Vision, personas, journeys, requirements, prioritisation, KPIs | Approved |
| Senior Software Architect | Modules, data, storage, versioning, search, scalability, security architecture | Approved |
| AI Engineering | AI architecture, RAG, agents, evaluation, guardrails, cost model | Approved |
| UX Design | Navigation, dashboards, UI philosophy, accessibility, design system | Approved |
| Security & Compliance | Threat model, controls, certifications, privacy | Pending external review |
| Engineering Leadership | Feasibility, staffing, release plan | Pending |

**Next steps:** (1) resolve Appendix F questions Q1–Q3 via ADRs; (2) produce high-fidelity prototypes of the Migration Reveal and the Faculty Dashboard — the two screens that determine adoption; (3) build the AI evaluation golden set with design partners before writing production prompts; (4) run a 25-academic design-partner alpha before committing to the R1 scope.

*End of Software Requirements Specification v1.0.*
