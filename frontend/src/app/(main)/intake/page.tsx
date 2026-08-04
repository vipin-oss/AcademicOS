"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { IntakeWorkspace } from "@/components/features/intake/IntakeWorkspace";

export default function IntakePage() {
  const router = useRouter();

  // A freshly created session navigates straight to its details view so the
  // user watches first progress as it happens.
  const handleOpenSession = useCallback(
    (id: string) => {
      router.push(`/intake/${encodeURIComponent(id)}`);
    },
    [router],
  );

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Intake" }]} />
          <div className="mt-4">
            <IntakeWorkspace onOpenSession={handleOpenSession} />
          </div>
        </main>
      </div>
    </div>
  );
}
