import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  DocumentAnalysisResult,
} from "./DocumentAnalysisResult";
import type { DocumentAnalysisResponse } from "@/lib/api/documentIntake";

function analysis(overrides: Partial<DocumentAnalysisResponse> = {}): DocumentAnalysisResponse {
  return {
    document_id: "doc:pdf:abc",
    document_type_id: "conference",
    confidence: 0.95,
    secondary_types: ["conference_certificate"],
    target_module: "research",
    status: "ingested",
    review_required: false,
    fields: [
      {
        field_name: "conference_name",
        predicate_id: "conference_name",
        value: "International Conference on Quantum Materials",
        original_text: "…",
        confidence: 0.9,
        extractor: "prose",
      },
    ],
    records: [],
    duplicates: [],
    conflicts: [],
    routing: [{ module: "event", kind: "created", object_id: "obj:event:1", existing_id: "", reason: "" }],
    ...overrides,
  };
}

describe("DocumentAnalysisResult", () => {
  it("shows the analyzing state", () => {
    render(<DocumentAnalysisResult analysis={null} analyzing />);
    expect(screen.getByText(/Analyzing document/i)).toBeTruthy();
  });

  it("renders a detected conference with created record", () => {
    render(<DocumentAnalysisResult analysis={analysis()} analyzing={false} fileName="conference.pdf" />);
    expect(screen.getByText(/Document analyzed/i)).toBeTruthy();
    expect(screen.getAllByText(/conference/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/International Conference on Quantum Materials/)).toBeTruthy();
    expect(screen.getByText(/Records detected/)).toBeTruthy();
    expect(screen.getByText(/Source: conference\.pdf/)).toBeTruthy();
  });

  it("shows review-required for conflicts", () => {
    render(
      <DocumentAnalysisResult
        analysis={analysis({
          review_required: true,
          routing: [],
          conflicts: [
            { predicate_id: "start_date", existing_claim_id: "c1", existing_value: "2022-12-06", extracted_value: "2022-12-07" },
          ],
        })}
        analyzing={false}
      />,
    );
    expect(screen.getAllByText(/Review required/i).length).toBeGreaterThan(0);
  });

  it("renders nothing when there is no analysis and not analyzing", () => {
    const { container } = render(<DocumentAnalysisResult analysis={null} analyzing={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows AI-assisted extraction mode and AI field badges", () => {
    render(
      <DocumentAnalysisResult
        analysis={analysis({
          extraction_mode: "ai_assisted",
          fields: [
            {
              field_name: "conference_name",
              predicate_id: "conference_name",
              value: "Quantum Materials",
              original_text: "…",
              confidence: 0.9,
              extractor: "prose",
            },
            {
              field_name: "city",
              predicate_id: "city",
              value: "New Delhi",
              original_text: "New Delhi",
              confidence: 0.95,
              extractor: "ai",
            },
          ],
        })}
        analyzing={false}
      />,
    );
    expect(screen.getByText(/AI-assisted/)).toBeTruthy();
    expect(screen.getByText(/New Delhi/)).toBeTruthy();
    expect(screen.getByText("AI")).toBeTruthy();
  });

  it("shows deterministic extraction mode by default", () => {
    render(<DocumentAnalysisResult analysis={analysis()} analyzing={false} />);
    expect(screen.getByText(/Deterministic/)).toBeTruthy();
  });
});
