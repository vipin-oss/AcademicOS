"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Mail } from "lucide-react";
import { programmeLine } from "@/lib/students/constants";
import { StudentStatusBadge, StudentTypeBadge } from "./StudentBadge";
import type { StudentResponse } from "@/types";

/**
 * One registry row. The id is encoded EXACTLY ONCE here (the encoding
 * contract: ids travel decoded everywhere else).
 */
export function StudentRow({ student }: { student: StudentResponse }) {
  const router = useRouter();
  const href = `/students/${encodeURIComponent(student.id)}`;

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
          {student.name}
        </Link>
        <div className="mt-0.5 text-xs text-[var(--text-tertiary)]">
          {student.roll_number ?? "—"}
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        <div>{programmeLine(student) || "—"}</div>
        {student.email ? (
          <div className="mt-0.5 flex items-center gap-1 text-xs text-[var(--text-tertiary)]">
            <Mail className="h-3 w-3" aria-hidden="true" />
            {student.email}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        {student.batch ?? "—"}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1.5">
          <StudentTypeBadge type={student.student_type} />
          <StudentStatusBadge status={student.status} />
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        {student.semester != null ? `Sem ${student.semester}` : "—"}
      </td>
    </tr>
  );
}
