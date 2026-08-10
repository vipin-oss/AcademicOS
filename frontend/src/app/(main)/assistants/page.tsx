"use client";

import { useState, useCallback, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { getAssistantRoles, queryAssistant } from "@/lib/api/ai";
import type { AssistantRole } from "@/types";
import { toErrorMessage, ApiError } from "@/lib/api/client";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Array<{ number: number; title: string }>;
}

const ROLE_FALLBACK: AssistantRole[] = [
  { key: "research", display_name: "Research Assistant", description: "Literature review, gap analysis, hypothesis framing (F18)." },
  { key: "teaching", display_name: "Teaching Assistant", description: "Lesson plans, explanations, quiz items, draft feedback (F19)." },
  { key: "publication", display_name: "Publication Assistant", description: "Drafting, restructuring, caption and reference checks (F20)." },
  { key: "administration", display_name: "Administrative Assistant", description: "Draft schedules, compliance notes, grant reports (F21)." },
];

export default function AssistantsPage() {
  const [roles, setRoles] = useState<AssistantRole[]>(ROLE_FALLBACK);
  const [role, setRole] = useState<string>("research");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load the role catalogue once (auth-required; falls back to the static list
  // if the endpoint is unreachable so the page still renders).
  useEffect(() => {
    let cancelled = false;
    getAssistantRoles()
      .then((items) => {
        if (!cancelled && items.length > 0) setRoles(items);
      })
      .catch(() => {
        /* keep ROLE_FALLBACK */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const send = useCallback(async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    setError(null);
    setLoading(true);
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: msg }]);

    try {
      const res = await queryAssistant(role, { message: msg, history });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.available
            ? res.answer
            : "AI is not configured. Set up a provider in Settings → AI, or use the external handoff.",
          citations: res.citations?.map((c) => ({ number: c.number, title: c.title })),
        },
      ]);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.isTimeout) {
          setError("The AI model is taking too long to respond. Local models (Ollama) may need more time — please wait or try a shorter question.");
        } else if (err.status === 404) {
          setError("Domain assistants are not enabled on the server. Add AI_ASSISTANTS_ENABLED=true to the backend .env file and restart the backend.");
        } else if (err.isNetwork) {
          setError("Cannot reach the backend server. Make sure the backend is running on port 8000.");
        } else {
          setError(err.message);
        }
      } else {
        setError(toErrorMessage(err, "The assistant could not respond. Please try again."));
      }
    } finally {
      setLoading(false);
    }
  }, [input, loading, role, messages]);

  // Switching role starts a fresh conversation.
  const changeRole = useCallback((next: string) => {
    setRole(next);
    setMessages([]);
    setError(null);
  }, []);

  const active = roles.find((r) => r.key === role) ?? roles[0];

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-3xl flex-col px-4 py-6">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Domain Assistants</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Role-specialized help grounded in your documents (F18–F21).
        </p>
      </header>

      <div className="mb-4 flex flex-wrap gap-2">
        {roles.map((r) => (
          <button
            key={r.key}
            type="button"
            onClick={() => changeRole(r.key)}
            title={r.description}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              r.key === role
                ? "border-[var(--accent)] bg-[var(--accent)] text-white"
                : "border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
            }`}
          >
            {r.display_name}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
        {messages.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--text-tertiary)]">
            {active?.display_name}: {active?.description} Ask anything to begin.
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
        {error ? <p className="text-sm text-[var(--text-danger)]">{error}</p> : null}
      </div>

      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={`Ask the ${active?.display_name ?? "assistant"}…`}
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
