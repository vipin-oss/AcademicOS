/** Document viewer type dispatch tests (Sprint M10). */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/annotations", () => ({
  listAnnotations: vi.fn().mockResolvedValue({ items: [] }),
}));
vi.mock("next/dynamic", () => ({ __esModule: true, default: () => null }));

import { DocumentViewer } from "./DocumentViewer";

const base = {
  id: "obj:document:1",
  title: "file",
  file_name: "file",
  file_size: 10,
  mime_type: "application/octet-stream",
  status: "active",
  version: 1,
  uploaded_by: "u",
  created_at: "2026-08-07T00:00:00+00:00",
  tags: [],
};

describe("DocumentViewer type dispatch", () => {
  it("renders the image viewer for png", () => {
    render(<DocumentViewer document={{ ...base, document_type: "png" } as never} />);
    expect(screen.getByText(/Loading image/)).toBeInTheDocument();
  });

  it("renders the office preview for docx", () => {
    render(<DocumentViewer document={{ ...base, document_type: "docx" } as never} />);
    expect(screen.getByText(/Preparing preview/)).toBeInTheDocument();
  });

  it("keeps the M3 preview for unknown types", () => {
    render(<DocumentViewer document={{ ...base, document_type: "zip" } as never} />);
    expect(screen.getByText(/file/)).toBeInTheDocument();
  });
});
