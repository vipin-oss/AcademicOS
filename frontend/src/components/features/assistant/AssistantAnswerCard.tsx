"use client";

/**
 * Renderer for the deterministic answer contract: the plain-language summary,
 * the KPI metric chips, flat item lists, the linked context-card grid (PART 4)
 * and the suggested actions (PART 5) — every card/action links back into the
 * frozen module it came from (no module UI is re-implemented here).
 */
import Link from "next/link";

import { ArrowRight, ExternalLink } from "lucide-react";

import { typeLabel } from "@/lib/assistant/constants";
import type { AssistantAnswer } from "@/types";

const CHIP_CLASS =
  "rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface-2)] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-[var(--text-tertiary)]";

export function AssistantAnswerCard({ answer }: { answer: AssistantAnswer }) {
  const metrics = Object.entries(answer.metrics ?? {});
  return (
    <article
      aria-label="Assistant answer"
      className="space-y-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={CHIP_CLASS}>{answer.intent_label}</span>
        {answer.sources.length > 0 ? (
          <span className="text-[11px] text-[var(--text-tertiary)]">
            Sources: {answer.sources.join(", ").replace(/_/g, " ")}
          </span>
        ) : null}
      </div>

      <p className="text-sm leading-relaxed text-[var(--text-primary)]">{answer.summary}</p>

      {metrics.length > 0 ? (
        <dl aria-label="Answer metrics" className="flex flex-wrap gap-2">
          {metrics.map(([label, value]) => (
            <div
              key={label}
              className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-1.5"
            >
              <dt className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                {label}
              </dt>
              <dd className="text-sm font-semibold text-[var(--text-primary)]">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {answer.items.length > 0 ? (
        <ul aria-label="Answer items" className="space-y-1.5">
          {answer.items.map((item, index) => (
            <li key={`${item.title}-${index}`} className="text-sm">
              {item.href ? (
                <Link
                  href={item.href}
                  className="font-medium text-[var(--accent)] underline-offset-2 hover:underline"
                >
                  {item.title}
                </Link>
              ) : (
                <span className="font-medium text-[var(--text-primary)]">{item.title}</span>
              )}
              {item.subtitle ? (
                <span className="ml-2 text-xs text-[var(--text-secondary)]">{item.subtitle}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {answer.cards.length > 0 ? (
        <div
          aria-label="Context cards"
          className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3"
        >
          {answer.cards.map((card) => (
            <Link
              key={`${card.object_type}:${card.object_id}:${card.title}`}
              href={card.href}
              aria-label={`Open ${typeLabel(card.object_type)}: ${card.title}`}
              className="group flex flex-col gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] p-3 hover:border-[var(--accent)] hover:bg-[var(--bg-hover)]"
            >
              <div className="flex items-center justify-between gap-2">
                <span className={CHIP_CLASS}>
                  {card.badge ? `${card.badge}` : typeLabel(card.object_type)}
                </span>
                <ExternalLink className="h-3.5 w-3.5 text-[var(--text-tertiary)] opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
              <p className="text-sm font-medium text-[var(--text-primary)]">{card.title}</p>
              {card.subtitle ? (
                <p className="text-xs text-[var(--text-secondary)]">{card.subtitle}</p>
              ) : null}
              {Object.keys(card.stats ?? {}).length > 0 ? (
                <p className="text-[11px] text-[var(--text-tertiary)]">
                  {Object.entries(card.stats)
                    .filter(([, value]) => value)
                    .map(([key, value]) => `${key}: ${value}`)
                    .join(" · ")}
                </p>
              ) : null}
            </Link>
          ))}
        </div>
      ) : null}

      {answer.actions.length > 0 ? (
        <div aria-label="Suggested actions" className="flex flex-wrap gap-2 pt-1">
          {answer.actions.map((action) => (
            <Link
              key={`${action.href}:${action.label}`}
              href={action.href}
              aria-label={`Action: ${action.label}`}
              className={
                action.kind === "module"
                  ? "inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:bg-[var(--accent-hover)]"
                  : "inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
              }
            >
              {action.label}
              <ArrowRight className="h-3 w-3" />
            </Link>
          ))}
        </div>
      ) : null}
    </article>
  );
}
