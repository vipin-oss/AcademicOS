"use client";

/**
 * Conversation thread: user bubbles on the right, assistant messages rendered
 * through the deterministic AnswerCard contract. Auto-scrolls to the newest
 * message; shows a local "thinking" indicator while a question is in flight.
 */
import { useEffect, useRef } from "react";

import { Bot, User } from "lucide-react";

import { AssistantAnswerCard } from "./AssistantAnswerCard";
import type { AssistantMessage } from "@/types";

function formatStamp(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function MessageThread({
  messages,
  sending,
}: {
  messages: AssistantMessage[];
  sending: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, sending]);

  return (
    <ol aria-label="Message thread" className="space-y-4">
      {messages.map((message) =>
        message.role === "user" ? (
          <li key={message.seq} className="flex justify-end">
            <div className="max-w-[85%] rounded-xl rounded-br-sm border border-[var(--accent)] bg-[var(--accent)] px-4 py-2.5 text-sm text-white">
              <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-wide opacity-80">
                <User className="h-3 w-3" /> You · {formatStamp(message.created_at)}
              </div>
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          </li>
        ) : (
          <li key={message.seq} className="flex justify-start">
            <div className="w-full max-w-[95%] space-y-1">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                <Bot className="h-3 w-3" /> AcademicOS Intelligence ·{" "}
                {formatStamp(message.created_at)}
              </div>
              {message.answer ? (
                <AssistantAnswerCard answer={message.answer} />
              ) : (
                <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-2.5 text-sm text-[var(--text-primary)]">
                  {message.content}
                </div>
              )}
            </div>
          </li>
        ),
      )}
      {sending ? (
        <li aria-label="Assistant thinking" className="flex items-center gap-2 pl-1 text-sm text-[var(--text-tertiary)]">
          <Bot className="h-3.5 w-3.5 animate-pulse" /> Thinking…
        </li>
      ) : null}
      <div ref={bottomRef} />
    </ol>
  );
}
