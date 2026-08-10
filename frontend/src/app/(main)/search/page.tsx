import { Suspense } from "react";

import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import SearchPage from "@/components/features/search/SearchPage";

export default function Page() {
  return (
    <div className="flex min-h-screen bg-[var(--bg-app)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 space-y-6 p-4 sm:p-6">
          <div>
            <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Search" }]} />
          </div>
          <Suspense fallback={<div className="py-16 text-center text-sm text-[var(--text-tertiary)]">Loading search…</div>}>
            <SearchPage />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
