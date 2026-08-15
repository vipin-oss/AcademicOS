import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentPreview } from "./DocumentPreview";
import type { DocumentResponse } from "@/types";

/**
 * Pins the Sprint-3 M3 inline PDF preview: the component fetches the
 * document bytes with the authenticated client, renders them via an
 * object URL, revokes the URL on unmount, and degrades honestly for
 * non-PDFs and fetch failures. Downloads (M10 RC1) go through the
 * authenticated client too — a plain href would 401.
 */
vi.mock("@/lib/api/client", () => ({
  api: { getBlob: vi.fn() },
  toErrorMessage: (err: unknown, fallback: string) =>
    err instanceof Error ? err.message : fallback,
}));

import { api } from "@/lib/api/client";

const mockedGetBlob = vi.mocked(api.getBlob);

function pdfDocument(overrides: Partial<DocumentResponse> = {}): DocumentResponse {
  return {
    id: "obj:document:X",
    title: "paper.pdf",
    document_type: "pdf",
    tags: [],
    file_name: "paper.pdf",
    file_size: 1234,
    url: "http://localhost:8000/api/v1/documents/obj:document:X/download",
    ...overrides,
  } as DocumentResponse;
}

describe("DocumentPreview", () => {
  beforeEach(() => {
    // jsdom lacks createObjectURL/revokeObjectURL; assign the stubs
    // directly so they survive the RTL cleanup that unmounts components
    // after this file's afterEach.
    URL.createObjectURL = vi.fn(() => "blob:mock-preview") as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = vi.fn() as unknown as typeof URL.revokeObjectURL;
    mockedGetBlob.mockReset();
  });

  it("renders an inline iframe for PDFs once the blob is fetched", async () => {
    mockedGetBlob.mockResolvedValue(new Blob(["%PDF-1.7"], { type: "application/pdf" }));

    render(<DocumentPreview document={pdfDocument()} />);

    expect(mockedGetBlob).toHaveBeenCalledWith(
      "/documents/obj:document:X/download",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    const iframe = await screen.findByTitle("Preview of paper.pdf");
    expect(iframe).toBeInTheDocument();
    expect(iframe.getAttribute("src")).toBe("blob:mock-preview");
  });

  it("keeps the placeholder for non-PDF documents", () => {
    render(
      <DocumentPreview
        document={pdfDocument({ document_type: "docx", title: "notes.docx" })}
      />,
    );

    expect(mockedGetBlob).not.toHaveBeenCalled();
    expect(screen.getByText(/Preview is available for PDF documents/)).toBeInTheDocument();
    expect(screen.queryByTitle("Preview of notes.docx")).not.toBeInTheDocument();
  });

  it("shows the error and no iframe when the fetch fails", async () => {
    mockedGetBlob.mockRejectedValue(new Error("boom"));

    render(<DocumentPreview document={pdfDocument()} />);

    await waitFor(() => expect(screen.getByText("boom")).toBeInTheDocument());
    expect(screen.queryByTitle("Preview of paper.pdf")).not.toBeInTheDocument();
  });

  it("revokes the object URL on unmount", async () => {
    mockedGetBlob.mockResolvedValue(new Blob(["%PDF-1.7"], { type: "application/pdf" }));

    const { unmount } = render(<DocumentPreview document={pdfDocument()} />);
    await screen.findByTitle("Preview of paper.pdf");

    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-preview");
  });

  it("downloads through the authenticated client, never a raw href", async () => {
    mockedGetBlob.mockResolvedValue(new Blob(["%PDF-1.7"], { type: "application/pdf" }));

    render(<DocumentPreview document={pdfDocument()} />);
    await screen.findByTitle("Preview of paper.pdf");

    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    await waitFor(() =>
      expect(mockedGetBlob).toHaveBeenLastCalledWith(
        "/documents/obj:document:X/download",
      ),
    );
    // no unauthenticated anchor to the API URL survives
    expect(
      screen.queryByRole("link", { name: "Download" }),
    ).not.toBeInTheDocument();
  });

  it("surfaces a failed download instead of silently swallowing it", async () => {
    render(<DocumentPreview document={pdfDocument({ document_type: "docx" })} />);
    mockedGetBlob.mockRejectedValueOnce(new Error("download boom"));

    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("download boom"),
    );
  });
});
