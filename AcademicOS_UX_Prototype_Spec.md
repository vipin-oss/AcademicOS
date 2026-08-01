# AcademicOS — Clickable UX Prototype Specification

> **Status of prior work:** The SRS, UI Spec, AI Architecture, Object-Centric Blueprint, Four Pillars Extension, and Persona Journeys are **final and frozen**. This document introduces **no new architecture or redesign** — it specifies the *interface* of that final system as a clickable prototype.
> **Deliverable:** A complete UX prototype specification (the Figma-equivalent brief). Loads into Figma as Frames + Components + Variants + Interactions. **No code. No implementation. After this, development begins.**
> **Design stance:** Senior Product Designer. Inspirations: **Notion** (calm, block-based), **Linear** (density, speed, issue states), **Apple** (clarity, motion, dark mode), **Raycast** (command palette, ⌘K-first), **Cursor** (AI inline, suggestion cards), **Microsoft Loop** (fluid components, workspaces).

---

## 0. HOW TO READ THIS SPEC (Prototype Map)

The prototype is a set of **Frames** (screens) wired by **Hotspots** into **Flows**. Each Frame is built from **Components** with **Variants/States**. This document enumerates:

- **§1 Design Language & Tokens** — the visual system (Figma Variables).
- **§2 Grid, Layout & Responsive** — 1440px desktop-first, breakpoints.
- **§3 Global Shell** — the persistent app frame (Topbar, Sidebar, Command Palette, Right Panel, Statusbar).
- **§4 Frame Index** — every Screen / Dialog / Panel as a named Frame.
- **§5 Component Specifications** — Cards, Tables, Forms, Dialogs, Timeline, Graph, AI Panel, Right Sidebar, Search Results, Workspaces, Notifications, Empty/Loading/Error, Keyboard, Hover/Motion.
- **§6 State Matrix** — component × state coverage.
- **§7 Clickable Flow Map** — how Frames connect (hotspots).
- **§8 Motion & Interaction Specification** — animations, transitions, micro-interactions.
- **§9 Accessibility, Theming & Prototype Build Notes.**

---

## 1. DESIGN LANGUAGE & TOKENS

### 1.1 Philosophy
- **Calm by default, dense on demand.** Generous whitespace, but information-rich when the user wants it (Linear-like).
- **One accent.** A single indigo/violet for actions; everything else is neutral. Status uses a restrained 4-color system.
- **Motion is meaning.** Every transition explains a spatial relationship (Apple). No decoration without purpose.
- **Command-first.** ⌘K opens everything; the mouse is optional (Raycast).

### 1.2 Color Tokens (Light / Dark)

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg.app` | #F7F7F5 | #0E0E10 | App background |
| `bg.surface` | #FFFFFF | #161618 | Cards, panels |
| `bg.surface-2` | #FBFBFA | #1C1C1F | Sidebar, inset |
| `bg.hover` | #F2F2F0 | #232327 | Row hover |
| `bg.active` | #ECECFE | #2A2540 | Selected row |
| `text.primary` | #1A1A1A | #EDEDED | Headings, body |
| `text.secondary` | #6B6B6B | #A0A0A6 | Sub-labels |
| `text.tertiary` | #9C9C9C | #6E6E76 | Hints, captions |
| `border.subtle` | #ECECEC | #26262A | Hairlines |
| `border.strong` | #DCDCDA | #34343A | Inputs |
| `accent` | #5B5BD6 | #7C7CF0 | Primary action, links |
| `accent.hover` | #4F4FC9 | #8E8EFF | Hover |
| `accent.subtle` | #EEEEFB | #211E33 | Tint backgrounds |
| `success` | #18794E | #34C98C | Done, positive |
| `warning` | #B25C00 | #E0A040 | Attention |
| `danger` | #C0392B | #F06A5C | Error, critical |
| `info` | #2563EB | #5B9CFF | Informational |

Glass surfaces (overlays): `rgba(255,255,255,0.72)` blur 20px (Light); `rgba(20,20,22,0.72)` (Dark).

### 1.3 Typography
- **Family:** Inter (UI), SF Pro fallback via system stack; **Mono:** JetBrains Mono / SF Mono for IDs, code, CLI-style hints.
- **Scale (px / weight / line):** Display 30/600/36 · H1 22/600/28 · H2 18/600/24 · H3 15/600/20 · Body 14/400/20 · Small 13/400/18 · Caption 12/500/16 · Micro 11/500/14 (uppercase for labels).
- **Tabular nums** for tables, dates, metrics.

### 1.4 Spacing & Radius
- **Spacing scale:** 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 (4px base).
- **Radius:** `r-sm` 6 · `r-md` 8 · `r-lg` 12 · `r-xl` 16 · `r-pill` 999.
- **Elevation:** `sh-sm` 0 1px 2px rgba(0,0,0,.04) · `sh-md` 0 4px 14px rgba(0,0,0,.06) · `sh-lg` 0 16px 40px rgba(0,0,0,.12).

### 1.5 Motion Tokens
- **Duration:** `t-fast` 120ms · `t-base` 200ms · `t-slow` 280ms.
- **Easing:** `e-out` cubic-bezier(.22,1,.36,1) · `e-in` cubic-bezier(.4,0,.2,1) · `spring` (stiffness .9, damping .8).
- **Reduced motion:** all durations → 0; cross-fades only.

---

## 2. GRID, LAYOUT & RESPONSIVE

- **Desktop canvas:** 1440 × 900 (default Frame). Content max-width 1320, centered with 24px gutters.
- **App frame:** Left Sidebar 244px (collapsible to 56px) · Right Panel 320px (toggle) · Topbar 56px · Statusbar 28px.
- **Breakpoints:** `≥1440` full · `1280` sidebar 220 · `1024` sidebar 56 auto · `768` sidebar overlay drawer · `375` mobile (single column, bottom tab bar — out of primary scope but specified for responsive integrity).
- **Auto-layout:** every Frame uses vertical/horizontal auto-layout with fixed-sidebar + flexible-center + fixed-right.

---

## 3. GLOBAL SHELL (Frame: `App_Shell`)

Persistent across all screens. Clicking any nav item swaps the **center workspace** only; Sidebar, Topbar, Right Panel, Statusbar persist.

### 3.1 Topbar (56px)
- Left: **Spaces** dropdown (avatar + name) · **breadcrumb** (Workspace › Object › section).
- Center: **Global Search** pill ("Search or ask… ⌘K") — click opens Command Palette.
- Right: **AI ⚡** quick button · **🔔 Notifications** (badge) · **@ avatar** (profile/menu) · **theme toggle**.
- Hairline bottom border; surface-2 background.

### 3.2 Left Sidebar (244px)
- **Workspace Switcher** (top): current Workspace chip with type icon; click → Workspace picker popover (Raycast-style list).
- **Primary nav** (grouped, from Object Blueprint §1.3 / Pillars §1.3):
  - *Focus:* Brain · Inbox · Search · Timeline
  - *Workspaces:* Teaching · Research · Grant · Committee · Event · Student · Personal (+ "More")
  - *System:* Workflows · Insights · Memory · Settings
- **Favorites / Recent** (collapsible).
- Hover: row bg `hover`; active: `accent.subtle` text `accent`; collapse toggle (⌘B).

### 3.3 Command Palette (Frame: `Overlay_CommandPalette`)
- Triggered ⌘K from anywhere. Centered modal (640px) with blurred backdrop.
- Input + categorized results: **Jump** (Objects), **Actions** (New Task, Summarize, Link…), **Ask AI** (natural language), **Navigate** (screens).
- Fuzzy match, arrow-key nav, ⏎ to execute, `→` to preview, `Esc` to close. Apple/Raycast feel: instant, no spinner for local.

### 3.4 Right Panel (320px, Frame: `RightPanel_Inspector`)
- Contextual **Inspector** for the focused Object: metadata, relationships mini-graph, activity peek, AI summary toggle.
- Toggle ⌘\ . On narrow screens becomes a slide-over.

### 3.5 Statusbar (28px)
- Left: **sync ●** (green), **index-lag ⏱** chip ("Indexed 2m ago") — from AI Architecture.
- Center: **degradation banner** (only when active, §5.13) — "AI running in reduced mode."
- Right: storage used · **? help** · **keyboard ⌘/**.

---

## 4. FRAME INDEX (Every Screen as a Frame)

> Each Frame below is a clickable screen or overlay. Numbers in [brackets] = Flow connections (§7).

### 4.1 Primary Screens
- `Screen_Brain_AP` … `Screen_Brain_Dean` — **Brain Home** (8 persona variants; spec in §4.10). [→ Inbox, Timeline, Object, Search, AI]
- `Screen_Inbox` — Universal Inbox (channels, triage). [→ Object, Settings]
- `Screen_Search` — Universal Search results (List/Gallery/Graph tabs). [→ Object, AI]
- `Screen_Timeline` — Universal Timeline (past/future, filters). [→ Object]
- `Screen_Workspace_{type}` — Workspace detail with Frame switch (Detail/List/Board/Graph/Canvas/Calendar). [→ Object]
- `Screen_Object_{type}` — Object Detail (generic template + type layouts: Faculty, Student, Course, Publication, Grant, Meeting, Committee, Event, Task, Document, Purchase, Budget, Journal, Conference, Dataset, Software, Lab, ResearchArea). [→ AI, RightPanel, Timeline, Link]
- `Screen_Workflows` — Workflow library + instances. [→ Instance, New]
- `Screen_Insights` — Proactive Insights inbox. [→ Object, Approve]
- `Screen_Memory` — Memory browser (by type/time). [→ Object]
- `Screen_Settings` — sub-pages: Personal, Space, Members, Integrations, AI&Models, Storage, Compliance, Appearance, Notifications, API. [→ Dialogs]
- `Screen_Notifications` — full notification feed. [→ Object]
- `Screen_Onboarding` — first-run workspace setup. [→ Brain]

### 4.2 Overlays / Dialogs (Frames)
- `Dialog_NewObject` (generic + typed) · `Dialog_Upload` (with auto-classify preview) · `Dialog_Link` (relationship picker) · `Dialog_Task` · `Dialog_Approval` · `Dialog_VersionHistory` · `Dialog_Properties` (metadata editor) · `Dialog_AIConfig` · `Dialog_WorkflowBuilder` · `Dialog_SaveSearch` · `Dialog_InviteMember` · `Dialog_Confirm` (destructive) · `Dialog_Export` · `Dialog_Settings_*`.
- `Panel_AIChat` — AI Assistant (also a right-dockable Frame).
- `Popover_EntityPicker` · `Popover_Filter` · `Popover_Mention` · `Popover_UserMenu` · `Popover_WorkspaceSwitcher` · `Popover_Datepicker` · `Toast_*` (success/info/warning/error).

### 4.3 System Frames
- `Screen_Login` (SSO + first-30s greeting) · `Screen_404` · `Screen_NoPermission` · `Screen_Offline` (degradation) · `State_Empty_*` · `State_Loading_*` · `State_Error_*`.

---

## 5. COMPONENT SPECIFICATIONS

### 5.1 Cards (Frame component `Card`)
- **Variants:** `default`, `interactive`, `selected`, `compact`, `stat`.
- **Anatomy:** icon/type-badge · title · 1–2 meta lines · optional action toolbar (appears on hover) · optional right-status chip.
- **Hover (interactive):** bg→`hover`; subtle `sh-sm`→`sh-md`; action toolbar fades in (top-right, ⌘-style icons: open, summarize, link, more). Title color→`accent` on hover.
- **Selected:** left 2px `accent` rail + `bg.active`.
- **Used for:** Brain cards, search results, workspace items, insight cards, memory cards.

### 5.2 Tables (Frame component `Table`)
- **Density:** comfortable (row 44px) / compact (32px, toggle).
- **Columns:** sortable headers (⌘-click multi-sort), resize handles, frozen first column (name).
- **Rows:** hover `bg.hover`; select → checkbox + `bg.active`; inline status pills; row-click → Object detail (right panel preview or navigate).
- **Bulk bar:** on multi-select, a sticky action bar appears (Link, Tag, Assign, Archive, Export).
- **Empty/Loading/Error:** dedicated states (§5.11–5.13).

### 5.3 Forms (Frame component `Form`)
- **Fields:** text, textarea (auto-grow), select, multiselect (token chips), date, user-picker, rich (block) editor, file-drop.
- **Validation:** inline, below-field, `danger` text + 1px `danger` border on error; success check on blur-valid.
- **AI-assist:** a small **⚡** inside relevant fields (e.g., title, description) → "Draft with AI" inline suggestion card (Cursor-style) that can be accepted (Tab) or dismissed.
- **Footer:** Cancel (ghost) + Primary (accent, disabled until valid). Sticky on scroll.

### 5.4 Dialogs / Modals (Frame component `Dialog`)
- **Sizes:** sm 420 · md 560 · lg 720 · xl 920. Centered, `sh-lg`, `r-xl`, backdrop blur.
- **Open animation:** scale .96→1 + opacity 0→1, `t-base` `e-out` (Apple). Close: reverse; `Esc` / backdrop-click / ✕.
- **Compose:** header (title + subtitle + ✕) · body (auto-layout) · footer (actions). Scroll body only.
- **Destructive (`Dialog_Confirm`):** warning icon, `danger` confirm button (requires type-to-confirm for irreversible), "Cancel" emphasized.

### 5.5 Timeline (Frame `Timeline`)
- Two modes:
  - **Universal Timeline** (screen): central vertical/horizontal rail, cards placed by date, past (left/cool) → future (right/warm); filter chips (type, person, space); "Today" marker; expandable clusters ("+6 more that week").
  - **Object Timeline** (inside Object detail): compact vertical list — icon · verb · object · timestamp · actor; grouped by day; hover shows source link.
- **Interaction:** hover card → peek preview; click → navigate; drag to pan (future mode); `⌘+scroll` zoom.

### 5.6 Knowledge Graph (Frame `Graph`)
- **Canvas** with force-directed nodes (Objects) + typed edges (color/pattern per relationship).
- **Nodes:** rounded squares with type icon + label; size by centrality; selected node gets `accent` ring + halo.
- **Edges:** labeled on hover; `contradicts` = dashed red, `cites` = thin gray, `funds` = green, etc.
- **Hover node:** lifts `sh-md`, dims non-neighbours (Apple focus), shows mini-toolbar (open, expand neighbourhood, link).
- **Click node:** open detail or expand ego-graph one ring. **Pan/zoom** spring-eased; **fit** button.
- **Empty graph:** friendly prompt to "Link your first object."

### 5.7 AI Panel / AI Chat (Frame `Panel_AIChat`)
- **Scope selector** (All / Space / Folder / Selection) — chip row.
- **Message stream:** user right-aligned bubble; assistant left with **citation cards** (quote + source chip, expand on hover) and **proposal cards** (editable suggestion: "Draft email", "Add to note", "Create summary" — Accept / Edit / Dismiss).
- **Source panel:** collapsible right-inside list of every chunk used, with confidence.
- **Typing:** pulsing dots + "Retrieving…/Thinking…" status (Linear/Apple restraint). Streaming text reveals char-by-char (`t-base`).
- **Agent console** (toggle): step list with status (pending/running/done/needs-approval); approval inline; undo available.
- **Toolbar:** regenerate, explain, copy, report wrong, attach, set scope.

### 5.8 Right Sidebar / Inspector (Frame `RightPanel_Inspector`)
- Tabs: **Overview** (key metadata, owner, dates) · **Relationships** (mini ego-graph + list) · **Activity** (recent) · **AI** (summary + chat-launch).
- Sticky header with Object type icon + title + ⌘ actions (link, share, more).
- Collapses to a thin rail showing only the type icon when narrow.

### 5.9 Search Results (Frame `Screen_Search`)
- **Input bar** (persistent, with mode chips: Keyword/Semantic/AI/NL).
- **Tabs:** List · Gallery · Graph. **Facets** left (type, entity, date, sensitivity, tag). **Index-lag chip** shows freshness.
- **List result:** type icon · title · snippet (matched term highlighted) · breadcrumb (entity path) · "why matched" on hover · actions on hover (open, summarize, ask AI, link, save).
- **AI mode result:** answer block with citation cards + "sources" expander + "refine" input.
- **Empty/No-result:** helpful state with relaxed-filter suggestion (§5.11).

### 5.10 Workspaces (Frame `Screen_Workspace_{type}`)
- **Header:** Workspace name + type chip + member avatars + "Automations" + "Insights" counters + frame switch.
- **Frame switch** (segmented control): Detail · List · Board · Graph · Canvas · Calendar · Map.
  - **Board:** Kanban columns by status/type; cards drag between; WIP subtle.
  - **Canvas:** free-form; place Object cards, draw relationship arrows, sticky notes; zoom/pan.
  - **Calendar:** month/week/agenda; events colored by type; drag to reschedule (conflict toast).
- **Empty workspace:** "Add your first object" + template suggestions.

### 5.11 Empty States (Frame `State_Empty_*`)
- **Anatomy:** friendly illustration (line-art, `accent.subtle`) · headline (not "No data") · 1-line helper · primary action + secondary.
- **Examples:** No objects yet → "Bring your knowledge in" + Upload/Connect Drive; No search results → "Try a broader query" + relax filters; No insights → "All quiet — we'll watch for you"; No relationships → "Link your first object."

### 5.12 Loading States (Frame `State_Loading_*`)
- **Skeletons:** shimmer (animated gradient sweep `t-slow`) matching final layout (cards/rows/sidebar) — never spinners for layout.
- **Inline:** buttons show spinner-in-button + disabled; AI "Retrieving…" status; graph shows faint nodes fading in (staggered `t-base`).
- **Full-screen first load:** centered logo + progress bar (determinate when known).

### 5.13 Error States (Frame `State_Error_*`)
- **Inline field error** (§5.3). **Toast error** (§5.14). **Empty-error screen:** icon + "Something went wrong" + "Retry" + "Open status" link.
- **No-permission:** lock illustration + "You don't have access" + request-access button (creates approval Task).
- **Degradation (Offline/Reduced):** Statusbar banner + relevant surface shows "AI unavailable — showing sources" (never silent). All errors are recoverable, never dead-ends.

### 5.14 Notifications & Toasts
- **Toast** (Frame `Toast_*`): top-right stack, auto-dismiss 4s (success/info), sticky until action (warning/error); slide-in from right `t-base` `e-out`; action button inline; ⌘-click "Dismiss all."
- **Notification card** (Inbox/feed): icon · title · snippet · source object link · timestamp · unread dot; bulk actions (mark read, snooze, unsubscribe).
- **Channels** (Inbox): Assigned · Approvals · Mentions · Shared · AI Digests · Deadlines · Watchlist · Flagged — each a filter.

### 5.15 Keyboard Shortcuts (global)
| Key | Action |
|---|---|
| ⌘K | Command Palette (omnipresent) |
| ⌘/ | Shortcut cheat sheet |
| ⌘F | Focus Search |
| ⌘N | New Object (context-aware to Workspace) |
| ⌘B | Toggle Sidebar |
| ⌘\ | Toggle Right Panel |
| ⌘E | Open AI Chat (scope = current) |
| ⌘↵ | Send in AI / submit form |
| Esc | Close overlay / deselect |
| G then H / I / S / T | Go Brain / Inbox / Search / Timeline |
| J / K | Move down/up in lists |
| ⌘J / ⌘K in list | Open item / Command on item |
| ? | Help |

Cheat-sheet overlay (⌘/) lists all, grouped, Raycast-style.

### 5.16 Hover / Interaction / Animation / Transition (summary — full in §8)
- **Hover:** rows/cards lift subtly; toolbars fade in; links underline-appear; buttons darken 1 step.
- **Focus:** 2px `accent` ring (accessible). 
- **Active/press:** scale .98 (`t-fast`).
- **Transitions:** panel slides (Right Panel 240ms `e-out`); dialog scale+fade; palette center; graph spring; AI stream; toasts slide; page changes cross-fade 160ms (no full reload feel).
- **Reduced motion:** honored globally.

---

## 6. STATE MATRIX (component × state)

| Component | States covered |
|---|---|
| Card | default · hover · selected · compact · loading · empty |
| Table | default · sorted · filtered · row-hover · row-selected · bulk · loading · empty · error |
| Form field | default · focus · filled · valid · error · disabled · AI-suggesting |
| Dialog | open · closed · sm/md/lg/xl · destructive · loading-submit |
| Timeline | past · future · filtered · clustered · empty |
| Graph | idle · node-hover · node-selected · neighbourhood · empty · loading |
| AI Panel | idle · retrieving · streaming · cited · proposal · agent-running · agent-approval · error |
| Right Panel | collapsed-rail · overview · relationships · activity · AI · empty |
| Search | keyword · semantic · AI · no-result · filtered · loading · index-lag |
| Workspace | detail · list · board · graph · canvas · calendar · empty |
| Toast | success · info · warning · error · stacking |
| Notification | unread · read · snoozed · grouped |
| Global | online · degraded · offline · no-permission |

---

## 7. CLICKABLE FLOW MAP (Hotspots → Frame)

```
LOGIN ──▶ BRAIN_HOME (persona variant by role)
BRAIN_HOME ──▶ INBOX | TIMELINE | SEARCH | OBJECT | AIChat | SETTINGS
SIDEBAR nav ──▶ WORKSPACE_{type} | INSIGHTS | MEMORY | WORKFLOWS | SETTINGS
OBJECT ──▶ AI_PANEL | RIGHT_PANEL | TIMELINE(tab) | LINK_DIALOG | TASK_DIALOG | VERSION_DIALOG | PROPERTIES_DIALOG
SEARCH ──▶ OBJECT | AI_PANEL (ask) | SAVESEARCH_DIALOG
COMMAND_PALETTE ──▶ any Frame / Action (New, Summarize, Link)
WORKFLOW_LIBRARY ──▶ WORKFLOW_INSTANCE ──▶ OBJECT/Task created
INSIGHTS ──▶ OBJECT (evidence) | APPROVAL_DIALOG (act)
INBOX ──▶ OBJECT | APPROVAL_DIALOG | TASK_DIALOG
SETTINGS ──▶ SETTINGS_*_DIALOG | INVITE_DIALOG | INTEGRATION_CONNECT
ERRORS ──▶ RETRY (back to source) | STATUS
```

Hotspot conventions: primary buttons → primary Frame; cards → detail; `⋯` → popover/menu; status chips → related Frame. Prototype uses Figma "On Click / While Hover / After Delay (loading)" interactions.

---

## 8. MOTION & INTERACTION SPECIFICATION

- **Page/screen change:** cross-fade 160ms; center content shifts 8px up→settle (`e-out`). No hard cuts.
- **Sidebar/Right Panel:** slide 240ms `e-out`; resize handle drag live.
- **Command Palette:** backdrop blur fades 120ms; panel scale .97→1 + fade 160ms; results filter with 80ms stagger.
- **Dialog:** scale .96→1 + fade 200ms; focus traps to first field.
- **Toast:** translateX 100%→0 200ms `e-out`; stack with 8px gap; exit fade+slide.
- **Graph:** nodes fade/scale in staggered 200ms; hover neighbour-focus 160ms; expand ring spring 220ms; pan/zoom `spring`.
- **AI streaming:** text reveal 20ms/char capped; citation cards slide-up 160ms on appear; proposal card pop 200ms `e-out`.
- **Board drag:** card lifts `sh-lg` + scale 1.02; column drop animates reflow 200ms.
- **Calendar drag:** event ghost follows cursor; conflict → red ring pulse + toast.
- **Skeleton shimmer:** 1200ms loop, gradient sweep L→R.
- **Micro-delight:** checkbox tick draws (SVG stroke 160ms); toggle slides; save = checkmark bounce.
- **All reversible; all respect `prefers-reduced-motion`.**

---

## 9. ACCESSIBILITY, THEMING & BUILD NOTES

- **Contrast:** text pairs ≥ 4.5:1 (tertiary ≥ 3:1 on large). Focus ring visible in both themes.
- **Keyboard:** full operability without mouse (§5.15); skip-link to center; logical tab order; ARIA roles for dialogs, menus, graphs (canvas has text fallback).
- **Theming:** Light/Dark via Figma Color Variables; auto by OS + manual toggle; `accent` swappable per Space (brand).
- **Figma structure:** 
  - **Variables** for all tokens (§1.2–1.5).
  - **Components** with Variants for each in §5 + §6 matrix.
  - **Frames** per §4; auto-layout + constraints set so responsive (§2) works.
  - **Prototype** tab wires §7 flows; **While Hover** for toolbars; **After Delay** for loading; **Overlays** for dialogs/palette/toasts.
- **Handoff:** this spec + Figma file = dev-ready. Component names map 1:1 to implementation components.

---

## 10. BRAIN HOME — PERSONA VARIANTS (Frame set `Screen_Brain_*`)

Built from `Persona_Journeys.md` first-30-seconds. Each Brain Frame shares a template: **Greeting line → My Day strip → Open Items → Persona cards → Timeline peek.** Only the cards + greeting vary:

| Frame | Greeting tone | Cards (left→right) |
|---|---|---|
| `Brain_AP` | Warm, urgent-aware | Teaching (at-risk) · Research/Grant (due Fri) · My Day · Open Items |
| `Brain_Assoc` | Steady, lab-focused | Lab (stuck/ontrack) · Reviews due · Grants (match) · Writing |
| `Brain_Prof` | Strategic | Approvals · Centre/Grants · People · Committees |
| `Brain_Scholar` | Quiet, deep-work | Manuscripts · Reading · Collaboration · Writing |
| `Brain_PhD` | Reassuring | My Path · Advisor · TA · Reading |
| `Brain_Office` | Operational | Pending Approvals · NAAC · Meetings · Purchases · Students |
| `Brain_Chair` | Departmental | Faculty · Budget · Accreditation · Students |
| `Brain_Dean` | Institutional | Departments · Approvals · Risks · Rankings · Opportunities |

Each card is interactive (§5.1): hover reveals "Open / Summarize / Ask AI"; click → relevant Frame (Workspace/Object/Insight). The greeting is editable-free, generated from the person's Workspaces + Inbox + Timeline + Memory (per Pillars).

---

*This specification is the final design artifact. It is complete, frozen, and ready to be loaded into Figma and built. No code follows from it; it precedes development.*
