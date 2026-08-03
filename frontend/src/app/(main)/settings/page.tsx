"use client";

/**
 * Settings & Preferences — the centralized place for user preferences and
 * system configuration (module 12). Section cards only; business data lives
 * in its own modules and is never duplicated here.
 */
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SettingsWorkspace } from "@/components/features/settings/SettingsWorkspace";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";

export default function SettingsPage() {
  return (
    <div className="flex min-h-screen bg-[var(--bg-app)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 space-y-6 p-4 sm:p-6">
          <div>
            <Breadcrumbs
              items={[{ label: "Dashboard", href: "/" }, { label: "Settings" }]}
            />
            <h1 className="mt-2 text-2xl font-bold text-[var(--text-primary)]">
              Settings &amp; Preferences
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Your profile, appearance, defaults and privacy controls — stored
              centrally, applied across every module.
            </p>
          </div>
          <SettingsWorkspace />
        </main>
      </div>
    </div>
  );
}
