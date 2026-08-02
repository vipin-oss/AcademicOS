"use client";

import { TableSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { StudentRow } from "./StudentRow";
import type { StudentResponse } from "@/types";

/** The registry table (mirrors PublicationTable structure). */
export function StudentTable({
  students,
  loading = false,
}: {
  students: StudentResponse[];
  loading?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <table className="w-full min-w-[760px] border-collapse text-left" aria-busy={loading}>
        <thead>
          <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th scope="col" className="px-4 py-3 font-medium">Student</th>
            <th scope="col" className="px-4 py-3 font-medium">Programme</th>
            <th scope="col" className="px-4 py-3 font-medium">Batch</th>
            <th scope="col" className="px-4 py-3 font-medium">Type / Status</th>
            <th scope="col" className="px-4 py-3 font-medium">Semester</th>
          </tr>
        </thead>
        <tbody>
          {/* TableSkeleton emits bare <tr>s — valid only inside <tbody>. */}
          {loading ? (
            <TableSkeleton rows={6} cols={5} />
          ) : (
            students.map((student) => (
              <StudentRow key={student.id} student={student} />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
