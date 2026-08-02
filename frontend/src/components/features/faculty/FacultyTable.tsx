"use client";

import Link from "next/link";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ResearchStatusBadge } from "@/components/features/research/ResearchBadges";
import { EmploymentTypeBadge } from "./FacultyBadges";
import type { FacultyResponse } from "@/types";

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("") || "?";
}

/** Small avatar: the profile photo when attached, initials otherwise. */
export function FacultyAvatar({
  name,
  photoUrl,
  size = "md",
}: {
  name: string;
  photoUrl?: string | null;
  size?: "md" | "lg";
}) {
  const box = size === "lg" ? "h-16 w-16 text-lg" : "h-9 w-9 text-xs";
  if (photoUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- the blob is served by our own API
      <img
        src={photoUrl}
        alt={`Profile photo of ${name}`}
        className={`${box} shrink-0 rounded-full border border-[var(--border-subtle)] object-cover`}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className={`${box} inline-flex shrink-0 items-center justify-center rounded-full bg-[var(--accent-subtle)] font-semibold text-[var(--accent)]`}
    >
      {initialsOf(name)}
    </span>
  );
}

/** The faculty directory table (mirrors ProjectTable / StudentTable structure). */
export function FacultyTable({
  items,
  loading = false,
}: {
  items: FacultyResponse[];
  loading?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[900px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Faculty</th>
            <th scope="col" className="px-4 py-3 font-medium">Designation</th>
            <th scope="col" className="px-4 py-3 font-medium">Department</th>
            <th scope="col" className="px-4 py-3 font-medium">Specialization</th>
            <th scope="col" className="px-4 py-3 font-medium">Contact</th>
            <th scope="col" className="px-4 py-3 font-medium">Employment</th>
            <th scope="col" className="px-4 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={6} cols={7} />
          ) : (
            items.map((faculty) => (
              <tr
                key={faculty.id}
                className="border-b border-[var(--border-subtle)] align-top transition-colors last:border-0 hover:bg-[var(--bg-hover)]"
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <FacultyAvatar name={faculty.name} photoUrl={faculty.photo_url} />
                    <div className="min-w-0">
                      <Link
                        href={`/faculty/${encodeURIComponent(faculty.id)}`}
                        className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                      >
                        {faculty.name}
                      </Link>
                      <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
                        {[faculty.employee_id, faculty.faculty_code]
                          .filter(Boolean)
                          .join(" · ") || "No employee id"}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {faculty.designation ?? "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {faculty.department ?? "—"}
                  {faculty.school ? (
                    <span className="block text-xs text-[var(--text-tertiary)]">
                      {faculty.school}
                    </span>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {faculty.specialization ?? "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {faculty.email ?? "—"}
                  {faculty.mobile ? (
                    <span className="block text-xs text-[var(--text-tertiary)]">
                      {faculty.mobile}
                    </span>
                  ) : null}
                </td>
                <td className="px-4 py-3">
                  {faculty.employment_type ? (
                    <EmploymentTypeBadge type={faculty.employment_type} />
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3">
                  <ResearchStatusBadge status={faculty.status} />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
