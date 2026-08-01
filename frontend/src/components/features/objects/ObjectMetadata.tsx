import { DEPARTMENT_METADATA_KEY } from "@/lib/objects/constants";
import { titleCase } from "@/lib/utils";
import type { ObjectResponse } from "@/types";

/**
 * Read-only metadata view. `department` is pinned first because it is a
 * first-class field in the editor; everything else is alphabetical.
 */
export function ObjectMetadata({ object }: { object: ObjectResponse }) {
  const entries = Object.entries(object.metadata ?? {}).sort(([a], [b]) => {
    if (a === DEPARTMENT_METADATA_KEY) return -1;
    if (b === DEPARTMENT_METADATA_KEY) return 1;
    return a.localeCompare(b);
  });

  if (entries.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-[var(--border-strong)] px-3 py-4 text-sm text-[var(--text-tertiary)]">
        No metadata yet. Use <span className="font-medium">Edit</span> to add key/value pairs.
      </p>
    );
  }

  return (
    <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div
          key={key}
          className="min-w-0 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-3 py-2"
        >
          <dt className="truncate text-xs text-[var(--text-tertiary)]" title={key}>
            {titleCase(key)}
          </dt>
          <dd className="break-words text-sm text-[var(--text-primary)]">{value || "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
