/**
 * Shared field label mapping — the single source of truth for converting
 * predicate_id values to professor-friendly labels.
 *
 * Every component that displays field names should import from here
 * rather than maintaining its own copy of the mapping.
 */

const FIELD_LABELS: Record<string, string> = {
  publication_title: "Title",
  publication_year: "Year",
  journal_name: "Journal",
  authors: "Authors",
  doi: "DOI",
  conference_name: "Conference",
  venue: "Venue",
  funding_agency: "Funding Agency",
  principal_investigator: "Principal Investigator",
  sanctioned_amount: "Amount",
  project_title: "Project Title",
  recipient: "Recipient",
  certificate_number: "Certificate Number",
  manuscript_id: "Manuscript ID",
  acceptance_date: "Acceptance Date",
  issuing_authority: "Issuing Authority",
  event_title: "Title",
  co_investigator: "Co-Investigator",
  project_duration_months: "Duration",
  sanction_order_number: "Sanction Number",
  start_date: "Start Date",
  end_date: "End Date",
  organizer: "Organizer",
  reference_number: "Reference Number",
  conference_organizer: "Organizer",
  editor_name: "Editor",
  city: "City",
  country: "Country",
  participation_type: "Participation Type",
  presentation_title: "Presentation Title",
};

/** Convert a predicate_id to a human-readable label. */
export function friendlyFieldName(predicateId: string): string {
  return (
    FIELD_LABELS[predicateId] ??
    predicateId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

export default FIELD_LABELS;
