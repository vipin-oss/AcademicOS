"use client";

/**
 * Academic Intelligence Assistant — the deterministic intelligence layer
 * workspace (module 13). Answers are computed from the data of the frozen
 * modules by the rules engine and every answer links back to them; nothing
 * is duplicated here. V1 is local and deterministic (rules-v1) — no
 * external AI of any kind. This is a distinct, non-LLM capability and is
 * preserved as its own workspace (reachable from the Academic AI workspace);
 * the LLM-based assistants live at /ai.
 */
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { AssistantWorkspace } from "@/components/features/assistant/AssistantWorkspace";
import { AssistantLabs } from "@/components/features/assistant/AssistantLabs";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";

export default function AssistantPage() {
  return (
    <div className="flex min-h-screen bg-[var(--bg-app)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 space-y-6 p-4 sm:p-6">
          <div>
            <Breadcrumbs
              items={[{ label: "Dashboard", href: "/" }, { label: "Assistant" }]}
            />
            <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">
              Academic Intelligence Assistant
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Ask in plain English — publications, projects, attendance, purchases,
              events, committees and reports, answered from your live AcademicOS
              data with links back to every source module.
            </p>
          </div>
          <AssistantWorkspace />
          <AssistantLabs />
        </main>
      </div>
    </div>
  );
}
