"use client";

/** Client-side route guard for every (main) page: while the session is
 * being restored a minimal loading screen is shown; a fully anonymous
 * session is redirected to /login. The server-side middleware handles the
 * cookie-based redirect; this layer covers the post-load state (e.g. an
 * expired session discovered by /auth/me). */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/lib/auth/session";

export default function MainLayout({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anon") router.replace("/login");
  }, [status, router]);

  if (status === "loading" || status === "anon") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-app)]">
        <p className="text-sm text-[var(--text-secondary)]">Loading…</p>
      </div>
    );
  }

  return <>{children}</>;
}
