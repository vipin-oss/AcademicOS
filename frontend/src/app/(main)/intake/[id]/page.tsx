"use client";

import { useParams } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SessionDetailsView } from "@/components/features/intake/SessionDetailsView";

/**
 * Next.js hands the dynamic segment back percent-encoded. This is the ONE and
 * ONLY decode in the whole flow — the hook and the API layer forward the
 * decoded id untouched, so the backend receives `intake:session:…` exactly as
 * `ObjectId.parse` expects. (Same convention as documents/[id].)
 */
function decodeRouteId(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value; // malformed escape sequence — use the raw segment
  }
}

export default function IntakeSessionDetailsPage() {
  const params = useParams<{ id: string }>();
  const sessionId = decodeRouteId(params?.id);

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs
            items={[
              { label: "Dashboard", href: "/" },
              { label: "Intake", href: "/intake" },
              { label: "Session" },
            ]}
          />
          <div className="mt-4">
            <SessionDetailsView sessionId={sessionId} />
          </div>
        </main>
      </div>
    </div>
  );
}
