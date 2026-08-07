import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AiSettingsView } from "./AiSettingsView";

/**
 * Pins the M11.1 AI Settings view: it renders the health surface
 * (status, default provider/model, provider catalogue, feature flags)
 * from the read-only AI endpoints, with honest loading/error states.
 */
vi.mock("@/lib/api/ai", () => ({
  getAiHealth: vi.fn(),
  getAiProviders: vi.fn(),
  getAiModels: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  toErrorMessage: (err: unknown, fallback: string) =>
    err instanceof Error ? err.message : fallback,
}));

import { getAiHealth, getAiModels, getAiProviders } from "@/lib/api/ai";
import type {
  AiHealth,
  AiModelsResponse,
  ListAiProvidersResponse,
} from "@/types";

const mockedHealth = vi.mocked(getAiHealth);
const mockedProviders = vi.mocked(getAiProviders);
const mockedModels = vi.mocked(getAiModels);

const NOT_CONFIGURED_HEALTH: AiHealth = {
  status: "not_configured",
  ai_enabled: true,
  default_provider: "local",
  default_model: "",
  default_provider_valid: true,
  providers_total: 5,
  providers_configured: 0,
  feature_flags: {
    chat: false,
    rag: false,
    memory: false,
    agents: false,
    document_understanding: false,
    streaming: true,
  },
  checked_at: "2026-08-07T00:00:00+00:00",
};

const PROVIDERS: ListAiProvidersResponse = {
  items: [
    {
      provider_id: "openai",
      display_name: "OpenAI",
      kind: "openai",
      status: "not_configured",
      configured: false,
      executable: false,
      operational: null,
      models: [{ provider_id: "oa", model_id: "gpt-4o-mini", display_name: "gpt-4o-mini", context_window: null, capabilities: [], configured: false }],
      detail: "not configured",
    },
    {
      provider_id: "local",
      display_name: "Local",
      kind: "local",
      status: "not_configured",
      configured: false,
      executable: false,
      operational: null,
      models: [],
      detail: "not configured",
    },
  ],
};

const MODELS: AiModelsResponse = {
  default_provider: "local",
  default_model: "",
  models: [
    { provider_id: "oa", model_id: "gpt-4o-mini", display_name: "gpt-4o-mini", context_window: null, capabilities: [], configured: false },
  ],
};

describe("AiSettingsView", () => {
  beforeEach(() => {
    mockedHealth.mockReset();
    mockedProviders.mockReset();
    mockedModels.mockReset();
  });

  it("renders the health banner with the not-configured status", async () => {
    mockedHealth.mockResolvedValue(NOT_CONFIGURED_HEALTH);
    mockedProviders.mockResolvedValue(PROVIDERS);
    mockedModels.mockResolvedValue(MODELS);

    render(<AiSettingsView />);

    expect(await screen.findByText("Not configured — no adapter is wired yet")).toBeInTheDocument();
    // The default provider appears in the health banner and again as the
    // catalogue row — assert the banner value specifically.
    const banner = screen.getByLabelText("AI health");
    expect(within(banner).getByText("local")).toBeInTheDocument();
    expect(within(banner).getByText("0 / 5 configured")).toBeInTheDocument();
  });

  it("lists every available provider with its status", async () => {
    mockedHealth.mockResolvedValue(NOT_CONFIGURED_HEALTH);
    mockedProviders.mockResolvedValue(PROVIDERS);
    mockedModels.mockResolvedValue(MODELS);

    render(<AiSettingsView />);

    const providersSection = await screen.findByLabelText("AI providers");
    expect(within(providersSection).getByText("OpenAI")).toBeInTheDocument();
    expect(within(providersSection).getByText("Local")).toBeInTheDocument();
    expect(within(providersSection).getAllByText("Not configured")).toHaveLength(2);
  });

  it("shows declared models and marks them not usable", async () => {
    mockedHealth.mockResolvedValue(NOT_CONFIGURED_HEALTH);
    mockedProviders.mockResolvedValue(PROVIDERS);
    mockedModels.mockResolvedValue(MODELS);

    render(<AiSettingsView />);

    const modelsSection = await screen.findByLabelText("AI models");
    expect(within(modelsSection).getByText("gpt-4o-mini")).toBeInTheDocument();
    expect(within(modelsSection).getByText("Declared — not usable yet")).toBeInTheDocument();
  });

  it("surfaces the feature-flag state", async () => {
    mockedHealth.mockResolvedValue(NOT_CONFIGURED_HEALTH);
    mockedProviders.mockResolvedValue(PROVIDERS);
    mockedModels.mockResolvedValue(MODELS);

    render(<AiSettingsView />);

    expect(await screen.findByText("RAG retrieval: off")).toBeInTheDocument();
    expect(screen.getByText("Streaming: on")).toBeInTheDocument();
  });

  it("shows a helpful error when the health endpoint fails", async () => {
    mockedHealth.mockRejectedValue(new Error("boom"));
    mockedProviders.mockResolvedValue(PROVIDERS);
    mockedModels.mockResolvedValue(MODELS);

    render(<AiSettingsView />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("boom"));
  });
});
