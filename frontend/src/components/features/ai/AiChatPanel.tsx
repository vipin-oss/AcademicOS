"use client";

/**
 * Shared grounded-AI conversation panel — the single message/streaming/
 * error/citation implementation for the AI workspace's General and
 * domain-role modes (M26 consolidation).
 *
 * - General mode  -> POST /ai/chat/stream (conversation persistence)
 * - Role modes    -> POST /ai/assistants/{role}/stream
 *
 * Both endpoints share the server contract: `token` deltas followed by a
 * `completion` event carrying the verified answer + citations. The server
 * buffers tokens until generation is confirmed, so a stream without a
 * completion is a failure and the honest fallback is shown — never a
 * partial answer.
 *
 * Grounding, citations, permission filtering and the integrity guardrails
 * all live server-side; this component only renders what the pipeline
 * produces.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Send, Square } from "lucide-react";

import { streamAi } from "@/lib/api/ai";
import { ApiError, toErrorMessage } from "@/lib/api/client";
import type { AiCitation } from "@/types";

export interface AiMessage {
  role: "user" | "assistant";
  content: string;
  citations?: AiCitation[];
}

export type AiMode =
  | { type: "chat" }
  | { type: "role"; role: string };

const NOT_CONFIGURED_TEXT =
  "AI is not configured. Set up a provider in Settings → AI, or use the external handoff.";

// Shown when generation STARTED (provisional tokens arrived) but the stream
// failed before a verified completion — the partial preview is discarded and
// the failure is stated honestly instead of pretending it is final.
const GENERATION_FAILED_TEXT =
  "The AI response was interrupted before it could be completed. Please try again.";

export function AiChatPanel({
  mode,
  description,
}: {
  mode: AiMode;
  description: string;
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [draft, setDraft] = useState(""); // in-flight assistant text (streaming)
  const [streaming, setStreaming] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  // True streaming (Phase B): tracks whether any provisional token arrived,
  // so a failed completion can be reported as an interrupted generation
  // rather than "not configured".
  const sawTokensRef = useRef(false);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    // jsdom does not implement scrollIntoView — optional call keeps tests clean.
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  const send = useCallback(async () => {
    const msg = input.trim();
    if (!msg || streaming) return;
    setInput("");
    setError(null);

    const history = messages
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setDraft("");
    sawTokensRef.current = false;
    setStreaming(true);
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);

    const controller = new AbortController();
    abortRef.current = controller;

    const path = mode.type === "chat" ? "/ai/chat/stream" : `/ai/assistants/${mode.role}/stream`;
    const body =
      mode.type === "chat"
        ? { message: msg, history, conversation_id: conversationId }
        : { message: msg, history };

    try {
      await streamAi(
        path,
        body,
        {
          onToken: (delta) => {
            sawTokensRef.current = true;
            setDraft((prev) => prev + delta);
          },
          onCompletion: (data) => {
            const answer = typeof data.answer === "string" ? data.answer : "";
            const available = data.available !== false;
            const citations = Array.isArray(data.citations)
              ? (data.citations as AiCitation[])
              : undefined;
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: available
                  ? answer
                  : sawTokensRef.current
                    ? GENERATION_FAILED_TEXT
                    : NOT_CONFIGURED_TEXT,
                citations: available ? citations : undefined,
              },
            ]);
            sawTokensRef.current = false;
            setDraft("");
            if (mode.type === "chat") {
              const cid = data.conversation_id;
              if (typeof cid === "string" && cid) setConversationId(cid);
            }
          },
        },
        { signal: controller.signal },
      );
    } catch (err) {
      if (err instanceof ApiError && err.isAborted) return;
      if (err instanceof ApiError && err.status === 404) {
        setError(
          mode.type === "chat"
            ? "AI Chat is not enabled on the server. Add AI_CHAT_ENABLED=true to the backend .env file and restart the backend."
            : "Domain assistants are not enabled on the server. Add AI_ASSISTANTS_ENABLED=true to the backend .env file and restart the backend.",
        );
      } else if (err instanceof ApiError && err.isTimeout) {
        setError(
          "The AI model is taking too long to respond. Local models (Ollama) may need more time — please wait or try a shorter question.",
        );
      } else if (err instanceof ApiError && err.isNetwork) {
        setError("Cannot reach the backend server. Make sure the backend is running on port 8000.");
      } else {
        setError(toErrorMessage(err, "The assistant could not respond. Please try again."));
      }
    } finally {
      setStreaming(false);
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [input, streaming, messages, mode, conversationId]);

  return (
    <div className="flex h-[calc(100vh-16rem)] min-h-[24rem] flex-col rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 py-8 text-center">
            <p className="text-sm text-[var(--text-tertiary)]">{description}</p>
            <p className="text-xs text-[var(--text-tertiary)]">
              Answers are grounded in your readable documents with citations.
            </p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "text-right" : ""}>
              <span
                className={`inline-block max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                  m.role === "user"
                    ? "bg-[var(--accent-subtle)] text-[var(--text-primary)]"
                    : "bg-[var(--bg-hover)] text-[var(--text-primary)]"
                }`}
              >
                {m.content}
              </span>
              {m.citations && m.citations.length > 0 ? (
                <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                  Sources: {m.citations.map((c) => `[${c.number}] ${c.title}`).join(", ")}
                </p>
              ) : null}
            </div>
          ))
        )}
        {streaming && draft ? (
          <div className="text-left">
            <span className="inline-block max-w-[85%] rounded-lg bg-[var(--bg-hover)] px-3 py-2 text-sm text-[var(--text-primary)]">
              {draft}
            </span>
          </div>
        ) : null}
        {streaming ? (
          <div className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking… {elapsed > 0 ? `${elapsed}s` : ""}
          </div>
        ) : null}
        {error ? <p className="text-sm text-[var(--text-danger)]">{error}</p> : null}
        <div ref={endRef} />
      </div>

      <div className="flex gap-2 border-t border-[var(--border-subtle)] p-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Ask about your documents…"
          disabled={streaming}
          className="flex-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-4 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none disabled:opacity-50"
        />
        {streaming ? (
          <button
            type="button"
            onClick={stop}
            aria-label="Stop generating"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--bg-hover)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:opacity-90"
          >
            <Square className="h-4 w-4" />
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={send}
            disabled={!input.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            Send
          </button>
        )}
      </div>
    </div>
  );
}
