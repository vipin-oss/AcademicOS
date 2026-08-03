"use client";

import Link from "next/link";
import { ArrowRight, BarChart3 } from "lucide-react";
import { REPORT_KINDS } from "@/lib/reports/constants";

/** Launchpad cards linking each PART 2..10 report workspace. */
export function ReportLaunchpad() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {REPORT_KINDS.map((kind) => (
        <Link
          key={kind.key}
          href={`/reports/${kind.key}`}
          className="group rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm transition-colors hover:border-[var(--accent)] hover:bg-[var(--bg-hover)]"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
              <BarChart3 className="h-4 w-4 text-[var(--accent)]" aria-hidden="true" />
              {kind.title}
            </span>
            <ArrowRight
              className="h-4 w-4 text-[var(--text-tertiary)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--accent)]"
              aria-hidden="true"
            />
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-[var(--text-secondary)]">
            {kind.description}
          </p>
        </Link>
      ))}
    </div>
  );
}
