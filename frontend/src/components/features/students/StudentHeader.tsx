import type { ReactNode } from "react";
import { GraduationCap, Mail, Phone, Upload } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { programmeLine, studentTypeLabel } from "@/lib/students/constants";
import { DocumentVersionBadge } from "@/components/features/documents/DocumentBadge";
import { StudentStatusBadge, StudentTypeBadge } from "./StudentBadge";
import type { StudentResponse } from "@/types";

/** Detail-page header (mirrors PublicationHeader, GraduationCap icon). */
export function StudentHeader({
  student,
  actions,
}: {
  student: StudentResponse;
  actions?: ReactNode;
}) {
  const line = programmeLine(student);

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          <GraduationCap
            className="mt-1 h-11 w-11 shrink-0 rounded-lg bg-[var(--accent-subtle)] p-2.5 text-[var(--accent)]"
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <h1 className="break-words text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">
              {student.name}
            </h1>
            <p className="mt-1.5 text-sm text-[var(--text-secondary)]">
              {[student.roll_number, line || null, student.batch ? `Batch ${student.batch}` : null]
                .filter(Boolean)
                .join(" · ") || studentTypeLabel(student.student_type)}
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StudentStatusBadge status={student.status} />
              <StudentTypeBadge type={student.student_type} />
              <DocumentVersionBadge version={student.version} />
            </div>

            <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-[var(--text-secondary)]">
              {student.email ? (
                <div className="flex items-center gap-1.5">
                  <Mail className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                  <dt className="sr-only">Email</dt>
                  <dd className="break-all">{student.email}</dd>
                </div>
              ) : null}
              {student.phone ? (
                <div className="flex items-center gap-1.5">
                  <Phone className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                  <dt className="sr-only">Phone</dt>
                  <dd>{student.phone}</dd>
                </div>
              ) : null}
              <div className="flex items-center gap-1.5">
                <Upload className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                <dt className="sr-only">Added by / at</dt>
                <dd>
                  {student.uploaded_by || "—"} · {formatDate(student.created_at)}
                </dd>
              </div>
            </dl>

            <p className="mt-2 break-all font-mono text-xs text-[var(--text-tertiary)]">
              {student.id}
            </p>
          </div>
        </div>

        {actions ? (
          <div className="flex flex-wrap gap-2 lg:justify-end">{actions}</div>
        ) : null}
      </div>
    </div>
  );
}
