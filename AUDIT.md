# AcademicOS — Complete Product Audit & Improvement Plan

**Auditor**: Arena AI Agent (Lead Product Architect / UX Designer / QA / Security / Full-Stack)
**Date**: 2026-08-18
**Commit**: ac02b44 (rev28)
**Scope**: Full codebase audit, professor workflow simulation, UX/security/performance analysis

---

## EXECUTIVE SUMMARY

AcademicOS is a well-architected academic information system with a solid foundation:
Clean Architecture backend, Universal Object model, claim-based extraction pipeline,
ACL/security, and AI integration. The technical core is production-grade.

**However, the professor-facing experience has significant UX debt.** The system exposes
too many internal concepts (claim states, predicate IDs, object types, routing modules)
to the user. The workflows are functional but not fluent. A professor would need
training to use this system effectively — which means it's not yet professor-first.

**The good news**: The architecture supports the right fixes without restructuring.
Most improvements are frontend-only or thin API adjustments.

---

## PART 1: WHAT IS ALREADY GOOD — DO NOT DISTURB

These are production-grade and must NOT be changed without strong justification:

1. **Clean Architecture backend** — domain/application/infrastructure layers are well-separated.
   The claim store, predicate catalogue, and extraction pipeline are correct.

2. **Universal Object model** — one table for all entity types with typed JSONB metadata.
   This is the right architecture for a 20-year system.

3. **Claim-based extraction pipeline** — Document → Extraction → Claim → Review → Confirm →
   Domain Object lifecycle is sound. The idempotency, dedup, and supersede patterns are correct.

4. **ACL/Security model** — owner-based with explicit grants, deny-by-default option,
   per-object scope propagation. Verified in acceptance testing.

5. **ClaimProjectionService (rev28)** — confirmed claims correctly project into domain
   objects with type inference, evidence validation, and ACL propagation.

6. **Search infrastructure** — FTS5 + outbox-driven indexing + backfill. Correct architecture.

7. **Notification lifecycle** — auto-resolution when review completes. Correct behavior.

8. **Auth flow** — JWT with refresh, session cookie for middleware, localStorage for tokens.
   Standard and correct.

9. **Extraction schemas** — data-driven field specs with synonyms. Additive, maintainable.

10. **Domain record router** — duplicate detection, provenance links, ACL propagation.
    Correct and idempotent.

---

## PART 2: PROFESSOR WORKFLOW SIMULATION

### Workflow 1: First Login → Empty Account
- **Current**: Dashboard shows "Dashboard" header + 4 quick action cards + empty state
- **Problem**: Empty state says "No documents yet" but the professor doesn't know WHERE to start
- **Verdict**: Acceptable but could be warmer. An onboarding wizard would help but is P3.

### Workflow 2: Upload Conference Certificate
- **Current**: Documents page → Single File tab → drag-drop → auto-analyze → shows extraction
- **Problem**: The Documents page has BOTH an upload section AND a table on the same page.
  The upload section takes up significant space. A professor uploading their first cert
  sees a confusing mix of upload area + empty table + filters.
- **Verdict**: P1 — Documents page layout needs redesign

### Workflow 3: Review Extracted Information
- **Current**: PendingReviewSection shows each field as a card with Confirm/Edit/Not Applicable
- **Problem**: For a conference certificate with 8-9 fields, the professor sees 8-9 separate
  cards. Each card has: field name, value, confidence badge, source evidence, source method,
  "Why am I seeing this?" text, and 3 action buttons. That's ~6 UI elements per field × 9 = 54
  elements to process.
- **Verdict**: P1 — Review workflow needs simplification. A table/list view would be more
  efficient. "Confirm All" button already exists (good) but the per-field view is too heavy.

### Workflow 4: Correct Wrong Information
- **Current**: Click Edit → inline input → Save
- **Problem**: Works correctly. The "correct" flow creates a new ASSERTED claim that supersedes
  the original. This is architecturally correct.
- **Verdict**: P3 — The edit experience is fine.

### Workflow 5: After Confirmation — What Happened?
- **Current**: After confirming all fields, the review section shows "Review complete" with a
  link to "View document". But the professor doesn't see WHAT was created.
- **Problem**: The ClaimProjectionService creates an Event, but the UI doesn't tell the professor
  "Your conference has been recorded as an Event." The projection happens silently.
- **Verdict**: P1 — Must show the professor what was created after confirmation.

### Workflow 6: Find an Event
- **Current**: Events page → table with type badge, dates, venue, department, status, priority
- **Problem**: The table shows 7 columns. For a professor with 50+ events, this is good.
  The filter dropdown includes all event types. The search works.
- **Verdict**: P2 — The events page is functional but the type badge shows the raw label
  (e.g., "Conference") which is correct after our rev28 changes.

### Workflow 7: Create an Event Manually
- **Current**: New Event → modal with 20+ fields organized in a grid
- **Problem**: A professor who just wants to log "I attended ICML 2025 on March 15-17" has
  to fill in: title, event code, event type, status, organizer, co-organizer, venue, mode,
  start date, end date, department, school, priority, tags, description, objectives, outcome,
  notes, registration counters, linked faculty/students/projects/grants/committees.
  That's 20+ fields. Most professors will never fill all of these.
- **Verdict**: P1 — Event form needs progressive disclosure. Show 5 essential fields by
  default, expand to show advanced fields.

### Workflow 8: Search Records
- **Current**: Search page with a text box. Results show object type, title, metadata.
- **Problem**: The search page is minimal. No faceted search, no filters, no sorting.
  A professor searching for "quantum" gets a flat list of results.
- **Verdict**: P2 — Search needs facets (type, date range, department) and better result cards.

### Workflow 9: Export Records
- **Current**: Settings → Export page with CSV export for events, publications, research, committees
- **Problem**: Export is buried in Settings. A professor who needs their CV data has to navigate
  to Settings → Export → select type → download CSV. This should be more prominent.
- **Verdict**: P2 — Export should be accessible from Records page and from individual module pages.

### Workflow 10: Notifications
- **Current**: Notifications appear as unread items. Auto-resolve when review completes.
- **Problem**: The notification system works correctly. The notification count is shown in the UI.
- **Verdict**: P3 — Notifications are functional.

### Workflow 11: Two-User ACL
- **Current**: Verified — User A cannot read User B's documents/events/publications.
- **Problem**: None. ACL is correct.
- **Verdict**: PASS — Do not change.

### Workflow 12: Re-analysis / Idempotency
- **Current**: Re-analyzing a document re-uses existing claims, doesn't create duplicates.
- **Problem**: None. Idempotency is correct.
- **Verdict**: PASS — Do not change.

---

## PART 3: COMPLETE FINDINGS

### P0 — Security, Data-Loss, Unusable Core Workflow

**None remaining.** All P0 issues were fixed in rev22-rev28.

### P1 — Major Professor Workflow Problems

#### P1-01: Documents Page Layout Confusion
- **Screen**: `/documents`
- **Current**: Upload section (Single/Multi tabs + drag-drop) AND document table AND filters
  all on the same page. The upload area dominates the top half.
- **Why bad**: A professor with 50 documents sees the upload area every time they visit
  the Documents page. The actual document list is pushed below the fold.
- **Fix**: Remove the inline upload section. Upload should be a button that opens a modal
  (which already exists: UploadModal). The Documents page should show: search + filters +
  document table. Upload button in the header.
- **Backend impact**: None
- **Complexity**: Low (frontend only)
- **Risk**: Low

#### P1-02: Review Workflow Too Heavy Per Field
- **Screen**: Document detail → PendingReviewSection
- **Current**: Each field is a separate card with 6+ UI elements and 3 buttons.
  9 fields = 54 interactive elements.
- **Why bad**: Professor spends 30+ seconds per field. For a conference certificate with
  9 fields, that's 4.5 minutes just to confirm what AI already extracted correctly.
- **Fix**: Replace per-field cards with a compact table view. Columns: Field | Value |
  Confidence | Actions. "Confirm All" button at top (already exists). Individual
  Edit/Reject only on hover or click. Reduce visual noise.
- **Backend impact**: None
- **Complexity**: Medium (frontend rewrite of PendingReviewSection)
- **Risk**: Low

#### P1-03: No Feedback After Confirmation
- **Screen**: Document detail → after confirming all fields
- **Current**: Shows "Review complete — your document information has been saved."
  Does NOT show what domain object was created.
- **Why bad**: Professor confirms 9 fields, then sees "saved" but doesn't know their
  Event/Publication was created. They have to navigate to Events page to find it.
- **Fix**: After confirming all fields, show: "✓ Conference 'ICQM-2024' has been recorded
  as an Event. [View Event]" with a link to the created domain object.
- **Backend impact**: The confirm-all endpoint already returns projection results. The
  frontend just needs to display them.
- **Complexity**: Low (frontend + minor API response enhancement)
- **Risk**: Low

#### P1-04: Event Creation Form Overload
- **Screen**: EventModal (New Event)
- **Current**: 20+ fields in a flat grid. No grouping, no progressive disclosure.
- **Why bad**: Professor who wants to log "Attended ICML 2025" sees fields for
  registration counters, linked committees, objectives, outcome, notes, etc.
- **Fix**: Progressive disclosure. Show 5 essential fields by default:
  Title, Type, Dates, Venue, Mode. "More details" expandable section for the rest.
  Pre-fill mode from event type (e.g., Conference → default mode = "Offline").
- **Backend impact**: None
- **Complexity**: Medium (frontend EventModal restructure)
- **Risk**: Low

#### P1-05: Multi-line Extraction Produces Bad Values
- **Screen**: Backend extraction pipeline
- **Current**: "Volume: 45 Issue: 2 Pages: 100-110" extracts `volume = "45 Issue: 2 Pages: 100-110"`
- **Why bad**: Creates invalid domain records. The CreatePublicationUseCase rejects bad
  data, so no incorrect records are created, but the professor sees confusing review items.
- **Fix**: In the label extractor (`_extract_label_value`), after finding "Label: value",
  truncate at the next known label keyword on the same line. Use the extraction schema's
  synonyms as stop words.
- **Backend impact**: Extraction pipeline change
- **Complexity**: Medium (label extractor enhancement)
- **Risk**: Medium (must not break existing extraction)

#### P1-06: "Paper Title" Synonym Overlap
- **Screen**: Backend extraction schemas
- **Current**: Both CONFERENCE_FIELDS.presentation_title and PUBLICATION_FIELDS.publication_title
  have "paper title" as a synonym. When both schemas are applied, "Paper Title: X" creates
  claims for both predicates.
- **Why bad**: Professor sees duplicate review items for the same value.
- **Fix**: Remove "paper title" from CONFERENCE_FIELDS.presentation_title. Conference
  certificates use "Presentation Title:" or "Title of Paper Presented:", not "Paper Title:".
  "Paper title" is a publication term.
- **Backend impact**: Extraction schema change
- **Complexity**: Low (data change)
- **Risk**: Low

#### P1-07: Backend Event Types Still 19
- **Screen**: Backend dtos/events.py
- **Current**: Frontend reduced to 10 types (rev28), but backend EVENT_TYPES tuple still
  has 19 values. The validation in CreateEventUseCase accepts any string from this list.
- **Why bad**: Inconsistency. Old data with types like "research_colloquium" still works
  (good) but new creation should match the frontend.
- **Fix**: Keep the backend EVENT_TYPES tuple as-is for backward compatibility, but add
  a mapping that normalizes old types to new types for display. The frontend already
  handles this via eventTypeLabel.
- **Backend impact**: None needed (frontend handles display)
- **Complexity**: None (already handled)
- **Risk**: None

### P2 — Important UX/Product Problems

#### P2-01: Sidebar Over-Engineering
- **Screen**: Sidebar
- **Current**: Sidebar has drag-drop reordering, visibility toggles, workspace creation,
  module selection, custom tabs. This is power-user functionality that 99% of professors
  will never use.
- **Why bad**: Adds complexity to the navigation. The "Customize" button at the bottom
  is confusing.
- **Fix**: Remove customization from the default sidebar. Keep it as a Settings option.
  Default sidebar: Home, Documents, Events, Research, Publications, Search, Settings.
- **Complexity**: Medium

#### P2-02: Records Page Is Just a Gateway
- **Screen**: `/records`
- **Current**: Shows 8 category cards (Publications, Research, Teaching, etc.) with counts.
  Clicking a card navigates to the module page.
- **Why bad**: Extra click. The professor has to go Records → Events instead of just Events.
- **Fix**: The sidebar already has direct links to modules. The Records page can remain
  as an overview/summary but shouldn't be the primary navigation path.
- **Complexity**: Low

#### P2-03: Search Page Too Minimal
- **Screen**: `/search`
- **Current**: Just a search box with results. No facets, no filters, no sorting.
- **Why bad**: Professor searching for "quantum" gets a flat list. Can't filter by type,
  date range, or department.
- **Fix**: Add facet filters: object type, date range, department. Add sort options:
  relevance, date (newest/oldest).
- **Complexity**: Medium

#### P2-04: Export Buried in Settings
- **Screen**: `/settings/export`
- **Current**: CSV export for events, publications, research, committees is in Settings.
- **Why bad**: Professor who needs their CV data has to navigate to Settings → Export.
- **Fix**: Add export buttons on each module page (Events, Publications, Research) and
  on the Records page.
- **Complexity**: Low

#### P2-05: No Bulk Operations on Events/Publications
- **Screen**: Events page, Publications page
- **Current**: Can only edit one event at a time. No bulk delete, bulk status change,
  bulk export.
- **Why bad**: Professor with 50 events who wants to mark all 2024 events as "Completed"
  has to edit each one individually.
- **Fix**: Add checkbox selection + bulk actions bar.
- **Complexity**: Medium

#### P2-06: Document Analysis Shows Technical Details
- **Screen**: DocumentAnalysisResult component
- **Current**: Shows "Document type: conference_certificate", "Confidence: High",
  "Category: Events", "AI assistance: No", then a list of fields with confidence scores.
- **Why bad**: "conference_certificate" is internal taxonomy. "AI assistance: No" is
  technical. The professor doesn't need to know the extraction mode.
- **Fix**: Show: "This is a Conference Certificate. AcademicOS found 8 pieces of
  information." Then list the fields. Remove technical details.
- **Complexity**: Low

#### P2-07: No Progress Indicator for Multi-Step Workflow
- **Screen**: Upload → Analyze → Review → Confirm
- **Current**: Each step happens independently. No visual progress indicator showing
  "Step 2 of 3: Review extracted information".
- **Why bad**: Professor doesn't know where they are in the workflow.
- **Fix**: Add a progress stepper: Upload → Review → Done.
- **Complexity**: Low

#### P2-08: "Object" Linking in Upload Modal Confuses Professors
- **Screen**: UploadModal → "Object" dropdown
- **Current**: Shows "— No linked object —" followed by academic objects.
- **Why bad**: "Object" is technical terminology. A professor doesn't think in terms of
  "linking objects". They think "this certificate is about a conference I attended."
- **Fix**: Rename to "Related to" with a hint: "Link this document to an existing
  record (optional)."
- **Complexity**: Low

#### P2-09: Notification Count Not Visible in Sidebar
- **Screen**: Sidebar
- **Current**: No notification badge on sidebar items.
- **Why bad**: Professor doesn't know they have pending items unless they visit the
  dashboard.
- **Fix**: Add notification badge on the Home sidebar item showing pending review count.
- **Complexity**: Low

#### P2-10: Search Results Don't Show Document Type
- **Screen**: Search results
- **Current**: Results show title and metadata but the document type badge is inconsistent.
- **Fix**: Show a clear type badge (Event, Publication, etc.) on each search result.
- **Complexity**: Low

### P3 — Polish/Enhancement

#### P3-01: Loading States Could Be Skeleton Screens
- **Current**: Some pages show "Loading..." text. Others show skeleton screens.
- **Fix**: Standardize on skeleton screens everywhere.

#### P3-02: Empty States Could Be More Helpful
- **Current**: "No documents yet. Upload your first document to get started."
- **Fix**: Add illustration + step-by-step guide for first-time users.

#### P3-03: Mobile Responsiveness Needs Testing
- **Current**: Sidebar collapses on mobile. Tables may overflow.
- **Fix**: Test and fix responsive breakpoints for all major pages.

#### P3-04: Accessibility (a11y) Audit Needed
- **Current**: Some aria-labels present. Color contrast may not meet WCAG AA.
- **Fix**: Run axe-core audit and fix violations.

#### P3-05: "AcademicOS" Branding in Sidebar
- **Current**: Shows "AcademicOS" with graduation cap icon.
- **Fix**: Allow customization of institution name in settings.

#### P3-06: AI Tip on Dashboard Is Static
- **Current**: Shows 3 hardcoded example queries.
- **Fix**: Rotate tips or show contextual suggestions based on the professor's data.

#### P3-07: Document Detail Page Shows Raw Predicate IDs
- **Screen**: `/documents/[id]` → review section
- **Current**: Uses `friendlyFieldName()` which maps predicate_ids to labels. This is
  correct but some predicates still show as "sanction_order_number" → "Sanction Order Number"
  instead of a more natural label.
- **Fix**: The fieldLabels.ts was expanded in rev28. Continue expanding coverage.

#### P3-08: Event Detail Page Shows Too Many Empty Fields
- **Screen**: `/events/[id]`
- **Current**: Shows all fields including empty ones (objectives, outcome, notes, etc.)
- **Fix**: Hide empty fields by default. Show "Add details" button to expand.

---

## PART 4: PRIORITIZED IMPLEMENTATION PLAN

### Tier 1 — Must Fix (P1, highest professor impact)

| ID | Change | Files | Complexity | Risk |
|---|---|---|---|---|
| P1-01 | Remove inline upload from Documents page | `documents/page.tsx` | Low | Low |
| P1-02 | Simplify review to table view | `PendingReviewSection.tsx` | Medium | Low |
| P1-03 | Show created record after confirmation | `PendingReviewSection.tsx`, `document_intake.py` | Low | Low |
| P1-04 | Event form progressive disclosure | `EventModal.tsx` | Medium | Low |
| P1-06 | Remove "paper title" from conference synonyms | `extraction_schemas.py` | Low | Low |

### Tier 2 — Should Fix (P2, important UX)

| ID | Change | Files | Complexity | Risk |
|---|---|---|---|---|
| P2-06 | Remove technical details from analysis result | `DocumentAnalysisResult.tsx` | Low | Low |
| P2-07 | Add progress stepper to upload workflow | `SimpleUpload.tsx` | Low | Low |
| P2-08 | Rename "Object" to "Related to" in upload | `UploadModal.tsx` | Low | Low |
| P2-04 | Add export buttons to module pages | Events/Publications pages | Low | Low |
| P2-01 | Simplify sidebar (remove customization from default) | `Sidebar.tsx` | Medium | Low |

### Tier 3 — Polish (P3)

| ID | Change | Complexity |
|---|---|---|
| P3-01 | Standardize loading states | Low |
| P3-02 | Better empty states | Low |
| P3-05 | Institution name customization | Low |
| P3-07 | Expand field label coverage | Low |
| P3-08 | Hide empty event detail fields | Low |

### Tier 4 — Defer (P1-05, P2-03, P2-05, P2-09, P2-10)

These are important but either have higher complexity or risk:

- **P1-05** (Multi-line extraction): Requires label-extractor redesign. Defer to separate pass.
- **P2-03** (Search facets): Requires backend search API changes. Defer.
- **P2-05** (Bulk operations): Requires significant frontend work. Defer.
- **P2-09** (Notification badge): Requires real-time count polling. Defer.
- **P2-10** (Search result badges): Minor. Defer.

---

## PART 5: ARCHITECTURE ASSESSMENT

### Database Model
**Verdict: Sound.** The Universal Object model with JSONB metadata is the right architecture
for a 20-year system. The claim-based extraction pipeline with supersede semantics is correct.
No restructuring needed.

### Frontend Architecture
**Verdict: Functional but needs UX layer.** The component structure is good (feature-based
organization). The hooks pattern is correct. The API client is well-designed. The issue is
UX debt, not architecture.

### Backend Architecture
**Verdict: Production-grade.** Clean Architecture with proper separation of concerns.
The claim store, predicate catalogue, extraction pipeline, and domain record router are
all correctly designed. No restructuring needed.

### AI Integration
**Verdict: Correctly designed.** AI is optional (deterministic-first). The enrichment
pipeline is separate from the core extraction. The assistant integration is clean.
No changes needed.

---

## PART 6: WHAT A WORLD-CLASS ACADEMIC SYSTEM WOULD NEED

Beyond the current feature set, a 20-year academic information system would eventually need:

1. **CV/Resume Generation** — One-click PDF CV from all confirmed records. (Not in current scope)
2. **Annual Report Generation** — Structured report for promotion/tenure committees.
3. **Collaboration** — Shared documents with co-authors, department-level visibility.
4. **Integration** — Google Scholar, ORCID, Scopus, DBLP imports.
5. **Mobile App** — For quick document scanning and review on the go.
6. **Multi-language** — Hindi/regional language document support.
7. **Offline Mode** — For areas with poor connectivity.

These are all future roadmap items, not current deficiencies.

---

## RECOMMENDATION

**Execute Tier 1 (5 changes) + Tier 2 (5 changes) in this pass.** These 10 changes will
transform the professor experience from "functional prototype" to "polished product" without
any backend architectural changes.

**Defer Tier 3 and Tier 4** to a follow-up pass.

**Do NOT touch** the backend architecture, database model, claim pipeline, ACL system,
search infrastructure, or notification system. They are production-grade.

---

*End of audit. Awaiting approval to implement.*
