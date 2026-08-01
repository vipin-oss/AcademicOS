"use client";

import type { ObjectResponse, ObjectStatus } from "@/types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<ObjectStatus, string> = {
  draft: "bg-[var(--bg-hover)] text-[var(--text-secondary)]",
  active: "bg-[var(--accent-subtle)] text-[var(--success)]",
  archived: "bg-[var(--bg-hover)] text-[var(--warning)]",
  superseded: "bg-[var(--bg-hover)] text-[var(--text-tertiary)]",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function RecentObjectsTable({ objects }: { objects: ObjectResponse[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm">
      <div className="border-b border-[var(--border-subtle)] px-4 py-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Recent Objects</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-[var(--text-tertiary)]">
              <th className="px-4 py-3 font-medium">Title</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Created By</th>
              <th className="px-4 py-3 font-medium">Created At</th>
            </tr>
          </thead>
          <tbody>
            {objects.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--text-tertiary)]">
                  No objects yet.
                </td>
              </tr>
            ) : (
              objects.map((o) => (
                <tr key={o.id} className="border-t border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                  <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{o.title}</td>
                  <td className="px-4 py-3 capitalize text-[var(--text-secondary)]">{o.object_type}</td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                        STATUS_STYLES[o.status]
                      )}
                    >
                      {o.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">{o.created_by}</td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">{formatDate(o.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
