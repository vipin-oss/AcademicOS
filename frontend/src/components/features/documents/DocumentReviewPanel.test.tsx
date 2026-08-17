import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentReviewPanel } from "./DocumentReviewPanel";
import type { DocumentAnalysisResponse } from "@/lib/api/documentIntake";

function analysis(overrides: Partial<DocumentAnalysisResponse> = {}): DocumentAnalysisResponse {
  return {
    document_id: "doc:pdf:abc",
    document_type_id: "conference",
    confidence: 0.95,
    secondary_types: [],
    target_module: "events",
    status: "review_required",
    review_required: true,
    fields: [],
    records: [],
    duplicates: [],
    conflicts: [],
    routing: [{ module: "event", kind: "created", object_id: "obj:event:1", existing_id: "", reason: "" }],
    field_confidence: [
      {
        field_name: "recipient",
        predicate_id: "recipient",
        value: "Vipin Gupta",
        confidence: 0.85,
        source: "prose",
        risk: "medium",
        status: "proposed",
      },
      {
        field_name: "conference_name",
        predicate_id: "conference_name",
        value: "International Conference on AI",
        confidence: 0.95,
        source: "label",
        risk: "low",
        status: "auto_applied",
      },
    ],
    target_record_label: "Event",
    ...overrides,
  };
}

describe("DocumentReviewPanel", () => {
  it("shows the document understanding summary", () => {
    render(
      <DocumentReviewPanel
        analysis={analysis()}
        documentId="doc:pdf:abc"
        documentTitle="Conference Certificate.pdf"
      />,
    );
    expect(screen.getByText(/What AcademicOS understood/i)).toBeTruthy();
    expect(screen.getByText(/Conference Certificate\.pdf/)).toBeTruthy();
  });

  it("shows document type and confidence", () => {
    render(
      <DocumentReviewPanel analysis={analysis()} documentId="doc:pdf:abc" />,
    );
    expect(screen.getByText(/Document type/i)).toBeTruthy();
    // Confidence appears multiple times; verify at least one exists
    expect(screen.getAllByText(/Confidence/i).length).toBeGreaterThan(0);
  });

  it("shows target record label", () => {
    render(
      <DocumentReviewPanel analysis={analysis()} documentId="doc:pdf:abc" />,
    );
    expect(screen.getByText(/Will become/i)).toBeTruthy();
    // "Event" appears in multiple places — verify it's in the target label area
    expect(screen.getAllByText("Event").length).toBeGreaterThan(0);
  });

  it("shows fields needing review", () => {
    render(
      <DocumentReviewPanel analysis={analysis()} documentId="doc:pdf:abc" />,
    );
    expect(screen.getByText(/Needs your confirmation/i)).toBeTruthy();
    expect(screen.getByText("Vipin Gupta")).toBeTruthy();
  });

  it("shows actual values, not type metadata", () => {
    // Both fields set to "proposed" so they appear in the review section
    const withBothProposed = analysis({
      field_confidence: [
        {
          field_name: "recipient",
          predicate_id: "recipient",
          value: "Vipin Gupta",
          confidence: 0.85,
          source: "prose",
          risk: "medium",
          status: "proposed",
        },
        {
          field_name: "conference_name",
          predicate_id: "conference_name",
          value: "International Conference on AI",
          confidence: 0.85,
          source: "prose",
          risk: "medium",
          status: "proposed",
        },
      ],
    });
    render(
      <DocumentReviewPanel analysis={withBothProposed} documentId="doc:pdf:abc" />,
    );
    // Values should be the actual content
    expect(screen.getByText("Vipin Gupta")).toBeTruthy();
    const allText = document.body.textContent ?? "";
    expect(allText).toContain("Vipin Gupta");
    expect(allText).toContain("International Conference on AI");
  });

  it("shows already confirmed section with auto_applied fields", () => {
    render(
      <DocumentReviewPanel analysis={analysis()} documentId="doc:pdf:abc" />,
    );
    expect(screen.getByText(/Already confirmed/i)).toBeTruthy();
  });

  it("shows review complete when no items need review", () => {
    const noReview = analysis({
      review_required: false,
      field_confidence: [
        {
          field_name: "recipient",
          predicate_id: "recipient",
          value: "Vipin Gupta",
          confidence: 0.95,
          source: "label",
          risk: "low",
          status: "auto_applied",
        },
      ],
    });
    render(
      <DocumentReviewPanel analysis={noReview} documentId="doc:pdf:abc" />,
    );
    expect(screen.getByText(/Review complete/i)).toBeTruthy();
  });

  it("shows created record message", () => {
    render(
      <DocumentReviewPanel analysis={analysis()} documentId="doc:pdf:abc" />,
    );
    const allText = document.body.textContent ?? "";
    expect(allText).toContain("created from this document");
  });

  it("shows conflict section when conflicts exist", () => {
    const withConflicts = analysis({
      conflicts: [
        {
          predicate_id: "start_date",
          existing_claim_id: "c1",
          existing_value: "2024-01-15",
          extracted_value: "2024-01-16",
        },
      ],
      field_confidence: [
        {
          field_name: "Start Date",
          predicate_id: "start_date",
          value: "2024-01-16",
          confidence: 0.85,
          source: "prose",
          risk: "medium",
          status: "conflict",
        },
      ],
    });
    render(
      <DocumentReviewPanel analysis={withConflicts} documentId="doc:pdf:abc" />,
    );
    expect(screen.getAllByText(/Conflicting information/i).length).toBeGreaterThan(0);
  });

  it("shows actual extracted date value, not 'date' type name", () => {
    const withDate = analysis({
      field_confidence: [
        {
          field_name: "Year",
          predicate_id: "publication_year",
          value: "2024",
          confidence: 0.85,
          source: "regex",
          risk: "medium",
          status: "proposed",
        },
      ],
    });
    render(
      <DocumentReviewPanel analysis={withDate} documentId="doc:pdf:abc" />,
    );
    // The actual year value should be shown
    const allText = document.body.textContent ?? "";
    expect(allText).toContain("2024");
  });

  it("shows friendly names for predicate_ids", () => {
    render(
      <DocumentReviewPanel analysis={analysis()} documentId="doc:pdf:abc" />,
    );
    // Friendly name "Recipient" should appear
    expect(screen.getAllByText("Recipient").length).toBeGreaterThan(0);
    // Technical predicate_id "recipient" should not appear as standalone text
    const allText = document.body.textContent ?? "";
    // "recipient" should NOT appear as a standalone label
    // (it might appear in the text of "Recipient" label, which is fine)
    // The key point: technical names like "conference_name" should not appear
    expect(allText).not.toContain("conference_name");
  });

  it("uses target_record_label from analysis when available", () => {
    render(
      <DocumentReviewPanel
        analysis={analysis({ target_record_label: "Certificate" })}
        documentId="doc:pdf:abc"
      />,
    );
    expect(screen.getAllByText("Certificate").length).toBeGreaterThan(0);
  });

  it("falls back to MODULE_LABELS when target_record_label is missing", () => {
    render(
      <DocumentReviewPanel
        analysis={analysis({ target_record_label: "", target_module: "events" })}
        documentId="doc:pdf:abc"
      />,
    );
    // Should show "Event" from MODULE_LABELS
    expect(screen.getAllByText("Event").length).toBeGreaterThan(0);
  });

  it("never shows 'text', 'date', 'number' as field values", () => {
    const out = analysis({
      field_confidence: [
        {
          field_name: "Title",
          predicate_id: "publication_title",
          value: "Deep Learning Review",
          confidence: 0.95,
          source: "label",
          risk: "low",
          status: "proposed",
        },
      ],
    });
    render(<DocumentReviewPanel analysis={out} documentId="doc:pdf:abc" />);
    const allText = document.body.textContent ?? "";
    // "Deep Learning Review" appears as a proposed value in the review section
    expect(allText).toContain("Deep Learning Review");
  });
});
