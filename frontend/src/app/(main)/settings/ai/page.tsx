"use client";

/**
 * AI Settings (Sprint M11.1 — AI Foundation).
 *
 * Read-only status surface for the AI Core: health, providers, models,
 * feature flags. No chat, no prompts, no generation — infrastructure only.
 */
import { AiSettingsView } from "@/components/features/settings/AiSettingsView";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";

export default function AiSettingsPage() {
  return (
    <div className="flex min-h-screen bg-[var(--bg-app)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 space-y-6 p-4 sm:p-6">
          <div>
            <Breadcrumbs
              items={[
                { label: "Dashboard", href: "/" },
                { label: "Settings", href: "/settings" },
                { label: "AI" },
              ]}
            />
            <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">
              AI Settings
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              The AI Foundation (M11.1): provider catalogue, model registry
              and health status. Generation capabilities arrive in later
              M11 sprints.
            </p>
          </div>
          <AiSettingsView />
        </main>
      </div>
    </div>
  );
}
