"use client";

import Link from "next/link";
import { Users } from "lucide-react";
import { Spinner } from "@/components/features/objects/Spinner";
import { useObjectClasses } from "@/hooks/useObjectClasses";
import { ClassStatusBadge } from "./TeachingBadges";
import { classLine } from "@/lib/teaching/constants";

/**
 * The object lens for classes — "classes this Student is enrolled in" (on a
 * student detail page) and "classes this Faculty member teaches" (on a
 * faculty object). One backend edge query serves both. Mirrors
 * `ObjectStudents` / `ObjectPublications`.
 */
export function ObjectClasses({ objectId }: { objectId: string }) {
  const { classes, loading, error } = useObjectClasses(objectId);

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
        <Spinner className="h-4 w-4" /> Loading classes…
      </p>
    );
  }
  if (error) {
    return <p className="text-sm text-[var(--danger)]">{error}</p>;
  }
  if (classes.length === 0) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">
        No classes are linked to this object yet.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-[var(--border-subtle)]">
      {classes.map((cls) => (
        <li key={cls.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
          <div className="min-w-0">
            <Link
              href={`/teaching/classes/${encodeURIComponent(cls.id)}`}
              className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
            >
              {cls.title}
            </Link>
            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-[var(--text-tertiary)]">
              <span>{classLine(cls) || "—"}</span>
              <span className="inline-flex items-center gap-1">
                <Users className="h-3 w-3" aria-hidden="true" />
                {cls.student_count} student{cls.student_count === 1 ? "" : "s"}
              </span>
            </p>
          </div>
          <ClassStatusBadge status={cls.status} />
        </li>
      ))}
    </ul>
  );
}
