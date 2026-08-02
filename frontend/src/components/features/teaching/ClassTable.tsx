"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Users } from "lucide-react";
import { classLine } from "@/lib/teaching/constants";
import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ClassStatusBadge } from "./TeachingBadges";
import type { ClassResponse } from "@/types";

function ClassRow({ cls }: { cls: ClassResponse }) {
  const router = useRouter();
  const href = `/teaching/classes/${encodeURIComponent(cls.id)}`;

  return (
    <tr
      onClick={() => router.push(href)}
      className="cursor-pointer border-b border-[var(--border-subtle)] transition-colors last:border-b-0 hover:bg-[var(--bg-hover)]"
    >
      <td className="px-4 py-3">
        <Link
          href={href}
          onClick={(event) => event.stopPropagation()}
          className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
        >
          {cls.title}
        </Link>
        <div className="mt-0.5 text-xs text-[var(--text-tertiary)]">{classLine(cls) || "—"}</div>
      </td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        {cls.links.teachers.length > 0
          ? cls.links.teachers.map((teacher) => teacher.title).join(", ")
          : "—"}
      </td>
      <td className="px-4 py-3">
        <span className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)]">
          <Users className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
          {cls.student_count}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        {cls.class_mode ?? "—"}
      </td>
      <td className="px-4 py-3">
        <ClassStatusBadge status={cls.status} />
      </td>
    </tr>
  );
}

/** The classes table (PART B). Mirrors StudentTable structure. */
export function ClassTable({
  classes,
  loading = false,
}: {
  classes: ClassResponse[];
  loading?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[760px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Class</th>
            <th scope="col" className="px-4 py-3 font-medium">Teacher(s)</th>
            <th scope="col" className="px-4 py-3 font-medium">Students</th>
            <th scope="col" className="px-4 py-3 font-medium">Mode</th>
            <th scope="col" className="px-4 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <TableSkeleton rows={6} cols={5} />
          ) : (
            classes.map((cls) => (
              <ClassRow key={cls.id} cls={cls} />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
