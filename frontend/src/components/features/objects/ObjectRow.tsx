"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { KeyboardEvent } from "react";
import { formatDate, titleCase } from "@/lib/utils";
import type { ObjectResponse } from "@/types";
import { ObjectBadge } from "./ObjectBadge";

export function ObjectRow({ object }: { object: ObjectResponse }) {
  const router = useRouter();

  // The ONLY place the object id is encoded. `obj:course:AB12` -> `obj%3A…`,
  // which Next.js hands back to the detail page, where it is decoded once.
  const href = `/objects/${encodeURIComponent(object.id)}`;

  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      router.push(href);
    }
  };

  return (
    <tr
      role="link"
      tabIndex={0}
      aria-label={`Open ${object.title}`}
      onClick={() => router.push(href)}
      onKeyDown={onKeyDown}
      className="cursor-pointer border-t border-[var(--border-subtle)] transition-colors hover:bg-[var(--bg-hover)] focus:bg-[var(--bg-hover)] focus:outline-none"
    >
      <td className="max-w-[220px] px-4 py-3 font-medium text-[var(--text-primary)] sm:max-w-none">
        <Link
          href={href}
          onClick={(event) => event.stopPropagation()}
          className="block truncate hover:text-[var(--accent)] hover:underline"
          title={object.title}
        >
          {object.title}
        </Link>
        {/* Compact secondary line for small screens where columns are hidden. */}
        <span className="mt-0.5 block truncate text-xs text-[var(--text-tertiary)] sm:hidden">
          {titleCase(object.object_type)} · {object.created_by || "—"}
        </span>
      </td>
      <td className="hidden px-4 py-3 text-[var(--text-secondary)] sm:table-cell">
        {titleCase(object.object_type)}
      </td>
      <td className="px-4 py-3">
        <ObjectBadge status={object.status} />
      </td>
      <td className="hidden max-w-[180px] truncate px-4 py-3 text-[var(--text-secondary)] md:table-cell">
        {object.created_by || "—"}
      </td>
      <td className="hidden whitespace-nowrap px-4 py-3 text-[var(--text-secondary)] lg:table-cell">
        {formatDate(object.created_at)}
      </td>
    </tr>
  );
}
