"use client";

import { Archive, CheckCircle2, FilePenLine, Library } from "lucide-react";

interface SummaryCardsProps {
  total: number;
  draft: number;
  active: number;
  archived: number;
}

const CARDS = [
  { key: "total", label: "Total Objects", icon: Library, tint: "text-[var(--accent)] bg-[var(--accent-subtle)]" },
  { key: "draft", label: "Draft Objects", icon: FilePenLine, tint: "text-[var(--text-secondary)] bg-[var(--bg-hover)]" },
  { key: "active", label: "Active Objects", icon: CheckCircle2, tint: "text-[var(--success)] bg-[var(--accent-subtle)]" },
  { key: "archived", label: "Archived Objects", icon: Archive, tint: "text-[var(--warning)] bg-[var(--bg-hover)]" },
] as const;

export function SummaryCards({ total, draft, active, archived }: SummaryCardsProps) {
  const values: Record<string, number> = { total, draft, active, archived };
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {CARDS.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.key}
            className="flex items-center justify-between rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm"
          >
            <div>
              <p className="text-sm text-[var(--text-secondary)]">{card.label}</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--text-primary)]">{values[card.key]}</p>
            </div>
            <div className={`flex h-11 w-11 items-center justify-center rounded-lg ${card.tint}`}>
              <Icon className="h-5 w-5" />
            </div>
          </div>
        );
      })}
    </div>
  );
}
