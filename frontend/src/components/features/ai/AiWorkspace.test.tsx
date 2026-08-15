import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AiWorkspace } from "./AiWorkspace";

/**
 * Reconciliation-pass tests: the Academic AI workspace exposes exactly the
 * five user-facing modes (General + the four domain roles). No speculative
 * tabs (no "Data Assistant", no "Labs" — the deterministic assistant keeps
 * its own workspace at /assistant, linked from here), one shared streaming
 * panel with token accumulation, citations and the honest not-configured
 * fallback.
 */

vi.mock("@/lib/api/ai", () => ({
  streamAi: vi.fn(),
}));

vi.mock("@/components/features/objects/Breadcrumbs", () => ({
  Breadcrumbs: () => <nav aria-label="Breadcrumb" />,
}));

vi.mock("@/components/layout/Sidebar", () => ({
  Sidebar: () => <aside data-testid="sidebar" />,
}));

vi.mock("@/components/layout/TopHeader", () => ({
  TopHeader: () => <header data-testid="topheader" />,
}));

import { streamAi } from "@/lib/api/ai";

describe("AiWorkspace", () => {
  beforeEach(() => {
    vi.mocked(streamAi).mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders exactly the five user-facing modes", () => {
    render(<AiWorkspace />);
    const tabs = screen
      .getAllByRole("tab")
      .map((t) => t.textContent?.trim())
      .filter(Boolean);
    expect(tabs).toEqual([
      "General",
      "Research",
      "Teaching",
      "Publication",
      "Administration",
    ]);
  });

  it("does not expose speculative tabs (no Data Assistant / Labs)", () => {
    render(<AiWorkspace />);
    expect(screen.queryByRole("tab", { name: "Data Assistant" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Labs" })).toBeNull();
  });

  it("links to the preserved deterministic assistant workspace", () => {
    render(<AiWorkspace />);
    const link = screen.getByRole("link", { name: /Deterministic Assistant/ });
    expect(link.getAttribute("href")).toBe("/assistant");
  });

  it("streams a general chat turn: tokens accumulate, completion renders answer + citations", async () => {
    vi.mocked(streamAi).mockImplementation(async (_path, _body, handlers) => {
      handlers.onToken?.("Hel");
      handlers.onToken?.("lo!");
      handlers.onCompletion?.({
        answer: "Hello!",
        available: true,
        citations: [{ number: 1, title: "Quantum Physics 101" }],
      });
    });

    render(<AiWorkspace initialMode="general" />);
    fireEvent.change(screen.getByPlaceholderText("Ask about your documents…"), {
      target: { value: "are you working" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("Hello!")).toBeTruthy();
    });
    expect(screen.getByText(/Sources: \[1\] Quantum Physics 101/)).toBeTruthy();
    const [path, body] = vi.mocked(streamAi).mock.calls[0];
    expect(path).toBe("/ai/chat/stream");
    expect(body).toMatchObject({ message: "are you working" });
  });

  it("routes role modes to the domain-assistant stream endpoint", async () => {
    vi.mocked(streamAi).mockImplementation(async (_path, _body, handlers) => {
      handlers.onCompletion?.({ answer: "draft plan", available: true });
    });

    render(<AiWorkspace initialMode="research" />);
    fireEvent.change(screen.getByPlaceholderText("Ask about your documents…"), {
      target: { value: "propose a hypothesis" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("draft plan")).toBeTruthy();
    });
    const [path] = vi.mocked(streamAi).mock.calls[0];
    expect(path).toBe("/ai/assistants/research/stream");
  });

  it("shows the honest not-configured fallback when completion reports unavailable", async () => {
    vi.mocked(streamAi).mockImplementation(async (_path, _body, handlers) => {
      handlers.onCompletion?.({
        answer: "",
        available: false,
        unavailable_reason: "not_configured",
      });
    });

    render(<AiWorkspace initialMode="general" />);
    fireEvent.change(screen.getByPlaceholderText("Ask about your documents…"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText(/AI is not configured/)).toBeTruthy();
    });
  });

  it("shows the provider-unreachable message instead of 'not configured'", async () => {
    vi.mocked(streamAi).mockImplementation(async (_path, _body, handlers) => {
      handlers.onCompletion?.({
        answer: "The configured AI provider is unreachable.",
        available: false,
        unavailable_reason: "provider_unreachable",
      });
    });

    render(<AiWorkspace initialMode="general" />);
    fireEvent.change(screen.getByPlaceholderText("Ask about your documents…"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText(/AI provider is unreachable/)).toBeTruthy();
    });
    // must NOT claim the provider is unconfigured
    expect(screen.queryByText(/AI is not configured/)).toBeNull();
  });
});
