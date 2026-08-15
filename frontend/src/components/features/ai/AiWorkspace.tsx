"use client";

/**
 * The unified Academic AI workspace (reconciliation pass) — ONE coherent
 * surface in the sidebar ("Academic AI") with five user-facing modes:
 *
 *   General        — grounded document chat (POST /ai/chat/stream)
 *   Research       — domain assistant (POST /ai/assistants/research/stream)
 *   Teaching       — domain assistant (teaching; academic-integrity guard)
 *   Publication    — domain assistant (publication)
 *   Administration — domain assistant (administration; proposal-only)
 *
 * All modes share one conversation panel, one streaming transport
 * (lib/api/ai.ts streamAi), one error/loading/citation rendering. The
 * M21–M25 composition pattern, AI Core authority, grounding, citations and
 * permission filtering are untouched server-side.
 *
 * The deterministic Academic Intelligence Assistant (rules-based answers
 * over live AcademicOS data, conversation memory, human review queue, eval
 * history) is a distinct, non-LLM capability and keeps its own workspace at
 * /assistant — reachable through the link below, not duplicated here.
 */
import { useState } from "react";
import Link from "next/link";
import { FlaskConical, GraduationCap, Landmark, MessageSquare, PenLine } from "lucide-react";

import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { cn } from "@/lib/utils";
import { AiChatPanel, type AiMode } from "./AiChatPanel";

export type WorkspaceMode =
  | "general"
  | "research"
  | "teaching"
  | "publication"
  | "administration";

const MODES: { key: WorkspaceMode; label: string; icon: typeof MessageSquare; description: string }[] = [
  { key: "general", label: "General", icon: MessageSquare, description: "Document-grounded chat over your readable documents." },
  { key: "research", label: "Research", icon: FlaskConical, description: "Literature review, gap analysis, hypothesis framing." },
  { key: "teaching", label: "Teaching", icon: GraduationCap, description: "Lesson plans, explanations, quiz items, draft feedback." },
  { key: "publication", label: "Publication", icon: PenLine, description: "Drafting, restructuring, caption and reference checks." },
  { key: "administration", label: "Administration", icon: Landmark, description: "Draft schedules, compliance notes, grant reports." },
];

function modeToAiMode(mode: WorkspaceMode): AiMode {
  if (mode === "general") return { type: "chat" };
  return { type: "role", role: mode };
}

export function AiWorkspace({ initialMode = "general" }: { initialMode?: WorkspaceMode }) {
  const [mode, setMode] = useState<WorkspaceMode>(initialMode);
  const aiMode = modeToAiMode(mode);
  const active = MODES.find((m) => m.key === mode) ?? MODES[0];

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 space-y-6 p-4 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <Breadcrumbs
                items={[{ label: "Dashboard", href: "/" }, { label: "Academic AI" }]}
              />
              <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">Academic AI</h1>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Grounded, permission-aware AI over your AcademicOS knowledge —
                with citations, role guardrails and honest degradation.
              </p>
            </div>
            <Link
              href="/assistant"
              className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            >
              Deterministic Assistant — answers from your live AcademicOS data, no LLM required →
            </Link>
          </div>

          <div className="flex flex-wrap gap-2" role="tablist" aria-label="Academic AI modes">
            {MODES.map((m) => {
              const Icon = m.icon;
              return (
                <button
                  key={m.key}
                  type="button"
                  role="tab"
                  aria-selected={mode === m.key}
                  onClick={() => setMode(m.key)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                    mode === m.key
                      ? "bg-[var(--accent-subtle)] text-[var(--accent)]"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {m.label}
                </button>
              );
            })}
          </div>

          <AiChatPanel key={mode} mode={aiMode} description={active.description} />
        </main>
      </div>
    </div>
  );
}
