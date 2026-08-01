# AcademicOS — Desktop UI/UX Specification

**Companion to:** `AcademicOS_SRS.md` v1.0
**Document:** UI Specification v1.0 — Desktop-First
**Design Language:** Microsoft Fluent 2 foundations · Notion-grade simplicity · Selective Glassmorphism
**Platforms:** Windows 11 (primary), macOS (parity), Web (Chromium/Safari/Firefox), Linux (best-effort)
**Date:** 31 July 2026
**Status:** Ready for high-fidelity prototyping

---

## Table of Contents

**Part I — Design Foundations**
- F1. Design DNA & Philosophy
- F2. Design Tokens (Colour, Type, Space, Radius, Elevation, Motion)
- F3. Light Mode & Dark Mode Systems
- F4. Glassmorphism Specification
- F5. Application Shell Anatomy
- F6. Window & Workspace Management
- F7. Universal Component Library
- F8. Menu Systems — Right-Click vs. Context Menus
- F9. Dialog & Overlay System
- F10. Global Keyboard Model
- F11. States: Empty · Loading · Error · Offline
- F12. Density, Accessibility & Motion Governance

**Part II — Screen Specifications**
1. Dashboard
2. Teaching
3. Research
4. Publications
5. Projects
6. Administration
7. Students
8. Calendar
9. AI Chat
10. Settings
11. Notifications
12. Search

**Part III — Appendices**
- A. Master Keyboard Shortcut Map
- B. Icon System
- C. Component Inventory & Coverage Matrix
- D. Motion Choreography Reference
- E. Design Do's and Don'ts

---

# PART I — DESIGN FOUNDATIONS

---

## F1. Design DNA & Philosophy

### F1.1 The Fusion Thesis

> **Fluent bones. Notion skin. Academic soul.**

We take three influences and assign each a strict job. Mixing them arbitrarily produces mush; assigning them domains produces coherence.

| Influence | What we take | What we deliberately reject |
|---|---|---|
| **Microsoft Fluent 2** | Material system (Mica, Acrylic), depth/elevation logic, motion curves, focus & keyboard rigour, window integration, icon geometry, high-contrast support, command surfaces (command bar, flyout, teaching callout) | Ribbon complexity, dense chrome, enterprise greyness, over-decorated controls |
| **Notion** | Content-first calm, generous whitespace on reading surfaces, near-invisible chrome, inline editing everywhere, block thinking, restrained monochrome palette, humane empty states | Everything-is-a-page ambiguity, weak data tables, slow perceived performance, no real keyboard model |
| **Linear (silent third influence)** | Speed, keyboard primacy, command palette centrality, crisp micro-interactions, opinionated defaults | Consumer-grade playfulness |

**The rule that resolves every conflict:** *Fluent governs structure and system integration; Notion governs content and calm; when they disagree, the surface the user is reading wins.*

### F1.2 The Five UI Laws

1. **Chrome recedes, content leads.** All navigation, toolbars and panels use neutral, low-saturation surfaces. Colour belongs to the user's data, status semantics, and the AI accent — nothing else.
2. **Every surface has exactly one primary action.** If a screen has two "primary" buttons, the screen is wrong.
3. **Nothing is more than one keystroke away.** `Ctrl+K` reaches every object, command and destination in the product.
4. **Preview before commit, undo after commit.** No consequential action without a preview; no completed action without an undo.
5. **Depth means meaning.** Elevation is never decorative. A raised surface is *temporary* (flyout, dialog, drag) or *above the reading plane* (inspector, dock). Persistent content is flat.

### F1.3 Desktop-First Commitments

This is not a responsive web app that happens to run large. Desktop-first means:

- **Optimised for 1440×900 through 3840×2160**, with a comfortable working target of 1920×1080.
- **Multi-pane by default** — up to five simultaneous zones (rail, context pane, canvas, inspector, AI dock).
- **Native window integration** — Windows 11 Mica title bar, snap layouts, taskbar jump lists, Fluent acrylic flyouts; macOS traffic lights, vibrancy, Stage Manager compatibility.
- **Pointer-precision affordances** — hover previews, right-click everywhere, drag-and-drop, marquee selection, resizable panes, column dragging.
- **Keyboard-complete** — every action reachable without a mouse; no mouse-only interaction anywhere in the product.
- **Multi-window and tabs** — a professor comparing three manuscripts should not be fighting the app.

---

## F2. Design Tokens

### F2.1 Colour System

**Architecture:** Primitive ramps → semantic aliases → component tokens. Components *never* reference primitives directly.

**Neutral ramp (16 steps)** — the backbone of the entire product.

| Step | Light Hex | Dark Hex | Typical Use |
|---|---|---|---|
| N0 | `#FFFFFF` | `#0B0B0F` | Canvas base / app background |
| N1 | `#FCFCFD` | `#111116` | Content surface |
| N2 | `#F8F9FB` | `#16161D` | Raised surface, sidebar |
| N3 | `#F2F3F6` | `#1C1C24` | Card, table header |
| N4 | `#EBECF0` | `#22222C` | Hover fill |
| N5 | `#E3E5EA` | `#292933` | Pressed fill, divider strong |
| N6 | `#D8DAE1` | `#31313C` | Border default |
| N7 | `#C6C9D2` | `#3B3B48` | Border strong |
| N8 | `#A8ACB8` | `#4B4B5A` | Disabled text |
| N9 | `#8B90A0` | `#5F5F70` | Placeholder |
| N10 | `#6E7385` | `#797989` | Tertiary text |
| N11 | `#585D6E` | `#9A9AAB` | Secondary text |
| N12 | `#3F4455` | `#BFBFCE` | Body text (secondary emphasis) |
| N13 | `#2A2E3D` | `#DCDCE6` | Body text |
| N14 | `#1A1D28` | `#EFEFF5` | Headings |
| N15 | `#0D0F16` | `#FFFFFF` | Max contrast |

**Accent & semantic ramps** (each with 12 steps; key values shown):

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `accent.primary` | `#4F46E5` | `#7C74F5` | Primary actions, active nav, selection |
| `accent.hover` | `#4338CA` | `#918AF7` | Hover state |
| `accent.subtle` | `#EEF0FE` | `#1E1B3A` | Selected row, active nav pill |
| `ai.primary` | `#8B5CF6` | `#A78BFA` | **All AI surfaces — reserved exclusively** |
| `ai.subtle` | `#F5F0FF` | `#241B3D` | AI card fills, AI badges |
| `success` | `#16A34A` | `#4ADE80` | Completed, on-track, approved |
| `warning` | `#D97706` | `#FBBF24` | Due soon, needs attention |
| `danger` | `#DC2626` | `#F87171` | Overdue, error, destructive |
| `info` | `#0284C7` | `#38BDF8` | Informational, in-progress |
| `teaching` | `#0891B2` | `#22D3EE` | Teaching domain tint |
| `research` | `#7C3AED` | `#A78BFA` | Research domain tint |
| `publication` | `#DB2777` | `#F472B6` | Publication domain tint |
| `funding` | `#059669` | `#34D399` | Grants/funding domain tint |
| `supervision` | `#EA580C` | `#FB923C` | Students/supervision domain tint |
| `admin` | `#475569` | `#94A3B8` | Governance/admin domain tint |

**Domain tints** appear only as: 3 px left accent bars on cards, entity-type icon colour, and thin category chips. Never as fills, never as backgrounds. This gives instant domain recognition without a rainbow interface.

**Contrast requirements:** body text ≥ 4.5:1, large text and UI glyphs ≥ 3:1, focus ring ≥ 3:1 against both the component and its background. All accent-on-surface pairs are pre-validated in both themes.

### F2.2 Typography

| Role | Family | Size / Line-height | Weight | Letter-spacing |
|---|---|---|---|---|
| Display | Inter Variable | 32 / 40 | 640 | −0.02em |
| H1 (page title) | Inter | 24 / 32 | 620 | −0.015em |
| H2 (section) | Inter | 20 / 28 | 600 | −0.01em |
| H3 (card title) | Inter | 16 / 24 | 600 | −0.005em |
| H4 (group label) | Inter | 14 / 20 | 600 | 0 |
| Body Large | Inter | 15 / 24 | 400 | 0 |
| Body | Inter | 14 / 20 | 400 | 0 |
| Body Small | Inter | 13 / 18 | 400 | 0 |
| Caption | Inter | 12 / 16 | 450 | 0.01em |
| Overline | Inter | 11 / 16 | 600 | 0.06em, uppercase |
| Reading (documents) | Source Serif 4 | 17 / 28 | 400 | 0 |
| Mono (code/data/IDs) | JetBrains Mono | 13 / 20 | 400 | 0 |
| Numeric (tables/metrics) | Inter (tabular figures) | inherits | 500 | 0 |

**Rules:** tabular figures mandatory in every table and metric — misaligned numbers destroy scannability. Reading surfaces (manuscript viewer, thesis chapters, notes) switch to the serif at 17 px with a 68–72 character measure. Never more than three type sizes visible in a single component.

### F2.3 Spacing, Radius, Elevation

**Spacing** — 4 px base grid. Tokens: `2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64`.
Rhythm: 8 px inside components · 12–16 px between related elements · 24 px between groups · 32–40 px between page sections.

**Radius:** `sm 4px` (chips, badges, inputs-small) · `md 6px` (buttons, inputs) · `lg 10px` (cards, panels) · `xl 14px` (dialogs, flyouts) · `full` (avatars, pills).

**Elevation (Fluent-derived, 5 levels):**

| Level | Shadow (light) | Shadow (dark) | Use |
|---|---|---|---|
| E0 | none | none | Page content, tables |
| E1 | `0 1px 2px rgba(16,20,35,.06)` + 1px border N6 | 1px border N6 only | Cards, panels |
| E2 | `0 2px 8px rgba(16,20,35,.08)` | `0 2px 8px rgba(0,0,0,.4)` | Hovered cards, dropdowns |
| E3 | `0 8px 24px rgba(16,20,35,.12)` | `0 8px 24px rgba(0,0,0,.55)` | Flyouts, popovers, right-click menus |
| E4 | `0 16px 48px rgba(16,20,35,.18)` | `0 16px 48px rgba(0,0,0,.7)` | Dialogs, command palette |

In dark mode, shadows alone are insufficient — every elevated surface *also* lightens by one neutral step and gains a 1 px `rgba(255,255,255,.08)` top-edge highlight. This is the Fluent approach and it is mandatory.

### F2.4 Motion

| Token | Duration | Easing | Applied to |
|---|---|---|---|
| `motion.instant` | 80 ms | linear | Hover fills, focus rings |
| `motion.fast` | 150 ms | `cubic-bezier(.33,0,.67,1)` | Button press, checkbox, chip toggle |
| `motion.normal` | 200 ms | `cubic-bezier(.33,0,.2,1)` | Dropdowns, tooltips, toasts |
| `motion.panel` | 250 ms | `cubic-bezier(.16,1,.3,1)` | Side panels, inspector, AI dock |
| `motion.dialog` | 300 ms | `cubic-bezier(.16,1,.3,1)` | Dialog entry (scale .96→1 + fade) |
| `motion.page` | 180 ms | `cubic-bezier(.33,0,.2,1)` | Route transitions (fade + 4 px rise) |
| `motion.spring` | — | spring(1, 90, 14) | Drag, reorder, dismiss |

**Governance:** motion communicates causality, spatial relationship or status change. Decorative animation is prohibited. `prefers-reduced-motion` collapses all durations to ≤ 80 ms opacity-only transitions, and disables parallax, blur transitions and spring physics entirely.

---

## F3. Light Mode & Dark Mode

Both themes are designed independently. Dark mode is **not** an inversion.

| Aspect | Light Mode | Dark Mode |
|---|---|---|
| **Character** | Paper. Clean, bright, archival, printable | Studio. Deep, focused, low-fatigue for night writing |
| **App background** | `N0 #FFFFFF` with Mica tint from wallpaper at 4% | `N0 #0B0B0F` with Mica tint at 6% |
| **Content surface** | `N1` with `E1` shadow + N6 border | `N2` with lightening + top highlight, no shadow reliance |
| **Elevation logic** | Higher = more shadow | Higher = lighter surface + subtle highlight |
| **Borders** | Visible, `N6` — structure comes from lines | Softer, `rgba(255,255,255,.07)` — structure comes from value steps |
| **Accent** | `#4F46E5` (deeper, holds against white) | `#7C74F5` (lifted, avoids vibration on dark) |
| **AI violet** | `#8B5CF6` | `#A78BFA` |
| **Text** | N14 headings / N13 body / N11 secondary | N14 headings / N12 body / N10 secondary |
| **Glass** | White-tinted acrylic, 72% opacity, 24 px blur | Black-tinted acrylic, 68% opacity, 28 px blur, +noise |
| **Shadows** | Cool-tinted, subtle | Near-black, deeper, larger spread |
| **Data-viz** | Saturated on white | Desaturated 12%, brightened 8% |
| **Images/PDFs** | Rendered natively | Rendered natively on a light "document card" — **never** invert user documents. Optional per-document "dim" toggle at 85% brightness |
| **Focus ring** | 2 px `accent.primary` + 2 px white offset | 2 px `accent.hover` + 2 px N0 offset |

**Additional themes:** `System` (default, follows OS with live switching), `High Contrast Light`, `High Contrast Dark` (Fluent HC token mapping, glass fully disabled, borders 2 px), and `Focus Sepia` (a warm reading theme for long-form review sessions).

**Switching:** instant, no flash, no reload, cross-fade 150 ms. Per-window theme override is allowed (a professor may keep a reading window light while the shell stays dark).

---

## F4. Glassmorphism Specification

Glass is a **material with rules**, not a decoration. Overused, it destroys legibility and performance; used precisely, it creates hierarchy and a sense of physical layering.

### F4.1 Material Ladder

| Material | Blur | Opacity | Saturation | Border | Where it is used |
|---|---|---|---|---|---|
| **Mica** (base) | — | Wallpaper tint 4–6% | — | none | App background, window body — a barely-perceptible desktop tint (Fluent Mica) |
| **Acrylic Thin** | 12 px | 82% | 120% | 1 px `rgba(255,255,255,.10)` | Topbar, sidebar rail |
| **Acrylic Base** | 24 px | 72% (L) / 68% (D) | 140% | 1 px `rgba(255,255,255,.14)` | Flyouts, right-click menus, dropdowns, inspector overlay |
| **Acrylic Strong** | 40 px | 60% | 160% | 1 px `rgba(255,255,255,.18)` + inner top highlight | Command palette, AI dock overlay, dialog scrims |
| **Frosted Card** | 16 px | 78% | 130% | 1 px hairline + 10 px radius | Hero cards on the Dashboard only |
| **Solid** | — | 100% | — | 1 px N6 | Tables, forms, document canvas, editors |

### F4.2 Where Glass Is Allowed

✅ Topbar and command bar · Left rail · Command palette (`Ctrl+K`) · Right-click and dropdown menus · Flyouts and popovers · AI dock and AI response cards · Notification toasts and the notification flyout · Dashboard hero/AI briefing card · Dialog backdrop scrim · Floating selection action bar · Media player overlay controls · Sticky table headers when content scrolls beneath.

### F4.3 Where Glass Is Banned

❌ Data tables and grids (numbers must be crisp) · Document, PDF and manuscript viewers · Form fields and text inputs · Long-form reading surfaces · Any surface containing body text longer than two lines · Charts and data visualisation · Print/export views · High Contrast themes · When `prefers-reduced-transparency` is set · On machines failing the performance probe.

### F4.4 Technical & Accessibility Rules

1. **Legibility floor:** any text on glass must maintain ≥ 4.5:1 against the *worst-case* backdrop. Implementation: every glass surface carries a solid-colour under-layer at 55–70% opacity beneath the blur, so contrast never depends on what is behind the window.
2. **Noise overlay:** 2–3% monochrome noise on all glass in dark mode prevents banding on gradients.
3. **Edge definition:** every glass surface needs a 1 px light border and, in dark mode, an inner top highlight — without an edge, glass reads as a rendering bug.
4. **No nested glass.** A glass surface may never contain another glass surface. Nested blur is visually incoherent and expensive.
5. **Blur never animates.** Glass surfaces fade and translate; the blur radius is static. Animating blur is the single biggest cause of jank.
6. **Performance probe:** on launch, measure composite frame time. If the device cannot hold 60 fps with blur, silently fall back to `Solid` materials with equivalent tokens. Users can force this in Settings → Appearance → *Reduce transparency*.
7. **Scrolling content beneath glass** must not be readable enough to distract — 24 px blur minimum for any surface with content moving behind it.

---

## F5. Application Shell Anatomy

### F5.1 The Five-Zone Shell

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ⌂ AcademicOS   [Dr. A. Iyer ▾]                                        ─  □  ✕        │ ← Title bar (Mica, 32px)
├───┬──────────────────────────────────────────────────────────────────────────────────┤
│   │ ← →  ⌂ Teaching › CS301 › Sessions            [⌘K Search]      ✦  🔔³  ⚙  ◐  👤 │ ← Topbar (Acrylic Thin, 48px)
│ R ├──────────────────────────────────────────────────────────────────────────────────┤
│ A │ [+ New ▾] [Import] [Share] │ [View: Grid ▾] [Sort ▾] [Filter ⚲] │      [⋯] [◨] │ ← Command bar (44px)
│ I ├────────────────┬───────────────────────────────────────────┬─────────────────────┤
│ L │                │                                           │                     │
│   │  CONTEXT PANE  │              CANVAS                       │     INSPECTOR       │
│ 5 │  (L2)          │              (L3)                         │     (L4)            │
│ 6 │  280–360px     │              flexible                     │     320px           │
│ p │  resizable     │              min 640px                    │     resizable       │
│ x │                │                                           │                     │
│   │  • Tree/list   │   Content: dashboard · table · grid ·     │  Tabs:              │
│ ▸ │  • Filters     │   document · board · timeline · chat      │  Details            │
│   │  • Smart       │                                           │  Metadata           │
│   │    folders     │                                           │  Versions           │
│   │  • Saved views │                                           │  Links              │
│   │                │                                           │  Activity           │
│   │                │                                           │  Permissions        │
│   ├────────────────┴───────────────────────────────────────────┴─────────────────────┤
│   │ 12 items · 3 selected · Synced 2 min ago          Indexing 4 ▸   ● Online  100% │ ← Status bar (28px)
└───┴──────────────────────────────────────────────────────────────────────────────────┘
                                                    ┌──────────────────────┐
                                                    │  ✦ AI DOCK (L5)      │ ← Overlay or docked
                                                    │  400px, Acrylic      │    right, Ctrl+J
                                                    └──────────────────────┘
```

### F5.2 Zone Specifications

**Title Bar (32 px)** — Fluent Mica; app icon + name; workspace/tenant switcher (for users in multiple institutions); native window controls. On macOS: traffic lights left, workspace switcher centred. Double-click maximises. Drag region excludes interactive elements.

**Left Rail — L1 (56 px collapsed / 240 px expanded, `Ctrl+\`)**

| Slot | Content |
|---|---|
| Top | Workspace avatar + name (expanded only) |
| Primary nav | ⌂ Dashboard · 🎓 Teaching · 🔬 Research · 📄 Publications · 📁 Projects · 👥 Students · 📅 Calendar · ✦ AI Chat · ⌕ Search |
| Divider | |
| Secondary | 🏛 Administration (role-gated) · 🔔 Notifications · ⚙ Settings |
| Pinned | User-pinned spaces (max 8, drag to reorder) |
| Bottom | Storage meter (mini) · Help · Profile avatar |

Behaviour: icons only when collapsed with 400 ms-delayed tooltips; active item shows a 3 px accent left bar + `accent.subtle` pill + accent icon; badge counts on Notifications and Students (at-risk); hovering while collapsed opens a 240 px flyout overlay (Acrylic Base) without expanding the rail; right-click any item → *Open in new tab / Open in new window / Pin / Unpin / Hide from rail*.

**Topbar (48 px, Acrylic Thin)** — back/forward with history dropdown on long-press · breadcrumb (entity path, not folder path; each segment is a dropdown of siblings) · centred global search invoker showing `Ctrl+K` hint (expands to a 720 px palette on click) · right cluster: AI assistant toggle (✦, violet), Notifications bell with count, quick settings, theme toggle (☀/◐), avatar menu.

**Command Bar (44 px, solid)** — screen-specific. Left: primary action (filled accent) + secondary actions (subtle). Centre-right: view switcher, sort, filter. Right: overflow `⋯`, panel toggles (inspector `◨`, AI dock `✦`). Collapses progressively into the overflow menu as the window narrows (Fluent command-bar behaviour). Never wraps to two lines.

**Context Pane — L2 (280–360 px, resizable, `Ctrl+Shift+E`)** — screen-specific navigation: trees, lists, filter groups, smart folders, saved views. Header has a scoped filter input and a `+` action. Collapsible to 0 for focus mode. Remembers width per screen.

**Canvas — L3 (flexible, min 640 px)** — the work surface. Supports six view modes where applicable: **Table**, **Grid/Cards**, **List**, **Board (kanban)**, **Timeline/Gantt**, **Document**. View choice persists per screen per user. Supports split view (`Ctrl+Alt+\`) for side-by-side comparison and tabs within the canvas.

**Inspector — L4 (320 px, resizable, `Ctrl+I`)** — contextual detail for the current selection. Six tabs: Details, Metadata, Versions, Links, Activity, Permissions. Shows a multi-select summary when several items are selected. Empty state: "Select an item to see its details." Content is inline-editable.

**AI Dock — L5 (400 px, Acrylic Strong, `Ctrl+J`)** — either overlays the canvas right edge or docks as a sixth column on displays ≥ 1920 px. Scope chip at top auto-set from context ("Asking about: CS301 › Sessions"). Persists a thread per space. Can be popped out into its own window.

**Status Bar (28 px)** — left: selection/count context ("248 artefacts · 3 selected · 1.2 GB"). Centre: background job ticker (indexing, uploads, AI runs) — click opens the Activity Centre flyout. Right: sync state, connection state, storage %, density toggle.

---

## F6. Window & Workspace Management

| Capability | Specification |
|---|---|
| **Multi-window** | `Ctrl+Shift+N` opens a new window on the same workspace; windows share session and sync live |
| **Canvas tabs** | `Ctrl+T` new tab, `Ctrl+W` close, `Ctrl+Tab` cycle, `Ctrl+1…9` jump to tab N. Tabs show entity icon + truncated title + dirty dot. Drag a tab out to spawn a window; drag between windows to merge |
| **Split view** | `Ctrl+Alt+\` splits the canvas vertically (50/50, draggable divider, min 480 px each). `Ctrl+Alt+Shift+\` for horizontal. Used heavily for version comparison and thesis review |
| **Pop-out** | Any artefact, dialog-free, can pop out into a frameless window (`Ctrl+Shift+O`) — designed for a second monitor |
| **Snap layouts** | Full Windows 11 snap-layout support via maximise hover; app declares preferred snap sizes |
| **Focus Mode** | `Ctrl+Shift+F` hides rail, context pane, inspector and status bar; canvas centres at 900 px max-width; topbar auto-hides with a 3 px reveal strip. `Esc` exits |
| **Zen Reading** | `Ctrl+Shift+R` in any document — serif type, sepia or dark reading theme, no chrome |
| **Session restore** | On relaunch, restore all windows, tabs, scroll positions, selections, pane widths and unsaved drafts |
| **Workspace switcher** | For multi-institution users: `Ctrl+Shift+W` — full switch of tenant context with a coloured top border and a workspace name chip so the user is never confused about which institution they are in |

---

## F7. Universal Component Library

### F7.1 Buttons

| Variant | Appearance | Use | Max per view |
|---|---|---|---|
| **Primary (Filled)** | Accent fill, white text, 6 px radius | The one main action | 1 per zone |
| **Secondary (Subtle)** | N3 fill, N13 text, hover N4 | Common alternatives | Unlimited |
| **Outline** | Transparent, 1 px N6 border | Alternative to subtle on tinted surfaces | — |
| **Ghost / Transparent** | No fill until hover | Toolbar, icon actions, low-emphasis | — |
| **Destructive** | Danger fill (or danger text on ghost) | Delete, revoke, purge — always with confirmation | 1 |
| **AI Action** | Violet gradient fill + ✦ glyph, subtle inner glow | Any AI-invoking action — instantly recognisable | — |
| **Split Button** | Action + `▾` dropdown of variants | `New ▾`, `Export ▾` | — |
| **Toggle** | Pressed state = `accent.subtle` fill + accent border | View modes, panel toggles | — |
| **Icon Button** | 32×32 (default) / 28×28 (compact), tooltip mandatory | Toolbars, table rows, cards | — |

**Sizes:** `sm 28px` · `md 32px` (default) · `lg 40px` (dialog primary, empty-state CTA).
**States:** rest · hover (fill +1 step, 80 ms) · active/pressed (fill +2 steps, scale .98) · focus (2 px accent ring + 2 px offset) · disabled (40% opacity, `not-allowed`, tooltip explaining *why*) · loading (spinner replaces label, width locked, button disabled) · success flash (150 ms check-mark morph on completion).
**Labelling rules:** verb-first, sentence case, ≤ 3 words. "Create course", not "Course Creation". Never "OK" — always the specific verb ("Delete 4 items", "Publish syllabus").

### F7.2 The Universal Data Table

Every table in AcademicOS is one component with consistent behaviour — this is a major learnability multiplier.

| Feature | Specification |
|---|---|
| **Row height** | Compact 32 px · Comfortable 40 px (default) · Relaxed 48 px — set globally in the status bar, overridable per table |
| **Header** | 40 px, N3 fill, 600 weight, 12 px overline-ish label, sticky on scroll (gains Acrylic Thin + bottom shadow once content scrolls beneath) |
| **Column controls** | Drag to reorder · drag edge to resize · double-click edge to auto-fit · right-click header for the column menu · pin left/right (pinned columns get a shadow edge) · hide/show via column picker |
| **Sorting** | Click header to sort; `Shift+Click` adds a secondary sort; sort chips appear in the filter bar showing the active order; arrow glyph + ordinal number for multi-sort |
| **Selection** | Checkbox column (appears on row hover or when any row is selected) · click row selects · `Ctrl+Click` toggles · `Shift+Click` range · `Ctrl+A` select all loaded · header checkbox with "Select all 1,248 matching" escalation link |
| **Selection action bar** | On ≥ 1 selection, a floating glass bar rises from the bottom centre: "3 selected" + contextual actions + `✕`. Fluent-style, `motion.panel` entry |
| **Row interactions** | Single click = select + populate inspector · Double click = open in canvas · `Enter` = open · `Space` = quick preview overlay · Right-click = context menu · Hover reveals a trailing quick-action cluster (open, share, `⋯`) |
| **Inline editing** | Editable cells show a pencil on hover; click or `F2` to edit; `Enter` commits, `Esc` cancels, `Tab` moves to the next editable cell; validation errors show inline with a red underline and a tooltip |
| **Grouping** | Group by any column; collapsible groups with sticky group headers and aggregate counts |
| **Density of information** | Rich cells allowed: avatar + name, status pill, progress bar, sparkline, multi-tag, relative date with absolute tooltip |
| **Virtualisation** | Windowed rendering; smooth 60 fps at 100,000 rows; skeleton rows during fetch |
| **Empty / loading / error** | Skeleton rows (8) while loading; illustrated empty state with primary action; inline error row with retry |
| **Export** | Right-click header → *Export view* (CSV/XLSX) — exports respect current filters, sort and column visibility |
| **Accessibility** | Full ARIA grid semantics; arrow-key cell navigation; `Home`/`End`/`PgUp`/`PgDn`; announced sort and selection changes |

### F7.3 The Universal Card

```
┌─────────────────────────────────────────┐
│▌ [icon] Title of the artefact       ⋯  │  ▌ = 3px domain tint bar
│  Secondary line · metadata · date       │  icon = artefact type glyph
│                                         │  ⋯ = overflow (appears on hover/focus)
│  [ optional thumbnail / preview ]       │
│                                         │
│  ● Status   👤 Owner   🔗 3 links       │
├─────────────────────────────────────────┤
│  [Primary action]   [Secondary]      ✦  │  footer appears on hover
└─────────────────────────────────────────┘
```

**Anatomy:** domain tint bar (3 px, left) · type icon (20 px) · title (H3, 2-line clamp) · subtitle/metadata (Body Small, N11) · optional media region (16:9 or 4:3, lazy-loaded, blurhash placeholder) · status/attribute row (pills and micro-icons) · hover footer with actions.
**States:** rest (E1) · hover (E2, 2 px rise, 150 ms, actions fade in) · selected (2 px accent border + `accent.subtle` fill) · dragging (E4, 3° tilt, 92% opacity, ghost placeholder at origin) · loading (shimmer skeleton) · error (danger left bar + inline message).
**Card sizes:** XS (metric tile, 3 col) · S (compact list card, 4 col) · M (standard, 4 col) · L (feature, 6–8 col) · XL (hero, 12 col).

### F7.4 Universal Filter Bar

Present on every list-bearing screen, directly beneath the command bar (40 px, solid).

```
[⚲ Filter] [Type: Slides ✕] [Semester: 2026-ODD ✕] [Owner: Me ✕] [+ Add filter]   [Clear all]   [Save view ▾]
```

- **Filter chips** are removable, editable (click opens its own value popover), and re-orderable.
- **`+ Add filter`** opens a searchable flyout listing all filterable fields grouped by category (Basic, Academic, People, Dates, Status, AI, Advanced).
- **Operators** per data type: text (is, contains, starts with, is empty), enum (is any of, is none of), date (on, before, after, between, in the last N, this semester, last semester), number (=, ≠, >, <, between), relation (is linked to, is not linked to), boolean.
- **Filter logic toggle**: AND (default) / OR / custom expression builder in Advanced mode.
- **Saved views** ("Save view ▾") persist filters + sort + columns + view mode + grouping. Views can be personal, shared with a space, or set as a departmental default by an admin. Saved views appear in the context pane and behave exactly like Smart Folders from the SRS.
- **Result count** updates live with a subtle number-roll animation: "248 → 31 results".
- **URL sync** — every filter state is encoded in the URL and is therefore shareable.

### F7.5 Other Core Components

| Component | Key notes |
|---|---|
| **Status pill** | 20 px, `sm` radius, dot + label, semantic colour at 12% fill with full-strength text |
| **Tag / chip** | Neutral by default; entity chips carry the domain tint and an icon; removable variant has an `✕` |
| **Avatar** | 20/24/32/40 px; initials fallback with deterministic hue; stacked group with `+N` overflow; presence dot (online/away/offline) |
| **Progress** | Linear (determinate/indeterminate) and ring (used for thesis and milestone completion); always with an accessible text equivalent |
| **Segmented control** | Fluent pill style for view modes; 2–5 segments max |
| **Combobox / picker** | Search-as-you-type, grouped results, recent items pinned at top, keyboard-complete, multi-select variant with chips |
| **Date & term picker** | Dual mode — calendar *and* academic term selector ("Odd 2026", "Week 3"); ranges supported |
| **Breadcrumb** | Entity-aware; each segment is a dropdown of siblings; collapses to `…` with a flyout when > 4 levels |
| **Tooltip** | 400 ms delay, 12 px text, Acrylic Base, max 240 px wide, never contains actions |
| **Teaching callout** | Fluent-style coach mark for first-run feature introduction; max 1 visible at a time; permanently dismissible |
| **Inline banner** | Full-width, semantic tint, icon + message + up to 2 actions + dismiss; used for policy notices, degraded AI, quota warnings |
| **Skeleton** | Shape-accurate placeholders with a 1.2 s shimmer; never a bare spinner for > 400 ms |
| **AI badge** | ✦ glyph + "AI" label in violet; appears on every AI-generated value, with a tooltip: model, timestamp, confidence, "View sources" |
| **Confidence indicator** | Three-state visual (high / medium / needs review) using a filled-segment glyph — never a raw percentage in primary UI |

---

## F8. Menu Systems — Right-Click vs. Context Menus

The specification treats these as **two distinct systems**, deliberately:

| System | Trigger | Purpose | Visual |
|---|---|---|---|
| **Right-Click Menu** | Right mouse button / `Shift+F10` / `☰` key on an *object* | Object-scoped commands — the full command set for the thing under the cursor | Acrylic Base flyout, E3, 220–280 px, icons left, shortcuts right, submenus on 200 ms hover |
| **Context Menu (Overflow / Command Context)** | `⋯` button, kebab icon, or a contextual action bar appearing due to *state* (selection, hover, mode) | State-scoped commands — what is possible right now given what is selected or active | Same flyout styling for `⋯`; floating glass action bar for selection state |

### F8.1 Right-Click Menu — Universal Structure

```
┌──────────────────────────────────────┐
│ ⊙ Open                        Enter  │  ← Group 1: OPEN
│ ⧉ Open in new tab       Ctrl+Enter   │
│ ⧉ Open in new window                 │
│ 👁 Quick preview              Space   │
├──────────────────────────────────────┤
│ ✦ Ask AI about this        Ctrl+J    │  ← Group 2: AI (always second — signals AI is native)
│ ✦ Summarise                          │
│ ✦ Find related                       │
├──────────────────────────────────────┤
│ ✎ Rename                       F2    │  ← Group 3: EDIT
│ ⧉ Duplicate                 Ctrl+D   │
│ ↔ Move to…              Ctrl+Shift+M │
│ 🔗 Link to entity…                    │
│ 🏷 Edit tags…                         │
├──────────────────────────────────────┤
│ ⇪ Share…                    Ctrl+S   │  ← Group 4: SHARE & EXPORT
│ 🔗 Copy link                Ctrl+L   │
│ ⤓ Download                          │
│ ⤴ Export as…                     ▸  │
├──────────────────────────────────────┤
│ ⏱ Version history           Ctrl+H  │  ← Group 5: INSPECT
│ ⓘ Details                    Ctrl+I │
│ ⚿ Permissions                       │
│ ⎘ Show provenance                   │
├──────────────────────────────────────┤
│ ⌸ Pin to sidebar                    │  ← Group 6: ORGANISE
│ ★ Add to favourites                 │
│ ⊞ Add to evidence pack…          ▸  │
│ 🗄 Archive                           │
├──────────────────────────────────────┤
│ 🗑 Move to trash            Delete   │  ← Group 7: DESTRUCTIVE (always last, danger text)
└──────────────────────────────────────┘
```

**Rules:** maximum 7 groups, maximum 6 items per group; overflow goes to a "More ▸" submenu. Unavailable commands are *hidden* if permanently inapplicable, *disabled with a tooltip reason* if temporarily unavailable ("You need Editor access to rename"). Destructive items are always last, always danger-tinted, always confirm. Every item shows its keyboard shortcut. Menus open toward available space and flip near screen edges. `Esc` closes; type-ahead jumps to items; arrow keys navigate; `→` opens a submenu.

**Multi-select right-click** replaces the header with a count and shows only commands valid for *every* selected item: `"12 items selected"` → Open all in tabs / Ask AI about these / Move / Tag / Share / Export / Archive / Trash.

**Right-click on empty canvas space** yields a surface menu: New ▾ · Paste · Upload here · Import from… · View mode ▸ · Sort by ▸ · Group by ▸ · Refresh · Select all · Screen settings.

### F8.2 Context Menu Surfaces

| Surface | Appears when | Contents |
|---|---|---|
| **Selection action bar** | ≥ 1 item selected | Count · 4–6 top actions · `⋯` for the rest · Clear selection. Floating glass, bottom-centre |
| **Hover quick actions** | Pointer over a row/card | 2–3 icon buttons (open, share, `⋯`) at the trailing edge, fading in over 80 ms |
| **Text selection menu** | Text selected in a document | Copy · Highlight ▸ (5 colours) · Add note · ✦ Explain · ✦ Summarise · ✦ Find similar in my corpus · Cite this · Create task |
| **`⋯` overflow** | Always present on cards, panels, rows, widgets | Full command set for that object, same grouping as the right-click menu |
| **Column header menu** | Right-click or `▾` on a table header | Sort asc/desc · Group by this · Filter by this · Pin left/right · Hide column · Auto-fit · Column picker… · Export view |
| **Drag context** | During drag over a valid target | Target highlights with a 2 px accent outline; a badge shows the operation ("Move 3 items to CS301 › Sessions"); `Ctrl` held switches to Copy; invalid targets show a `⃠` cursor and a reason tooltip |

---

## F9. Dialog & Overlay System

| Type | Size | Dismiss | Backdrop | Use |
|---|---|---|---|---|
| **Popover** | Auto, ≤ 320 px | Click-away, `Esc` | None | Small pickers, filter value editors |
| **Flyout** | 320–420 px | Click-away, `Esc` | None | Menus, notification panel, quick settings |
| **Dialog — Small** | 440 px | `Esc`, backdrop click, `✕` | Scrim 40% + 8 px blur | Confirmations, single-field input |
| **Dialog — Medium** | 640 px | `Esc`, `✕` (backdrop click disabled if dirty) | Scrim 40% + 8 px blur | Create/edit forms, share, move |
| **Dialog — Large** | 880 px, max 80vh | `✕` + confirm-if-dirty | Scrim 50% + 12 px blur | Multi-step wizards, evidence mapping, import review |
| **Full-screen overlay** | 100% − 64 px inset | `Esc` + confirm | Scrim 70% | Migration Reveal, PDF annotation, presentation mode |
| **Side sheet** | 480 px, right | `Esc`, click-away | None | Details that need more room than the inspector, e.g. "New Publication" |
| **Command palette** | 720 × 480 px, top-centred at 15vh | `Esc` | Scrim 30% + 16 px blur | `Ctrl+K` |
| **Toast** | 360 px, bottom-right stack (max 3) | Auto 5 s / 8 s with action | None | Confirmations with Undo |

**Universal dialog rules:** focus moves to the first interactive element (or the safe/cancel action for destructive dialogs) on open and returns to the trigger on close; focus is trapped inside; `Enter` triggers the primary action unless focus is in a multiline field; primary button sits right, cancel left of it (Windows convention), reversed on macOS builds; destructive primaries are danger-filled and, for irreversible actions, require typing a confirmation token; every dialog has exactly one primary action; forms autosave drafts so an accidental close never loses input; dialogs never stack more than two deep — a third requires a wizard step instead.

**Standard dialog catalogue (reused everywhere):** Create Entity · Rename · Move to… · Share & Permissions · Version History · Delete Confirmation · Bulk Action Preview · Import/Upload · Export · Link to Entity · Add to Evidence Pack · AI Action Preview (with diff) · Conflict Resolution · Keyboard Shortcut Reference (`Ctrl+/`).

---

## F10. Global Keyboard Model

**Philosophy:** single keys for navigation when no input is focused (Gmail/Linear style), modifiers for commands, chords for rare operations. Every shortcut is discoverable via `Ctrl+/` and every menu item displays its binding.

### F10.1 Global (work anywhere)

| Shortcut | Action |
|---|---|
| `Ctrl+K` | Command palette / universal search |
| `Ctrl+J` | Toggle AI dock |
| `Ctrl+I` | Toggle inspector |
| `Ctrl+\` | Toggle left rail |
| `Ctrl+Shift+E` | Toggle context pane |
| `Ctrl+/` | Keyboard shortcut reference |
| `Ctrl+,` | Settings |
| `Ctrl+N` | New (context-aware split action) |
| `Ctrl+U` | Upload / import |
| `Ctrl+F` | Find in current view |
| `Ctrl+Shift+F` | Focus mode |
| `Ctrl+T` / `Ctrl+W` | New tab / close tab |
| `Ctrl+Shift+N` | New window |
| `Ctrl+1…9` | Jump to tab |
| `Alt+←` / `Alt+→` | Back / forward |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `Ctrl+Shift+T` | Reopen closed tab |
| `Ctrl+Alt+\` | Split view |
| `Ctrl+Shift+D` | Toggle dark/light |
| `Esc` | Close topmost overlay / clear selection / exit mode |
| `F1` | Contextual help |

### F10.2 Navigation (single key, no input focused)

| Key | Destination |
|---|---|
| `G` then `D` | Dashboard |
| `G` then `T` | Teaching |
| `G` then `R` | Research |
| `G` then `P` | Publications |
| `G` then `J` | Projects |
| `G` then `S` | Students |
| `G` then `C` | Calendar |
| `G` then `A` | AI Chat |
| `G` then `N` | Notifications |
| `G` then `X` | Administration |
| `G` then `,` | Settings |
| `G` then `H` | Home/Dashboard |

### F10.3 List & Object (no input focused)

| Key | Action |
|---|---|
| `↑ ↓` | Move selection |
| `← →` | Collapse / expand (trees), previous/next column (grids) |
| `Enter` | Open |
| `Space` | Quick preview |
| `X` | Toggle selection |
| `Shift+↑/↓` | Extend selection |
| `Ctrl+A` | Select all |
| `E` | Edit / rename |
| `S` | Share |
| `L` | Link to entity |
| `T` | Tags |
| `V` | Version history |
| `C` | Comment |
| `A` | Ask AI about this |
| `P` | Pin |
| `F` | Favourite |
| `#` | Move to trash |
| `Shift+F10` | Right-click menu |

---

## F11. States: Empty · Loading · Error · Offline

| State | Specification |
|---|---|
| **First-run empty** | Illustration (line-art, accent-tinted, theme-aware) · headline stating what this screen is for · one sentence of value · **primary action** · secondary "Import existing" · a "See an example" link that loads a demo dataset in a sandbox |
| **Filtered empty** | No illustration. "No results for these filters." · list of active filters as removable chips · "Clear all filters" · "Search everywhere instead" · AI suggestion: "Did you mean…?" |
| **Search empty** | Explain which constraint eliminated results · offer relaxations · offer to search external sources · never a bare "0 results" |
| **Permission empty** | "You don't have access to this." · what it is (if existence is not confidential) · who owns it · **Request access** button with an optional message |
| **Loading — initial** | Layout-accurate skeletons, 1.2 s shimmer, no spinners |
| **Loading — incremental** | Content stays interactive; a subtle progress line under the topbar; the status bar shows the job |
| **Loading — long job** | Move to background with a status-bar entry and a toast on completion; never block the UI |
| **Error — recoverable** | Inline banner: what happened, why, what to do, Retry button. Plain language, never an error code alone (code available under "Details") |
| **Error — blocking** | Full-panel state with illustration, explanation, retry, "Copy diagnostics", support link |
| **Offline** | Amber status-bar chip "Offline — working locally" · synced content remains fully usable · unavailable actions are disabled with an explanatory tooltip · edits queue with a "3 changes pending" indicator · a reconnection toast confirms sync |
| **Degraded AI** | Violet-to-neutral banner: "AI features are temporarily limited. Search and browsing are unaffected." — this is the graceful-degradation ladder from the SRS made visible |
| **Quota warning** | Inline banner at 80% (info), 90% (warning), 100% (danger, with what stops working and how to fix it) |

---

## F12. Density, Accessibility & Motion Governance

**Density modes** (status bar toggle, persisted): *Compact* (32 px rows, 4 px card gaps — for 1440 px laptops and power users), *Comfortable* (default, 40 px rows), *Relaxed* (48 px rows, larger type — for presentations and accessibility).

**Accessibility (build gates, not aspirations):**
- WCAG 2.2 AA verified per component; contrast tokens machine-checked in CI.
- Full keyboard operability; visible 2 px focus ring with 2 px offset on every focusable element; logical DOM/tab order matching visual order; skip links between the five zones (`F6` cycles zones — a Fluent convention).
- Screen-reader semantics: landmark regions, ARIA grid/tree/tablist patterns, live regions for async updates (search counts, AI streaming, save confirmations), descriptive labels on all icon buttons.
- Every chart has an accessible data table behind a "View as table" toggle; every colour-coded status also carries an icon and text label — colour is never the sole carrier of meaning.
- Respect `prefers-reduced-motion`, `prefers-reduced-transparency`, `prefers-contrast`, and OS text-scaling up to 200% without loss of function.
- Target sizes ≥ 24×24 px minimum (AA), 32 px preferred; 8 px minimum spacing between adjacent targets.

---

# PART II — SCREEN SPECIFICATIONS

*Each screen is specified against a fixed template: Purpose · Layout · Sidebar · Topbar & Command Bar · Components · Cards · Tables · Filters · Search · Buttons · Dialogs · Right-Click Menus · Context Menus · Keyboard Shortcuts · Modern UX · Glass · Dark/Light · Edge States.*

---

## SCREEN 1 — DASHBOARD

### 1.1 Purpose

The Dashboard answers one question in under five seconds: **"What deserves my attention right now?"** It is not a chart wall and not a homepage. It is a triage surface that converts institutional noise into three or four concrete actions, then gets out of the way. It adapts entirely to the user's active role (Faculty, Scholar, PI, HoD, Administrator) as specified in SRS §9.

**Primary success metric:** ≥ 60% of sessions begin with an action taken directly from a dashboard card, not from navigation.

### 1.2 Layout

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ TOPBAR:  ← →  ⌂ Dashboard                    [Ctrl+K]         ✦  🔔³  ⚙  ◐  👤      │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ COMMAND BAR: [+ Quick Capture ▾] [Customise ⊞] │ [Period: This week ▾] │      [⋯] [◨]│
├───┬──────────────────────────────────────────────────────────────────────────────────┤
│ R │  Good morning, Dr. Iyer                  Tuesday, 4 August · Odd Sem, Week 3     │
│ A │  ┌────────────────────────────────────────────────────────────────────────────┐  │
│ I │  │ ✦  AI BRIEFING                                       Generated 06:12  ⟳  ⋯ │  │ ← Frosted glass hero
│ L │  │                                                                            │  │
│   │  │ "Three things need you today. The SERB progress report is due in 6 days   │  │
│   │  │  and 2 deliverables have no evidence attached. Rahul's Chapter 3 has      │  │
│   │  │  waited 9 days for your feedback. CS-301 starts in 90 minutes and the     │  │
│   │  │  slides haven't been updated since last year."                            │  │
│   │  │                                                            [3 sources ▾]   │  │
│   │  │  [Review report draft]  [Open Chapter 3]  [Prepare CS-301]     [Dismiss]  │  │
│   │  └────────────────────────────────────────────────────────────────────────────┘  │
│   │  ┌───────────────────────────────┐  ┌───────────────────────────────────────┐   │
│   │  │ ⏱ TODAY                  ⋯   │  │ ⚠ NEEDS ATTENTION            5    ⋯  │   │
│   │  │ ─────────────────────────────  │  │ ───────────────────────────────────── │   │
│   │  │ ● 10:30  CS-301 Lecture 8      │  │ 🔴 Grant report      6 days   [Open] │   │
│   │  │   Automata · B204 · 62 std     │  │ 🔴 Ch.3 feedback     9d late  [Open] │   │
│   │  │   ▸ Slides ▸ Attendance        │  │ 🟠 Ethics renewal    21 days  [Open] │   │
│   │  │ ● 12:30  Meeting: R. Menon     │  │ 🟠 Review queue      14 items [Triage]│   │
│   │  │ ● 15:00  DC Meeting: A. Sharma │  │ 🔵 Approvals         2        [Review]│   │
│   │  └───────────────────────────────┘  └───────────────────────────────────────┘   │
│   │  ┌───────────────────────────────┐  ┌───────────────────────────────────────┐   │
│   │  │ ▤ CONTINUE WHERE YOU LEFT OFF │  │ ◈ MY SPACES                       ⋯  │   │
│   │  └───────────────────────────────┘  └───────────────────────────────────────┘   │
│   │  ┌────────────────────────────────────────────────────────────────────────────┐  │
│   │  │ 👥 SUPERVISION BOARD                                                   ⋯  │  │
│   │  └────────────────────────────────────────────────────────────────────────────┘  │
│   │  ┌───────────────────────────────┐  ┌───────────────────────────────────────┐   │
│   │  │ 📈 MY OUTPUT (12 months)      │  │ 🎯 APPRAISAL READINESS            76% │   │
│   │  └───────────────────────────────┘  └───────────────────────────────────────┘   │
│   ├──────────────────────────────────────────────────────────────────────────────────┤
│   │ STATUS: 12 widgets · Data fresh 2 min ago    Indexing 4 ▸    ● Online   72% used │
└───┴──────────────────────────────────────────────────────────────────────────────────┘
```

Grid: 12 columns, 24 px gutters, 32 px page padding, content max-width 1680 px centred on ultrawide displays.

### 1.3 Sidebar (Context Pane)

The Dashboard is the one screen where the **context pane is hidden by default** — nothing should compete with the briefing. Pressing `Ctrl+Shift+E` reveals a *Widget Library* pane:

| Section | Contents |
|---|---|
| **Search widgets** | Filter input across the widget catalogue |
| **Available widgets** | Grouped by domain (Attention, Teaching, Research, Publications, Funding, Supervision, Admin, Personal). Each entry is a draggable mini-card with a preview thumbnail and a one-line description |
| **Layouts** | Saved dashboard layouts: "Default", "Semester start", "Writing week", "Accreditation mode". Switch, duplicate, rename, delete |
| **Role view** | For multi-role users: switch between "As Faculty" / "As HoD" / "As PI" dashboards |
| **Footer** | "Reset to role default" (with confirmation) |

The left rail (L1) behaves globally; the Dashboard item shows the accent bar and no badge.

### 1.4 Topbar & Command Bar

**Topbar:** standard global bar. Breadcrumb reads simply `⌂ Dashboard`. The AI icon pulses once (single 600 ms glow, never repeating) when a fresh briefing is available.

**Command bar (Dashboard-specific):**

| Position | Control | Behaviour |
|---|---|---|
| Left | `+ Quick Capture ▾` (primary, split) | Dropdown: Upload files · Scan document · Voice note · Quick note · Email to workspace · Paste from clipboard |
| Left | `Customise ⊞` (secondary, toggle) | Enters Edit Layout mode: cards gain drag handles, resize grips and remove `✕`; a dashed drop-grid appears; command bar switches to "Done / Reset / Add widget" |
| Centre | `Period: This week ▾` | Global time scope for all time-aware widgets: Today · This week · This month · This semester · This academic year · Custom range. Individual cards may override (shown by a small clock badge) |
| Right | `⋯` overflow | Refresh all · Export dashboard as PDF · Schedule weekly email digest · Print · Dashboard settings |
| Right | `◨` | Toggle inspector (shows detail for a focused widget) |

### 1.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Greeting header** | Time-aware salutation, full date, academic context chip ("Odd Semester · Week 3 of 16"). The academic chip is clickable → Calendar semester view |
| C2 | **AI Briefing hero (frosted glass)** | Streaming text on first generation (30 chars/s typewriter, skippable by click); 2–4 action buttons derived from the content; `[N sources ▾]` expands to source cards; `⟳` regenerates; `⋯` offers Change tone / Change frequency / What data is used? / Turn off |
| C3 | **Today timeline** | Vertical time rail with a live "now" indicator line that animates position every minute; each event expandable inline to reveal linked artefacts; join-link button for virtual sessions |
| C4 | **Needs Attention list** | Severity-sorted; each row = icon + label + age/deadline + inline action; hovering a row shows why it surfaced ("Flagged because the deliverable has no linked evidence") |
| C5 | **Continue list** | Last 6 artefacts with resume context ("PDF page 14", "Chapter 3, §3.2"), thumbnail, and relative time |
| C6 | **Spaces grid** | Compact space cards with a health dot, progress bar and member avatars |
| C7 | **Supervision board** | Mini-table of scholars: name, stage, last contact, next milestone, risk pill. Row click → Students screen filtered to that scholar |
| C8 | **Metric tiles** | Number + sparkline + delta vs. previous period (green/red arrow) + label. Click → Insights drill-down |
| C9 | **Readiness gauge** | Segmented horizontal bars per category with an overall ring; "View gaps" opens a side sheet listing missing evidence |
| C10 | **Widget chrome** | Every widget: title + icon, optional count badge, freshness dot (green < 5 min, amber < 1 h, grey older) with tooltip timestamp, `⋯` menu, drag handle (edit mode only) |
| C11 | **Activity ticker** (optional widget) | Live feed of space activity with avatars; pauses on hover |
| C12 | **Storage & AI usage** (optional widget) | Dual ring gauges with "Manage" link |

### 1.6 Cards

| Card | Size | Content | Interactions |
|---|---|---|---|
| AI Briefing | XL (12 col) | Narrative + actions + sources | Regenerate, dismiss, expand sources, act |
| Today | M (4 col) | Up to 5 events, "+3 more" | Expand event, open artefacts, join |
| Needs Attention | M (4 col) | Up to 6 items | Inline resolve, snooze, open |
| Continue | M (4 col) | 6 recent artefacts | Open, preview (Space), pin |
| My Spaces | M (4 col) | Up to 6 spaces | Open, pin, `⋯` |
| Supervision | L (8 col) | Scholar mini-table | Open scholar, log meeting, message |
| Metric tile | XS (3 col) | Single KPI | Drill down |
| Readiness | M (4 col) | Category bars | View gaps |
| Deadlines | M (4 col) | Chronological list with countdown pills | Open, add to calendar |
| Manuscript pipeline | L (8 col) | Mini-kanban by stage | Drag between stages, open |

Card behaviour: hover raises E1→E2 with a 2 px lift and reveals `⋯`; drag in edit mode uses spring physics with a live drop-grid; removal animates out at 200 ms with an undo toast; loading uses shape-accurate skeletons; a card that fails to load shows an inline retry without breaking the grid.

### 1.7 Tables

The Dashboard uses **mini-tables** only (embedded in cards) — never a full data grid.

**Supervision mini-table**

| Column | Width | Content | Sortable |
|---|---|---|---|
| Scholar | 22% | Avatar + name + programme | ✓ |
| Stage | 18% | Stage pill + progress micro-bar | ✓ |
| Last contact | 14% | Relative ("14 days") with absolute tooltip; amber > 21 days, red > 30 | ✓ |
| Next milestone | 22% | Label + date + countdown | ✓ |
| Risk | 12% | Risk pill (Low/Medium/High) with tooltip explaining the signals | ✓ |
| Actions | 12% | Hover cluster: message · log meeting · open | — |

Rules for all mini-tables: max 6 visible rows with a "View all N →" footer link that navigates to the full screen with the same sort/filter applied; no pagination; no column resizing; row click opens; right-click gives the full object menu.

### 1.8 Filters

Dashboard filtering is deliberately minimal — it is a triage screen, not an analysis screen.

- **Global period selector** in the command bar (applies to all time-aware widgets).
- **Per-card scope chips** where meaningful, e.g. Needs Attention → `All · Teaching · Research · Supervision · Admin`; Supervision → `All · At risk`.
- **Role context** (for multi-role users) switches the entire widget set.
- No filter bar, no chip row. Anything requiring real filtering sends the user to the relevant screen with filters pre-applied.

### 1.9 Search

The Dashboard has no local search field. `Ctrl+K` is the search affordance, and the topbar invoker is always visible. However, three search entry points exist contextually: the Widget Library filter (edit mode), a filter input inside the "View all" expansion of any mini-table, and the AI Briefing's `?` follow-up field ("Ask a follow-up about this briefing…") which routes into the AI dock with the briefing as context.

### 1.10 Buttons

| Button | Variant | Location | Action |
|---|---|---|---|
| Quick Capture | Primary split | Command bar | Opens capture menu |
| Customise | Secondary toggle | Command bar | Edit layout mode |
| Period selector | Ghost dropdown | Command bar | Time scope |
| Briefing actions (2–4) | Primary (first) + Secondary | Hero card | Context-derived |
| Regenerate `⟳` | Icon ghost | Hero card | Re-run briefing |
| Dismiss | Ghost text | Hero card | Hide until tomorrow |
| Sources `▾` | Ghost text with count | Hero card | Expand provenance |
| Open / Triage / Review | Secondary sm | Attention rows | Navigate to item |
| Snooze | Icon ghost | Attention row hover | 1 day / 3 days / next week |
| View all → | Ghost text | Card footers | Navigate with context |
| Add widget | Secondary | Edit mode | Open widget library |
| Done / Reset | Primary / Ghost | Edit mode | Save or restore layout |

### 1.11 Dialogs

| Dialog | Size | Trigger | Contents |
|---|---|---|---|
| **Quick Capture** | Medium (640) | `+ Quick Capture` / `Ctrl+U` | Tabbed: Upload (drop zone + browse) · Scan (camera/scanner) · Voice (record with live waveform + transcript preview) · Note (block editor) · Email (shows the user's private ingest address with copy button). Footer shows AI destination prediction: "I'll file this under… [Course CS-301 ▾]" |
| **Add Widget** | Large (880) | Edit mode → Add widget | Two-pane: category list left, gallery with live previews right; each widget shows description, data source and required permission; click adds to the first free grid slot |
| **Widget Settings** | Small (440) | Widget `⋯` → Settings | Title override, data scope, time period, row limit, refresh interval, visibility |
| **Briefing Settings** | Medium | Briefing `⋯` → Settings | Frequency (each login / daily / weekdays / off), delivery time, tone (Direct / Neutral / Encouraging), included domains (checkbox list), max length, "Explain what data is used" link to the privacy panel |
| **Gap Details** | Side sheet (480) | Readiness → View gaps | Grouped list of missing evidence with per-item "Attach existing" (opens picker) or "Upload" |
| **Reset Layout** | Small | Edit mode → Reset | Warning + "Reset to role default" destructive confirm |
| **Export Dashboard** | Small | `⋯` → Export | Format (PDF/PNG), include/exclude widgets, date stamp, branding toggle |
| **Schedule Digest** | Medium | `⋯` → Schedule digest | Frequency, day, time, recipients (self + optional others), content selection |

### 1.12 Right-Click Menus

**On a widget/card:**
```
✦ Ask AI about this card
─────────────────────────
⟳ Refresh now
⚙ Widget settings…
⇱ Expand to full screen
─────────────────────────
⤴ Export as image
🔗 Copy link to this view
─────────────────────────
↕ Move up / Move down
⤢ Resize                ▸   (Small · Medium · Large · Full width)
─────────────────────────
👁 Hide this widget
```

**On a Needs-Attention row:** Open · Open in new tab · ✦ Why is this flagged? · Snooze ▸ (1 day / 3 days / Next week / Custom) · Mark as handled · Assign to… · Add to calendar · Mute this type of alert.

**On a Today event:** Open session · Join meeting · Open linked materials ▸ · Log meeting notes · Reschedule… · Copy invite link · Cancel event.

**On a Continue item:** the universal artefact right-click menu (F8.1) plus "Remove from Continue" and "Pin to top".

**On empty dashboard grid space:** Add widget… · Paste widget · Reset layout · Change period ▸ · Switch role view ▸ · Dashboard settings.

### 1.13 Context Menus

- **Widget hover context:** `⋯` (full menu), `⟳` (refresh), drag handle in edit mode.
- **Edit-mode context bar:** a floating glass bar at the bottom: "Editing layout · 12 widgets" with `Add widget`, `Reset`, `Cancel`, `Done`.
- **Briefing source context:** clicking `[3 sources ▾]` expands inline source cards, each with a mini context menu (Open · Open in new tab · Why was this used? · Exclude this source and regenerate).
- **Selection context:** not applicable — the Dashboard has no multi-select.

### 1.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `D` | Go to Dashboard |
| `R` | Regenerate AI briefing |
| `1`–`9` | Focus widget N (focus ring + arrow-key navigation inside) |
| `Tab` / `Shift+Tab` | Move between widgets |
| `Enter` | Activate the focused widget's primary action |
| `E` | Enter/exit Customise mode |
| `P` | Open period selector |
| `Ctrl+U` | Quick Capture |
| `Ctrl+Shift+E` | Toggle Widget Library |
| `Alt+1..5` | Switch role view (multi-role users) |
| `Esc` | Exit edit mode / close expansion |

### 1.15 Modern UX Details

- **Progressive reveal on load:** widgets fade+rise (4 px, 180 ms) in staggered sequence at 40 ms intervals, top-left to bottom-right. Total choreography under 500 ms — it reads as "assembling", not "slow".
- **The briefing streams.** Text appears progressively on first generation of the day, which makes a 3-second LLM call feel instant and signals genuine computation. Cached briefings render instantly with no animation.
- **Live "now" line** on the Today timeline moves each minute with a 400 ms ease — the only continuously animating element on the screen.
- **Number transitions** roll rather than swap (300 ms count-up) when metrics update.
- **Contextual greeting intelligence:** "Good morning" before 12:00, "Good afternoon", "Good evening"; on a day with no obligations the briefing says so plainly ("Nothing urgent today. A good day for deep work.") — refusing to manufacture busywork is a deliberate trust signal.
- **Zero-state dignity:** a brand-new user sees a three-step setup card instead of empty widgets, with progress ("2 of 3 complete").
- **No badges for vanity.** No streaks, no confetti, no gamification.

### 1.16 Glassmorphism Application

| Element | Material |
|---|---|
| AI Briefing hero | **Frosted Card** — 16 px blur, 78% opacity, violet-tinted (2% `ai.primary`), 1 px hairline border, subtle inner top highlight. The *only* glass card on the screen, which is exactly why it commands attention |
| Topbar / rail | Acrylic Thin |
| Quick Capture dropdown | Acrylic Base |
| Edit-mode floating bar | Acrylic Base |
| All other widgets | **Solid** — data must be crisp |

### 1.17 Dark & Light Mode

| Aspect | Light | Dark |
|---|---|---|
| Page background | `N0` with 4% Mica wallpaper tint | `N0 #0B0B0F` with 6% Mica tint |
| Widgets | `N1` surface, `E1` shadow, `N6` border | `N2` surface, no shadow, `rgba(255,255,255,.07)` border + top highlight |
| AI hero | White-frosted, violet tint 2%, border `rgba(255,255,255,.5)` | Dark-frosted, violet tint 6%, border `rgba(255,255,255,.12)`, 2% noise |
| Sparklines | `accent.primary` on white | `accent.hover` at 85% saturation |
| Severity dots | Full saturation | Brightened 8%, desaturated 12% |
| Greeting text | `N14` | `N14` (near-white) |
| Freshness dot | `success` | `success` dark variant |

### 1.18 Edge States

- **New user (no data):** "Let's set up your workspace" card with 3 steps (Connect your files · Confirm your courses · Ask your first question), progress indicator, and a "Skip for now" that leaves a persistent setup chip in the status bar.
- **AI unavailable:** the hero collapses to a neutral summary card built from deterministic data ("3 items need attention today") with a small note: "AI briefing unavailable — showing a basic summary."
- **No obligations:** honest empty message + a "Deep work" suggestion listing the user's oldest stalled draft.
- **Permission-limited role:** widgets requiring unavailable data never render and never leave holes; the grid reflows.
- **Very wide display (≥ 2560 px):** the grid caps at 1680 px and centres; optionally a third column of narrow widgets can be enabled in settings.

---

## SCREEN 2 — TEACHING

### 2.1 Purpose

Teaching is the professor's **course operations centre**. It manages the full lifecycle of every course offering: design, sessions, assessments, submissions, feedback and outcome evidence. Its defining feature is **Semester Roll-Forward** — cloning last year's course into this year with a reviewable diff, which alone eliminates the single most wasteful annual ritual in academic life.

### 2.2 Layout

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  🎓 Teaching › 2026 Odd › CS-301 Automata Theory › Sessions      [Ctrl+K]  ✦ 🔔 ◐│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [+ New Session ▾] [⟲ Roll Forward] [Import] [Share] │ [⊞ Grid|☰ List|▦ Board] [↕ Sort]│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [⚲ Filter] [Type: All ✕] [Week: 1-16 ✕] [Status: Any ✕] [+ Add filter]  [Save view ▾]│
├────────────────────┬──────────────────────────────────────────┬──────────────────────┤
│ CONTEXT PANE       │  CANVAS — Sessions                       │  INSPECTOR           │
│ ─────────────────  │  ──────────────────────────────────────  │  ──────────────────  │
│ ⚲ Filter courses   │  ┌─────────────────────────────────────┐ │  Lecture 8           │
│                    │  │ ▌Week 3 ─────────────────────────── │ │  ─────────────────   │
│ ▾ 2026 · Odd       │  │  ┌──────────┐ ┌──────────┐          │ │  Details Metadata    │
│   ▾ CS-301 Automata│  │  │ L07      │ │ L08 ●    │          │ │  Versions Links      │
│     · Overview     │  │  │ Pumping  │ │ Graph    │          │ │                      │
│     · Design       │  │  │ Lemma    │ │ Algos    │          │ │  Type: Lecture       │
│     · Sessions  ◀  │  │  │ ✓ Taught │ │ ⏱ Today  │          │ │  Week: 3             │
│     · Assessments  │  │  │ 3 files  │ │ 5 files  │          │ │  CO: CO2, CO3        │
│     · Submissions  │  │  └──────────┘ └──────────┘          │ │  Materials: 5        │
│     · Feedback     │  │ ▌Week 4 ─────────────────────────── │ │  Status: Ready       │
│     · Outcomes     │  │  ┌──────────┐ ┌──────────┐          │ │  Last updated:       │
│   ▸ CS-540 ML      │  │  │ L09      │ │ L10      │          │ │   2025-09-14 ⚠ old  │
│ ▸ 2026 · Even      │  │  │ Draft    │ │ Planned  │          │ │                      │
│ ▸ 2025 · Odd (arch)│  │  └──────────┘ └──────────┘          │ │  [Open] [Update]     │
│ ─────────────────  │  └─────────────────────────────────────┘ │                      │
│ SMART VIEWS        │                                          │                      │
│ ★ Needs updating 7 │                                          │                      │
│ ★ Missing CO map 3 │                                          │                      │
│ ★ This week        │                                          │                      │
├────────────────────┴──────────────────────────────────────────┴──────────────────────┤
│ 16 sessions · 1 selected · CS-301 · 62 students        Syncing LMS ▸    ● Online     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Sidebar (Context Pane)

**Structure:** a three-level tree — Academic Year/Term → Course Offering → Course Section.

| Element | Detail |
|---|---|
| Header | Scoped filter input ("Filter courses…") + `+` (New course) |
| Tree | Terms are collapsible; current term auto-expanded; archived terms greyed with an archive glyph. Course nodes show code + short title, a colour dot for teaching domain, and badges for pending items (e.g. `3` ungraded) |
| Course children | Overview · Design · Sessions · Assessments · Submissions · Feedback · Outcomes · Materials · Students |
| Smart Views | System-provided: *Needs updating* (materials older than one offering), *Missing CO mapping*, *This week*, *Ungraded submissions*, *Low attendance*. User-saved views appear below with a `★` |
| Footer | Storage used by teaching materials + "Manage" |
| Interactions | Drag a course onto a term to move it; right-click a course for the course menu; double-click to open Overview; `→`/`←` expand/collapse |

### 2.4 Topbar & Command Bar

Breadcrumb: `🎓 Teaching › 2026 Odd › CS-301 Automata Theory › Sessions`, each segment a dropdown of siblings (switching course keeps the same sub-tab — a small detail that saves thousands of clicks per semester).

| Control | Type | Behaviour |
|---|---|---|
| `+ New Session ▾` | Primary split | Session · Lecture material · Assignment · Assessment · Reading · Announcement · Bulk create from plan |
| `⟲ Roll Forward` | Secondary (AI-accented) | Opens the Roll-Forward wizard |
| `Import` | Secondary | From LMS · From previous offering · From file · From template · From colleague |
| `Share` | Secondary | Opens share dialog scoped to the course |
| View switcher | Segmented | Grid (session cards) · List (table) · Board (by status) · Timeline (semester calendar) |
| `↕ Sort` | Ghost dropdown | Week ▲ · Date · Status · Last updated · Title |
| `⋯` | Overflow | Course settings · Duplicate course · Export course pack · Print syllabus · Archive course · LMS sync now · Attainment report |
| `◨` `✦` | Toggles | Inspector, AI dock |

### 2.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Course header strip** (Overview tab) | Course code, title, credits, term, enrolment count, delivery mode, syllabus status pill, progress bar "Week 3 of 16", instructor avatars |
| C2 | **Session card** | Session number, topic, date/time, status (Planned/Draft/Ready/Taught/Cancelled), material count, CO chips, attendance %, a warning glyph if materials predate the current offering |
| C3 | **Week grouping bands** | Sticky group headers with week number, date range, and a collapse toggle; a "current week" band is accent-tinted |
| C4 | **Syllabus editor** (Design tab) | Two-pane: structured outline left, rich editor right; CO definitions with Bloom level pickers; approval status banner and history |
| C5 | **CO–PO matrix** (Outcomes tab) | Interactive grid — COs as rows, POs as columns, cells hold correlation levels 1–3; heatmap colouring; AI-suggested mappings shown as dashed cells awaiting confirmation; attainment column computed from assessment data |
| C6 | **Assessment builder** | Question list with drag reorder, marks, Bloom level, CO tag, difficulty, reuse warning ("used in 2024 midsem"); live totals panel (marks, Bloom distribution, CO coverage) |
| C7 | **Submission grid** | Student × assessment matrix with status cells, inline marks entry, rubric drawer, plagiarism score chips |
| C8 | **Feedback panel** | Aggregate scores, sentiment trend, AI-extracted themes with representative quotes, comparison to previous offerings |
| C9 | **Material list** | File rows with type icon, version, last updated, usage ("used in L08"), staleness flag |
| C10 | **Roll-Forward diff view** | Side-by-side previous vs. proposed offering with per-item Keep/Update/Drop toggles |
| C11 | **AI teaching assistant strip** | Contextual chips inside the canvas: "Generate lesson plan", "Create question paper", "Suggest updates to these slides", "Map to outcomes" |
| C12 | **Attendance widget** | Per-session bar with a click-through to the roster |

### 2.6 Cards

**Session card (Grid view, 3 per row at 1920 px)**

```
┌──────────────────────────────────┐
│▌L08                    ⏱ Today ⋯│   ▌ teaching tint
│  Graph Algorithms                │
│  Tue 4 Aug · 10:30 · B204        │
│  ┌────────────────────────────┐  │
│  │  [slide thumbnail preview] │  │
│  └────────────────────────────┘  │
│  CO2  CO3        📎 5   👥 62    │
│  ⚠ Materials last updated 2025   │
├──────────────────────────────────┤
│ [Open]  [Materials]           ✦  │
└──────────────────────────────────┘
```

**Other cards:** Course card (context of Teaching home — code, title, term, enrolment, progress ring, next session, alert count); Assessment card (title, type, date, marks, submission progress bar, grading progress); Material card (thumbnail, type, version, size, linked sessions); Template card (in the template picker — preview, source, usage count).

### 2.7 Tables

**Sessions — List view**

| Column | Width | Content | Notes |
|---|---|---|---|
| ⬚ | 40 px | Selection checkbox | — |
| # | 60 px | Session number | Sortable, default sort |
| Topic | 24% | Title + 1-line description | Inline editable |
| Date & time | 14% | Date + time + room | Sortable |
| Status | 10% | Status pill | Filterable |
| Materials | 8% | Count + type glyphs | Click opens material drawer |
| Outcomes | 10% | CO chips | Inline editable |
| Attendance | 8% | % + micro-bar | Sortable |
| Updated | 10% | Relative date; amber if from a prior offering | Sortable |
| ⋯ | 48 px | Overflow | — |

**Submissions table:** Student (avatar+name+roll), Submitted (timestamp, late pill), File, Similarity %, Rubric score breakdown (expandable), Total, Grade, Feedback status, Actions. Supports inline marks entry with `Tab` traversal, bulk grading, and a "Grade next ungraded" flow.

**Question bank table:** Question (truncated with expand), Type, Marks, Bloom, CO, Difficulty, Times used, Last used, Performance (avg score), Actions.

**Outcome attainment table:** CO, Description, Target %, Direct attainment, Indirect attainment, Overall, Status pill, Contributing assessments (expandable).

### 2.8 Filters

Filter fields available: Term · Course · Session type · Week range · Status · Has materials · Materials age · CO mapped (yes/no) · Delivery mode · Instructor · Attendance range · Submission status · Grading status · Similarity threshold · Tag.

Quick filter chips above the table: `All · This week · Needs prep · Ungraded · No CO mapping · Stale materials`. Saved views: "Prep queue", "Grading backlog", "Accreditation evidence", "Guest-lecture sessions".

### 2.9 Search

- **Scoped search field** in the context pane filters the course tree.
- **`Ctrl+F`** opens an in-canvas find bar filtering the current list/grid with match highlighting and `↵`/`Shift+↵` traversal.
- **`Ctrl+K` with Teaching scope pre-set** when invoked from this screen — the palette shows a `Teaching` scope chip that can be removed to search everywhere.
- **AI search examples surfaced as placeholder hints:** "the slides where I explained NFA to DFA conversion", "assessments not mapped to CO3".

### 2.10 Buttons

Primary: `+ New Session`. AI-accented: `⟲ Roll Forward`, `✦ Generate lesson plan`, `✦ Create question paper`, `✦ Suggest outcome mapping`, `✦ Summarise feedback`. Secondary: Import, Share, Export course pack, Publish to LMS, Approve syllabus, Bulk grade, Download submissions, Print. Destructive: Cancel session, Delete assessment, Archive course. Icon: preview, attach, reorder, duplicate, comment, more.

### 2.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **Roll Forward Wizard** | Full-screen overlay | *Step 1 Source* (pick the previous offering) → *Step 2 Review* (side-by-side diff, per-item Keep/Update/Drop, AI flags for outdated references, broken links, superseded readings) → *Step 3 Schedule* (map sessions to the new academic calendar, auto-shifting for holidays) → *Step 4 Confirm* (summary: 14 kept, 6 flagged for update, 2 dropped) → progress → success with "Open new offering" |
| **New Session** | Medium | Number, topic, type, date/time, room, delivery mode, description, CO mapping, material attach, "Copy from previous offering" toggle |
| **Create Assessment** | Large | Metadata + question builder + live Bloom/CO/marks distribution panel + AI generate + reuse warnings |
| **Question Picker** | Large | Searchable question bank with filters, multi-select, marks preview, "avoid recently used" toggle |
| **Grade Submission** | Full-screen overlay | Document viewer left, rubric right, annotation tools, previous/next navigation, quick comment bank, AI-assisted feedback draft (clearly labelled) |
| **CO Mapping** | Medium | Matrix editor with AI suggestions and rationale on hover |
| **Publish to LMS** | Medium | Target LMS, items to publish, visibility dates, mapping preview, dry-run result |
| **Import Materials** | Medium | Source picker, file list with AI-proposed session assignment, per-item override |
| **Course Settings** | Large, tabbed | General · Schedule · Team (co-instructors, TAs with role scopes) · Outcomes · Grading scheme · Integrations · Permissions · Archive |
| **Attainment Report** | Large | Configuration + live preview + export |
| **Delete/Archive** | Small | Impact summary ("This will archive 47 artefacts; they remain searchable") + confirm |

### 2.12 Right-Click Menus

**On a session card/row:**
```
⊙ Open session                    Enter
⧉ Open in new tab           Ctrl+Enter
👁 Quick preview                  Space
─────────────────────────────────────
✦ Generate lesson plan
✦ Suggest updates to materials
✦ Create quiz from this session
✦ Ask AI about this session
─────────────────────────────────────
✎ Edit details                      E
📎 Manage materials
🎯 Map to outcomes
📅 Reschedule…
👥 Take attendance
─────────────────────────────────────
⧉ Duplicate session                 D
↔ Move to week…                    ▸
🔗 Copy link                   Ctrl+L
⇪ Share…                            S
─────────────────────────────────────
✓ Mark as taught
⊘ Cancel session
🗑 Delete session              Delete
```

**On a course (tree node):** Open · Open in new window · ⟲ Roll forward to next term · Duplicate course · Export course pack · Publish to LMS · Course settings · Manage team · View attainment · Pin to sidebar · Archive course · Delete course.

**On a material row:** universal artefact menu + "Attach to session ▸", "Replace with new version", "Compare with previous offering's version", "Mark as up to date".

**On a submission row:** Open in grader · Download · View similarity report · Request resubmission · Excuse late penalty · Add private note · Message student · Return with feedback.

**On a question (bank):** Edit · Duplicate · View usage history · View performance stats · Change difficulty ▸ · Retag CO ▸ · Retire question · Delete.

**On empty canvas:** New session · Bulk create sessions from plan · Import materials · Paste · View ▸ · Group by ▸ (Week / Status / Type / Outcome) · Refresh.

### 2.13 Context Menus

- **Selection bar** (multi-select sessions): "6 sessions selected" → Mark as taught · Reschedule · Map outcomes · Export · Duplicate to another course · Delete · `⋯`.
- **Grading context bar:** in the grader overlay — "Submission 12 of 62" with Previous/Next, Save & next, Skip, Flag for review, and a running average indicator.
- **Text selection in a syllabus/material:** Copy · Comment · ✦ Explain · ✦ Simplify for students · ✦ Generate question from this · Link to outcome.
- **Column header menu:** standard plus "Show attainment column", "Show similarity column".

### 2.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `T` | Go to Teaching |
| `N` | New session |
| `Shift+R` | Roll Forward wizard |
| `1`/`2`/`3`/`4` | Switch view: Grid / List / Board / Timeline |
| `W` | Jump to current week |
| `[` / `]` | Previous / next session |
| `M` | Manage materials for selection |
| `O` | Open outcome mapping |
| `A` | Take attendance |
| `Shift+G` | Open grader for the selected assessment |
| `Ctrl+Enter` (in grader) | Save and go to next submission |
| `Ctrl+Shift+P` | Publish to LMS |
| `Ctrl+F` | Find in view |
| `E` / `D` / `Delete` | Edit / duplicate / delete selection |

### 2.15 Modern UX Details

- **Staleness intelligence:** any material whose last update predates the current offering shows an amber dot and a "last taught with" tooltip. The *Needs updating* smart view is generated from this automatically — it is the highest-value nudge in the entire Teaching screen.
- **Roll-Forward is a celebration moment, not a chore:** the diff screen shows a summary ribbon ("You're reusing 14 sessions and 87 materials — saving an estimated 22 hours") before the user commits. Honest, quantified value.
- **Inline attendance:** clicking the attendance chip opens a fast roster overlay with keyboard-only marking (`↓` next student, `P/A/L` present/absent/late).
- **Live enrolment sync ticker** in the status bar when LMS sync runs.
- **Drag-and-drop everywhere:** drag files onto a session card to attach; drag a session between weeks to reschedule (with a confirmation toast and undo); drag a question from the bank into an assessment.
- **Semester progress** is always visible as a thin bar under the course breadcrumb — spatial awareness of where you are in the term.

### 2.16 Glassmorphism

Glass is used for: the sticky week-band headers once content scrolls beneath them (Acrylic Thin), the grading overlay's floating toolbar (Acrylic Base), the AI suggestion strip (Frosted Card with violet tint), the material drawer that slides over the canvas (Acrylic Base), and the Roll-Forward wizard's step header. Session cards, tables and the syllabus editor remain solid.

### 2.17 Dark & Light Mode

Light: teaching-domain cyan tint bars at full strength; slide thumbnails on white cards; week bands `N2`. Dark: cyan lifted to `#22D3EE` at 85% saturation; slide thumbnails rendered on a light "paper card" with a 10 px inset so decks never invert; week bands `N3` with a top highlight; the "today" band uses a 6% accent wash rather than a border to avoid glare; attendance heat colours are desaturated 15% to prevent vibration against dark surfaces.

### 2.18 Edge States

- **No courses:** "Add your first course" with three paths — Import from LMS · Import from a previous semester's files · Create manually. Shows an example course preview.
- **Course with no sessions:** "Plan your semester" → AI offers to generate a 16-week session plan from the syllabus.
- **Archived term:** entire canvas gets a subtle diagonal watermark and a banner: "This offering is archived and read-only. [Roll forward to a new offering]".
- **Co-taught course:** instructor avatars in the header; edits show attribution; simultaneous editing shows presence indicators.
- **LMS sync conflict:** inline banner with a "Resolve conflicts" action opening a three-way comparison.

---

## SCREEN 3 — RESEARCH

### 3.1 Purpose

Research is the **scientific workspace**: literature, protocols, experiments, datasets, analysis and figures, bound together by an unbroken provenance chain. Where *Projects* (Screen 5) manages the *management* of research (money, milestones, people, deliverables), Research manages the *substance* of it. Its defining feature is the **Provenance Graph** — the ability to answer "how was this figure produced?" in one click, from raw instrument file to published claim.

**Primary success metric:** ≥ 80% of figures in submitted manuscripts have a complete, machine-verified lineage.

### 3.2 Layout

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  🔬 Research › NANOCAT › Experiments › Run 42                    [Ctrl+K] ✦ 🔔 ◐ │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [+ New ▾] [⇪ Ingest data] [⎘ Provenance] [Reproducibility pack] │ [☰|▦|◈ Graph|⏱ TL] │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [⚲ Filter] [Type: Dataset ✕] [Status: Validated ✕] [+ Add filter]      [Save view ▾] │
├────────────────────┬──────────────────────────────────────────┬──────────────────────┤
│ CONTEXT PANE       │  CANVAS — Experiment Run 42              │  INSPECTOR           │
│ ─────────────────  │  ─────────────────────────────────────── │  ─────────────────   │
│ ⚲ Filter           │  ┌─ Run 42 · Selectivity Assay ────────┐ │  raw_run42.csv       │
│ ▾ 🔬 NANOCAT       │  │ Protocol: PROT-07 v2.1  ● Complete  │ │  ────────────────    │
│   · Overview       │  │ Operator: R. Menon · 14 Mar 2026    │ │  Details Provenance  │
│   · Literature  12 │  │ Instrument: XRD-2 · Session 8841    │ │                      │
│   · Protocols    7 │  ├──────────────────────────────────────┤ │  Type: Raw dataset   │
│   · Experiments ◀42│  │ PARAMETERS                           │ │  Size: 412 MB        │
│   · Datasets    89 │  │ Temp 340K · pH 7.2 · Catalyst 2.4mg │ │  Rows: 1,204,882     │
│   · Analysis    23 │  │                                      │ │  Hash: a3f9…verified │
│   · Figures     31 │  │ ARTEFACTS                            │ │  Tier: Hot           │
│   · Lab notebook   │  │ 📊 raw_run42.csv       412 MB  ⛓     │ │  Licence: CC-BY-4.0  │
│   · Ethics         │  │ 🐍 preprocess.py    @8b21c4d  ⛓     │ │  ⚿ Immutable (raw)   │
│ ▸ 🔬 BIOSENS       │  │ 📊 cleaned_v2.parquet  88 MB   ⛓     │ │                      │
│ ▸ 🔬 Archive       │  │ 📈 fig3_selectivity.svg        ⛓     │ │  Used by: 3 outputs  │
│ ─────────────────  │  ├──────────────────────────────────────┤ │  [View lineage ⎘]    │
│ SMART VIEWS        │  │ ⎘ LINEAGE  raw → clean → fig3 → MS187│ │                      │
│ ★ Unlinked data 6  │  │ NOTES · 4 entries · last 2 days ago  │ │                      │
│ ★ No DMP coverage 3│  └──────────────────────────────────────┘ │                      │
│ ★ Failed runs      │                                          │                      │
├────────────────────┴──────────────────────────────────────────┴──────────────────────┤
│ 42 runs · 89 datasets · 1.4 TB (620 GB cold)   Provenance complete 94% ▸   ● Online  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Sidebar (Context Pane)

Tree rooted at **research spaces (labs/programmes)**, each expanding into eight fixed sections mirroring the SRS folder spine: Overview · Literature · Protocols · Experiments · Datasets · Analysis · Figures · Lab notebook · Ethics. Counts appear as trailing badges; a red badge marks integrity issues (e.g. `Datasets 89 ⚠2` for hash-verification failures).

Smart Views: *Unlinked data* (datasets with no experiment), *No DMP coverage*, *Failed runs*, *Awaiting validation*, *Cold storage* (archived data, with retrieval time), *Recently ingested*, *My contributions*.

Footer: a storage bar split into Hot/Warm/Cold segments with a hover breakdown and a "Manage storage" link — a genuinely important control for labs with terabytes of instrument data.

### 3.4 Topbar & Command Bar

| Control | Type | Behaviour |
|---|---|---|
| `+ New ▾` | Primary split | Experiment run · Protocol · Dataset · Analysis · Figure · Literature note · Lab notebook entry · Research space |
| `⇪ Ingest data` | Secondary | Opens ingest dialog: upload, instrument drop folder, S3/SFTP pull, Git repository, cloud connector |
| `⎘ Provenance` | Secondary toggle | Switches the canvas into the lineage graph view for the current selection |
| `Reproducibility pack` | Secondary (AI-accented) | Assembles data + code + environment + README + licence |
| View switcher | Segmented | List · Board (by status) · **Graph** (provenance/knowledge graph) · Timeline (chronological runs) |
| `⋯` | Overflow | Space settings · Team & roles · Data management plan · Ethics approvals · Instrument links · Export space · Archive |

### 3.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Experiment run panel** | Header (ID, title, protocol link + version, operator, instrument, date, status), parameters block (key–value grid, copyable, diffable against the protocol's defaults with deviations highlighted amber), artefact list with chain glyphs `⛓`, inline lineage strip, notes timeline |
| C2 | **Provenance graph canvas** | Force-directed / layered DAG. Nodes: datasets (cylinder), code (angle-bracket), figures (chart), manuscripts (page), grants (coin). Edges typed and labelled. Interactions: pan/zoom, click to focus, double-click to open, `F` to fit, filter by node type, "highlight path to publication", export as SVG/PNG for a data-availability statement |
| C3 | **Dataset viewer** | Schema/variable dictionary table, sample rows (first 100 with virtualisation), summary statistics, distribution mini-charts per column, missing-value map, licence and access class, DOI status, checksum verification badge |
| C4 | **Protocol document** | Versioned structured steps with materials list, hazards, expected duration; "Start run from this protocol" button that pre-fills parameters; deviation log |
| C5 | **Literature matrix** | AI-populated comparison grid (Paper × Method/Sample/Findings/Limitations/Relevance); cells expandable to the source passage with citation; add/remove columns; export to CSV or a review draft |
| C6 | **Lab notebook** | Append-only, timestamped entries with rich text, images, attachments, and optional witness countersignature; entries are immutable after a 15-minute grace window, with amendments recorded as linked addenda |
| C7 | **Analysis viewer** | Notebook renderer (cells, outputs, plots) with the bound Git commit, environment manifest, and a "re-run" indicator if inputs changed since execution |
| C8 | **Figure card** | Rendered preview, caption, source data link, generating script link, "used in" list, version history, export at publication resolution |
| C9 | **Integrity strip** | Persistent thin bar on data views: "Checksum verified 2 h ago · 89/89 datasets intact" — green, or danger if any mismatch |
| C10 | **DMP posture widget** | Overview tab: promised vs. actual (where data lives, licence, retention, sharing), with a per-clause compliance pill |
| C11 | **AI research strip** | "Summarise these 12 papers" · "Find gaps" · "Compare with Run 38" · "Draft methods section" · "Check reproducibility" |

### 3.6 Cards

**Dataset card:** domain tint (research violet), type glyph, name, size, row/column count, format badge, status pill (Raw / Cleaned / Validated / Published), storage tier chip (Hot/Warm/Cold with retrieval time), DOI badge if minted, lineage glyph with upstream/downstream counts, integrity check mark, hover footer: Open · Lineage · Download · `⋯`.

**Experiment run card (Board view):** run ID, title, protocol version, operator avatar, date, status pill, parameter summary chips, artefact count, a small result thumbnail if a figure exists, and a deviation warning if parameters diverged from protocol.

**Literature card:** paper title, authors, venue, year, relevance score (AI, with rationale on hover), read status, annotation count, "cited in my work" badge, key-finding one-liner.

**Protocol card:** name, version, step count, estimated duration, hazard chips, times used, last used, linked equipment.

### 3.7 Tables

**Datasets table**

| Column | Content |
|---|---|
| ⬚ / Type | Selection + format glyph |
| Name | Filename + title, inline editable |
| Experiment | Linked run (chip, click to navigate) |
| Status | Raw / Cleaned / Validated / Published / Deprecated |
| Size | Human-readable, right-aligned tabular |
| Records | Row count |
| Created | Date + operator avatar |
| Tier | Hot / Warm / Cold with retrieval estimate |
| Lineage | `↑2 ↓3` upstream/downstream counts, click opens graph |
| Integrity | ✓ verified / ⚠ mismatch / — unverified, with timestamp tooltip |
| Licence | SPDX chip |
| DOI | Minted / Ready / — |
| ⋯ | Overflow |

**Experiments table:** Run ID · Title · Protocol (with version) · Operator · Date · Duration · Status · Deviations count · Outputs count · Quality flag.
**Analysis table:** Notebook/script · Language · Commit · Environment · Inputs · Outputs · Last run · Reproducible (✓/⚠) · Runtime.
**Literature table:** Title · Authors · Venue · Year · Relevance · Status · Annotations · Linked to (projects/manuscripts) · Added.

### 3.8 Filters

Fields: Research space · Section · Status · Data type/format · Size range · Date range · Operator/contributor · Protocol · Instrument · Storage tier · Integrity state · Licence · Has DOI · Has lineage · DMP covered · Ethics approval · Tag · Quality flag · Deviation present.

Quick chips: `All · My data · Validated · Unlinked · Cold · Failed runs · Publication-ready`. Saved views: "Ready to deposit", "Needs validation", "Reproducibility gaps", "Last 30 days".

### 3.9 Search

Context-pane filter for the tree; `Ctrl+F` in-canvas find; `Ctrl+K` with a `Research` scope chip. Research-specific search superpowers surfaced as hint text: search *inside* dataset column names and data dictionaries, inside notebook cells and code comments, inside lab notebook entries, and **provenance queries** ("what produced fig3?", "which datasets feed MS-0187?", "datasets with no downstream use"). Semantic search across the literature library returns passage-level hits with page anchors.

### 3.10 Buttons

Primary: `+ New`. AI-accented: `✦ Summarise literature`, `✦ Find gaps`, `✦ Draft methods`, `✦ Check reproducibility`, `✦ Suggest links`. Secondary: Ingest data, Provenance view, Reproducibility pack, Mint DOI, Deposit to repository, Verify integrity, Start run from protocol, Export lineage. Destructive: Deprecate dataset, Delete run, Purge (admin only, blocked for raw data under policy).

### 3.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **Ingest Data** | Large | Source tabs (Upload / Instrument folder / S3-SFTP / Git / Cloud). File list with AI-detected type, proposed experiment link, proposed licence, sensitivity. Warnings for PII detection. Per-file override. "Treat as raw (immutable)" toggle, on by default for instrument sources |
| **New Experiment Run** | Medium | Protocol picker (with version), auto-filled parameters, operator, instrument/session, planned date, expected outputs, deviations note |
| **Provenance Explorer** | Full-screen overlay | The lineage graph at full size with a left filter panel, a right node-detail panel, path highlighting, and export |
| **Reproducibility Pack** | Large wizard | Select outputs → resolve dependencies (auto-detected data + code + environment) → completeness check with warnings → licence and README → destination (download / Zenodo / Dataverse / OSF / institutional repo) → confirm |
| **Mint DOI** | Medium | DataCite metadata form pre-filled from artefact metadata, validation of required fields, embargo option, preview of the landing page |
| **Data Management Plan** | Large, tabbed | Plan text · Promised storage/licence/retention/sharing · Live compliance check per clause with links to offending artefacts · Version history · Export to funder template |
| **Verify Integrity** | Small | Progress + result summary; on mismatch, shows affected files with a "restore from replica" action |
| **Link Artefacts** | Medium | Relationship type picker + target search + confidence + note; supports bulk linking |
| **Ethics Approval** | Medium | Approval body, reference, dates, scope, documents, expiry alerting |
| **Cold Retrieval** | Small | "This dataset is in cold storage. Estimated retrieval: 3–5 hours. [Standard] [Expedited (cost)] [Notify me when ready]" |

### 3.12 Right-Click Menus

**On a dataset:**
```
⊙ Open                            Enter
👁 Preview data                    Space
⤓ Download                             
─────────────────────────────────────
✦ Describe this dataset
✦ Suggest analyses
✦ Check for anomalies
─────────────────────────────────────
⎘ View lineage                        
🔗 Link to experiment…                 
🏷 Edit metadata & licence             
✓ Mark as validated                    
─────────────────────────────────────
⬆ Promote to publication-ready         
◈ Mint DOI…                            
⇪ Deposit to repository…            ▸  
📦 Add to reproducibility pack         
─────────────────────────────────────
⚿ Verify integrity                     
❄ Move to cold storage                 
🗄 Archive                              
⊘ Deprecate (keeps lineage)            
```
Note: **Delete is absent for raw datasets** — the menu offers Deprecate instead, and only a policy-holding admin sees a purge option, behind a typed confirmation. This is a deliberate integrity guarantee made visible in the UI.

**On an experiment run:** Open · Duplicate as new run · Start from this protocol · Add artefacts · Log deviation · Mark complete/failed · View lineage · Compare with another run ▸ · Export run record · Archive.

**On a figure:** Open · Copy image · Copy at publication resolution ▸ (300/600 dpi, PNG/SVG/PDF/EPS) · Show source data · Show generating code · Insert into manuscript ▸ · Regenerate from source · Version history.

**On a literature item:** Open PDF · Open in reader · ✦ Summarise · ✦ Add to literature matrix · ✦ Find similar in my library · Cite ▸ (BibTeX/RIS/formatted) · Link to project ▸ · Mark as read · Add to reading queue · Annotate.

**On a graph node (provenance view):** Focus on this node · Expand upstream · Expand downstream · Highlight path to publication · Open artefact · Hide node · Explain this relationship (AI) · Copy node ID.

### 3.13 Context Menus

Selection bar for datasets: "8 datasets selected · 3.2 GB" → Link to experiment · Set licence · Set status · Move to tier ▸ · Add to pack · Verify · Export manifest · `⋯`. Graph canvas context bar: layout picker (Hierarchical / Force / Timeline), depth slider (1–5 hops), node-type filters, "Fit to view", "Export". Data-cell context (in the dataset preview): Copy value · Copy column · Filter by this value · Show distribution · Flag as anomaly.

### 3.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `R` | Go to Research |
| `N` | New (context-aware) |
| `I` | Ingest data |
| `L` | Toggle lineage/provenance view |
| `1`–`4` | List / Board / Graph / Timeline |
| `V` | Verify integrity of selection |
| `P` | Reproducibility pack |
| `Shift+D` | Mint DOI |
| `F` (graph) | Fit graph to view |
| `+` / `−` (graph) | Zoom |
| `Space` | Preview data/figure |
| `Ctrl+Shift+L` | Link artefacts |
| `[` / `]` | Previous / next run |

### 3.15 Modern UX Details

- **The chain glyph `⛓`** appears beside every artefact with complete provenance and is greyed when the chain is broken. Clicking it opens the lineage. This tiny, ubiquitous affordance is how the platform teaches researchers to value provenance.
- **Immutability is visible, not just enforced:** raw data rows carry a small lock and a "Raw — write-protected" tooltip; attempting to edit produces an explanatory inline message with the policy reason, not a generic denial.
- **Cold storage is honest:** cold items show a snowflake and an estimated retrieval time *before* the user clicks, and previews/summaries/search still work because derived data stays hot (SRS §13.1) — a fact the UI states explicitly on first encounter.
- **Deviation highlighting:** parameters differing from the protocol default are amber-tinted with the expected value on hover — catching methodological drift automatically.
- **Live ingest ticker:** instrument-folder ingests appear in the status bar and as a subtle "new data" pill in the context pane without stealing focus.
- **Graph performance:** the provenance canvas virtualises beyond 500 nodes, progressively loading hops and showing "+142 more nodes" expanders.

### 3.16 Glassmorphism

Applied to: the provenance graph's floating control bar and node-detail popover (Acrylic Base over the graph — glass is genuinely appropriate here because the canvas beneath is abstract, not textual), the AI research strip (Frosted Card, violet), the data-preview overlay toolbar, and the cold-retrieval toast. Data tables, dataset previews, notebooks and lab-notebook entries are strictly solid.

### 3.17 Dark & Light Mode

Light: research violet tint bars; graph on `N1` with `N6` edges; charts saturated. Dark: the provenance graph is where dark mode shines — nodes glow subtly (2 px violet outer glow on focus), edges use `rgba(255,255,255,.25)`, and the canvas uses `N0` for depth; dataset distribution charts desaturate 12%; figure previews render on light cards to preserve scientific colour accuracy — **never** invert or dim a figure without explicit user action, since colour is data.

### 3.18 Edge States

- **No research space:** "Create your first research space" with templates (Wet lab · Computational · Field study · Clinical · Social science) that pre-configure sections, protocols and metadata schemas.
- **Broken lineage:** an amber banner "3 artefacts have incomplete provenance" with a "Fix now" action opening a guided linking flow.
- **Integrity failure:** a danger banner, the affected file marked, automatic replica comparison, and an escalation path to support — treated as a serious event, never a silent log entry.
- **Very large dataset preview:** streams the first 100 rows with a note "Previewing 100 of 1,204,882 rows — [Open in analysis tool]".
- **Embargoed data:** lock icon, embargo end date, and a request-access path.

---

## SCREEN 4 — PUBLICATIONS

### 4.1 Purpose

Publications tracks every scholarly output through its **entire lifecycle** — idea → draft → internal review → submitted → under review → revision → accepted → published → post-publication impact — and maintains the authoritative, evidence-backed record of a scholar's contribution. It replaces the spreadsheet every academic maintains for their CV, and it feeds appraisal, accreditation and funder reporting automatically.

### 4.2 Layout (Pipeline / Board default)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  📄 Publications › Pipeline                                     [Ctrl+K] ✦ 🔔 ◐  │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [+ New Publication ▾] [⇩ Import by DOI] [ORCID sync] │ [▦ Board|☰ List|⏱ TL|▤ CV] │⋯│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [⚲ Filter] [Year: 2024-2026 ✕] [Role: Any ✕] [Type: Journal ✕] [+ Add]  [Save view ▾]│
├────────────────────┬──────────────────────────────────────────────────────────────────┤
│ CONTEXT PANE       │  CANVAS — Pipeline Board                                         │
│ ────────────────── │  ┌────────┬────────┬────────┬────────┬────────┬────────┐        │
│ ⚲ Filter           │  │ IDEA 3 │DRAFT 4 │REVIEW 2│SUBMIT 5│REVISE 2│ACCEPT 1│PUB 37  │
│ ▾ Pipeline      ◀  │  ├────────┼────────┼────────┼────────┼────────┼────────┤        │
│   · All          54│  │┌──────┐│┌──────┐│┌──────┐│┌──────┐│┌──────┐│┌──────┐│        │
│   · My first-author│  ││MS0201││MS0187││MS0192││MS0174││MS0166││MS0158││        │
│   · Corresponding  ││Catalytic│Selectiv│Graph  ││Nano   ││Deep   ││Auto   ││        │
│ ▾ By type          ││degradat│ity XRD │neural ││sensor ││learn  ││mata   ││        │
│   · Journal     31 ││        ││⚠ 9d    ││       ││Nature ││R1 due ││✓ IEEE ││        │
│   · Conference  14 ││👥3 ✦   ││👥2     ││👥4    ││Under  ││14 Aug ││TPAMI  ││        │
│   · Book ch.     5 ││        ││review  ││       ││rev 61d││       ││       ││        │
│   · Preprint     4 │└──────┘│└──────┘│└──────┘│└──────┘│└──────┘│└──────┘│        │
│ ▾ By venue         │  │+ Add   │+ Add   │        │        │        │        │        │
│ ▾ By year          │  └────────┴────────┴────────┴────────┴────────┴────────┘        │
│ ────────────────── │                                                                  │
│ SMART VIEWS        │  ┌─ METRICS STRIP ───────────────────────────────────────────┐  │
│ ★ Awaiting my input│  │ 54 outputs · 143 citations · h-index 9 · 31 Q1 · 4 OA gaps│  │
│ ★ Revisions due  2 │  └───────────────────────────────────────────────────────────┘  │
│ ★ OA non-compliant4│                                                                  │
│ ★ Stale > 90 days 3│                                                                  │
├────────────────────┴──────────────────────────────────────────────────────────────────┤
│ 54 publications · Last ORCID sync 3 h ago       Crossref updated ▸       ● Online     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Sidebar (Context Pane)

Grouped navigation rather than a file tree: **Pipeline** (All, My first-author, Corresponding author, Co-authored, Supervised student outputs) · **By type** (Journal, Conference, Book, Chapter, Preprint, Patent, Report, Dataset publication, Software) · **By venue** (top venues with counts) · **By year** (reverse chronological) · **By project/grant** (outputs attributable to funding) · **Collaborators** (people with counts).

Smart Views: *Awaiting my input*, *Revisions due*, *Under review > 90 days* (with a nudge to contact the editor), *OA non-compliant*, *Missing DOI*, *Unclaimed on ORCID*, *Stale drafts*.

### 4.4 Topbar & Command Bar

| Control | Behaviour |
|---|---|
| `+ New Publication ▾` | Journal article · Conference paper · Book chapter · Preprint · Patent · Report · Thesis · From an existing manuscript draft |
| `⇩ Import by DOI` | Paste one or many DOIs / a BibTeX file / a Scopus or WoS export; shows a match preview with duplicate detection before import |
| `ORCID sync` | Two-way sync with a review step; shows "12 works in ORCID not here · 3 here not in ORCID" |
| View switcher | **Board** (pipeline kanban) · List (table) · Timeline (by year with volume bars) · **CV view** (formatted, citation-styled, export-ready) |
| `⋯` | Citation style ▸ (APA/IEEE/Vancouver/Chicago/Harvard/custom) · Export ▸ (BibTeX, RIS, CSV, Word, PDF CV) · Metrics settings · Venue list management · Merge duplicates · Bulk claim |

### 4.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Pipeline board** | Seven stage columns with WIP counts; drag cards between stages (triggers stage-appropriate prompts, e.g. moving to *Submitted* opens a small form for venue, date and submission ID); column collapse; per-column sort |
| C2 | **Publication detail page** | Header (title, authors with CRediT roles, venue, status, DOI, metrics) + tabbed body: Manuscript (versions) · Authors & contributions · Submission history · Reviews & responses · Linked outputs (data, code, figures) · Funding · Compliance (OA, embargo, deposit) · Impact |
| C3 | **Author list editor** | Drag-to-reorder authors, corresponding-author flag, affiliation per author, ORCID chip, CRediT role matrix (14 roles × authors, checkbox grid), contribution statement generator |
| C4 | **Submission tracker** | Timeline of events (submitted, editor assigned, under review, decision, revision submitted) with durations between each — instantly reveals slow journals |
| C5 | **Reviewer response builder** | Two-column: reviewer comment (parsed into numbered points) | your response, with a "link to manuscript change" control that binds each response to the actual edit; completeness meter ("9 of 11 points addressed") |
| C6 | **Metrics strip / panel** | Citations (with source and last-updated), h-index, i10, field-weighted impact, altmetric, venue quartile — each with a provenance tooltip stating the data source and date |
| C7 | **Venue intelligence card** | On selecting a target venue: scope fit (AI, with rationale), acceptance rate, median time to first decision, APC, OA policy, indexing, quartile, and whether colleagues have published there |
| C8 | **OA compliance panel** | Funder mandate, licence, embargo clock, repository deposit status, and a one-click "Deposit accepted manuscript" |
| C9 | **CV view** | Formatted publication list in the chosen citation style, grouped and numbered, with print/export; supports "highlight my name in bold" and a role filter |
| C10 | **AI publication strip** | "Suggest target venues" · "Draft cover letter" · "Check reviewer points addressed" · "Generate lay summary" · "Find my related work" |

### 4.6 Cards

**Pipeline card:** MS ID, short title (2-line clamp), venue chip (target or actual), author avatars with a `+N`, stage-specific status line (e.g. "Under review · 61 days" or "R1 due 14 Aug" with an urgency colour), co-author activity dot, attachment count, and an AI badge if an AI-drafted element awaits review. Overdue items pulse once on load then stay static with a red left bar.

**Published card (grid/list):** full citation line in the active style, DOI chip (click to copy, `Ctrl+Click` to open), OA status badge (Gold/Green/Closed with colour), citation count with a sparkline, quartile badge, linked-dataset glyph, and a "verified" tick when metadata is confirmed against Crossref.

### 4.7 Tables

**Publications list view**

| Column | Content |
|---|---|
| ⬚ / Type | Selection + output-type glyph |
| Title | Title, 1-line clamp, inline expandable |
| Authors | Avatar stack + "et al."; the user's name bolded; position indicator (1st/corr/N of M) |
| Venue | Name + quartile badge + indexing chips |
| Year | Tabular |
| Status | Stage pill |
| Citations | Count + sparkline + source tooltip |
| OA | Badge (Gold/Green/Bronze/Closed) + compliance tick |
| DOI | Mono chip, copyable |
| Funding | Grant chips |
| Linked | Data/code/figure glyph counts |
| Updated | Relative |
| ⋯ | Overflow |

**Submission history table:** Venue · Submitted · Decision · Days · Outcome pill · Reviewer count · Notes.
**Contribution table (author view):** Author · Position · CRediT roles · Affiliation · ORCID · Corresponding · Verified.

### 4.8 Filters

Fields: Year/range · Type · Status/stage · Venue · Quartile · Indexing (Scopus/WoS/PubMed/DOAJ) · Author role (first/corresponding/co/supervisor) · Co-author · Project · Grant/funder · OA status · Licence · Embargo state · Citation range · Has dataset/code · Has DOI · Language · Department · Peer-reviewed (y/n) · AI-assisted (disclosure flag).

Quick chips: `All · This year · First author · Under review · Needs action · Q1 · Open access · Unclaimed`.

### 4.9 Search

`Ctrl+F` filters the current board/list. `Ctrl+K` scoped to Publications searches titles, abstracts, full manuscript text across all versions, reviewer comments, cover letters and author names. Distinctive capability surfaced in hints: **search inside your own reviewer responses** ("where did I address the sample-size critique?") and **semantic self-search** ("my work on catalytic selectivity") which returns outputs ranked by conceptual match rather than keyword.

### 4.10 Buttons

Primary: `+ New Publication`. AI-accented: `✦ Suggest venues`, `✦ Draft cover letter`, `✦ Check response completeness`, `✦ Lay summary`, `✦ Detect duplicates`. Secondary: Import by DOI, ORCID sync, Deposit to repository, Mint DOI, Export CV, Generate citation, Add co-author, Record submission, Record decision. Destructive: Withdraw submission, Retract (with a heavy, policy-aware confirmation and permanent record), Delete draft.

### 4.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **New Publication** | Medium | Type, title, target venue (with venue intelligence preview), authors (with ORCID lookup), linked project/grant, initial stage, optional manuscript upload |
| **Import by DOI/BibTeX** | Large | Input area → resolved preview table with confidence and duplicate warnings → per-row include/exclude → field-conflict resolution ("Crossref says 2024, you have 2023") → import summary |
| **ORCID Sync** | Large | Three-column diff: In ORCID only / In both (with conflicts) / Here only. Per-item direction control. Explains exactly what will be written to the public ORCID record before committing |
| **Record Submission** | Medium | Venue, date, submission ID, manuscript version snapshot (auto-frozen), cover letter attach, expected decision date |
| **Record Decision** | Medium | Outcome (Accept / Minor / Major / Reject / Desk reject), date, editor comments, reviewer reports upload, next-step suggestion |
| **Reviewer Response Builder** | Full-screen | Parsed reviewer points left, response editor right, manuscript diff bottom, completeness meter, export to the journal's format |
| **Author & Contributions** | Large | Author reordering, CRediT matrix, affiliation editor, contribution statement preview, "notify co-authors" toggle |
| **Venue Comparison** | Large | Side-by-side comparison of up to 4 venues across fit, quartile, acceptance rate, time to decision, APC, OA policy |
| **OA Compliance Check** | Medium | Per-mandate checklist with pass/fail, the action needed for each failure, and one-click deposit |
| **Merge Duplicates** | Medium | Field-by-field selection of the surviving value with a preview of the merged record |
| **Export CV** | Medium | Style, grouping, date range, types to include, numbering, highlight-own-name, output format (DOCX/PDF/LaTeX/HTML) |
| **Retract / Withdraw** | Small (destructive) | Reason, date, notice text, confirmation typed; the record is never deleted, only marked, preserving integrity |

### 4.12 Right-Click Menus

**On a publication:**
```
⊙ Open                            Enter
⧉ Open in new tab           Ctrl+Enter
─────────────────────────────────────
✦ Suggest target venues
✦ Generate lay summary
✦ Find my related work
─────────────────────────────────────
📋 Copy citation                    ▸   (APA · IEEE · Vancouver · BibTeX · RIS)
🔗 Copy DOI link
⤴ Export                            ▸
─────────────────────────────────────
✎ Edit details                      E
👥 Manage authors & contributions
📅 Record submission…
✓ Record decision…
🔗 Link to project / grant…          ▸
📊 Link dataset or code…
─────────────────────────────────────
◈ Mint DOI…
⇪ Deposit to repository…
🔓 Check OA compliance
─────────────────────────────────────
➡ Move to stage                     ▸
🗄 Archive
🗑 Delete draft                 Delete
```
For published items, *Delete* is replaced by *Withdraw / Retract…* and requires elevated confirmation — a published record is part of the institutional memory and cannot simply vanish.

**On a board column header:** Sort by ▸ · Collapse column · Set WIP limit · Add publication here · Select all in column.
**On an author chip:** View profile · View their other outputs with me · Set as corresponding · Edit CRediT roles · Remove author · Copy ORCID.
**On a venue chip:** Venue details · Compare venues · My history with this venue · Open venue site · Set as target.

### 4.13 Context Menus

Selection bar: "5 publications selected" → Export citations ▸ · Add to CV section ▸ · Link to grant · Set OA status · Bulk claim on ORCID · Merge · Archive. Card hover context: quick stage-advance arrow (`→` moves to the next stage with a confirmation toast and undo). Metrics context: clicking any metric opens a popover with its definition, source, last-updated timestamp and "how is this calculated?" — satisfying the SRS rule that every number is drillable.

### 4.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `P` | Go to Publications |
| `N` | New publication |
| `D` | Import by DOI |
| `1`–`4` | Board / List / Timeline / CV view |
| `→` / `←` | Advance / regress stage for the selected card |
| `C` | Copy citation in the active style |
| `Shift+C` | Citation style picker |
| `O` | ORCID sync |
| `R` | Record decision |
| `S` | Record submission |
| `A` | Manage authors |
| `Ctrl+E` | Export CV |

### 4.15 Modern UX Details

- **Time-in-stage is always visible.** A card that has sat in "Under review" for 61 days says so, and at 90 days the smart view surfaces it with a suggested action ("Journals in this venue average 47 days — consider a status enquiry. [Draft email]"). This converts passive anxiety into action.
- **Dragging a card between stages is a transaction**, not a cosmetic move: dropping into *Submitted* freezes a manuscript version snapshot automatically, so the record of exactly what was submitted always exists.
- **Co-author presence:** avatars show live presence when co-authors are viewing the same manuscript, with a subtle "R. Menon is viewing" chip.
- **Citation copy is one keystroke** (`C`) and respects the active style — a micro-optimisation that academics notice immediately.
- **Metric honesty:** every metric shows its source and age; the product never displays a citation count without saying where it came from and when.
- **CV view is genuinely print-perfect** — correct margins, hanging indents, no UI chrome, page numbers — because faculty will print it.

### 4.16 Glassmorphism

Board column headers become Acrylic Thin when cards scroll beneath them. The venue-intelligence popover, the citation-style flyout and the metrics-definition popover use Acrylic Base. The AI strip uses the Frosted Card. Publication detail pages, CV view, tables and the reviewer-response builder are solid — CV view in particular must be pixel-crisp for export fidelity.

### 4.17 Dark & Light Mode

Light: publication pink tint bars; OA badges in full-strength semantic colour; CV view always renders on white regardless of theme (with a note "CV preview always uses print colours"). Dark: board columns get `N2` surfaces with subtle top highlights; quartile badges desaturate slightly; the citation-sparkline uses `accent.hover`; the manuscript reading view offers the sepia focus theme; PDF proofs render on light cards.

### 4.18 Edge States

- **No publications:** "Import your publication record" with three paths — ORCID (recommended, one click), DOI list, BibTeX file — plus "Add manually". Shows an estimated time ("~2 minutes for 40 works").
- **Import conflicts:** a clear resolution table rather than silent overwrite; the system never changes an author-asserted field without asking (SRS FR-MET-009).
- **Retracted or corrected work:** permanent, prominent banner with the notice and date — handled with editorial seriousness.
- **Preprint/version relationships:** grouped display showing preprint → submitted → published as one lineage, not three duplicates.
- **External co-author without an account:** shown as a name chip with a "not on AcademicOS" marker and an invite affordance.

---

## SCREEN 5 — PROJECTS

### 5.1 Purpose

Projects is the **execution and accountability layer** across every domain: funded research projects, consultancy, institutional initiatives, curriculum-development projects and internal programmes. Where Research holds the science, Projects holds the *commitments* — milestones, deliverables, budgets, teams, tasks and reporting obligations. It answers: "Are we on track, who owes what, and what happens if we slip?"

*Boundary rule, stated explicitly for implementers:* a Research space may have zero or many Projects; a Project may span multiple Research spaces, courses and publications. Projects never duplicate artefacts — it links to them.

### 5.2 Layout (Project detail, Timeline view)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  📁 Projects › NANOCAT-2024 › Timeline                          [Ctrl+K] ✦ 🔔 ◐  │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [+ New ▾] [Report ▾] [Add expense] [Invite] │ [▦ Board|⏱ Timeline|☰ List|◱ Budget] │⋯│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [⚲ Filter] [Owner: Any ✕] [Status: Active ✕] [Overdue only ☐] [+ Add]   [Save view ▾]│
├────────────────────┬──────────────────────────────────────────────────────────────────┤
│ CONTEXT PANE       │  ┌─ PROJECT HEALTH ──────────────────────────────────────────┐  │
│ ────────────────── │  │ NANOCAT · SERB CRG/2024/1187 · ● On track                 │  │
│ ⚲ Filter projects  │  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░  62% elapsed  ·  58% delivered       │  │
│ ▾ Active         6 │  │ ₹62.0L sanctioned · ₹38.4L used (62%) · 14 mo remaining   │  │
│  ▾ NANOCAT-2024 ◀  │  │ 3 deliverables due in 30 days · 1 at risk                  │  │
│    · Overview      │  └───────────────────────────────────────────────────────────┘  │
│    · Milestones  8 │  ┌─ TIMELINE (Gantt) ────────────────────────────────────────┐  │
│    · Deliverables 6│  │        2025          2026              2027                │  │
│    · Tasks      24 │  │  Q3 Q4 │ Q1 Q2 Q3 Q4 │ Q1 Q2                              │  │
│    · Budget        │  │ M1 ████✓                        Literature & setup         │  │
│    · Team        7 │  │ M2   ██████✓                    Synthesis protocol         │  │
│    · Reports     3 │  │ M3      ████████●               Characterisation  ← today  │  │
│    · Compliance    │  │ M4          ░░░░░░░░            Scale-up trials            │  │
│    · Documents  84 │  │ D1  ◆ Interim report      ✓                                │  │
│  ▸ BIOSENS-2025    │  │ D2        ◆ Dataset release   ⚠ 14 Aug (at risk)          │  │
│  ▸ CURRIC-REV      │  │ D3               ◆ Final report                            │  │
│ ▸ Proposals      3 │  │ ─── dependencies shown as connectors, critical path in red │  │
│ ▸ Completed     11 │  └───────────────────────────────────────────────────────────┘  │
│ ────────────────── │  ┌─ AT RISK ─────────────┐ ┌─ RECENT ACTIVITY ──────────────┐  │
│ SMART VIEWS        │  │ D2 Dataset release    │ │ R. Menon uploaded 4 datasets   │  │
│ ★ Overdue        3 │  │ ⚠ No evidence linked  │ │ Budget: ₹1.2L equipment logged │  │
│ ★ Due in 30 days 7 │  │ [Attach] [Reschedule] │ │ M3 marked 80% complete         │  │
│ ★ Budget > 80%   2 │  └───────────────────────┘ └────────────────────────────────┘  │
├────────────────────┴──────────────────────────────────────────────────────────────────┤
│ 6 active projects · ₹1.84Cr managed · 3 overdue items        Report due in 6 d ▸      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Sidebar (Context Pane)

Grouped tree: **Active** (each project expanding into Overview · Milestones · Deliverables · Tasks · Budget · Team · Reports · Compliance · Documents · Risks) · **Proposals** (pre-award pipeline) · **Completed** · **Archived**.

Each project node shows a health dot (green/amber/red), a mini progress bar, and an alert badge. Right-click a project for the project menu; drag to reorder pinned projects.

Smart Views: *Overdue*, *Due in 30 days*, *Budget over 80%*, *My tasks*, *Awaiting my approval*, *No evidence attached*, *Reports due*, *Unassigned deliverables*.

Footer: aggregate portfolio figure ("₹1.84 Cr across 6 projects") with a link to the portfolio dashboard.

### 5.4 Topbar & Command Bar

| Control | Behaviour |
|---|---|
| `+ New ▾` | Project · Proposal · Milestone · Deliverable · Task · Risk · Expense · Report |
| `Report ▾` | Progress report · Utilisation certificate · Funder template ▸ · Custom report — each opens the AI-assisted generator |
| `Add expense` | Quick expense entry with document attach |
| `Invite` | Add a team member with a scoped role |
| View switcher | **Board** (tasks/deliverables kanban) · **Timeline** (Gantt with dependencies and critical path) · List (table) · **Budget** (financial view) |
| `⋯` | Project settings · Duplicate as template · Change funder details · Manage dependencies · Baseline vs actual · Export project pack · Close project |

### 5.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Project health header** | Name, funder + award number, status pill, dual progress bars (time elapsed vs. work delivered — the gap between them *is* the health signal), budget summary, days remaining, risk count |
| C2 | **Gantt timeline** | Milestones as bars, deliverables as diamonds, dependencies as connectors, critical path highlighted, today line, baseline ghost bars behind actuals, drag to reschedule (with dependency-shift preview), zoom (week/month/quarter/year), collapse by workstream |
| C3 | **Milestone panel** | Title, dates (planned/actual), % complete, owner, linked artefacts as evidence, acceptance criteria checklist, dependency list |
| C4 | **Deliverable card** | Type, due date, owner, status, **evidence slot** (the deliverable is not "done" until an artefact is linked — this is enforced, not advisory), funder-visibility flag, submission record |
| C5 | **Budget view** | Head-wise table (Equipment, Consumables, Travel, Manpower, Contingency, Overhead) with sanctioned / committed / utilised / balance, a burn-rate chart with projection to end-of-project, over/under-spend flags, and an expense ledger with document attachments |
| C6 | **Team panel** | Members with role, allocation %, start/end, contribution summary; vacancy slots; onboarding checklist per member |
| C7 | **Task board** | Kanban (To do / In progress / Blocked / Review / Done) with assignee avatars, due dates, priority, linked deliverable, subtasks, and blocked-reason chips |
| C8 | **Risk register** | Risk, likelihood, impact, score matrix, mitigation, owner, review date, status — with an auto-generated heat grid |
| C9 | **Reports panel** | Generated reports with status (Draft / Internal review / Submitted / Accepted), due dates, and the evidence used |
| C10 | **Compliance panel** | Ethics approvals, DMP posture, OA obligations, reporting obligations, IP declarations — each with a status pill and expiry alerting |
| C11 | **AI project strip** | "Draft progress report" · "What's at risk?" · "Find evidence for D2" · "Forecast budget" · "Summarise this month" |
| C12 | **Activity feed** | Chronological, filterable by type and person, with inline artefact previews |

### 5.6 Cards

**Project card (portfolio grid):** funding-domain green tint bar, project acronym + full name, funder logo/name, award number (mono), status pill, dual progress bars, budget ring (utilised %), team avatar stack, next milestone with countdown, alert badges (overdue/at-risk counts), hover footer: Open · Report · `⋯`.

**Deliverable card:** ID + title, due date with countdown pill (green > 30 d, amber ≤ 30 d, red overdue), owner avatar, status, **evidence indicator** (`📎 3 linked` in green or `⚠ No evidence` in amber — impossible to miss), funder-visible flag.

**Task card:** title, assignee, due, priority flag, linked deliverable chip, subtask progress, blocked indicator with reason on hover.

**Proposal card (pre-award):** call name, funder, deadline countdown (prominent), amount requested, completeness meter, assigned sections with owner avatars, submission checklist status.

### 5.7 Tables

**Deliverables table**

| Column | Content |
|---|---|
| ⬚ / ID | Selection + deliverable ID |
| Deliverable | Title + type glyph |
| Milestone | Parent milestone chip |
| Owner | Avatar + name |
| Due | Date + countdown pill |
| Status | Not started / In progress / Submitted / Accepted / Overdue |
| Evidence | Linked artefact count; amber warning if zero |
| Funder visible | Toggle indicator |
| Submitted | Date + submission reference |
| ⋯ | Overflow |

**Budget table:** Head · Sanctioned · Committed · Utilised · Balance · Utilisation % (bar) · Variance · Last transaction. Expandable rows reveal the expense ledger: Date · Description · Amount · Document · Approver · Status.

**Tasks table:** Task · Assignee · Deliverable · Priority · Due · Status · Blocked by · Effort · Updated.
**Team table:** Member · Role · Allocation % · Start · End · Contributions · Access level · Status.
**Risk table:** Risk · Category · Likelihood · Impact · Score (colour-coded) · Mitigation · Owner · Review date · Trend arrow.

### 5.8 Filters

Fields: Project · Status · Funder/agency · Scheme · PI/Co-PI · Team member · Date range · Milestone · Deliverable status · Task status/priority/assignee · Budget head · Amount range · Utilisation % · Risk score · Overdue (bool) · Evidence attached (bool) · Funder-visible (bool) · Compliance state.

Quick chips: `All · My projects · Overdue · Due 30 days · At risk · Over budget · Awaiting approval`.

### 5.9 Search

Context-pane project filter; `Ctrl+F` in-view; `Ctrl+K` scoped to Projects searches project names, award numbers, deliverable text, task titles, report content, expense descriptions and meeting notes. Distinctive queries surfaced as hints: "deliverables with no evidence", "expenses over ₹50,000 without an invoice", "tasks blocked for more than a week", "what did we promise SERB for Q3?".

### 5.10 Buttons

Primary: `+ New`. AI-accented: `✦ Draft progress report`, `✦ What's at risk?`, `✦ Find evidence`, `✦ Forecast budget`, `✦ Summarise period`. Secondary: Add expense, Invite member, Link artefact, Set baseline, Reschedule, Request approval, Submit report, Export pack. Destructive: Cancel deliverable, Remove member, Close project (with a closure checklist), Delete draft proposal.

### 5.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **New Project** | Large wizard | Basics (name, acronym, type) → Funding (agency, scheme, award number, amount, period, budget heads) → Team (PI, Co-PIs, members with roles) → Structure (milestones and deliverables, or import from the proposal, or start from a template) → Compliance (ethics, DMP, OA obligations) → Review |
| **New Deliverable** | Medium | Title, type, milestone, owner, due date, acceptance criteria, funder-visible toggle, evidence requirement selector |
| **Link Evidence** | Medium | Search/browse artefacts, AI-suggested matches at top with rationale ("This dataset matches D2's description"), multi-select, relationship note |
| **Add Expense** | Medium | Date, head, amount, vendor, description, document upload (invoice/receipt), approver routing, GST/tax fields (locale-aware) |
| **Generate Report** | Large wizard | Report type & template → Period → Auto-gathered content preview (achievements, outputs, expenditure, deviations — each item citing its source artefact) → Gaps flagged in amber with "attach evidence" inline → Edit → Approvals routing → Export/Submit |
| **Reschedule** | Medium | New dates with a dependency-impact preview showing every downstream item that shifts, plus a "keep dependents fixed" option, and a required reason for the baseline variance log |
| **Budget Revision** | Medium | Head-wise reallocation with validation against funder rules (e.g. "Equipment cannot exceed 40%"), justification, approval routing |
| **Invite Member** | Medium | Person search (internal/external), role, allocation, period, access scope preview showing exactly what they will be able to see |
| **Risk Entry** | Small | Description, category, likelihood, impact, mitigation, owner, review date |
| **Close Project** | Large | Closure checklist (final report, UC, data deposited, outputs linked, team offboarded, documents archived) with per-item status and blockers; cannot complete until mandatory items pass |
| **Baseline vs Actual** | Large | Comparison view of planned vs. actual dates and spend with variance analysis |

### 5.12 Right-Click Menus

**On a project (tree or card):**
```
⊙ Open project                    Enter
⧉ Open in new window
─────────────────────────────────────
✦ Summarise project status
✦ What's at risk?
✦ Draft progress report
─────────────────────────────────────
+ Add milestone / deliverable / task ▸
👥 Manage team
💰 Manage budget
📅 View timeline
─────────────────────────────────────
📄 Generate report                  ▸
⤴ Export project pack
🔗 Copy link
─────────────────────────────────────
⚙ Project settings
⧉ Duplicate as template
📌 Pin to sidebar
─────────────────────────────────────
🏁 Close project…
🗄 Archive
```

**On a milestone (Gantt bar):** Open · Edit dates · Mark % complete ▸ · Reschedule with dependencies… · Add deliverable · Link evidence · Set as baseline · View dependencies · Split milestone · Delete.

**On a deliverable:** Open · Link evidence… · Mark submitted · Mark accepted · Reassign owner ▸ · Change due date… · Toggle funder-visible · Request evidence from owner (sends a notification) · Export deliverable pack · Cancel deliverable.

**On a task:** Open · Assign to ▸ · Set priority ▸ · Set due date ▸ · Mark blocked (with reason) · Convert to deliverable · Add subtask · Link artefact · Duplicate · Delete.

**On a budget row:** View transactions · Add expense · Request revision… · Export ledger · Set alert threshold… · View funder rules for this head.

**On a team member:** View profile · View contributions · Change role ▸ · Change allocation… · Message · Offboard from project.

**On the Gantt canvas (empty):** Add milestone here · Zoom ▸ · Show/hide ▸ (dependencies, baseline, critical path, weekends, holidays) · Fit to window · Export as image · Print.

### 5.13 Context Menus

Selection bar (multi-select deliverables): "4 deliverables selected" → Reassign · Change due date · Link evidence · Mark submitted · Export · `⋯`. Gantt drag context: while dragging a bar, a live tooltip shows new start/end and "3 dependent items will shift by 12 days"; dropping opens a small confirm with an undo. Budget cell context: right-click any figure → "Show contributing transactions" opens a filtered ledger. Approval context bar: when a report awaits the user's approval, a persistent glass bar appears at the canvas top: "Progress report Q3 awaiting your approval · [Review] [Approve] [Request changes]".

### 5.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `J` | Go to Projects |
| `N` | New (context-aware) |
| `1`–`4` | Board / Timeline / List / Budget |
| `T` | New task |
| `D` | New deliverable |
| `M` | New milestone |
| `E` | Add expense |
| `R` | Generate report |
| `L` | Link evidence to selection |
| `Shift+B` | Show/hide baseline on Gantt |
| `Shift+C` | Toggle critical path |
| `+` / `−` | Gantt zoom |
| `Home` | Jump to today on the timeline |
| `A` | Approve (when an approval is pending) |

### 5.15 Modern UX Details

- **Two progress bars, always.** Time elapsed vs. work delivered, stacked. When delivery lags time by more than 10 points the bar turns amber automatically. No project manager should have to compute this.
- **Evidence enforcement is the product's spine here:** a deliverable cannot be marked complete without a linked artefact. The dialog says so plainly and offers AI-suggested candidates — turning a compliance rule into a two-second action.
- **Dependency shift preview** before any reschedule commits — the single most requested feature by anyone who has used a Gantt tool that shifted 40 tasks silently.
- **Budget alerts are proactive:** at 80% utilisation of any head, an inline banner appears with a projection ("At the current rate, Consumables will exhaust by 12 Nov, 4 months before project end").
- **Report generation shows its sources.** Every auto-filled paragraph carries a small source chip; hovering highlights the underlying artefacts. Gaps appear as amber inline placeholders rather than invented text.
- **Currency and locale awareness** throughout (₹ Lakh/Crore formatting for Indian tenants, with a toggle to plain numerals for export).

### 5.16 Glassmorphism

Gantt floating controls (zoom, today, fit, legend) sit in an Acrylic Base bar over the timeline. The approval context bar and the risk-detail popover use Acrylic Base. The AI strip is a Frosted Card. Budget tables, ledgers, report editors and deliverable lists are solid — financial data must never sit on a translucent surface.

### 5.17 Dark & Light Mode

Light: funding-green tint bars; Gantt on `N1` with `N4` gridlines; critical path in `danger`; baseline ghosts at 30% opacity. Dark: Gantt canvas `N0` with `N3` gridlines; milestone bars use domain colours at 80% saturation with a 1 px lighter top edge for definition; the today line is `accent.hover` at full brightness; budget over-spend cells use a 12% danger wash rather than a solid fill to avoid glare on large tables; funder logos get a white pill background so they remain legible.

### 5.18 Edge States

- **No projects:** "Track your first project" with paths — Import from a proposal · Start from a funder template (SERB/DST/DBT/NSF/Horizon presets) · Create manually.
- **Proposal stage (pre-award):** the whole screen simplifies — no budget ledger, no deliverable evidence; instead a submission checklist, section owners, and a deadline countdown as the hero element.
- **Project overdue at the portfolio level:** the portfolio card shows a red state and the context pane sorts overdue projects first.
- **Closed project:** read-only with a watermark; reports and evidence remain accessible; a "Reopen" action requires an admin and a reason.
- **Multi-currency projects:** amounts display in the project currency with the institutional currency in a tooltip and an as-of exchange-rate note.

---

## SCREEN 6 — ADMINISTRATION

### 6.1 Purpose

Administration is the **institutional control plane**: organisation structure, people and roles, policies, accreditation and compliance, storage and licensing, integrations, audit and reporting. It is role-gated (Institution Administrator, Compliance Officer, Research Office, Dean/HoD see progressively narrower slices) and is designed so that a governance officer can answer any regulator's question with evidence, not assertion.

**Primary success metric:** accreditation evidence pack assembled in days, not months (SRS §6.3).

### 6.2 Layout (Compliance section)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  🏛 Administration › Compliance › NAAC Cycle 4 › Criterion 3     [Ctrl+K] ✦ 🔔 ◐ │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [+ Add framework] [⤴ Export evidence pack] [Assign gaps] [Verify] │ [◱ Heatmap|☰ List]│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [⚲ Filter] [Dept: All ✕] [Readiness: <80% ✕] [Owner: Any ✕]  [+ Add]   [Save view ▾] │
├────────────────────┬──────────────────────────────────────────────────────────────────┤
│ CONTEXT PANE       │  ┌─ NAAC CYCLE 4 · READINESS 78% ─────────────────────────────┐ │
│ ────────────────── │  │ Submission: 14 Mar 2027 (226 days)   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░  │ │
│ ▾ ORGANISATION     │  │ 7 criteria · 42 metrics · 318 evidence items · 34 gaps      │ │
│   · Structure      │  └────────────────────────────────────────────────────────────┘ │
│   · People     812 │  ┌─ CRITERION HEATMAP ────────────────────────────────────────┐ │
│   · Roles          │  │      C1    C2    C3    C4    C5    C6    C7                │ │
│   · Groups         │  │ CSE  ██92  ██88  ██68  ██95  ██81  ██74  ██90              │ │
│ ▾ GOVERNANCE       │  │ ECE  ██85  ██91  ██55  ██88  ██79  ██70  ██86    ← click   │ │
│   · Policies    24 │  │ MECH ██78  ██83  ██49  ██92  ██77  ██68  ██81      any cell│ │
│   · Approvals    9 │  │ MGMT ██94  ██90  ██72  ██89  ██85  ██79  ██93              │ │
│   · Delegations    │  │       green ≥85   amber 60-84   red <60                    │ │
│ ▾ COMPLIANCE    ◀  │  └────────────────────────────────────────────────────────────┘ │
│   ▾ NAAC Cycle 4   │  ┌─ CRITERION 3 · RESEARCH · 68% ─────────────────────────────┐ │
│     · C1 Curric 92%│  │ Metric              Target  Actual  Evidence  Owner  State │ │
│     · C2 T&L   88% │  │ 3.1.1 Grants        ₹5Cr    ₹4.2Cr    24     R.Off  ⚠ 84% │ │
│     · C3 Rsrch 68%◀│  │ 3.2.1 Publications  400     372       372     IQAC   ⚠ 93% │ │
│     · C4 Infra 95% │  │ 3.3.1 PhD awarded   60      41        41      Acad   ⚠ 68% │ │
│     · C5 Std   81% │  │ 3.4.2 Consultancy   ₹1Cr    ₹0.4Cr    9       R.Off  🔴 40%│ │
│   ▸ NBA (CSE)      │  │ 3.5.1 Extension     30      28        26      NSS    ⚠ 93% │ │
│   ▸ NIRF 2027      │  └────────────────────────────────────────────────────────────┘ │
│ ▾ PLATFORM         │  ┌─ GAPS (34) ────────────┐ ┌─ ACTIVITY ───────────────────┐   │
│   · Storage        │  │ 🔴 3.4.2 needs 6 more  │ │ Dr. Rao verified 12 items    │   │
│   · Licences       │  │ 🔴 3.3.1 needs 19 recs │ │ IQAC exported C1 pack        │   │
│   · Integrations   │  │ [Assign] [Notify]      │ │ 4 items rejected in review   │   │
│   · Audit log      │  └────────────────────────┘ └──────────────────────────────┘   │
├────────────────────┴──────────────────────────────────────────────────────────────────┤
│ 812 users · 47 TB used · 34 open gaps · Last audit export 2 d ago       ● Online      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Sidebar (Context Pane)

Four collapsible groups, each item role-gated (invisible if not permitted, never merely disabled — the SRS forbids leaking the existence of governance surfaces):

| Group | Items |
|---|---|
| **Organisation** | Structure (faculties → departments → centres → labs, effective-dated) · People · Roles & capabilities · Groups · Onboarding/Offboarding queue |
| **Governance** | Policies · Approval workflows · Delegations · Legal holds · Retention schedules · Conflict-of-interest declarations |
| **Compliance** | One node per active framework (NAAC, NBA per programme, NIRF, ABET, internal QA), each expanding to its criterion tree with live readiness percentages |
| **Platform** | Storage · Licences & seats · AI usage & budgets · Integrations · Taxonomies & vocabularies · Templates · Branding · Audit log · Data residency · Export & deletion |

Each criterion node shows a readiness pill; nodes below 60% get a red dot. Search field at the top filters across all four groups.

### 6.4 Topbar & Command Bar

Contextual to the active section. In Compliance: `+ Add framework` · `⤴ Export evidence pack` · `Assign gaps` · `Verify` · view switcher (Heatmap / List / Criterion detail) · `⋯` (Framework settings · Import criterion tree · Clone from previous cycle · Submission history · Print). In People: `+ Add user` · `Import CSV` · `Sync from HRIS` · `Bulk role change` · `Access review`. In Storage: `Set quotas` · `Tiering policy` · `Reclaim space` · `Usage report`.

### 6.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Org chart** | Interactive hierarchy with drag-to-restructure (effective-dated, with a "changes apply from" date picker and an impact preview), head assignment, headcount, and a history slider to view the structure as of any past date |
| C2 | **People directory** | Rich table with role, department, status, last active, storage used, license type; bulk actions; per-person drawer showing roles across scopes, delegations, access reviews and offboarding state |
| C3 | **Role & capability matrix** | The full 20-role × capability grid from SRS §3.3, editable for custom roles, with a "test as this role" simulator that shows exactly what a role can see |
| C4 | **Policy editor** | Rule builder (condition → action) with plain-language preview ("Members of Department of Physics cannot share unpublished datasets externally"), dry-run against the last 30 days of activity showing what would have been blocked, and staged rollout (monitor → warn → enforce) |
| C5 | **Criterion tree & heatmap** | Department × criterion grid; every cell is drillable to metrics, then to evidence items, then to source artefacts |
| C6 | **Metric row** | Target, actual, evidence count, owner, verification state, trend vs. previous cycle, and a "how is this calculated?" link to the Metric Registry definition |
| C7 | **Evidence panel** | Per-metric list of linked artefacts with verification status (Pending / Verified / Rejected with reason), the verifier, timestamp, and AI-suggested candidates awaiting acceptance |
| C8 | **Gap manager** | List of shortfalls with owner assignment, deadline, notification, and progress; bulk-assign by department |
| C9 | **Audit log explorer** | Filterable, exportable event stream with actor, action, resource, outcome, reason, IP, and hash-chain verification indicator; saved investigations; SIEM export configuration |
| C10 | **Storage administration** | Consumption by unit/type/age/tier with treemap, quota editor, tiering policy rules, reclaimable-space recommendations with projected savings |
| C11 | **Integration manager** | Connector cards with health status, last sync, error counts, credential expiry warnings, and per-connector logs |
| C12 | **Access review campaign** | Attestation workflow: reviewers, scope, progress, auto-expiry of unreviewed external access |

### 6.6 Cards

**Framework card:** framework logo/name, cycle, submission date with countdown, overall readiness ring, criteria count, gap count, owner, last export date, status pill.
**Policy card:** policy name, scope, enforcement mode chip (Monitor/Warn/Enforce), triggered count last 30 days, last modified, owner.
**Integration card:** service logo, connection status dot, last sync relative time, synced object counts, error badge, actions (Sync now / Configure / Disconnect).
**Department scorecard:** department name, head avatar, headcount, output metrics, compliance readiness, storage used, trend arrows.
**License card:** plan name, seats used/total with bar, renewal date, cost, and an "add seats" action.

### 6.7 Tables

**People table**

| Column | Content |
|---|---|
| ⬚ / Avatar | Selection + avatar with presence |
| Name | Name + email, inline link to profile drawer |
| Employee ID | Mono |
| Department | Chip, filterable |
| Designation | Text |
| Roles | Role chips with scope tooltips; `+N` overflow |
| Status | Active / Invited / Suspended / Offboarding / Alumni |
| Last active | Relative, amber if > 90 days |
| Storage | Used, with a bar |
| MFA | ✓ / ⚠ |
| Joined | Date |
| ⋯ | Overflow |

**Audit log table:** Timestamp (precise, sortable) · Actor (avatar + name + type badge for user/service/AI agent) · Action · Resource (type + link) · Outcome (Success/Denied/Error pill) · Reason · IP · Session — with an expandable row showing before/after hashes and the chain-verification state.

**Evidence table:** Artefact · Type · Owner · Criterion(s) mapped · Mapping source (Human/AI + confidence) · Verification status · Verifier · Date · Actions.

**Policy violation table:** Timestamp · Policy · Actor · Attempted action · Resource · Outcome (Blocked/Warned/Allowed with override) · Justification.

### 6.8 Filters

Fields vary by section. People: department, role, status, designation, last-active range, MFA state, storage range, license type, joined range. Compliance: framework, criterion, department, readiness range, owner, verification status, evidence source, gap severity. Audit: date/time range, actor, actor type, action category, resource type, outcome, IP range, session. Storage: unit, tier, artefact type, age, size range, owner.

Quick chips per section, e.g. Compliance: `All · Below 60% · Unassigned gaps · Unverified evidence · AI-suggested pending`. Audit: `All · Denied only · Privileged actions · External access · AI actions · Last 24 h`.

### 6.9 Search

Every Administration section has a local search field (people by name/email/ID; policies by text; audit by free text across actor/action/resource; evidence by title). `Ctrl+K` scoped to Administration additionally supports operational queries: "who has admin access?", "show denied access attempts this week", "which departments are below 70% on Criterion 3?", "users inactive for 6 months with active licences".

### 6.10 Buttons

Primary (per section): `+ Add framework` / `+ Add user` / `+ New policy`. AI-accented: `✦ Suggest evidence for this metric`, `✦ Explain this gap`, `✦ Draft criterion narrative`, `✦ Summarise audit anomalies`. Secondary: Export evidence pack, Assign gaps, Verify selected, Import CSV, Sync HRIS, Run access review, Set quotas, Dry-run policy, Export audit. Destructive: Suspend user, Revoke access, Delete policy, Apply legal hold (semi-destructive — heavily confirmed), Purge data (double-approval + typed confirmation + reason).

### 6.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **Add Framework** | Large wizard | Framework picker (library with logos and descriptions) → Cycle/period → Scope (institution/departments/programmes) → Criterion tree preview → Owner assignment → Baseline scan option ("Let AI map existing evidence now — estimated 40 minutes") → Confirm |
| **Evidence Mapping** | Large | Left: criterion + expected evidence description. Right: artefact search with AI-suggested candidates ranked with rationale. Multi-select, map, and set verification requirement. Shows an artefact's other criterion mappings (reuse is legitimate and encouraged) |
| **Verify Evidence** | Medium | Artefact preview, criterion context, Approve / Reject (with reason) / Request better evidence; keyboard-driven for bulk verification (`A` approve, `R` reject, `→` next) |
| **Export Evidence Pack** | Large wizard | Scope (framework/criteria/departments) → Format (regulator-specific structure, indexed PDF, ZIP with hyperlinked index) → Options (include provenance appendix, watermark, page numbering, cover page) → Preview table of contents → Generate (background job with progress and notification) |
| **Assign Gaps** | Medium | Gap list with owner picker, deadline, message; supports bulk assignment by department; preview of notifications to be sent |
| **Add / Edit User** | Medium | Identity, department, designation, roles with scope, manager, start date, license type, initial space provisioning |
| **Bulk Role Change** | Medium | Selected users list, role add/remove, effective date, reason, impact preview ("47 users will gain access to 12 spaces") |
| **New Policy** | Large | Condition builder, action, scope, exceptions, enforcement mode, message shown to users on denial, dry-run results |
| **Access Review Campaign** | Medium | Scope, reviewers, deadline, escalation, auto-revoke setting |
| **Legal Hold** | Medium (destructive-adjacent) | Scope selector, case reference, custodians, start date, notification text, and a clear statement of what is suspended (deletion, tiering, retention) |
| **Storage Quota** | Medium | Per-unit quota editor with current usage bars and overflow behaviour selection |
| **Integration Setup** | Medium | Credentials, scope selection, sync schedule, field mapping, test connection, dry-run |
| **Offboarding Workflow** | Large | Person, last day, successor picker, artefact ownership transfer preview (counts by type), access revocation schedule, alumni conversion toggle, handover manifest preview |

### 6.12 Right-Click Menus

**On a person:**
```
⊙ Open profile
📊 View activity
─────────────────────────────────────
✎ Edit details
🎭 Manage roles                     ▸
🔑 Reset MFA
📧 Resend invitation
👤 Impersonate…            (dual-approval, banner shown)
─────────────────────────────────────
💾 View storage usage
🔍 View audit trail
📋 Export user data (DSR)
─────────────────────────────────────
⏸ Suspend account
➡ Start offboarding…
🗄 Convert to alumni
```

**On a criterion / metric:** Open details · ✦ Suggest evidence · ✦ Draft narrative · Assign owner ▸ · Set target… · View evidence (N) · View history across cycles · Export criterion pack · Mark as complete.

**On an evidence item:** Open artefact · Approve · Reject with reason… · Request better evidence · View other criteria this maps to · View provenance · Unmap from this criterion · Replace with a newer version.

**On a policy:** Edit · Duplicate · Dry-run against last 30 days · Change enforcement mode ▸ · View violations · Disable · Delete.

**On an audit event:** View full detail · Copy event ID · Show related events (same session/actor/resource) · Verify hash chain · Export selection · Create investigation · Report as suspicious.

**On an org unit:** Open · Add child unit · Assign head · View members · View analytics · Rename (effective-dated) · Merge with… · Dissolve (with member reassignment).

### 6.13 Context Menus

Selection bar (people): "23 users selected" → Assign role · Remove role · Change department · Send message · Run access review · Suspend · Export. Verification context bar (during evidence review): "Item 8 of 34 · [Approve] [Reject] [Skip]" with running counters, keyboard-first. Heatmap cell context: hover shows a tooltip with metric breakdown; click drills into that department × criterion; right-click offers "Assign this cell's gaps", "Export this cell", "Compare with last cycle". Audit investigation context: selecting multiple events offers "Create timeline view" producing a chronological narrative of an incident.

### 6.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `X` | Go to Administration |
| `1`–`4` | Switch group: Organisation / Governance / Compliance / Platform |
| `N` | New (context-aware) |
| `V` | Enter verification mode |
| `A` / `R` (verify mode) | Approve / reject current item |
| `→` / `←` (verify mode) | Next / previous item |
| `E` | Export evidence pack |
| `Shift+A` | Assign gaps |
| `Ctrl+Shift+A` | Open audit log |
| `Ctrl+Shift+U` | People directory |
| `/` | Focus section search |

### 6.15 Modern UX Details

- **The heatmap is the hero.** A governance officer sees institutional readiness in one glance and can drill from colour → number → evidence → source artefact in four clicks. This is the visual that sells the platform to a Vice-Chancellor.
- **Every governance number is drillable and sourced** — clicking "372 publications" opens the exact list, with export. No trust required.
- **Verification is a keyboard-first assembly line.** A compliance officer can verify 200 evidence items in a session using only `A`, `R` and `→`, with a preview pane. Batch work deserves batch ergonomics.
- **Policies are dry-run first.** Nothing enforces silently; the admin sees exactly what would have been blocked before switching to enforce mode. This single pattern prevents the most common cause of enterprise software revolt.
- **Impersonation is honest:** a persistent orange banner across the entire window — "You are viewing as Dr. Iyer · Started 14:02 · [Exit]" — plus an entry in both users' audit logs and a notification to the impersonated user.
- **Effective-dated org changes** mean historical reports never break when a department is renamed or merged.

### 6.16 Glassmorphism

Used sparingly and deliberately — this is the most data-dense screen in the product. Permitted: the verification context bar (Acrylic Base, floating), heatmap cell tooltips, the framework switcher flyout, and the impersonation banner (Acrylic Thin with an amber tint). Everything else — tables, audit logs, policy editors, org charts, evidence lists — is strictly solid. Financial, legal and audit data on glass would be an accessibility and credibility failure.

### 6.17 Dark & Light Mode

Light: admin slate tint; heatmap uses a green→amber→red scale calibrated for deuteranopia (with an optional pattern overlay); audit rows alternate `N0`/`N1`. Dark: the heatmap desaturates 15% and increases luminance separation between bands so the three states remain distinguishable; the audit log becomes a genuinely comfortable long-session surface (this is where security staff spend hours) with `N1` rows, `N2` hover, and mono timestamps in `N11`; danger states use text + icon + colour, never colour alone; the impersonation banner remains high-contrast amber in both themes because it must never be missed.

### 6.18 Edge States

- **Insufficient permission:** sections the user cannot access are absent from the sidebar entirely. Direct URL access shows a clean "You don't have access to Administration" with a "Request access" path — never a partial render.
- **No framework configured:** "Set up your first accreditation framework" with the library and an estimate of the baseline-scan time.
- **Baseline scan running:** a progress banner with live counts ("Mapped 2,140 of 8,900 artefacts · 34 minutes remaining") and the ability to keep working.
- **Audit log at scale:** queries beyond 90 days route to the archive tier with an explicit notice and an estimated query time.
- **Tenant approaching licence limit:** persistent banner for admins with usage detail and an upgrade path.
- **Data residency lock:** attempts to configure a service outside the tenant's region are blocked with an explanatory dialog naming the policy and its owner.

---

## SCREEN 7 — STUDENTS

### 7.1 Purpose

Students is the **supervision and scholar-lifecycle workspace**. For a faculty member it is the place where doctoral and masters supervision actually happens: milestones, meetings, chapter feedback, progress and risk. For a department it is the place where scholar progression is monitored and defended. It converts supervision from an undocumented relationship into an evidenced, fair and disputable-proof record — for the benefit of both parties.

**Design ethic (non-negotiable):** risk indicators exist to trigger *support*, never punishment. Scholars can see their own risk signals and the reasoning behind them. No hidden scoring of human beings.

### 7.2 Layout (Scholar detail)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  👥 Students › PhD › Rahul Menon › Progress                     [Ctrl+K] ✦ 🔔 ◐  │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [+ Log meeting] [Give feedback] [+ Milestone] [Message] │ [◱ Overview|⏱ Timeline|☰]│⋯│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [⚲ Filter] [Programme: PhD ✕] [Stage: Any ✕] [Risk: Any ✕] [+ Add]     [Save view ▾] │
├────────────────────┬──────────────────────────────────────────────────────────────────┤
│ CONTEXT PANE       │ ┌─ RAHUL MENON · PhD Materials Science · Year 3 ─────────────┐  │
│ ────────────────── │ │ 👤 Admitted Aug 2023 · Supervisor: Iyer · Co: Krishnan     │  │
│ ⚲ Filter scholars  │ │ ● Medium risk — last contact 14 d, Ch.3 feedback 9 d late  │  │
│ ▾ PhD            3 │ │ ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░  Overall progress 62% · Month 36/48  │  │
│   ● R. Menon    ◀  │ └────────────────────────────────────────────────────────────┘  │
│   ● A. Sharma      │ ┌─ MILESTONE TIMELINE ───────────────────────────────────────┐  │
│   ● P. Nair    ⚠   │ │ ✓Coursework  ✓Comprehensive  ✓Proposal  ●DC-3  ○Synopsis   │  │
│ ▾ M.Tech         6 │ │  Nov 23       Apr 24          Sep 24    Aug 26   Mar 27    │  │
│ ▸ Completed     11 │ │                                    ▲today                   │  │
│ ▸ Prospective    2 │ └────────────────────────────────────────────────────────────┘  │
│ ────────────────── │ ┌─ THESIS ─────────────────┐ ┌─ RECENT MEETINGS ────────────┐  │
│ SMART VIEWS        │ │ Ch.1 Intro      ✓ Final  │ │ 21 Jul · Ch.3 structure      │  │
│ ★ Feedback overdue2│ │ Ch.2 Lit review ✓ Final  │ │  3 decisions · 2 actions ✓   │  │
│ ★ No contact 30d 1 │ │ Ch.3 Methods    ⚠ v7 awaiting│ │ 07 Jul · Data validation │  │
│ ★ Milestone due  3 │ │ Ch.4 Results    ◐ Draft  │ │  Actions: 1 overdue ⚠        │  │
│ ★ At risk        1 │ │ Ch.5 Discussion ○ Outline│ │ [Log meeting]                │  │
│ ────────────────── │ │ Ch.6 Conclusion ○ —      │ └──────────────────────────────┘  │
│ MY LOAD            │ │ 42,180 words · 62%       │ ┌─ OUTPUTS ────────────────────┐  │
│ 3 PhD · 6 M.Tech   │ │ [Open thesis] [Feedback] │ │ 2 journal · 1 conf · 3 datasets│ │
│ Feedback SLA 78%   │ └──────────────────────────┘ └──────────────────────────────┘  │
├────────────────────┴──────────────────────────────────────────────────────────────────┤
│ 9 scholars · 2 feedback overdue · 3 milestones this month        ● Online              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Sidebar (Context Pane)

Grouped by programme: **PhD · M.Phil · M.Tech/MS · Undergraduate projects · Postdocs · Completed · Prospective (admissions pipeline)**. Each scholar entry shows an avatar, name, a risk dot (green/amber/red) and a stage micro-label. Sorting options: name, risk, last contact, milestone proximity, year.

Smart Views: *Feedback overdue*, *No contact in 30 days*, *Milestone due this month*, *At risk*, *Awaiting my approval*, *Thesis in final year*, *Ready for examination*.

**My Load panel** (footer): counts by programme, aggregate feedback-SLA adherence, and an "equity" note if load is above the departmental norm — useful for workload conversations with an HoD.

For HoD/Dean roles the pane gains a **Department** switcher and an "All supervisors" grouping.

### 7.4 Topbar & Command Bar

| Control | Behaviour |
|---|---|
| `+ Log meeting` | Primary — opens the meeting log with the previous meeting's actions pre-loaded |
| `Give feedback` | Opens the chapter/artefact feedback flow for the current scholar |
| `+ Milestone` | Add or schedule a milestone event |
| `Message` | Secure in-product message thread with the scholar |
| View switcher | Overview (scholar dashboard) · Timeline (milestone Gantt) · List (all scholars table) · Board (by stage) |
| `⋯` | Scholar record settings · Committee management · Generate DC report · Generate viva pack · Progress report · Change supervisor… · Transfer record · Convert to alumni · Export scholar file |

### 7.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Scholar header** | Photo, name, programme, area, admission date, expected completion, supervisors, committee, funding source, enrolment status, risk pill with an explainer link |
| C2 | **Progress ring / bar** | Composite of milestone completion, thesis progress and output count, with a "months elapsed vs. months of progress" comparison and a plain-language verdict ("Slightly behind the typical trajectory for month 36") |
| C3 | **Milestone timeline** | Horizontal stepper with completed/current/future states, dates (planned vs. actual), overdue highlighting, and click-through to milestone records |
| C4 | **Thesis chapter board** | Chapter list with status (Outline / Draft / Under review / Revising / Final), word count, last edit, feedback state, and a supervisor-action badge when a chapter awaits response |
| C5 | **Meeting log** | Chronological entries with agenda, notes, decisions, action items (with owners and due dates), attachments, and **dual acknowledgement** state (supervisor ✓ / scholar ✓) — the disputable-proof record |
| C6 | **Action item tracker** | Cross-meeting list of open actions for both parties with overdue flags |
| C7 | **Feedback thread** | Inline document annotations grouped by chapter with resolve/unresolve, response threading, and a turnaround-time indicator |
| C8 | **Outputs panel** | Publications, datasets, presentations and awards attributable to the scholar, auto-linked from the graph |
| C9 | **Risk explainer** | A panel listing the exact signals contributing to a risk level ("Last contact 14 days (threshold 21) · Chapter feedback pending 9 days · Milestone DC-3 in 12 days · Output velocity below cohort median") with a "this looks wrong" feedback control |
| C10 | **Committee panel** | Members, roles, meeting history, next meeting, report status |
| C11 | **Supervisor load view** (HoD) | All supervisors × scholars matrix with load, SLA adherence and risk distribution |
| C12 | **AI supervision strip** | "Summarise progress since last meeting" · "Draft DC report" · "Prepare viva questions" · "Check thesis consistency" · "Draft feedback summary" |

### 7.6 Cards

**Scholar card (grid/board):** photo, name, programme + year, supervisor(s), current stage pill, progress ring, last-contact chip (colour-coded by recency), next milestone with countdown, risk dot with tooltip, output count, and hover actions (Open · Log meeting · Message · `⋯`).

**Milestone card:** milestone name, planned/actual dates, status, committee involved, documents required vs. attached, outcome.

**Meeting card:** date, duration, attendees, agenda summary, decision count, action count with completion state, acknowledgement status, attachments.

**Chapter card:** chapter number and title, status, word count with target, last edit, reviewer, days awaiting feedback (amber past SLA), version number.

### 7.7 Tables

**All scholars table**

| Column | Content |
|---|---|
| ⬚ / Photo | Selection + avatar |
| Scholar | Name + programme + year |
| Supervisor(s) | Avatar stack |
| Stage | Stage pill + micro progress bar |
| Progress | % with bar |
| Last contact | Relative, colour-graded |
| Next milestone | Name + date + countdown |
| Feedback pending | Count + oldest age |
| Outputs | Publication/dataset counts |
| Funding | Source + end date |
| Risk | Pill with tooltip |
| ⋯ | Overflow |

**Meetings table:** Date · Duration · Type (regular/DC/ad-hoc) · Attendees · Decisions · Actions (open/total) · Acknowledged · Attachments.
**Action items table:** Action · Owner · From meeting · Due · Status · Age · Linked artefact.
**Milestones table:** Milestone · Planned · Actual · Variance · Status · Documents · Committee · Outcome.
**Cohort table (HoD):** Scholar · Supervisor · Admitted · Expected · Elapsed % · Progress % · Variance · Risk · Interventions.

### 7.8 Filters

Fields: Programme · Year/cohort · Stage · Supervisor · Co-supervisor · Department · Risk level · Last-contact range · Feedback-pending age · Milestone due range · Funding source · Funding end · Enrolment status · Thesis progress range · Output count · Committee member · Nationality/visa status (admin-gated, for compliance reporting only).

Quick chips: `All · My scholars · At risk · Feedback overdue · Milestone this month · Final year · Awaiting my action`.

### 7.9 Search

Context-pane scholar filter; `Ctrl+F` in-view; `Ctrl+K` scoped to Students searches scholar names, thesis content across all chapter versions, meeting notes, decisions, action items and feedback comments. Distinctive queries: "what did I tell Rahul about the sample size?", "meetings where we discussed scope change", "scholars whose funding ends within 6 months", "chapters awaiting my feedback for more than a week".

### 7.10 Buttons

Primary: `+ Log meeting`. AI-accented: `✦ Summarise progress`, `✦ Draft DC report`, `✦ Prepare viva questions`, `✦ Check thesis consistency`, `✦ Draft feedback summary`. Secondary: Give feedback, Add milestone, Message, Schedule meeting, Upload document, Generate progress report, Add committee member, Approve chapter, Request revision. Destructive: Remove from supervision (with transfer requirement), Withdraw scholar (heavily confirmed, records preserved), Delete meeting log (blocked once acknowledged — an important integrity rule surfaced with an explanation).

### 7.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **Log Meeting** | Large | Date/time/duration/mode, attendees (pre-filled), agenda (with last meeting's open actions auto-inserted), notes (rich, with voice-to-text and "upload recording → transcribe" options), **Decisions** (structured list), **Action items** (text + owner + due date), attachments, and a footer: "Send to scholar for acknowledgement" (default on) |
| **Give Feedback** | Full-screen | Document viewer with inline annotation, a structured feedback panel (Strengths / Issues / Required changes / Optional suggestions), rubric option, overall verdict (Accept / Minor revision / Major revision / Restructure), AI-assisted drafting clearly labelled, and an estimated-turnaround note visible to the scholar |
| **Add Milestone** | Medium | Milestone type (from the institutional framework), planned date, committee, required documents checklist, notification settings |
| **Complete Milestone** | Medium | Actual date, outcome, documents upload, committee remarks, next milestone auto-scheduling |
| **Generate DC Report** | Large | Period, auto-assembled content (progress, meetings held, outputs, milestones, issues) with source chips, gaps flagged, editable, committee routing, export to institutional template |
| **Viva Preparation Pack** | Large wizard | Select thesis version → include publications, examiner reports, provenance appendix → AI-generated anticipated questions grouped by chapter with rationale → compile → export |
| **Thesis Consistency Check** | Large | AI report on terminology drift, figure/table numbering, citation completeness, undefined acronyms, cross-reference errors, and chapter-level style variance — each finding linked to its exact location |
| **Change Supervisor** | Medium | New supervisor, effective date, reason, record-transfer preview, notification to all parties, approval routing |
| **Scholar Record Settings** | Large, tabbed | Enrolment · Programme & milestones · Supervisors & committee · Funding · Access & permissions · Alerts & thresholds |
| **Risk Explanation** | Small | The signal list with thresholds, the computation, and controls to adjust thresholds or dismiss a signal with a reason |
| **Convert to Alumni** | Medium | Completion date, final outcome, degree awarded, archive scope, permanent attribution confirmation, continued-access settings |

### 7.12 Right-Click Menus

**On a scholar:**
```
⊙ Open record                     Enter
💬 Message
📅 Schedule meeting
─────────────────────────────────────
✦ Summarise progress
✦ Draft DC report
✦ Prepare viva questions
─────────────────────────────────────
📝 Log meeting                       L
✍ Give feedback                      F
🎯 Add milestone                     M
📄 Open thesis
─────────────────────────────────────
📊 Progress report
📋 Export scholar file
🔗 Copy link
─────────────────────────────────────
👥 Manage committee
🔄 Change supervisor…
⚙ Record settings
─────────────────────────────────────
🎓 Convert to alumni…
```

**On a meeting log:** Open · Edit (disabled after acknowledgement, with reason) · Add addendum · Acknowledge · Export as PDF · Copy decisions · Create tasks from actions · Email summary to scholar.

**On a chapter:** Open · Open in split view with the previous version · Give feedback · Approve · Request revision · Version history · Compare versions ▸ · Check consistency · Export chapter · Comment.

**On a milestone:** Open · Mark complete… · Reschedule… · Attach documents · Notify committee · View history · Remove.

**On an action item:** Mark complete · Reassign ▸ · Change due date… · Add note · Convert to task · Link artefact · Remove.

### 7.13 Context Menus

Selection bar (multi-select scholars, HoD view): "6 scholars selected" → Send message · Schedule group meeting · Export cohort report · Assign committee member · Change supervisor. Feedback context bar (in the feedback overlay): "Chapter 3 · Comment 4 of 12" with Previous/Next, Resolve, Save draft, Send. Annotation context (text selected in a chapter): Comment · Suggest edit · Mark as required change · ✦ Explain the issue · Link to a reference · Highlight ▸. Timeline context: right-click a milestone marker for reschedule/complete/notify.

### 7.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `S` | Go to Students |
| `L` | Log meeting for the selected scholar |
| `F` | Give feedback |
| `M` | Add milestone |
| `T` | Open thesis |
| `1`–`4` | Overview / Timeline / List / Board |
| `[` / `]` | Previous / next scholar |
| `R` | Show risk explanation |
| `Ctrl+Enter` (feedback) | Send feedback |
| `Ctrl+D` (meeting) | Add decision |
| `Ctrl+Shift+A` (meeting) | Add action item |
| `A` | Acknowledge meeting record |

### 7.15 Modern UX Details

- **The feedback SLA is visible to both sides.** A supervisor sees "Chapter 3 awaiting your feedback — 9 days"; the scholar sees the same figure. Mutual visibility, rather than one-sided surveillance, is what makes this ethically sound and behaviourally effective.
- **Meeting logs pre-load the previous meeting's open actions** into the agenda. Continuity becomes automatic rather than dependent on memory.
- **Dual acknowledgement** turns a note into a record. Once both parties acknowledge, the entry becomes immutable (amendments are appended, never overwritten) — protecting both supervisor and scholar in any future dispute.
- **Risk is explainable and contestable.** Every risk indicator opens a plain-language explanation with the contributing signals and thresholds, plus a "this is wrong" control that logs the disagreement and adjusts.
- **Progress framing is comparative but humane:** "Slightly behind the typical trajectory" rather than a red "FAILING" badge. Language matters enormously here.
- **Scholar-side parity:** when a scholar logs in, they see the same record — their milestones, their feedback wait times, their supervisor's SLA. Transparency in both directions.
- **Quiet celebration:** completing a milestone triggers a brief, dignified confirmation (a subtle check animation and a record entry) — never confetti.

### 7.16 Glassmorphism

Applied to: the feedback overlay's floating toolbar (Acrylic Base over the document), the annotation popover, the risk-explanation popover, the scholar quick-switch flyout, and the AI supervision strip (Frosted Card). The meeting log, thesis chapters, tables and reports are solid — legal-grade records must never render on translucency.

### 7.17 Dark & Light Mode

Light: supervision orange tint bars; chapter status colours at full strength; thesis documents on white. Dark: the thesis reading and feedback surface defaults to the sepia/dark reading theme with serif type at 17 px — this is where scholars and supervisors spend hours, so comfort is a functional requirement; annotation highlights use 25%-opacity fills that remain legible on dark; the milestone stepper uses filled/outlined states plus icons so completion is not conveyed by colour alone; photos and avatars get a subtle 1 px `rgba(255,255,255,.1)` ring for separation.

### 7.18 Edge States

- **No scholars:** "Add your first scholar" with paths — Import from the student information system · Invite by email · Create manually — plus an explanation of what the record will track.
- **Scholar with no activity:** the overview shows a gentle prompt to log the first meeting and set milestones rather than a set of empty charts.
- **Co-supervised scholar:** both supervisors visible with their respective SLA states; feedback attribution is explicit; conflicting feedback is flagged for discussion rather than hidden.
- **Scholar on leave / suspended:** timeline pauses with a clearly marked leave band; risk calculations exclude the leave period; expected completion auto-adjusts.
- **Overdue by a large margin:** escalation surfaces for the HoD with intervention options, framed as support (extension, additional supervision, resource allocation).
- **Completed scholar:** record becomes read-only with an alumni banner; outputs and attribution remain permanently linked; the supervisor retains access to the archive.

---

## SCREEN 8 — CALENDAR

### 8.1 Purpose

Calendar is the **temporal spine of academic life**. It is not a generic scheduling grid: it understands semesters, teaching weeks, examination periods, grant deadlines, milestone dates, conference calls for papers, and institutional holidays — and it binds every event to the artefacts and entities it concerns. Opening a class event should surface that session's slides; opening a DC meeting should surface the scholar's progress pack.

### 8.2 Layout (Week view)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  📅 Calendar › August 2026 › Week 32                            [Ctrl+K] ✦ 🔔 ◐  │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [+ New Event ▾] [Today] [◀ ▶] │ [Day|Week|Month|Term|Agenda|Deadlines] │ [⚲] [⋯] [◨]│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [Calendars: Teaching ✓ Research ✓ Supervision ✓ Admin ✓ Personal ✓ Deadlines ✓]      │
├────────────────────┬──────────────────────────────────────────────────────────────────┤
│ CONTEXT PANE       │      Mon 3   Tue 4   Wed 5   Thu 6   Fri 7   Sat 8   Sun 9      │
│ ────────────────── │      ─────   ─────   ─────   ─────   ─────   ─────   ─────      │
│ ◀ August 2026 ▶    │ 08                                                               │
│ M  T  W  T  F  S  S│ 09         ┌──────┐                ┌──────┐                      │
│             1  2   │ 10  ┌─────┐│CS-301│  ┌─────┐       │CS-540│                      │
│  3  4  5  6  7  8 9│ 11  │Lab  ││Lec 8 │  │CS-540      └──────┘                      │
│ 10 11 12 13 14 15..│ 12  │Mtg  │└──────┘  │Lec 8 │                                    │
│ ────────────────── │ 13  └─────┘┌──────┐  └─────┘  ┌────────────┐                     │
│ CALENDARS          │ 14         │R.Menon│          │Faculty mtg │                     │
│ ☑ 🎓 Teaching      │ 15         │1-on-1 │┌────────┐└────────────┘                     │
│ ☑ 🔬 Research      │ 16         └──────┘│DC Mtg  │                                    │
│ ☑ 👥 Supervision   │ 17                 │A.Sharma│                                    │
│ ☑ 🏛 Administration│ 18                 └────────┘                                    │
│ ☑ 👤 Personal      │ ────────────────────────────────────────────────────────────    │
│ ☑ ⏰ Deadlines     │ ALL-DAY / DEADLINES                                              │
│ ☐ 🌐 Institutional │ ▬▬▬ SERB Q3 report due (6 d) ▬▬▬  ▬ ICML abstract (12 d) ▬      │
│ ────────────────── │                                                                  │
│ ACADEMIC CONTEXT   │                                                                  │
│ Odd Sem · Week 3/16│                                                                  │
│ Next: Mid-sem exams│                                                                  │
│ 14–21 Sep          │                                                                  │
│ ────────────────── │                                                                  │
│ UPCOMING DEADLINES │                                                                  │
│ 🔴 SERB report  6d │                                                                  │
│ 🟠 ICML abstract12d│                                                                  │
│ 🟠 Ethics renew 21d│                                                                  │
├────────────────────┴──────────────────────────────────────────────────────────────────┤
│ 14 events this week · 3 deadlines · Synced with Outlook 4 min ago         ● Online    │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Sidebar (Context Pane)

| Block | Contents |
|---|---|
| **Mini-month navigator** | Compact month grid with event-density dots per day; click to jump; drag across days to select a range; current day ringed |
| **Calendars** | Toggleable layers, each with a colour swatch matching the domain tints: Teaching (cyan) · Research (violet) · Supervision (orange) · Administration (slate) · Personal (neutral) · Deadlines (red) · Institutional (green) · Subscribed external calendars |
| **Academic context** | Current term, teaching week N of M, next academic period (exams, breaks, results), with click-through to the Term view |
| **Upcoming deadlines** | Chronological list with urgency colouring and countdown; click scrolls the canvas to that date |
| **Room / resource** (optional) | Filter by room or equipment for booking-aware institutions |

### 8.4 Topbar & Command Bar

| Control | Behaviour |
|---|---|
| `+ New Event ▾` | Event · Class session · Meeting · Deadline · Milestone · Focus block · Out of office · Recurring series |
| `Today` | Jump to now (also `T`) |
| `◀ ▶` | Navigate period |
| View switcher | **Day · Week · Month · Term · Agenda · Deadlines** — Term view is the differentiator: a 16-week semester grid showing teaching weeks, exam windows, holidays and milestone markers on one screen |
| `⚲` | Filter (event type, participant, course, project, room, status) |
| `⋯` | Calendar settings · Working hours · Time zone · Connect external calendar · Import ICS · Export ICS · Print · Availability sharing link |
| `◨` | Inspector (event details) |

### 8.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Time grid** | Configurable working hours (default 08:00–20:00 with a collapsible "outside hours" band), 15-minute snapping, current-time line that updates each minute, overlapping-event side-by-side layout with intelligent narrowing |
| C2 | **Event block** | Colour = calendar; left border = domain tint; content adapts to duration (a 30-minute block shows title only; a 2-hour block shows title, location, attendees and linked artefacts); status via pattern (tentative = diagonal hatch, cancelled = strikethrough, declined = outline only) |
| C3 | **All-day / deadline band** | A horizontal strip above the grid for deadlines and multi-day items, with countdown pills |
| C4 | **Term view** | Weeks as rows, days as columns, sessions as compact chips; overlays for exam windows, holidays and institutional events; milestone diamonds; the single best view for semester planning |
| C5 | **Agenda view** | Chronological list grouped by day with rich rows (time, title, duration, location, attendees, linked artefacts, join button) — the most keyboard-friendly view |
| C6 | **Deadlines view** | All time-bound obligations across the system (grant reports, milestones, submissions, reviews, renewals, examination dates) in one prioritised list with owner and evidence state |
| C7 | **Event detail (inspector or popover)** | Title, time, recurrence, location/room, virtual link, attendees with RSVP state, description, **linked entities and artefacts**, agenda, notes, attachments, and a "prepare" action |
| C8 | **Scheduling assistant** | Availability grid across selected attendees with suggested slots ranked by fit (fewest conflicts, respects focus blocks and working hours across time zones) |
| C9 | **Focus blocks** | User-declared deep-work periods that the assistant protects and that visibly discourage meeting scheduling |
| C10 | **Conflict indicator** | Overlapping commitments flagged with a warning glyph and a one-click resolution flyout |
| C11 | **AI calendar strip** | "Prepare me for today" · "Find time with Meera and Rahul next week" · "Reschedule my Thursday" · "What's at risk this month?" |
| C12 | **Sync status chip** | Per-connected-calendar sync state with last-sync time and error surfacing |

### 8.6 Cards

**Event card (popover on click):** header with colour bar and type icon, title, date/time with duration, recurrence summary, location + room + capacity, virtual meeting join button, attendee avatars with RSVP, linked artefacts as chips (click to open in a side pane), agenda preview, and actions (Edit · Prepare · Log meeting · Cancel · `⋯`).

**Deadline card:** obligation title, source entity chip (grant/project/publication), due date + countdown, owner, evidence state (attached/missing), and actions (Open · Attach evidence · Request extension · Snooze).

**Preparation card (AI, morning):** "Your day: 3 events, 1 needs preparation" listing each event with what is ready and what is missing ("CS-301 Lecture 8 — slides not updated since 2025").

### 8.7 Tables

**Deadlines view table**

| Column | Content |
|---|---|
| ⬚ / Type | Selection + obligation type glyph |
| Obligation | Title + source entity chip |
| Due | Date + countdown pill (colour-graded) |
| Owner | Avatar |
| Status | Not started / In progress / Submitted / Complete / Overdue |
| Evidence | Attached count or amber warning |
| Escalation | Who is notified on miss |
| Effort | Estimated remaining |
| ⋯ | Overflow |

**Agenda table:** Time · Duration · Event · Type · Location · Attendees · Linked items · Prep state.
**Room booking table (institutional):** Room · Capacity · Facilities · Availability bar · Bookings · Actions.

### 8.8 Filters

Fields: Calendar layer · Event type · Course · Project · Scholar · Participant · Location/room · Status (confirmed/tentative/cancelled) · My response (accepted/declined/pending) · Organiser · Recurrence (single/series) · Has linked artefacts · Preparation state · Time of day · Duration range.

Quick chips: `All · My events · Needs preparation · Unanswered invitations · Deadlines only · Teaching only · This term`.

### 8.9 Search

`Ctrl+F` filters events in the current period with match highlighting. `Ctrl+K` scoped to Calendar searches event titles, descriptions, agendas, attendees, locations and linked meeting notes across all time — including the past, which matters enormously ("when did I last meet the industry partner?"). Natural-language date parsing is supported in the search box itself: "meetings with Meera in March", "all DC meetings last year", "free Thursday afternoons next month".

### 8.10 Buttons

Primary: `+ New Event`. AI-accented: `✦ Prepare me for today`, `✦ Find a time`, `✦ Reschedule my day`, `✦ What's at risk?`. Secondary: Today, Import ICS, Export ICS, Connect calendar, Share availability, Book room, Print. Destructive: Cancel event (with attendee notification), Delete series, Decline all.

### 8.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **New / Edit Event** | Medium | Title, type, date/time with duration, all-day toggle, recurrence builder (with academic-aware options: "every teaching week", "excluding holidays", "for the remainder of the term"), location/room picker with availability, virtual link generation, attendees with availability preview, description, **link entities/artefacts** picker, reminders, visibility, colour/calendar assignment |
| **Scheduling Assistant** | Large | Attendee list with availability lanes, a proposed-slot ranked list, time-zone display for each attendee, focus-block awareness, room availability integration, and "send proposal" for external participants |
| **Recurrence Editor** | Small | Pattern, interval, end condition, exception dates, academic-calendar exclusions |
| **Event Preparation** | Side sheet | Checklist of linked materials, their readiness state, quick actions to open/update, AI-generated briefing for the event ("Last time you met Rahul you agreed to three actions; two are complete") |
| **Cancel Event** | Small | Reason, notify attendees toggle, message, and for recurring events a scope selector (this occurrence / this and future / entire series) |
| **Connect Calendar** | Medium | Provider (Outlook/Google/CalDAV/ICS URL), sync direction, calendars to include, conflict handling, privacy level for busy-only sharing |
| **Book Room** | Medium | Room search with capacity/facility filters, availability grid, recurring booking support, approval routing if required |
| **Share Availability** | Medium | Date range, duration, working-hours constraint, buffer, generated link with expiry, branding |
| **Deadline Detail** | Medium | Obligation detail, evidence attach, extension request, delegation, escalation preview |
| **Import ICS** | Medium | File/URL, preview of events, duplicate detection, target calendar, per-event include/exclude |

### 8.12 Right-Click Menus

**On an event block:**
```
⊙ Open event                      Enter
🎥 Join meeting                          (if virtual)
📋 Prepare for this                 P
─────────────────────────────────────
✦ Brief me on this meeting
✦ Draft an agenda
─────────────────────────────────────
✎ Edit                              E
⧉ Duplicate                         D
🕐 Reschedule…                      R
⏱ Change duration                  ▸   (30m · 1h · 90m · 2h · Custom)
👥 Manage attendees
📎 Link artefacts…                  L
─────────────────────────────────────
📝 Log meeting notes
✓ Mark as attended
🔁 Edit series…                          (recurring only)
─────────────────────────────────────
📤 Forward invitation
🔗 Copy link
─────────────────────────────────────
⊘ Cancel event
🗑 Delete
```

**On an empty time slot:** New event here · New class session · New focus block · Find a time with… · Paste event · Book a room here.

**On a day header:** Open day view · Add all-day event · Mark out of office · Copy day's agenda · Print day · Set as a no-meeting day.

**On a deadline chip:** Open source item · Attach evidence · Request extension… · Delegate ▸ · Snooze reminder ▸ · Mark complete · Mute this deadline type.

**On a calendar layer (sidebar):** Show only this · Hide · Change colour ▸ · Rename · Sync settings · Share · Export · Remove.

### 8.13 Context Menus

Selection bar (multi-select events): "4 events selected" → Reschedule by ▸ (offset picker) · Change calendar ▸ · Add attendee · Cancel · Export. Drag context: dragging an event shows a live time tooltip and highlights conflicts in red as you move; resizing shows the new duration; `Ctrl` while dragging copies. Availability context: hovering another person's lane in the scheduling assistant shows their busy-block reason if permitted, or "Busy" if not. Term-view context: right-click a week for "Set as exam week", "Mark as holiday", "Bulk-shift sessions from here".

### 8.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `C` | Go to Calendar |
| `D` / `W` / `M` / `Y` | Day / Week / Month / Term view |
| `A` | Agenda view |
| `Shift+D` | Deadlines view |
| `T` | Today |
| `←` / `→` | Previous / next period |
| `N` | New event |
| `P` | Prepare for the selected event |
| `R` | Reschedule selected |
| `E` | Edit selected |
| `J` / `K` | Next / previous event (agenda) |
| `F` | Find a time (scheduling assistant) |
| `Delete` | Cancel selected event |

### 8.15 Modern UX Details

- **Academic-aware recurrence** is the feature that makes this calendar academic rather than generic: "every teaching week, excluding the mid-semester break and institutional holidays" is a single choice, not a manual exception list.
- **Term view** compresses an entire semester into one legible screen — the planning artefact every professor currently maintains on paper.
- **Events carry their materials.** A class event is not a reminder; it is a launcher for that session's slides, roster and notes. This is the payoff of the entity graph.
- **Preparation intelligence:** the morning briefing flags events whose linked materials are missing or stale, hours before they matter.
- **Deadlines are first-class citizens**, aggregated from every module (grants, milestones, reviews, renewals) rather than manually re-entered — the single most common source of academic anxiety, solved by integration rather than discipline.
- **Focus blocks are respected, not decorative:** the scheduling assistant deprioritises them and warns anyone attempting to book over them.
- **Time-zone clarity** for international collaborations: attendee lanes show local times, and the event popover shows "09:00 your time · 15:30 Berlin · 23:30 Tokyo".

### 8.16 Glassmorphism

The current-time indicator's "now" label chip, the floating view switcher on wide screens, the event popover (Acrylic Base — appropriate because it floats over a grid, not over text), the scheduling assistant's suggestion bar, the deadline countdown pills in the all-day band, and the AI calendar strip (Frosted Card). The grid itself, agenda rows, tables and event editors remain solid.

### 8.17 Dark & Light Mode

Light: grid lines `N4`, hour labels `N10`, working hours on `N0` with outside-hours on `N2`, event blocks in domain colours at 12% fill with a full-strength 3 px left border and dark text. Dark: event blocks invert to 22% fill with a bright left border and light text — a critical calibration, since low-opacity fills that work on white become invisible on black; the current-time line is `danger` in both themes for instant recognition; the outside-hours band darkens rather than lightens; holidays and exam windows use a subtle diagonal pattern in addition to colour so the distinction survives both themes and colour-vision differences.

### 8.18 Edge States

- **No events:** "Your calendar is empty" with actions — Connect Outlook/Google · Import your timetable · Add your first class. Includes a note that class sessions created in Teaching appear here automatically.
- **Heavy day (> 8 events):** the day view compresses intelligently and offers an "Agenda" prompt; overlapping blocks stack with a "+3 more" expander rather than becoming unreadable slivers.
- **Sync conflict:** an inline banner with a three-way comparison (local / external / merged) and explicit resolution — never silent overwrite.
- **Declined/cancelled events** remain visible in a muted, struck-through state for the day so the user understands what changed, then disappear at end of day.
- **Cross-institution scheduling:** external attendees show as "Availability unknown" with an option to send a poll link rather than guessing.
- **Term not configured:** the Term view prompts the administrator (or the user, for personal workspaces) to define the academic calendar, with common presets.

---

## SCREEN 9 — AI CHAT

### 9.1 Purpose

AI Chat is the **full-screen reasoning workspace** — the expanded counterpart to the AI dock. Where the dock answers quick, in-context questions, this screen is for sustained intellectual work: multi-document synthesis, literature analysis, drafting with sources open alongside, and running agents with visible plans. It is the surface where the SRS promise — *cited, scoped, reversible, explainable AI over your own corpus* — is made concrete.

**Non-negotiable:** every claim carries a citation; every action is previewed; every scope is visible; nothing is silently written to the workspace.

### 9.2 Layout

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  ✦ AI Chat › Literature synthesis for Chapter 2                 [Ctrl+K]  🔔 ◐   │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [+ New chat] [Agents ▾] [Templates ▾] │ Scope: [🔬 NANOCAT ▾] [Model: Balanced ▾] │⋯│
├────────────────────┬─────────────────────────────────────────┬───────────────────────┤
│ THREADS            │  CONVERSATION                            │  SOURCES & CONTEXT    │
│ ─────────────────  │  ─────────────────────────────────────   │  ───────────────────  │
│ ⚲ Search threads   │                                          │  IN SCOPE             │
│ [+ New chat]       │  👤 Compare the selectivity findings     │  🔬 NANOCAT space     │
│                    │     across my last three experiments     │  · 89 datasets        │
│ ▾ TODAY            │     and the Zhang 2025 paper             │  · 42 experiments     │
│ ● Literature synth◀│                                          │  · 12 papers          │
│ ○ SERB report      │  ✦ Across Runs 38, 41 and 42 your        │  ─────────────────    │
│ ▾ YESTERDAY        │    selectivity peaked at 340 K (94.2%),  │  USED IN THIS ANSWER  │
│ ○ Ch.3 feedback    │    which is 6.1 points above Zhang's     │  ┌─────────────────┐  │
│ ○ Venue options    │    reported optimum [1]. Two differences │  │📊 run38_sel.csv │  │
│ ▾ LAST 7 DAYS      │    may explain this: your catalyst       │  │  Run 38 · 88%   │  │
│ ○ Grant budget     │    loading is 2.4 mg vs their 1.8 mg [2],│  │  ▸ Open  ▸ Why? │  │
│ ○ CO mapping       │    and you used a 45-min equilibration   │  └─────────────────┘  │
│ ─────────────────  │    they did not report [3].              │  ┌─────────────────┐  │
│ SAVED / PINNED     │                                          │  │📄 Zhang2025.pdf │  │
│ ★ Thesis Q&A       │    ⚠ Caution: Run 41 shows a 3.2 point   │  │  p.7, Table 2   │  │
│ ★ Course design    │    deviation flagged as an outlier —     │  │  ▸ Open  ▸ Why? │  │
│ ─────────────────  │    I excluded it from the mean.          │  └─────────────────┘  │
│ AGENTS             │                                          │  ┌─────────────────┐  │
│ ⚙ Semester setup   │    [1] Zhang 2025, p.7  [2] PROT-07 v2.1 │  │🧪 PROT-07 v2.1  │  │
│ ⚙ Compliance scan  │    [3] run42_notes.md                    │  └─────────────────┘  │
│ ⚙ Literature watch │                                          │  ─────────────────    │
│ ⚙ Data hygiene     │    High confidence · 3 sources · 4.2 s   │  CONFIDENCE           │
│                    │    👍 👎  ⧉ Copy  ⤴ Save  ⟳ Regenerate   │  ●●● High             │
│                    │  ─────────────────────────────────────   │  All claims sourced   │
│                    │  [Ask a follow-up…            ] [✦ Send] │  ─────────────────    │
│                    │  📎 Attach  🎯 Scope  ⚡ Actions          │  [Show retrieval ▸]   │
├────────────────────┴─────────────────────────────────────────┴───────────────────────┤
│ Thread: 8 messages · 24 sources · 12.4k tokens · ₹2.10 this session      ● AI Online  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Sidebar (Context Pane) — Threads

| Block | Contents |
|---|---|
| Header | `+ New chat` (primary), thread search field |
| **Threads** | Grouped by recency (Today / Yesterday / Last 7 days / Last 30 days / Older). Each row: status dot (active/complete), auto-generated title, scope glyph, message count, relative time. Hover reveals pin, rename, delete |
| **Saved / Pinned** | User-pinned threads that persist at the top |
| **Agents** | Configured agents with status (idle / scheduled / running with progress / needs approval). Click opens the agent console |
| **Templates** | Reusable prompt templates (institutional + personal): "Draft a progress report", "Compare methodologies", "Prepare viva questions" |
| Footer | Monthly AI usage meter with a link to AI settings |

Threads are automatically titled from their first exchange, renameable, and scoped — a thread remembers its scope so returning to it restores full context.

### 9.4 Topbar & Command Bar

| Control | Behaviour |
|---|---|
| `+ New chat` | Starts a thread; scope defaults to the last-used or to the space the user came from |
| `Agents ▾` | Run an agent: Semester Setup · Compliance Scan · Grant Report · Literature Monitor · Thesis Consistency · Onboarding · Data Hygiene · Custom |
| `Templates ▾` | Insert a structured prompt template with fill-in fields |
| **Scope selector** | The most important control on the screen. A chip showing the current retrieval boundary: This artefact · This entity · This space · My workspace · My lab · My department · Everything I can access · Custom selection. Opens a picker with counts ("12 papers, 89 datasets in scope") |
| **Model selector** | Fast · Balanced · Deep reasoning — described in outcome terms ("Deep: slower, better for synthesis across many documents"), with cost implication shown subtly |
| `⋯` | Export thread ▸ (Markdown/PDF/DOCX) · Share thread · Thread settings · Clear thread · AI settings · View data usage |

### 9.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Message stream** | User messages right-aligned in a subtle neutral bubble; AI responses left-aligned, full-width, no bubble (long-form content deserves reading width), with a violet ✦ avatar |
| C2 | **Streaming response** | Token-by-token rendering with a subtle caret; a "Stop" button appears during generation; partial output is preserved if stopped |
| C3 | **Inline citations** | Numbered superscript markers `[1]` that highlight the corresponding source card on hover and scroll it into view on click; hovering a citation shows the exact quoted passage in a popover |
| C4 | **Source panel (right)** | *In scope* summary (what the AI can see) and *Used in this answer* (what it actually retrieved), each source as a card with title, type glyph, the specific location (page, cell, timestamp), a relevance bar, `Open` and `Why this source?` |
| C5 | **Confidence display** | Three-state indicator with a plain-language explanation ("High — all claims are supported by retrieved sources") and a link to "Show retrieval" |
| C6 | **Retrieval inspector** | Expandable panel showing the query as interpreted, the rewritten queries, retrieved chunks with scores, what was filtered by permissions (count only, never content), and the final context assembled. This is the "show your work" requirement made real |
| C7 | **Action proposals** | When the AI proposes a workspace change, it renders as a distinct **proposal card**: what will change, a diff or preview, affected item count, and `Preview` / `Apply` / `Discard`. Never auto-applied |
| C8 | **Agent console** | For agent runs: a visible plan as a numbered step list with per-step status (pending/running/complete/failed/awaiting approval), live logs, elapsed time, cost, and Pause/Stop/Approve controls |
| C9 | **Composer** | Multi-line input with `Enter` to send and `Shift+Enter` for a newline; attachment, scope and quick-action buttons; slash commands (`/summarise`, `/compare`, `/draft`, `/find`, `/table`); @-mentions to reference entities directly; drag-drop files into the composer |
| C10 | **Suggested follow-ups** | Two to four contextual chips after each answer ("Show me the outlier analysis", "Draft this as a methods paragraph") |
| C11 | **Artefact preview pane** | Clicking a source opens it in a split pane beside the conversation rather than navigating away — essential for source-checking while reading an answer |
| C12 | **Cost & token meter** | Status bar shows session tokens and cost; users on metered plans see remaining budget |

### 9.6 Cards

**Source card:** type glyph, title (2-line clamp), precise locator ("p. 7, Table 2" / "cell 14" / "00:23:11"), relevance bar, space/entity breadcrumb, date, and actions (Open · Open in split · Why this source? · Exclude and regenerate).

**Proposal card:** violet-bordered, `✦ Proposed change` header, plain-language description ("Reclassify 47 artefacts from *Unsorted* to *CS-301 › Sessions*"), an expandable item list, an impact line ("47 items · reversible for 30 days"), and buttons `Preview changes` (primary) / `Apply` / `Discard`.

**Agent card (sidebar and console):** agent name, icon, schedule, last run, status, next run, and a run button; in-console it expands to the step plan.

**Template card:** name, description, required inputs, example output, "Use template".

### 9.7 Tables

AI Chat renders tables when the answer is tabular — a first-class output format, not a text approximation:

- **Comparison table** (e.g. across experiments or papers) with sortable columns, cell-level citations (each cell can carry its own source marker), and an `Export` action that saves it as a real artefact into the workspace.
- **Retrieval inspector table:** Chunk · Source · Section/page · Lexical score · Vector score · Fused score · Included (✓/✗ with reason).
- **Agent step table:** Step · Action · Target · Status · Duration · Result · Approval required.
- **AI usage table** (settings-linked): Date · Feature · Model · Tokens · Cost · Outcome.

All AI-generated tables carry a "Save as artefact" action so analysis products become part of the corpus rather than disappearing into a chat log.

### 9.8 Filters

Thread list filters: date range, scope, has proposals, has agent runs, pinned, shared, model used. In-conversation filters apply to sources: type, space, date, relevance threshold, and "only show sources I have not yet opened". The scope selector itself is the primary filter of the whole screen and supports a **custom scope builder**: pick spaces, entities, date ranges, artefact types and sensitivity levels, with a live count of what is included.

### 9.9 Search

`Ctrl+F` searches within the current thread with match highlighting. The thread-list search searches across all threads' content, not just titles ("which conversation discussed the pumping lemma?"). `Ctrl+K` from this screen offers a "Ask AI" mode directly. Additionally, the source panel has its own filter for long source lists.

### 9.10 Buttons

Primary: `✦ Send`, `+ New chat`. AI-accented throughout by nature. Secondary: Attach, Scope, Actions, Regenerate, Stop, Copy, Save as artefact, Export thread, Share thread, Run agent, Use template. Proposal buttons: Preview changes (primary), Apply, Discard. Feedback: 👍 / 👎 (opens a short reason picker: inaccurate · missing sources · wrong scope · unhelpful · other). Destructive: Clear thread, Delete thread, Stop agent.

### 9.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **Scope Builder** | Large | Tree of spaces and entities with checkboxes, artefact-type filters, date range, sensitivity cap, live inclusion count ("2,140 artefacts · 18,900 chunks in scope"), save as a named scope for reuse |
| **Preview Changes** | Large | Full diff of a proposed action — before/after for each affected item, grouped, with per-item exclusion, and a summary footer ("Applying to 44 of 47 items") |
| **Retrieval Inspector** | Large | The full "show your work" view: interpreted query, sub-queries, retrieved chunks with scores and text, permission-filtered count, assembled context, model and prompt version |
| **Agent Configuration** | Large, tabbed | Trigger (manual/scheduled/event), scope, parameters, approval requirements per step type, budget ceiling, notification settings, dry-run |
| **Agent Approval** | Medium | The step awaiting approval, what it will do, affected items, and Approve / Modify / Reject with reason |
| **Save as Artefact** | Medium | Title, type, destination space/entity, tags, and a mandatory AI-provenance note ("Generated by AI on 4 Aug 2026 from 12 sources") that cannot be removed |
| **Share Thread** | Medium | Recipients or link, permission (view/comment), whether sources are included (with a permission warning if recipients lack access to some sources — the system will redact rather than leak), expiry |
| **Export Thread** | Small | Format (Markdown/PDF/DOCX), include sources, include retrieval details, include timestamps |
| **AI Settings** (shortcut into Settings) | Large | Feature toggles, model preferences, data-boundary settings, memory/personalisation, budget |
| **Feedback** | Small | Reason picker, optional comment, and consent to include the conversation in evaluation data |

### 9.12 Right-Click Menus

**On an AI message:**
```
⧉ Copy message
⧉ Copy as Markdown
─────────────────────────────────────
⤴ Save as artefact…
📊 Save table as dataset…               (when tabular)
📌 Pin to thread summary
─────────────────────────────────────
⟳ Regenerate
✎ Regenerate with different scope…
🎚 Regenerate with deeper model
─────────────────────────────────────
🔍 Show retrieval details
📚 Show all sources
⚠ Report an issue
─────────────────────────────────────
🗑 Delete message
```

**On a user message:** Edit and resend · Copy · Branch conversation from here (creates a new thread preserving prior context) · Delete.

**On a source card:** Open · Open in split view · Why was this used? · Show the exact passage · Exclude from this answer and regenerate · Exclude from scope permanently · Open in its space · Copy citation.

**On a thread (sidebar):** Open · Open in new tab · Rename · Pin · Duplicate · Change scope · Export ▸ · Share · Archive · Delete.

**On an agent:** Run now · Configure · View run history · Pause schedule · Duplicate · View permissions (what this agent can access and do) · Disable · Delete.

**On selected text in a response:** Copy · Quote in follow-up · ✦ Expand on this · ✦ Find sources for this claim · Save as note · Insert into document ▸.

### 9.13 Context Menus

Generation context bar: while streaming, a floating glass bar shows "Generating… 4.2 s · [Stop]". Agent context bar: during an agent run, a persistent bar shows "Compliance Scan · Step 3 of 7 · [Pause] [View plan]" and turns amber when approval is required. Proposal context: an unresolved proposal keeps a sticky footer reminder ("1 pending proposal") so it cannot be forgotten. Selection context in the source panel: multi-select sources → "Use only these", "Exclude these", "Compare these".

### 9.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `A` | Go to AI Chat |
| `Ctrl+J` | Toggle AI dock (from any screen) |
| `Ctrl+N` | New chat |
| `Enter` | Send |
| `Shift+Enter` | New line |
| `↑` (empty composer) | Edit last message |
| `Ctrl+Shift+S` | Open scope selector |
| `Ctrl+Shift+M` | Model selector |
| `Ctrl+R` | Regenerate last response |
| `Esc` | Stop generation |
| `Ctrl+Shift+C` | Copy last response |
| `Ctrl+Shift+A` | Save last response as artefact |
| `Ctrl+Shift+R` | Show retrieval details |
| `/` (empty composer) | Slash-command menu |
| `@` | Mention an entity |
| `Alt+↑/↓` | Previous / next thread |

### 9.15 Modern UX Details

- **Scope is always visible and always honest.** The chip in the command bar never hides what the AI can see. Changing scope mid-thread inserts a visible divider in the conversation ("Scope changed to Department") so answers are never silently comparable across different knowledge boundaries.
- **Citations are interactive, not decorative.** Hovering `[2]` highlights the source card and shows the quoted passage; clicking opens the artefact at the exact page or timestamp. This is the single feature that converts scepticism into trust.
- **Refusal is a designed state, not an error.** When the corpus cannot answer, the response is explicit — "I couldn't find anything in your workspace about X. I can search external sources, or you may not have uploaded it yet." — with actions attached. It never invents.
- **Proposals are visually distinct from prose.** A violet-bordered card with a diff. Users learn within one session that AI *talking* and AI *doing* look completely different.
- **Branching conversations** let a researcher explore an alternative line without losing the original thread — modelled on how academics actually think.
- **Cost transparency** without anxiety: a subtle session figure, not a ticking meter. Only surfaced prominently when approaching a budget limit.
- **Stopping is instant and lossless.** Partial answers remain, with a "continue" affordance.
- **Latency choreography:** a scope-confirmation chip appears immediately, retrieval progress shows as "Searching 89 datasets…", then tokens stream. The user always knows what phase the system is in — perceived speed comes from narration, not just raw speed.

### 9.16 Glassmorphism

This is the screen where glass is most heavily and most appropriately used, because the AI identity is expressed materially:

| Element | Material |
|---|---|
| AI response container | Frosted Card, violet-tinted (3% light / 6% dark), 16 px blur, hairline border |
| Source panel background | Acrylic Thin |
| Proposal card | Frosted Card with a 2 px violet border and a subtle inner glow |
| Generation/agent context bars | Acrylic Base, floating |
| Scope and model flyouts | Acrylic Base |
| Composer | **Solid** — text input must never sit on blur |
| Tables and retrieval inspector | **Solid** — data legibility wins |
| Thread list | Solid with a subtle tint on the active thread |

### 9.17 Dark & Light Mode

Light: AI violet at `#8B5CF6`; response cards a near-white frosted violet wash; source cards `N1` with `N6` borders; citation markers violet superscript. Dark: violet lifts to `#A78BFA`; the response card uses a 6% violet wash over `N2` with a 1 px top highlight and 2% noise; the streaming caret glows faintly; source relevance bars brighten 10%; code blocks in responses use a dedicated syntax theme per mode; the agent console adopts a terminal-like aesthetic in dark mode (mono, high contrast) which power users appreciate for long runs.

### 9.18 Edge States

- **Empty state:** not a blank screen — a set of scoped example prompts drawn from the user's actual corpus ("Summarise the 12 papers in NANOCAT", "What did I promise SERB for Q3?"), plus a one-line explanation of scoping.
- **Empty corpus:** "I don't have anything to work with yet. Upload files or connect your Drive and I'll be useful in about ten minutes."
- **AI unavailable / degraded:** a neutral banner explaining the limitation, with search and browsing still fully available; queued questions can be saved for when service returns.
- **Budget exhausted:** clear message with what still works (cached answers, lexical search), when the budget resets, and who to contact for an increase.
- **Permission-filtered retrieval:** the answer notes "3 potentially relevant items were excluded because you don't have access" — the *count* is disclosed for honesty, never the content or titles.
- **Very long thread:** older messages collapse into a summarised context block with an "expand full history" control; the thread's token budget is shown when approaching limits.
- **Conflicting sources:** the AI surfaces the disagreement explicitly rather than averaging it away ("Run 41 contradicts Runs 38 and 42; here's the discrepancy").

---

## SCREEN 10 — SETTINGS

### 10.1 Purpose

Settings is the **control surface for identity, workspace behaviour, AI boundaries, privacy and integrations**. Its design goal is that a user can find any setting in under 20 seconds and understand its consequence without documentation. Every setting states what it does, what it affects, and — where relevant — who else can see or override it.

### 10.2 Layout

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  ⚙ Settings › AI & Automation › Data boundaries                 [Ctrl+K]  🔔 ◐   │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [⚲ Search all settings…                                    ]     [Reset section] [⋯] │
├────────────────────┬──────────────────────────────────────────────────────────────────┤
│ ⚲ Search settings  │  AI & AUTOMATION                                                 │
│ ────────────────── │  ──────────────────────────────────────────────────────────────  │
│ ▾ ACCOUNT          │  Data boundaries                                                 │
│   Profile          │  ┌────────────────────────────────────────────────────────────┐  │
│   Identity & ORCID │  │ Where your content may be processed                        │  │
│   Security         │  │ ◉ Institution region only (India)      🔒 Locked by admin  │  │
│   Sessions         │  │ ○ Any region with equivalent safeguards                    │  │
│   Notifications    │  │ Set by: IT Administration · Policy DR-04 · [Why?]          │  │
│ ▾ WORKSPACE        │  └────────────────────────────────────────────────────────────┘  │
│   Appearance       │  ┌────────────────────────────────────────────────────────────┐  │
│   Language & region│  │ Model training on your content                             │  │
│   Density & layout │  │ [ OFF ]  Your content is never used to train models.       │  │
│   Default views    │  │ This is enforced contractually with all model providers.   │  │
│   Shortcuts        │  │ [Read the data processing agreement ↗]                     │  │
│ ▾ CONTENT          │  └────────────────────────────────────────────────────────────┘  │
│   Naming rules     │  ┌────────────────────────────────────────────────────────────┐  │
│   Metadata         │  │ AI features                          [Enable all] [Disable]│  │
│   Templates        │  │ ☑ Auto-classification of new files      ●●● 94% accepted   │  │
│   Taxonomies       │  │ ☑ Metadata extraction                   ●●● 91% accepted   │  │
│   Storage & tiers  │  │ ☑ Grounded chat over my corpus                             │  │
│ ▾ AI & AUTOMATION ◀│  │ ☑ Proactive briefings          Daily 06:00 ▾               │  │
│   Features         │  │ ☐ Draft generation for assessments   ⚠ Disabled by policy  │  │
│   Data boundaries◀ │  │ ☑ Agents                       3 configured ▸              │  │
│   Models & cost    │  └────────────────────────────────────────────────────────────┘  │
│   Agents           │  ┌────────────────────────────────────────────────────────────┐  │
│   Memory           │  │ AI memory & personalisation                                │  │
│ ▾ INTEGRATIONS     │  │ ☑ Remember my corrections to improve suggestions           │  │
│   Connected apps   │  │ ☑ Remember my writing style for drafts                     │  │
│   Calendars        │  │ [View what AI remembers about me]  [Clear memory]          │  │
│   Repositories     │  └────────────────────────────────────────────────────────────┘  │
│ ▾ PRIVACY & DATA   │                                                                  │
│   Data & privacy   │                                    [Discard changes] [Save]      │
│   Export           │                                                                  │
│   Delete account   │                                                                  │
├────────────────────┴──────────────────────────────────────────────────────────────────┤
│ Changes save automatically · Last changed 2 min ago                        ● Online   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Sidebar (Context Pane)

Six top-level groups, each expanding to sections. The active section is highlighted; sections with unsaved changes show a dot; sections locked by institutional policy show a small lock glyph.

| Group | Sections |
|---|---|
| **Account** | Profile · Identity & ORCID · Security (password, MFA, passkeys) · Sessions & devices · Notification preferences |
| **Workspace** | Appearance (theme, accent, glass, motion) · Language & region · Density & layout · Default views · Keyboard shortcuts |
| **Content** | Naming rules · Metadata requirements · Templates · Taxonomies & vocabularies · Storage & tiering · Version retention |
| **AI & Automation** | Features · Data boundaries · Models & cost · Agents · Memory & personalisation · AI activity log |
| **Integrations** | Connected apps · Calendars · Cloud storage · Reference managers · Repositories · Developer/API keys |
| **Privacy & Data** | Data & privacy dashboard · Access log (who viewed my content) · Export my data · Delete account |

A persistent search field at the top searches **all settings by name, description and synonym** — the single most important navigation aid in any settings surface.

### 10.4 Topbar & Command Bar

Breadcrumb `⚙ Settings › Group › Section`. Command bar holds only the settings search, a `Reset section to defaults` action (confirmed), and `⋯` (Export settings · Import settings · View change history · Institutional policy summary).

### 10.5 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Setting group card** | A titled card containing related settings with a one-line group description |
| C2 | **Setting row** | Label, description (always present — no setting exists without an explanation), control on the right, and optional metadata (who set it, when, policy reference) |
| C3 | **Policy lock** | When an institution enforces a setting: the control is disabled, a lock glyph appears, and a line states "Set by IT Administration · Policy DR-04 · [Why?]" opening the policy text. Never a silently greyed control |
| C4 | **Live preview** | Appearance settings preview instantly in a miniature app mock inside the card — theme, density and accent changes are visible before committing |
| C5 | **Effectiveness indicator** | AI feature rows show real acceptance rates from the user's own usage ("94% of suggestions accepted") — helping users decide whether to keep a feature on |
| C6 | **Connected-app card** | Logo, account, status, permissions granted (expandable), last sync, actions (Sync now / Reconfigure / Disconnect) |
| C7 | **Security panel** | MFA methods with add/remove, passkey list, recovery codes (view once), sign-in history with device/location/IP, and "sign out everywhere" |
| C8 | **Privacy dashboard** | What is stored about the user, who has accessed their content (with dates), what AI has done with it, data-residency status, and per-category retention |
| C9 | **Storage panel** | Usage by type and tier with a treemap, quota, reclaimable space suggestions with projected savings, and tiering-policy controls |
| C10 | **Shortcut editor** | Searchable list of all commands with current bindings, conflict detection, custom rebinding, and reset |
| C11 | **Naming rules editor** | Token grammar builder with live example generation ("CS301_LEC_graph-algorithms_2026-ODD_L08_v1.2.pptx") — a direct expression of SRS §19 |
| C12 | **Change history** | Chronological log of settings changes with actor (self or admin), old value, new value, and revert |

### 10.6 Cards

Cards in Settings are functional groupings rather than content objects: **Setting group card** (standard), **Integration card**, **Device/session card** (device type, browser, location, last active, current-session marker, revoke), **Agent card** (configuration summary, schedule, permissions, last run, toggle), **Plan/licence card** (plan, seats, renewal, usage bars, upgrade), **Danger-zone card** (visually distinct with a danger border, containing account deletion and data purge).

### 10.7 Tables

| Table | Columns |
|---|---|
| **Sessions & devices** | Device · Browser/app · Location · IP · First seen · Last active · Current? · Revoke |
| **Access log** | When · Who · What they accessed · Action · Reason/context · Source (UI/API/admin) |
| **AI activity log** | When · Feature · Scope · Model · Outcome · Accepted? · Cost · View details |
| **Connected apps** | App · Account · Scopes granted · Connected on · Last used · Status · Actions |
| **Keyboard shortcuts** | Command · Category · Binding · Conflict? · Reset |
| **Version retention rules** | Artefact class · Keep all versions · Thin after · Minimum retained · Legal hold override · Edit |
| **Settings change history** | When · Setting · Old value · New value · Changed by · Revert |

### 10.8 Filters

Settings search is the primary filter and supports synonym matching ("dark mode" finds Appearance › Theme; "who can see my files" finds Privacy › Access log). Additional filters: in Access log (date range, person, action type, source), in AI activity (feature, model, date, accepted/rejected), in Sessions (active only, this device, suspicious), in Shortcuts (category, customised only, conflicts only), in Connected apps (status, permission scope).

A global toggle — **"Show only settings I've changed"** — is a small feature with outsized usefulness for debugging one's own workspace.

### 10.9 Search

The settings search field is prominent, permanently visible, keyboard-focusable with `/`, and searches labels, descriptions, synonyms and section names. Results display as a flat list with breadcrumbs ("Workspace › Appearance › Theme"), jump directly to the setting, and briefly highlight it on arrival (a 1.2 s accent flash). `Ctrl+K` also indexes every setting as a navigable command ("> dark mode", "> change ORCID").

### 10.10 Buttons

Primary: `Save` (only shown for sections that batch changes; most settings autosave with a subtle "Saved" confirmation). Secondary: Discard changes, Reset section, Sync now, Reconfigure, Add MFA method, Generate recovery codes, Export settings, Export my data. AI-accented: View what AI remembers, Run agent now. Destructive: Disconnect app, Revoke session, Sign out everywhere, Clear AI memory, Delete all versions older than…, **Delete account** (in a visually separated danger zone with a multi-step confirmation).

### 10.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **Change Password** | Small | Current, new (with strength and breach check), confirm |
| **Add MFA Method** | Medium | Method choice, QR/passkey enrolment flow, verification, recovery-code generation |
| **Recovery Codes** | Small | One-time display with copy/download and a mandatory "I've saved these" confirmation |
| **Connect App** | Medium | OAuth consent summary in plain language ("AcademicOS will be able to read your Drive files. It will not be able to delete them."), scope list, connect |
| **Disconnect App** | Small | What stops working, whether synced data is retained, confirm |
| **Export My Data** | Medium | Scope, format (original files + JSON-LD metadata + relationship graph, per SRS §13.3), delivery (download link / email), size estimate, and an explanation that this is a complete, re-importable export |
| **Delete Account** | Large (destructive) | Multi-step: consequences (what is deleted, what is retained by institutional policy, what remains attributed), export offer, typed confirmation of the account email, cooling-off notice (30-day recovery window), final confirm |
| **AI Memory Viewer** | Large | Everything the system has learned about the user's preferences and corrections, per-item deletion, and bulk clear |
| **Policy Explanation** | Small | The institutional policy text, its owner, effective date, and contact for exceptions |
| **Shortcut Conflict** | Small | The conflicting command, options to reassign or override |
| **Naming Rule Preview** | Medium | The grammar builder with live examples across artefact types and a bulk-apply option |
| **Storage Reclaim** | Medium | Categorised reclaimable items (duplicates, stale previews, old exports, thinnable versions) with sizes and per-category selection |

### 10.12 Right-Click Menus

Settings is deliberately low on right-click affordances — discoverability here should not depend on hidden menus. Where they exist:

**On a setting row:** Copy setting link (a deep link to that exact setting, invaluable for support) · Reset to default · View change history for this setting · Why is this locked? (when applicable).
**On a connected app:** Sync now · Reconfigure · View permissions · View sync log · Disconnect.
**On a session:** Revoke · View details · Mark as suspicious (triggers a security review).
**On a shortcut row:** Rebind · Reset · Remove binding · Copy command name.
**On an agent:** Run now · Edit · View history · Duplicate · Disable · Delete.

### 10.13 Context Menus

An unsaved-changes context bar appears at the bottom of any batching section: "You have unsaved changes · [Discard] [Save]" — sticky, glass, and blocking navigation with a confirm. A policy-override request context: when a locked setting is clicked, a small inline panel offers "Request an exception" with a message field routed to the policy owner. Bulk-selection context in the Access log and AI activity tables: "12 events selected → Export · Report an issue".

### 10.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `Ctrl+,` | Open Settings |
| `/` | Focus settings search |
| `↑ ↓` | Navigate results / sections |
| `Enter` | Open the highlighted section or activate the setting |
| `Space` | Toggle the focused switch |
| `Ctrl+S` | Save (in batching sections) |
| `Esc` | Discard / close |
| `Ctrl+Shift+D` | Toggle theme (works globally) |
| `Alt+←` | Back to the previous section |

### 10.15 Modern UX Details

- **Every setting explains itself.** No setting ships without a description of its effect. If a description cannot be written clearly, the setting is wrong.
- **Institutional locks are transparent, not mysterious.** The user sees who set it, which policy applies, why, and how to request an exception. This turns a frustrating dead end into a legitimate process.
- **Live preview for appearance** means no guess-and-check theme switching.
- **Effectiveness data on AI toggles** is unusual and powerful: showing a user that they accept 94% of auto-classifications makes the value tangible and the toggle decision informed.
- **Autosave by default, batch-save where consequential.** Toggles save instantly; anything with a blast radius (naming rules, retention, data boundaries) batches with an explicit Save.
- **Deep links to settings** make support conversations trivial: "Open this link and turn on X."
- **The privacy dashboard is a feature, not a compliance chore** — showing users who accessed their content builds more trust than any policy document.

### 10.16 Glassmorphism

Minimal and functional. Permitted: the unsaved-changes context bar (Acrylic Base), the settings-search results dropdown (Acrylic Base), the appearance live-preview mock (which renders its own miniature glass to demonstrate the setting), and policy-explanation popovers. All setting cards, forms, tables and logs are solid — a settings screen full of blur would be both unreadable and self-parodying.

### 10.17 Dark & Light Mode

Light: cards `N1` on an `N0` page; section headers `N14`; descriptions `N11`; locked rows get an `N2` fill. Dark: cards `N2` with top highlights; the danger zone uses a `danger` border at 40% opacity plus a 4% danger wash (never a saturated red block, which would be visually violent); toggle switches use accent fill in both themes with a clear off-state contrast; the appearance preview always shows both themes side by side so the user can compare without switching.

### 10.18 Edge States

- **Institutionally managed workspace:** a banner at the top of Settings — "Some settings are managed by <Institution>. [See what's managed]".
- **Personal workspace upgraded to institutional:** a one-time explanation of which settings have transferred to institutional control.
- **Integration credential expired:** the connected-app card turns amber with "Reconnect required" and an explanation of what has stopped syncing.
- **Quota exceeded:** the storage section leads with a prominent state and a reclaim wizard.
- **Account pending deletion:** a persistent banner across the entire app with days remaining and a one-click cancel.
- **Offline:** settings become read-only with an explanatory chip; changes queue and apply on reconnection.

---

## SCREEN 11 — NOTIFICATIONS

### 11.1 Purpose

Notifications is the **single inbox for everything the system needs from you or wants you to know**. Academics abandon tools that generate noise; this screen is therefore designed around *aggressive intelligent bundling* and a hard distinction between **Action Required** (things that block others or carry deadlines) and **Awareness** (things that merely happened). It exists in two forms: a topbar **flyout** for triage in five seconds, and a **full screen** for weekly clearing.

**Design target:** a professor should be able to clear a day's notifications in under 90 seconds and never miss something consequential.

### 11.2 Layout — Full Screen

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  🔔 Notifications › Action required                             [Ctrl+K] ✦  ◐    │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [✓ Mark all read] [⏰ Snooze all] [⚙ Preferences] │ [☰ List|👥 Grouped|⏱ Timeline] │⋯│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [⚲ Filter] [Unread ✕] [Type: Any ✕] [From: Anyone ✕] [Period: 30 days ✕]  [Save view]│
├────────────────────┬──────────────────────────────────────────────────────────────────┤
│ CONTEXT PANE       │  ⚡ ACTION REQUIRED (5)                          [Clear all ▾]   │
│ ────────────────── │  ┌────────────────────────────────────────────────────────────┐  │
│ ▾ INBOX            │  │🔴 APPROVAL · Syllabus CS-540 awaiting your sign-off        │  │
│   ⚡ Action req.  5│  │   Requested by Dr. Sharma · 3 days ago · Due in 2 days      │  │
│   👁 Awareness   23│  │   [Approve] [Request changes] [View]              ⏰ 🔇 ✕   │  │
│   💬 Mentions     4│  ├────────────────────────────────────────────────────────────┤  │
│   ✦ AI proposals  7│  │🔴 FEEDBACK · Rahul's Chapter 3 waiting 9 days              │  │
│   📅 Reminders    3│  │   Your SLA target is 7 days                                 │  │
│ ────────────────── │  │   [Give feedback] [Message Rahul]                 ⏰ 🔇 ✕   │  │
│   ✓ Done         — │  ├────────────────────────────────────────────────────────────┤  │
│   ⏰ Snoozed      2│  │🟠 DEADLINE · SERB Q3 progress report due in 6 days          │  │
│   🗄 Archive       │  │   2 deliverables have no evidence attached                  │  │
│ ────────────────── │  │   [Draft report ✦] [Attach evidence] [View project]  ⏰ ✕  │  │
│ FILTERS            │  ├────────────────────────────────────────────────────────────┤  │
│ ☑ Approvals      2 │  │🟠 REVIEW QUEUE · 14 items need classification confirmation  │  │
│ ☑ Deadlines      3 │  │   AI confidence below threshold · oldest 6 days             │  │
│ ☑ Mentions       4 │  │   [Triage now] [Auto-accept high confidence]         ⏰ ✕  │  │
│ ☑ AI proposals   7 │  └────────────────────────────────────────────────────────────┘  │
│ ☑ Comments       6 │                                                                  │
│ ☑ System         3 │  👁 AWARENESS · Today (bundled)                                  │
│ ────────────────── │  ┌────────────────────────────────────────────────────────────┐  │
│ QUIET HOURS        │  │ 👥 Activity in NANOCAT — 12 updates                    ▾   │  │
│ 20:00 – 08:00 ✓    │  │   R. Menon uploaded 4 datasets · A. Sharma commented ×3 ... │  │
│ Weekends muted     │  ├────────────────────────────────────────────────────────────┤  │
│ [Edit]             │  │ 📄 Citation update — 3 of your papers gained 7 citations ▾  │  │
│                    │  ├────────────────────────────────────────────────────────────┤  │
│                    │  │ ✦ AI organised 34 new files into 6 spaces              ▾   │  │
│                    │  │   [Review changes] [It's fine]                              │  │
│                    │  └────────────────────────────────────────────────────────────┘  │
├────────────────────┴──────────────────────────────────────────────────────────────────┤
│ 5 action required · 23 awareness · 2 snoozed · Digest sends daily 18:00    ● Online   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 11.3 Layout — Topbar Flyout (the 5-second triage surface)

A 420 px Acrylic Base panel anchored to the bell icon, max 560 px tall, with: a header (count + "Mark all read" + gear), two tabs (**Action** / **All**), a scrollable list of compact notification rows with inline primary actions, and a footer link "Open notifications ↗". Rows here are single-line-plus-action; anything more complex requires the full screen.

### 11.4 Sidebar (Context Pane)

| Block | Contents |
|---|---|
| **Inbox** | Action required · Awareness · Mentions · AI proposals · Reminders — each with an unread count; the active category is highlighted |
| **Status folders** | Done (cleared today, recoverable) · Snoozed (with wake times) · Archive |
| **Type filters** | Checkbox list with counts: Approvals · Deadlines · Mentions · Comments · AI proposals · Shares · System · Security · Integration errors |
| **Quiet hours** | Current schedule summary with an edit link; a "Pause all notifications" toggle with duration options (1 h / until tomorrow / until Monday / custom) |
| **Digest** | Next digest time and a link to preferences |

### 11.5 Topbar & Command Bar

| Control | Behaviour |
|---|---|
| `✓ Mark all read` | Marks the current view read (never deletes) with an undo toast |
| `⏰ Snooze all` | Snoozes the current view with a duration picker |
| `⚙ Preferences` | Jumps to Settings › Notifications |
| View switcher | **List** (chronological) · **Grouped** (bundled by source/entity/person) · **Timeline** (day-banded) |
| `⋯` | Digest settings · Notification history (90 days) · Export · Mute rules · Test notification |

### 11.6 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Notification row** | Severity glyph + category label (overline) + title + context line + timestamp + inline actions + row controls (snooze ⏰ / mute 🔇 / dismiss ✕). Unread rows carry a 3 px accent left bar and a slightly stronger surface |
| C2 | **Bundle row** | Aggregated notifications with a summary line, a count, an avatar stack, and a `▾` expander revealing individual items; bundles collapse by source entity, actor or type |
| C3 | **Inline action buttons** | Approve / Reject / Give feedback / Review / Attach / Open — executing without leaving the screen, with an optimistic state and undo |
| C4 | **Snooze picker** | 1 hour · This evening · Tomorrow 9 am · Next week · When I'm next free (calendar-aware) · Custom |
| C5 | **Mute controls** | Mute this thread · Mute this entity · Mute this notification type · Mute this person (with a confirmation explaining what will still get through — safety notifications and direct approvals always penetrate mutes) |
| C6 | **Priority reasoning** | Hovering a severity glyph explains the ranking ("Marked urgent: blocks another person and is past its SLA") |
| C7 | **AI proposal notification** | A distinct violet-bordered variant with a summary of the proposed change, an item count, and `Review` / `Accept all` / `Discard` |
| C8 | **Digest preview** | A card showing what the next email digest will contain, with the ability to remove items pre-emptively |
| C9 | **Empty state** | "You're all caught up" with a genuinely restrained visual and the time saved this week ("You cleared 47 notifications this week") |
| C10 | **Delivery channel indicator** | Small glyphs on each row showing where else it was delivered (email / push / Teams) — useful for diagnosing noise |

### 11.7 Cards

**Action-required card:** the richest variant — severity bar, category overline, bold title, one-line context, actor avatar, age and deadline, up to three inline actions, and row controls. Blocking items (someone else waiting) carry a small "blocking" chip because that framing changes behaviour.

**Bundle card:** collapsed summary with a count and avatar stack; expanded, it becomes a nested compact list with individual actions.

**AI proposal card:** violet border, ✦ header, plain-language change description, affected count, reversibility note, and three actions.

**Digest card:** a scheduled-summary preview with per-item removal.

### 11.8 Tables

Notifications is list-first, but two tabular surfaces exist:

**Notification history table** (`⋯` → History): When · Category · Title · Source entity · Actor · Channels delivered · Read at · Action taken · Time to action.
**Mute rules table:** Rule · Scope (type/entity/person/thread) · Created · Expires · Items suppressed (count) · Edit/Remove.

Both support filtering and export — genuinely useful when a user complains "I never got told about X", since the history proves what was sent, when, and through which channel.

### 11.9 Filters

Fields: Read/unread · Category · Priority · Source entity (course/project/scholar/publication) · Actor · Date range · Channel delivered · Action taken/not taken · Snoozed · Muted · Has deadline · Blocking others.

Quick chips: `Unread · Action required · Mentions · Overdue · From my scholars · AI proposals · This week`. Saved views: "Monday triage", "Approvals only", "Everything about NANOCAT".

### 11.10 Search

A local search field filters notifications by title, context, actor and entity across the full 90-day history — including read and archived items. `Ctrl+K` scoped to Notifications supports queries like "approvals I rejected last month" or "notifications about Rahul". Search results show the notification *and* a link to its underlying object.

### 11.11 Buttons

Primary (per row): the single most likely action — Approve, Give feedback, Review, Triage. Secondary: the alternate action — Request changes, Message, View. AI-accented: Draft report ✦, Review AI changes ✦, Auto-accept high confidence ✦. Row controls: Snooze ⏰, Mute 🔇, Dismiss ✕. Bulk: Mark all read, Snooze all, Archive selected. Destructive: none — notifications are never deleted, only archived, because the history has evidentiary value.

### 11.12 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **Approval Review** | Medium | The item requiring approval with a preview, requester's message, prior approval chain, comment field, and Approve / Request changes / Reject with reason |
| **Snooze Custom** | Small | Date/time picker with calendar-aware suggestions ("Your next free slot: Thursday 14:00") |
| **Mute Rule** | Medium | Scope selector, duration, an explicit list of what will still come through, and a preview of how many of the last 30 days' notifications would have been suppressed |
| **Notification Preferences** | Large, tabbed | Per-category matrix: In-app / Email / Push / Teams-Slack, with frequency (Instant / Bundled hourly / Daily digest / Weekly / Off) for each; quiet hours; weekend rules; escalation settings ("notify me by email if an approval is unactioned for 48 hours") |
| **Digest Settings** | Medium | Schedule, content selection, ordering, format preview, and a "send me a test" action |
| **AI Proposal Review** | Large | The full change preview with per-item accept/reject (shared component with AI Chat's Preview Changes) |
| **Notification History** | Large | The searchable, exportable history table |
| **Bulk Action Confirm** | Small | For actions over 20 items, with a count and undo assurance |

### 11.13 Right-Click Menus

**On a notification:**
```
⊙ Open source item                Enter
⧉ Open in new tab
─────────────────────────────────────
✓ Mark as read / unread            R
⏰ Snooze                          ▸   (1h · Evening · Tomorrow · Next week · Custom)
📌 Pin to top
─────────────────────────────────────
🔇 Mute this thread
🔇 Mute this entity                ▸
🔇 Mute this type                  ▸
👤 Mute notifications from…
─────────────────────────────────────
ℹ Why did I get this?
📊 Where else was this delivered?
─────────────────────────────────────
🗄 Archive                     Delete
```

**On a bundle:** Expand all · Mark bundle read · Snooze bundle · Unbundle (show individually) · Change bundling rule for this source · Archive bundle.
**On a category (sidebar):** Mark category read · Snooze category · Notification preferences for this category · Mute for 24 hours.
**On an AI proposal:** Review changes · Accept all · Discard all · Adjust the confidence threshold that produced this · Turn off this proposal type.

### 11.14 Context Menus

Selection bar (multi-select): "8 notifications selected" → Mark read · Snooze ▸ · Archive · Mute source ▸ · Export. Triage mode context bar: entering triage (`T`) shows a focused single-notification view with "Item 4 of 23 · [Action] [Snooze] [Skip] [Archive]" and keyboard-first navigation — clearing an inbox becomes a rhythmic, satisfying loop rather than a scroll-and-click slog. Flyout context: right-click the bell icon itself → Pause notifications ▸ · Open notifications · Preferences · Mark all read.

### 11.15 Keyboard Shortcuts

| Key | Action |
|---|---|
| `G` `N` | Go to Notifications |
| `Ctrl+Shift+N` | Toggle the notification flyout |
| `J` / `K` | Next / previous notification |
| `Enter` | Open source item |
| `E` | Archive |
| `R` | Toggle read/unread |
| `S` | Snooze (opens picker) |
| `M` | Mute menu |
| `A` | Primary action (approve/act) |
| `X` | Toggle selection |
| `T` | Enter triage mode |
| `Shift+A` | Mark all read |
| `Esc` | Exit triage / close flyout |

### 11.16 Modern UX Details

- **Two-tier severity is the entire design.** *Action required* and *Awareness* are visually and structurally separate. Mixing them is what makes every other notification system useless.
- **Bundling is aggressive and intelligent.** Twelve updates in one lab space become one row. The bundling rule is visible and adjustable, so users who want granularity can have it.
- **"Blocking" framing changes behaviour.** Marking an item as blocking another human is more motivating than any red badge — and it is honest, since approvals genuinely hold people up.
- **Why did I get this?** is a first-class menu item. Users who understand the rules trust the system and stop muting everything.
- **Snooze is calendar-aware.** "When I'm next free" is a genuinely better option than an arbitrary timer.
- **Nothing is deleted.** Archive plus a 90-day searchable history means the notification record can settle disputes ("I was never told") with evidence.
- **Triage mode** turns inbox clearing into a keyboard rhythm — the single feature most likely to make this screen loved rather than tolerated.
- **Escalation, not repetition.** An unactioned approval escalates to email at 48 hours rather than re-notifying in-app five times.

### 11.17 Glassmorphism

The topbar flyout is Acrylic Base — a canonical use of glass, floating over the app. Toast notifications are Acrylic Base with a semantic left border. The triage-mode context bar and the snooze picker are Acrylic Base. The full-screen notification list is **solid**, because rapid scanning of dense text rows is the core task and blur would slow it measurably.

### 11.18 Dark & Light Mode

Light: unread rows `N1` with an accent left bar, read rows `N0` with `N11` text; severity glyphs at full saturation. Dark: unread rows `N2` with a brighter accent bar, read rows drop to `N1` with `N10` text — the read/unread distinction must rely on both surface value *and* text weight in dark mode, since colour separation alone is weaker. Severity colours desaturate 10% and gain icon reinforcement. The flyout's glass gets 3% noise to prevent banding over varied app content.

### 11.19 Edge States

- **All caught up:** a calm confirmation with a weekly stat, not a celebration animation.
- **Notification storm** (e.g. a bulk import generating hundreds): automatic super-bundling with a single row ("Import completed: 1,240 items processed · 14 need review") and a rate-limit notice explaining that similar events were combined.
- **Muted-but-critical:** security alerts, direct approvals and legal-hold notices bypass all mutes and quiet hours, and say so explicitly on the row ("Delivered despite quiet hours — security").
- **Delivery failure:** if email or push fails, the in-app row shows a small warning glyph with the reason and a retry.
- **First-time user:** a short explanation of the two-tier model and an offer to set quiet hours immediately — setting expectations before the first flood.

---

## SCREEN 12 — SEARCH

### 12.1 Purpose

Search is the **universal retrieval surface** and, per the SRS, the primary answer to "the three-click rule". It fuses lexical, semantic and graph retrieval into one permission-aware experience, and it can return either *results* (things) or *answers* (grounded synthesis with citations). It exists in three forms: the **command palette** (`Ctrl+K`, instant), the **full search screen** (deep exploration with facets), and **in-context search** (scoped to the current screen).

### 12.2 Layout — Full Screen

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← →  ⌕ Search › "selectivity 340K"                                  [Ctrl+K] ✦ 🔔 ◐  │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ ⌕ [ selectivity 340K                                    ] [✦ Ask AI] [Save search ▾] │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Scope: [Everything I can access ▾]  Sort: [Relevance ▾]  [☰ List|⊞ Grid|▤ Table]     │
├────────────────────┬──────────────────────────────────────────────────────────────────┤
│ FACETS             │  ✦ AI ANSWER                                          [Expand ▾] │
│ ────────────────── │  ┌────────────────────────────────────────────────────────────┐  │
│ TYPE               │  │ Your peak selectivity at 340 K was 94.2% (Run 42, 14 Mar   │  │
│ ☑ Dataset      24  │  │ 2026) [1]. Runs 38 and 41 recorded 88.0% and 91.3% at the  │  │
│ ☐ Document     18  │  │ same temperature with lower catalyst loading [2][3].       │  │
│ ☐ Figure        9  │  │ High confidence · 3 sources · [Show sources]  👍 👎        │  │
│ ☐ Notebook      6  │  └────────────────────────────────────────────────────────────┘  │
│ ☐ Slides        4  │                                                                  │
│ SPACE              │  62 results · 0.28 s                                             │
│ ☑ NANOCAT      41  │  ┌────────────────────────────────────────────────────────────┐  │
│ ☐ BIOSENS      12  │  │📊 run42_selectivity.csv                        ★ Relevance │  │
│ ☐ Teaching      9  │  │   NANOCAT › Experiments › Run 42 · 412 MB · 14 Mar 2026    │  │
│ DATE               │  │   …peak **selectivity** 94.2% at **340 K**, catalyst 2.4mg…│  │
│ ○ Any time         │  │   ⛓ lineage · used in MS-0187 fig.3      [Open] [Preview]  │  │
│ ○ Last 7 days      │  ├────────────────────────────────────────────────────────────┤  │
│ ● Last 12 months   │  │📄 MS0187_catalytic-degradation_v3.1.docx                    │  │
│ ○ This semester    │  │   Publications › Under review · 2.1 MB · 20 Jun 2026        │  │
│ ○ Custom…          │  │   …at **340 K** the **selectivity** peaked, consistent with…│  │
│ PERSON             │  │   p.11, §Results                          [Open at p.11]    │  │
│ ☐ Me           38  │  ├────────────────────────────────────────────────────────────┤  │
│ ☐ R. Menon     19  │  │🎞 Group meeting 2026-03-18 (recording)                      │  │
│ ☐ M. Krishnan   5  │  │   Research › NANOCAT › Meetings · 48 min                    │  │
│ MORE FACETS ▾      │  │   "…we saw **selectivity** jump at **340**…"  00:14:22      │  │
│ Status · Tag ·     │  │                                        [Play from 00:14:22] │  │
│ Language · Grant · │  └────────────────────────────────────────────────────────────┘  │
│ Sensitivity · Tier │  [Load more]                                                     │
├────────────────────┴──────────────────────────────────────────────────────────────────┤
│ 62 results (3 excluded — no access) · Index fresh 1 min ago                ● Online   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 Layout — Command Palette (`Ctrl+K`)

720 × 480 px, Acrylic Strong, top-centred at 15vh, over a 30% scrim with 16 px blur.

```
┌────────────────────────────────────────────────────────────────┐
│ ⌕  selectivity 340K                                     [Esc]  │
├────────────────────────────────────────────────────────────────┤
│  ✦ Ask AI: "selectivity 340K"                           ↵      │
│ ──────────────────────────────────────────────────────────────  │
│  RECENT                                                         │
│  📊 run42_selectivity.csv          NANOCAT › Experiments        │
│  📄 MS0187_catalytic…v3.1.docx     Publications                 │
│ ──────────────────────────────────────────────────────────────  │
│  ARTEFACTS (24)                                                 │
│  📊 run38_selectivity.csv          NANOCAT › Experiments        │
│  📈 fig3_selectivity.svg           NANOCAT › Figures            │
│ ──────────────────────────────────────────────────────────────  │
│  ENTITIES (3)                                                   │
│  🔬 NANOCAT (Research space)                                    │
│  📄 MS-0187 (Manuscript)                                        │
│ ──────────────────────────────────────────────────────────────  │
│  COMMANDS                                                       │
│  > Create dataset                                               │
│  > Open provenance view                                         │
│ ──────────────────────────────────────────────────────────────  │
│  ↑↓ navigate · ↵ open · ⌘↵ new tab · Tab filter · See all →    │
└────────────────────────────────────────────────────────────────┘
```

Prefix modes (from F7.5): none = universal · `>` commands · `@` people · `#` entities/tags · `/` navigation · `?` ask AI.

### 12.4 Sidebar (Facets)

The full search screen replaces the context pane with a **facet panel** — the classic and correct pattern for retrieval.

| Facet group | Behaviour |
|---|---|
| **Type** | Artefact types with live counts; multi-select; "more types" expander |
| **Space / Entity** | Spaces, courses, projects, scholars, grants with counts |
| **Date** | Radio presets (Any / 7 days / 30 days / 12 months / This semester / Last semester) + custom range + academic-term picker |
| **Person** | Owner, author, contributor, mentioned — with avatar chips |
| **Status** | Draft / Active / Published / Superseded / Archived |
| **More facets** (collapsed by default) | Tag · Language · Grant · Venue · Sensitivity · Storage tier · Licence · Has DOI · Has lineage · AI-generated · File size · File format · Version count |

Facet behaviour: counts update live as other facets are applied; selected facets appear as removable chips above the results; a facet with zero results is dimmed rather than hidden (so users understand the shape of their corpus); "Clear all" resets.

### 12.5 Topbar & Command Bar

The search input itself dominates: full-width, 44 px, with a magnifier glyph, clear `✕`, and two adjacent controls — `✦ Ask AI` (converts the query into a grounded question) and `Save search ▾` (creates a Smart Folder, optionally with alerting). Below it: **Scope selector** (Everything I can access / My workspace / This space / My lab / Department / Custom), **Sort** (Relevance / Newest / Oldest / Recently modified / Most used / Title A–Z / Size), and the view switcher (List / Grid / Table).

### 12.6 Components

| # | Component | Detail |
|---|---|---|
| C1 | **Query input** | Instant search-as-you-type (debounced 180 ms), inline syntax highlighting for field queries (`type:dataset` renders as a chip inside the input), history dropdown on focus, voice input option |
| C2 | **AI answer card** | Appears only when the query is question-shaped or when the user presses `✦ Ask AI`; grounded, cited, collapsible, with feedback controls; never blocks the result list beneath it |
| C3 | **Result row** | Type glyph, title with query-term highlighting, entity breadcrumb, metadata line (size, date, owner), **snippet with highlighted matches in context**, capability chips (lineage, versions, links), and hover actions |
| C4 | **Deep-link result** | For page/timestamp/cell hits, the row shows the precise locator and the open action jumps directly there ("Open at p.11", "Play from 00:14:22") |
| C5 | **Preview panel** | `Space` or hover-preview opens an inline preview without navigation — PDF page, image, dataset head, video frame, code snippet |
| C6 | **Grouped results** | Optional grouping by space, type or date with collapsible bands |
| C7 | **Did-you-mean / query assistance** | Spelling correction, acronym expansion ("CO → Course Outcome?"), synonym suggestions, and a "search for the exact phrase instead" option |
| C8 | **Exclusion notice** | "3 results were excluded because you don't have access" — count only, never titles (SRS security requirement) |
| C9 | **Search-within-results** | A secondary input that narrows the current result set without a new query |
| C10 | **Saved searches / Smart Folders** | A dropdown listing saved queries with counts; saving offers alerting ("Notify me when new items match") |
| C11 | **Zero-result recovery** | Explains which constraint eliminated results, offers relaxations as one-click chips, and offers external-source search |
| C12 | **Search insights** (admin) | Top queries, zero-result queries, low-click queries — feeding taxonomy improvement |

### 12.7 Cards (Grid view)

Grid view uses the universal card with search-specific additions: a **relevance badge** (star or score bar) in the corner, the matched snippet as the card's subtitle, and the matched location as a chip. Visual-first result types (figures, slides, images, videos) benefit most from grid view, and the view switcher defaults to Grid automatically when > 60% of results are visual — a small adaptive touch that feels intelligent.

### 12.8 Tables (Table view)

| Column | Content | Notes |
|---|---|---|
| ⬚ / Type | Selection + glyph | — |
| Title | Name with highlighting | Sortable |
| Snippet | Best matching passage | Truncated, expandable |
| Location | Entity breadcrumb | Filterable |
| Owner | Avatar + name | Sortable |
| Modified | Relative + absolute tooltip | Sortable, default secondary sort |
| Size | Human-readable | Sortable |
| Type | Artefact type | Filterable |
| Relevance | Score bar | Sortable, default primary sort |
| ⋯ | Overflow | — |

Table view supports the full universal-table feature set (column picker, pinning, grouping, export) — important for power users assembling evidence packs or literature sets from a query.

### 12.9 Filters

Facets *are* the filters here (§12.4), plus inline query syntax for power users:

| Syntax | Meaning |
|---|---|
| `type:dataset` | Field filter |
| `space:NANOCAT` | Scope to a space |
| `owner:@menon` | Person filter |
| `after:2025-01-01` `before:…` | Date bounds |
| `semester:2026-odd` | Academic-term filter |
| `"exact phrase"` | Phrase match |
| `-excluded` | Negation |
| `tag:#reproducibility` | Tag filter |
| `has:lineage` `has:doi` | Capability filters |
| `in:versions` | Search historical versions too |
| `sensitivity:confidential` | Classification filter |

Syntax is discoverable: typing `type:` triggers an inline value autocomplete, and a "Search syntax" help link sits beside the input.

### 12.10 Buttons

Primary: `✦ Ask AI`. Secondary: Save search, Search within results, Load more, Clear filters, Export results, Add all to evidence pack, Search external sources. Row actions: Open, Open in new tab, Preview, Add to selection, `⋯`. Feedback: a subtle "Was this helpful?" on the result set, and thumbs on the AI answer.

### 12.11 Dialogs

| Dialog | Size | Contents |
|---|---|---|
| **Save Search** | Medium | Name, description, scope summary, filters summary, alerting toggle with frequency, where it appears (sidebar pin / space), sharing option |
| **Advanced Search** | Large | Visual query builder for users who dislike syntax: field rows with operators and values, AND/OR grouping, live result count, and a "copy as query syntax" affordance that teaches the syntax |
| **Search Syntax Help** | Medium | Reference table with copyable examples |
| **Export Results** | Medium | Format (CSV/XLSX/BibTeX for publications/JSON), columns, scope (current page / all results, with a cap warning) |
| **Add to Evidence Pack** | Medium | Framework and criterion picker with the selected results listed |
| **External Search** | Large | Federated results from library catalogue, institutional repository, Crossref, OpenAlex — clearly separated from internal results with a source badge and an "Import to my library" action per item |
| **Preview** | Overlay | Full artefact preview with navigation (`←`/`→` through results), open, and quick actions |

### 12.12 Right-Click Menus

**On a result:** the universal artefact right-click menu (F8.1), plus search-specific items:
```
⊙ Open                            Enter
📍 Open at match location              (page/timestamp/cell)
⧉ Open in new tab           Ctrl+Enter
👁 Preview                        Space
─────────────────────────────────────
✦ Ask AI about this
✦ Find similar
✦ Why did this match?
─────────────────────────────────────
[…universal artefact commands…]
─────────────────────────────────────
🔍 Search within this space only
⊘ Exclude this type from results
```

**On a facet value:** Filter by only this · Exclude this · Add to current filters · Show all values · Copy as query syntax.
**On the search input:** standard text menu plus Paste and search · Clear history · Search syntax help · Advanced search.
**On a snippet:** Copy snippet · Copy with citation · Quote in AI chat · Highlight in source.

### 12.13 Context Menus

Selection bar (multi-select results): "14 results selected" → Open all in tabs (with a warning above 10) · Add to evidence pack · Export citations · Move to space · Tag · Share · Download · Add to AI scope (a powerful move: turn a search result set into the retrieval scope for a chat). Preview context bar: "Result 4 of 62 · [←] [→] [Open] [Close]". Query context: hovering the result count shows "62 results in 0.28 s · lexical 41, semantic 34, graph 9 (overlap removed)" — a transparency touch that power users appreciate.

### 12.14 Keyboard Shortcuts

| Key | Action |
|---|---|
| `Ctrl+K` | Command palette (from anywhere) |
| `G` `/` or `Ctrl+Shift+K` | Full search screen |
| `/` | Focus the search input |
| `↑ ↓` | Navigate results |
| `Enter` | Open |
| `Ctrl+Enter` | Open in new tab |
| `Space` | Preview |
| `Tab` (in palette) | Cycle result categories |
| `Alt+1..9` | Toggle the Nth facet group |
| `Ctrl+S` | Save search |
| `Ctrl+Shift+A` | Ask AI with the current query |
| `X` | Toggle result selection |
| `Ctrl+F` | Search within results |
| `Esc` | Clear query / close palette |

### 12.15 Modern UX Details

- **Sub-300 ms or it doesn't count.** Every design decision here serves perceived speed: instant palette open, streaming results, optimistic highlighting, cached recents shown before the query returns.
- **The palette answers most needs; the screen answers hard ones.** Users should rarely need the full screen — and when they do, facets and syntax make it genuinely powerful rather than merely bigger.
- **Snippets are the product.** A result without a contextual, highlighted snippet forces the user to open it to find out if it is right. Snippet quality is the difference between a good and a useless search.
- **Deep links to the exact match** (page, cell, timestamp) eliminate the second search *inside* the document.
- **"Why did this match?"** explains semantic hits that contain none of the query words — essential for trust in hybrid retrieval.
- **Excluded-count honesty** discloses that results were withheld for permission reasons without leaking anything.
- **Search becomes structure.** Saving a query creates a Smart Folder, which is the mechanism by which the SRS's "folders are projections" philosophy becomes a daily habit.
- **Result-set → AI scope** is the highest-leverage interaction on the screen: find 40 relevant papers, then ask a question of exactly those 40.

### 12.16 Glassmorphism

The command palette is the flagship glass surface in the entire product — Acrylic Strong (40 px blur, 60% opacity, 160% saturation) over a blurred scrim, with a 1 px light border and an inner top highlight. It should feel like it is floating above the workspace. Also glass: the preview overlay's toolbar, the facet "more" flyout, the AI answer card (Frosted Card, violet), and the selection action bar. The result list, tables and facet panel are solid — scanning dense results is the core task.

### 12.17 Dark & Light Mode

Light: query-term highlights use a warm amber background (`#FEF3C7`) with dark text — the classic, most legible highlight; palette glass is white-tinted. Dark: highlights invert to a 25%-opacity amber fill with light text (a plain amber background would glare); the palette's glass is black-tinted with 3% noise and a stronger border so it separates from dark content behind it; relevance bars use `accent.hover`; the AI answer card uses a 6% violet wash. In both themes, the focused result row uses a 2 px accent left bar plus a surface change, never colour alone.

### 12.18 Edge States

- **Empty query (palette open):** recent items, frequent destinations, and three suggested queries drawn from the user's actual corpus.
- **Zero results:** the constraint-explanation pattern — "No results. The *Type: Dataset* filter removed 41 matches. [Remove filter] [Search everywhere] [Search external sources]".
- **Too many results (> 10,000):** a notice suggesting refinement, with the top facets offered as one-click narrowing.
- **Slow query:** progressive results — lexical matches appear immediately while semantic and graph results stream in, with a subtle "finding related items…" indicator.
- **Index lag:** a chip stating "3 recently uploaded items are still being indexed" with a live count, so users never wonder why something new is missing.
- **Permission-heavy corpus:** the exclusion notice appears consistently; clicking it explains the policy without naming the items.
- **Offline:** search falls back to locally synced content with a clear banner: "Searching offline content only (2,140 items). Reconnect to search everything."

---

# PART III — APPENDICES

---

## Appendix A — Master Keyboard Shortcut Map

### A.1 Global (any screen, any state)

| Shortcut | Action |
|---|---|
| `Ctrl+K` | Command palette / universal search |
| `Ctrl+Shift+K` | Full search screen |
| `Ctrl+J` | Toggle AI dock |
| `Ctrl+I` | Toggle inspector |
| `Ctrl+\` | Toggle left rail |
| `Ctrl+Shift+E` | Toggle context pane |
| `Ctrl+Shift+N` | New window |
| `Ctrl+T` / `Ctrl+W` | New tab / close tab |
| `Ctrl+Shift+T` | Reopen closed tab |
| `Ctrl+1…9` | Jump to tab N |
| `Ctrl+Tab` | Cycle tabs |
| `Ctrl+Alt+\` | Split view (vertical) |
| `Ctrl+Shift+O` | Pop out current item |
| `Ctrl+Shift+F` | Focus mode |
| `Ctrl+Shift+R` | Zen reading mode |
| `Ctrl+Shift+W` | Workspace (tenant) switcher |
| `Alt+←` / `Alt+→` | Back / forward |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `Ctrl+N` | New (context-aware) |
| `Ctrl+U` | Upload / quick capture |
| `Ctrl+F` | Find in view |
| `Ctrl+P` | Print / export current view |
| `Ctrl+,` | Settings |
| `Ctrl+/` | Keyboard shortcut reference |
| `Ctrl+Shift+D` | Toggle dark / light |
| `Ctrl+Shift+Alt+D` | Toggle density |
| `F1` | Contextual help |
| `F6` | Cycle between the five shell zones |
| `F11` | Full screen |
| `Esc` | Close overlay / clear selection / exit mode |

### A.2 Navigation chords (`G` then key, no input focused)

`G D` Dashboard · `G T` Teaching · `G R` Research · `G P` Publications · `G J` Projects · `G X` Administration · `G S` Students · `G C` Calendar · `G A` AI Chat · `G N` Notifications · `G ,` Settings · `G /` Search · `G H` Home

### A.3 Object & list operations (no input focused)

| Key | Action |
|---|---|
| `↑ ↓` | Move selection |
| `← →` | Collapse / expand · previous / next column |
| `Enter` | Open |
| `Ctrl+Enter` | Open in new tab |
| `Space` | Quick preview |
| `X` | Toggle selection |
| `Shift+↑/↓` | Extend selection |
| `Ctrl+A` | Select all |
| `E` | Edit / rename |
| `D` | Duplicate |
| `S` | Share |
| `L` | Link to entity |
| `T` | Tags |
| `V` | Version history |
| `C` | Comment |
| `A` | Ask AI about this |
| `P` | Pin |
| `F` | Favourite |
| `M` | Move to… |
| `#` or `Delete` | Move to trash |
| `Shift+F10` or `☰` | Right-click menu |
| `F2` | Rename inline |

### A.4 Screen-specific summary

| Screen | Distinctive bindings |
|---|---|
| Dashboard | `R` regenerate briefing · `1–9` focus widget · `E` customise · `P` period |
| Teaching | `Shift+R` roll forward · `W` current week · `A` attendance · `Shift+G` grader · `Ctrl+Enter` save & next submission |
| Research | `I` ingest · `L` lineage view · `V` verify integrity · `P` reproducibility pack · `F` fit graph |
| Publications | `→`/`←` advance stage · `C` copy citation · `O` ORCID sync · `S`/`R` record submission/decision |
| Projects | `T`/`D`/`M` new task/deliverable/milestone · `E` expense · `R` report · `Shift+B` baseline · `Shift+C` critical path |
| Administration | `V` verification mode · `A`/`R` approve/reject · `E` export pack · `Ctrl+Shift+A` audit log |
| Students | `L` log meeting · `F` give feedback · `M` milestone · `T` thesis · `R` risk explanation |
| Calendar | `D/W/M/Y` views · `T` today · `N` new event · `P` prepare · `F` find a time |
| AI Chat | `Ctrl+Shift+S` scope · `Ctrl+R` regenerate · `Esc` stop · `/` slash commands · `@` mention |
| Settings | `/` search settings · `Space` toggle · `Ctrl+S` save |
| Notifications | `J/K` navigate · `A` act · `S` snooze · `E` archive · `T` triage mode |
| Search | `/` focus · `Alt+1..9` facets · `Ctrl+S` save search · `Ctrl+Shift+A` ask AI |

### A.5 Shortcut governance

No shortcut may conflict with OS-reserved bindings (`Ctrl+Alt+Del`, `Cmd+Space`, `Alt+Tab`, `F5` refresh) or with the browser's essential set in the web build. Single-key shortcuts are suppressed whenever a text input, editor or dialog has focus. All bindings are user-remappable (Settings › Shortcuts) with conflict detection. On macOS, `Ctrl` maps to `Cmd` throughout, with `Ctrl` reserved for text-navigation conventions.

---

## Appendix B — Icon System

**Style:** single-weight line icons, 1.5 px stroke at 20 px and 24 px, 2 px at 32 px; rounded caps and joins; 24 px optical grid with 2 px padding; geometric rather than illustrative. Fluent-aligned geometry with a slightly softer terminal treatment to match the product's calmer tone.

**Rules:** every icon in a toolbar has a tooltip; icons never carry meaning alone in status contexts (always paired with text or a label); filled variants are reserved for *active/selected* states; domain icons carry domain tints only in navigation, never in content.

| Domain | Icon concepts |
|---|---|
| Navigation | Dashboard (grid), Teaching (mortarboard), Research (flask), Publications (document with fold), Projects (folder-tree), Students (people), Calendar (calendar), AI (four-point sparkle ✦), Search (magnifier), Notifications (bell), Settings (gear), Administration (columned building) |
| Artefact types | Document, Slides, Spreadsheet, PDF, Image, Video, Audio, Dataset (cylinder), Notebook (code cell), Code (angle brackets), Archive (box), Link, Note, Form, Certificate |
| Actions | Open, Preview (eye), Edit (pencil), Duplicate, Move (arrows), Delete (trash), Share (arc), Download, Upload, Link (chain), Tag, Pin, Star, Comment, Approve (check), Reject (cross), Snooze (clock), Mute (bell-slash), Filter (funnel), Sort (arrows), Refresh, Export, Print |
| Status | Success (check-circle), Warning (triangle), Error (x-circle), Info (i-circle), Pending (clock), In progress (half-circle), Blocked (slash-circle), Locked (padlock), Verified (badge-check), Immutable (shield-lock) |
| Domain-specific | Provenance (chain-link ⛓), Version (branching), Milestone (diamond), Deliverable (package), Grant (coin), Citation (quote), ORCID (iD mark), DOI (globe-link), Cold storage (snowflake), Legal hold (gavel), CO/PO mapping (matrix), Attendance (checklist) |

---

## Appendix C — Component Inventory & Coverage Matrix

### C.1 Component count by category

| Category | Components |
|---|---|
| **Primitives** (14) | Button, Icon button, Split button, Input, Textarea, Select, Combobox, Checkbox, Radio, Switch, Slider, Chip/Tag, Avatar, Badge |
| **Data display** (16) | Table, Data grid, Card, List row, Tree, Timeline, Gantt, Kanban board, Calendar grid, Graph canvas, Metric tile, Progress bar, Progress ring, Sparkline, Chart set, Heatmap |
| **Navigation** (10) | Rail, Context pane, Breadcrumb, Tabs, Segmented control, Pagination, Command palette, Stepper, Anchor nav, Workspace switcher |
| **Overlay** (9) | Dialog, Side sheet, Flyout, Popover, Tooltip, Toast, Banner, Teaching callout, Context menu |
| **Feedback** (8) | Skeleton, Spinner, Empty state, Error state, Confidence indicator, AI badge, Status pill, Freshness dot |
| **Composite** (12) | Filter bar, Selection action bar, Inspector, AI dock, Upload dropzone, Version timeline, Permission editor, Entity picker, Date/term picker, Rich text editor, Annotation layer, Diff viewer |

**Total: 69 core components**, each requiring: light/dark variants, all interaction states, compact/comfortable/relaxed densities, keyboard specification, ARIA semantics, RTL support, and reduced-motion behaviour.

### C.2 Screen × requirement coverage matrix

| Screen | Purpose | Sidebar | Topbar | Components | Cards | Tables | Filters | Search | Buttons | Dialogs | Right-click | Context | Shortcuts | Glass | Dark/Light |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 Dashboard | ✓ | ✓ | ✓ | 12 | 10 | mini | ✓ | ⌘K | 12 | 8 | 5 | 4 | 11 | hero | ✓ |
| 2 Teaching | ✓ | ✓ | ✓ | 12 | 4 | 4 | ✓ | ✓ | 18 | 11 | 6 | 4 | 15 | ✓ | ✓ |
| 3 Research | ✓ | ✓ | ✓ | 11 | 4 | 4 | ✓ | ✓ | 16 | 10 | 5 | 3 | 13 | ✓ | ✓ |
| 4 Publications | ✓ | ✓ | ✓ | 10 | 2 | 3 | ✓ | ✓ | 17 | 12 | 4 | 3 | 12 | ✓ | ✓ |
| 5 Projects | ✓ | ✓ | ✓ | 12 | 4 | 5 | ✓ | ✓ | 17 | 11 | 7 | 4 | 14 | ✓ | ✓ |
| 6 Administration | ✓ | ✓ | ✓ | 12 | 5 | 4 | ✓ | ✓ | 16 | 13 | 6 | 4 | 10 | minimal | ✓ |
| 7 Students | ✓ | ✓ | ✓ | 12 | 4 | 5 | ✓ | ✓ | 15 | 11 | 4 | 4 | 12 | ✓ | ✓ |
| 8 Calendar | ✓ | ✓ | ✓ | 12 | 3 | 3 | ✓ | ✓ | 13 | 10 | 5 | 4 | 14 | ✓ | ✓ |
| 9 AI Chat | ✓ | ✓ | ✓ | 12 | 4 | 4 | ✓ | ✓ | 14 | 10 | 5 | 4 | 15 | heavy | ✓ |
| 10 Settings | ✓ | ✓ | ✓ | 12 | 6 | 7 | ✓ | ✓ | 13 | 12 | 5 | 3 | 9 | minimal | ✓ |
| 11 Notifications | ✓ | ✓ | ✓ | 10 | 4 | 2 | ✓ | ✓ | 11 | 8 | 4 | 3 | 12 | flyout | ✓ |
| 12 Search | ✓ | facets | ✓ | 12 | 1 | 1 | ✓ | core | 10 | 7 | 4 | 3 | 13 | palette | ✓ |

---

## Appendix D — Motion Choreography Reference

| Interaction | Choreography |
|---|---|
| App launch | Shell paints instantly (cached) → rail and topbar at 0 ms → context pane fade 100 ms → canvas skeleton 120 ms → content resolves progressively. Never a splash screen |
| Route change | Outgoing content fades to 0 over 80 ms → incoming fades in with a 4 px rise over 180 ms. Rail and topbar never move |
| Dashboard load | Widgets stagger in at 40 ms intervals, fade + 4 px rise, 180 ms each; total under 500 ms |
| Panel open (inspector, AI dock) | Slide from edge, 250 ms, `cubic-bezier(.16,1,.3,1)`; canvas reflows simultaneously, never after |
| Dialog | Scrim fades 150 ms; dialog scales 0.96 → 1 with fade over 300 ms; on close, reverse at 200 ms |
| Command palette | Scrim + blur in 120 ms; palette drops 8 px with fade over 180 ms; results stream without re-animating the container |
| Right-click menu | Fade + 4 px directional slide from the cursor over 120 ms; submenus 100 ms on 200 ms hover delay |
| Toast | Slide up 16 px + fade, 200 ms; stack shifts with spring; auto-dismiss fades over 150 ms |
| Row hover | Fill transition 80 ms; trailing actions fade in 80 ms with no layout shift (space is pre-reserved) |
| Card hover | Elevation E1→E2 and 2 px translate over 150 ms |
| Drag | Item lifts to E4 with 3° tilt and 92% opacity over 100 ms; origin shows a dashed placeholder; drop settles with spring; invalid targets shake 4 px |
| Selection | Checkbox check draws over 150 ms; selection bar rises from the bottom over 250 ms |
| Number change | Count-up roll over 300 ms with `motion.normal` easing |
| Progress | Determinate bars ease to new values over 400 ms; indeterminate uses a 1.4 s sweep |
| AI streaming | Tokens append with no per-token animation (that causes jank); a caret pulses at 1 Hz; the source panel populates as citations resolve |
| AI proposal applied | Affected rows flash `accent.subtle` for 400 ms then settle; the undo toast appears simultaneously |
| Theme switch | Cross-fade all surfaces over 150 ms; no flash of unstyled or inverted content |
| Error shake | 3 × 4 px horizontal, 300 ms total — used only for invalid input, never for system errors |
| Success | Check-mark path draws over 200 ms; no confetti, ever |

**Reduced motion:** all of the above collapse to opacity-only transitions of ≤ 80 ms; drag uses instant repositioning; streaming renders in 200 ms chunks rather than token-by-token.

---

## Appendix E — Design Do's and Don'ts

### E.1 Do

- **Do** put the single most likely action as a filled primary button, and only one per zone.
- **Do** show the entity breadcrumb, not the folder path — users think in courses and projects, not directories.
- **Do** pre-reserve space for hover actions so nothing shifts when the pointer arrives.
- **Do** show relative dates with absolute values in tooltips ("9 days ago" / "26 Jul 2026, 14:22 IST").
- **Do** use tabular figures in every number column.
- **Do** explain every AI output with sources, confidence and a "show your work" path.
- **Do** make every destructive action undoable for at least 30 days, and say so at the moment of action.
- **Do** disclose when results, cards or menu items are hidden for permission reasons — by count, never by content.
- **Do** write empty states that teach: what this is, why it matters, one action.
- **Do** keep the five shell zones in fixed positions so spatial memory forms within days.
- **Do** localise dates, numbers, currencies and academic calendars.
- **Do** test every screen at 200% OS text scaling and with a screen reader before it ships.

### E.2 Don't

- **Don't** use glass behind body text, data tables, form inputs or documents.
- **Don't** animate blur radius, ever.
- **Don't** nest one glass surface inside another.
- **Don't** invert user documents, figures or slides in dark mode — colour is often data.
- **Don't** use colour as the sole carrier of status; always add an icon or label.
- **Don't** show a spinner for anything under 400 ms, or a bare spinner for anything over it.
- **Don't** put two primary buttons in the same zone.
- **Don't** hide a disabled control's reason — always explain in a tooltip.
- **Don't** gamify scholarship: no streaks, no confetti, no vanity leaderboards, no badges for logging in.
- **Don't** let AI mutate the workspace without a preview and an undo.
- **Don't** surface individual-performance judgements about people generated by a model.
- **Don't** stack more than two dialogs; convert the third into a wizard step.
- **Don't** rely on hover for anything essential — it does not exist on touch and is invisible to keyboard users.
- **Don't** ship a setting you cannot describe in one clear sentence.

---

## Design Sign-Off & Next Steps

| Role | Responsibility | Status |
|---|---|---|
| UX Design | Shell, screens, interaction patterns, accessibility | Approved for prototyping |
| Design System | Tokens, 69 components, light/dark, glass materials, motion | Approved |
| Product Management | Screen scope, priority, success metrics | Approved |
| Engineering | Feasibility of glass performance, virtualisation, streaming | Pending performance spike |
| Accessibility | WCAG 2.2 AA conformance plan, screen-reader test matrix | Pending audit plan |

**Immediate next steps**

1. **High-fidelity prototypes of the two decisive screens first** — the Migration Reveal (from SRS §6.1) and the Faculty Dashboard. These determine adoption; everything else is downstream.
2. **Build the design system before the screens.** Tokens, then the 14 primitives, then the universal Table / Card / Filter bar / Dialog / Menu — the four composites that account for roughly 70% of every screen in this document.
3. **Run a glass performance spike** on low-end institutional hardware (integrated graphics, 1366×768, 8 GB RAM) and finalise the fallback threshold before glass is committed anywhere.
4. **Usability-test the command palette and Search screen** with eight academics before locking the interaction model — these two surfaces carry the "three-click rule".
5. **Write the accessibility test matrix** (NVDA + JAWS + VoiceOver × 12 screens × light/dark/HC) as a release gate, not a retrospective audit.
6. **Prototype the AI proposal pattern** (preview → apply → undo) in isolation and validate that users understand the distinction between AI *talking* and AI *doing*. This single pattern carries the product's trust model.

*End of Desktop UI/UX Specification v1.0.*
