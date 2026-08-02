"use client";

import { Globe } from "lucide-react";
import { ResearchStatusBadge } from "@/components/features/research/ResearchBadges";
import { EmploymentTypeBadge } from "./FacultyBadges";
import { FacultyAvatar } from "./FacultyTable";
import { formatDate } from "@/lib/research/constants";
import type { FacultyResponse } from "@/types";

/** The ORCID record URL when the id looks like a bare ORCID iD. */
function orcidUrl(orcid: string): string {
  return orcid.startsWith("http") ? orcid : `https://orcid.org/${orcid}`;
}

/** Compact faculty identity header for the workspace page (with action slot). */
export function FacultyHeader({
  faculty,
  actions,
}: {
  faculty: FacultyResponse;
  actions?: React.ReactNode;
}) {
  const scholarLinks: { label: string; href: string }[] = [];
  if (faculty.orcid) scholarLinks.push({ label: "ORCID", href: orcidUrl(faculty.orcid) });
  if (faculty.google_scholar) {
    scholarLinks.push({
      label: "Google Scholar",
      href: faculty.google_scholar.startsWith("http")
        ? faculty.google_scholar
        : `https://scholar.google.com/citations?user=${faculty.google_scholar}`,
    });
  }
  if (faculty.researchgate) {
    scholarLinks.push({
      label: "ResearchGate",
      href: faculty.researchgate.startsWith("http")
        ? faculty.researchgate
        : `https://www.researchgate.net/profile/${faculty.researchgate}`,
    });
  }
  if (faculty.website) scholarLinks.push({ label: "Website", href: faculty.website });

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <FacultyAvatar name={faculty.name} photoUrl={faculty.photo_url} size="lg" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">{faculty.name}</h2>
              {faculty.employment_type ? (
                <EmploymentTypeBadge type={faculty.employment_type} />
              ) : null}
              <ResearchStatusBadge status={faculty.status} />
            </div>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {[
                faculty.designation,
                faculty.department,
                faculty.school,
              ]
                .filter(Boolean)
                .join(" · ") || " "}
            </p>
            <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
              {[
                faculty.employee_id ? `Employee ID ${faculty.employee_id}` : null,
                faculty.faculty_code ? `Code ${faculty.faculty_code}` : null,
                faculty.joining_date ? `Joined ${formatDate(faculty.joining_date)}` : null,
                faculty.office ? `Office ${faculty.office}` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            {faculty.specialization ? (
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                <span className="font-medium text-[var(--text-secondary)]">Specialization: </span>
                {faculty.specialization}
              </p>
            ) : null}
            {scholarLinks.length > 0 ? (
              <p className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <Globe className="h-3.5 w-3.5 text-[var(--text-tertiary)]" aria-hidden="true" />
                {scholarLinks.map((link) => (
                  <a
                    key={link.label}
                    href={link.href}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-[var(--accent)] hover:underline"
                  >
                    {link.label}
                  </a>
                ))}
              </p>
            ) : null}
            {faculty.tags.length > 0 ? (
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                {faculty.tags.map((tag) => `#${tag}`).join(" ")}
              </p>
            ) : null}
          </div>
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
        ) : null}
      </div>
      {faculty.biography ? (
        <p className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-sm text-[var(--text-secondary)]">
          <span className="font-medium text-[var(--text-primary)]">Biography: </span>
          {faculty.biography}
        </p>
      ) : null}
    </div>
  );
}
