import { PROFILE_SECTIONS } from "@/lib/faculty/constants";
import type { FacultyResponse, FacultySectionEntry } from "@/types";

function entryLine(entry: FacultySectionEntry, sectionKey: string): string {
  if (sectionKey === "degrees") {
    return [entry.degree, entry.institution && `— ${entry.institution}`, entry.year && `(${entry.year})`]
      .filter(Boolean)
      .join(" ");
  }
  if (sectionKey === "experience") {
    const span = [entry.from, entry.to].filter(Boolean).join(" – ");
    return [entry.role, entry.organization && `at ${entry.organization}`, span && `(${span})`, entry.note]
      .filter(Boolean)
      .join(" ");
  }
  if (sectionKey === "awards") {
    return [entry.title, entry.year && `(${entry.year})`, entry.by && `— ${entry.by}`]
      .filter(Boolean)
      .join(" ");
  }
  if (sectionKey === "memberships") {
    return [entry.body, entry.year && `(since ${entry.year})`, entry.note]
      .filter(Boolean)
      .join(" ");
  }
  if (sectionKey === "certifications") {
    return [entry.title, entry.issuer && `— ${entry.issuer}`, entry.year && `(${entry.year})`]
      .filter(Boolean)
      .join(" ");
  }
  // admin_positions
  const span = [entry.from, entry.to].filter(Boolean).join(" – ");
  return [entry.position, entry.unit && `— ${entry.unit}`, span && `(${span})`]
    .filter(Boolean)
    .join(" ");
}

/**
 * PART 2 academic profile: the six sections (degrees, experience, awards,
 * memberships, certifications, administrative positions) rendered from the
 * frozen PROFILE_SECTIONS config — one generic renderer, no per-section copy.
 */
export function AcademicProfilePanel({ faculty }: { faculty: FacultyResponse }) {
  const filled = PROFILE_SECTIONS.filter(
    (section) => (faculty[section.key] ?? []).length > 0,
  );
  return (
    <section
      aria-label="Academic profile"
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5"
    >
      <h2 className="text-sm font-semibold text-[var(--text-primary)]">Academic Profile</h2>
      {filled.length === 0 ? (
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">
          No profile entries yet — edit the faculty record to add degrees, experience, awards,
          memberships, certifications and administrative positions.
        </p>
      ) : (
        <dl className="mt-2 space-y-3">
          {filled.map((section) => (
            <div key={section.key}>
              <dt className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
                {section.label}
              </dt>
              <dd className="mt-1">
                <ul className="list-disc space-y-0.5 pl-5 text-sm text-[var(--text-secondary)]">
                  {(faculty[section.key] ?? []).map((entry, index) => (
                    <li key={index}>{entryLine(entry, section.key)}</li>
                  ))}
                </ul>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
