"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Redirect /chat → /ai (unified assistant surface). */
export default function ChatRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/ai"); }, [router]);
  return null;
}
