"use client";

import { useState, useCallback } from "react";
import { Send, Loader2 } from "lucide-react";
import { aiChat } from "@/lib/api/ai";
import type { AiChatResponse } from "@/types";
import { toErrorMessage } from "@/lib/api/client";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Array<{ number: number; title: string }>;
}

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const send = useCallback(async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: msg }]);

    try {
      const res: AiChatResponse = await aiChat({
        message: msg,
        conversation_id: conversationId,
      });
      if (res.conversation_id) setConversationId(res.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.available
            ? res.answer
            : "AI is not configured. Set up a provider in Settings → AI, or use the external handoff.",
          citations: res.citations?.map((c: { number: number; title: string }) => ({ number: c.number, title: c.title })),
        },
      ]);
    } catch (err) {
      const status = (err as { status?: number }).status;
      if (status === 404) {
        setError(
          "AI Chat is not enabled on the server. Add AI_CHAT_ENABLED=true to the backend .env file and restart the backend.",
        );
      } else {
        setError(toErrorMessage(err, "Chat failed. Please try again."));
      }
    } finally {
      setLoading(false);
    }
  }, [input, loading, conversationId]);

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-3xl flex-col px-4 py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">AI Chat</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Ask questions grounded in your documents.
        </p>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
        {messages.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--text-tertiary)]">
            Type a message to start chatting with your knowledge base.
          </p>
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
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-[var(--text-tertiary)]">
            <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
          </div>
        ) : null}
        {error ? (
          <p className="text-sm text-[var(--text-danger)]">{error}</p>
        ) : null}
      </div>

      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about your documents…"
          disabled={loading}
          className="flex-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-4 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none disabled:opacity-50"
        />
        <button
          type="button"
          onClick={send}
          disabled={loading || !input.trim()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          Send
        </button>
      </div>
    </div>
  );
}
