"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Redirect /assistant → /ai (unified assistant surface). */
export default function AssistantRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/ai"); }, [router]);
  return null;
}
