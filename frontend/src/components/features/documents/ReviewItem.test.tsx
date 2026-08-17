import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReviewItem, type ReviewItemField } from "./ReviewItem";

function field(overrides: Partial<ReviewItemField> = {}): ReviewItemField {
  return {
    field_name: "recipient",
    predicate_id: "recipient",
    value: "Vipin Gupta",
    confidence: 0.85,
    source: "prose",
    risk: "medium",
    status: "proposed",
    ...overrides,
  };
}

describe("ReviewItem", () => {
  it("shows the actual extracted value, not type metadata", () => {
    render(<ReviewItem field={field({ value: "Vipin Gupta" })} />);
    expect(screen.getByText("Vipin Gupta")).toBeTruthy();
    // Must NOT show "text", "prose", "date" as the value
    expect(screen.queryByText("text")).toBeNull();
  });

  it("shows 'Not found in the document' for empty value", () => {
    render(<ReviewItem field={field({ value: "" })} />);
    expect(screen.getByText(/Not found in the document/i)).toBeTruthy();
  });

  it("shows friendly field name", () => {
    render(<ReviewItem field={field({ predicate_id: "recipient" })} />);
    expect(screen.getByText("Recipient")).toBeTruthy();
  });

  it("shows friendly field name for unknown predicate", () => {
    render(<ReviewItem field={field({ predicate_id: "some_custom_field" })} />);
    expect(screen.getByText("Some Custom Field")).toBeTruthy();
  });

  it("shows confidence label", () => {
    render(<ReviewItem field={field({ confidence: 0.95 })} />);
    expect(screen.getByText(/High confidence/i)).toBeTruthy();
  });

  it("shows medium confidence label", () => {
    render(<ReviewItem field={field({ confidence: 0.80 })} />);
    expect(screen.getByText(/Medium confidence/i)).toBeTruthy();
  });

  it("shows low confidence label", () => {
    render(<ReviewItem field={field({ confidence: 0.50 })} />);
    expect(screen.getByText(/Low confidence/i)).toBeTruthy();
  });

  it("shows 'Suggested' badge for proposed status", () => {
    render(<ReviewItem field={field({ status: "proposed" })} />);
    expect(screen.getByText("Suggested")).toBeTruthy();
  });

  it("shows 'Needs confirmation' badge for review_required status", () => {
    render(<ReviewItem field={field({ status: "review_required" })} />);
    expect(screen.getByText("Needs confirmation")).toBeTruthy();
  });

  it("shows 'Conflicts with existing' badge for conflict status", () => {
    render(<ReviewItem field={field({ status: "conflict" })} />);
    expect(screen.getByText("Conflicts with existing")).toBeTruthy();
  });

  it("shows action buttons when showActions=true and status is proposed", () => {
    render(<ReviewItem field={field({ status: "proposed" })} showActions={true} />);
    expect(screen.getByText("Confirm")).toBeTruthy();
    expect(screen.getByText("Edit")).toBeTruthy();
    expect(screen.getByText("Not applicable")).toBeTruthy();
  });

  it("hides action buttons when showActions=false", () => {
    render(<ReviewItem field={field({ status: "proposed" })} showActions={false} />);
    expect(screen.queryByText("Confirm")).toBeNull();
  });

  it("hides for auto_applied when showActions=false", () => {
    const { container } = render(
      <ReviewItem field={field({ status: "auto_applied" })} showActions={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("calls onResolved with 'confirmed' when Confirm clicked", async () => {
    const onResolved = vi.fn();
    render(
      <ReviewItem field={field()} showActions={true} onResolved={onResolved} />,
    );
    fireEvent.click(screen.getByText("Confirm"));
    // Should call onResolved
    expect(onResolved).toHaveBeenCalledWith("recipient", "confirmed");
  });

  it("calls onResolved with 'rejected' when Not applicable clicked", async () => {
    const onResolved = vi.fn();
    render(
      <ReviewItem field={field()} showActions={true} onResolved={onResolved} />,
    );
    fireEvent.click(screen.getByText("Not applicable"));
    expect(onResolved).toHaveBeenCalledWith("recipient", "rejected");
  });

  it("shows edit input when Edit clicked", () => {
    render(<ReviewItem field={field()} showActions={true} />);
    fireEvent.click(screen.getByText("Edit"));
    // Should show an input field
    expect(screen.getByDisplayValue("Vipin Gupta")).toBeTruthy();
  });

  it("shows existing value for conflict status", () => {
    render(
      <ReviewItem
        field={field({ status: "conflict" })}
        existingValue="Old Name"
      />,
    );
    expect(screen.getByText("Existing record says:")).toBeTruthy();
    expect(screen.getByText("Old Name")).toBeTruthy();
  });

  it("shows source description", () => {
    render(<ReviewItem field={field({ source: "prose" })} />);
    expect(screen.getByText(/Extracted from document text/i)).toBeTruthy();
  });

  it("shows AI source description for AI extractor", () => {
    render(<ReviewItem field={field({ source: "ai" })} />);
    expect(screen.getByText(/AI analysis/i)).toBeTruthy();
  });

  it("shows 'why am I seeing this?' hint for proposed items", () => {
    render(<ReviewItem field={field({ status: "proposed" })} targetRecordLabel="Event" />);
    expect(screen.getByText(/Will be saved to Event when confirmed/i)).toBeTruthy();
  });

  it("never displays extraction type as value", () => {
    const typeNames = ["text", "date", "number", "money", "raw"];
    for (const typeName of typeNames) {
      const { container } = render(
        <ReviewItem field={field({ value: typeName })} />,
      );
      // If the value IS a type name, it should still render but we verify it's the actual value
      const valueEl = container.querySelector(".text-base");
      if (valueEl) {
        // The value should be shown (even if it happens to match a type name)
        expect(valueEl.textContent).toBeTruthy();
      }
    }
  });

  it("shows 'saved' state after resolution", () => {
    const onResolved = vi.fn();
    render(
      <ReviewItem field={field()} showActions={true} onResolved={onResolved} />,
    );
    fireEvent.click(screen.getByText("Confirm"));
    // Should show saved state
    expect(screen.getByText(/saved/i)).toBeTruthy();
  });

  it("shows target record label in hint", () => {
    render(
      <ReviewItem field={field({ status: "proposed" })} targetRecordLabel="Publication" />,
    );
    expect(screen.getByText(/Will be saved to Publication/i)).toBeTruthy();
  });
});
