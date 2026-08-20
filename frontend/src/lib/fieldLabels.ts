/**
 * Shared field label mapping — the single source of truth for converting
 * predicate_id values to professor-friendly labels.
 *
 * Every component that displays field names should import from here
 * rather than maintaining its own copy of the mapping.
 *
 * RULE: Labels must be what a professor would say in conversation.
 * "What conference did you attend?" not "What is the conference_name?"
 */

const FIELD_LABELS: Record<string, string> = {
  // Conference / Event
  conference_name: "Conference Name",
  conference_acronym: "Short Name",
  conference_organizer: "Organizer",
  event_title: "Event Title",
  event_date: "Event Date",
  venue: "Venue",
  city: "City",
  country: "Country",
  start_date: "Start Date",
  end_date: "End Date",
  participation_type: "How You Participated",
  presentation_title: "Your Paper / Presentation",
  presentation_type: "Presentation Format",
  certificate_number: "Certificate Number",
  event_url: "Event Website",
  issuing_authority: "Issued By",
  deadline: "Deadline",
  organizer: "Organizer",
  reference_number: "Reference Number",

  // Publication
  publication_title: "Paper Title",
  publication_year: "Year",
  publication_status: "Publication Status",
  journal_name: "Journal",
  authors: "Authors",
  doi: "DOI",
  volume: "Volume",
  issue: "Issue",
  pages: "Pages",
  publisher: "Publisher",
  issn: "ISSN",
  manuscript_id: "Manuscript ID",
  acceptance_date: "Acceptance Date",
  editor_name: "Editor",

  // Research / Grant
  project_title: "Project Title",
  funding_agency: "Funding Agency",
  principal_investigator: "Principal Investigator",
  co_investigator: "Co-Investigator",
  sanctioned_amount: "Sanctioned Amount",
  sanction_order_number: "Sanction Order Number",
  project_duration_months: "Duration (months)",
  project_status: "Project Status",
  issue_date: "Issue Date",
  file_number: "File Number",
  scheme_name: "Scheme Name",
  sanctioned_by: "Sanctioned By",
  grant_category: "Grant Category",

  // Award
  award_title: "Award Name",
  award_date: "Award Date",
  award_category: "Category",
  awarding_body: "Awarded By",
  recipient: "Recipient",

  // Committee
  committee_name: "Committee Name",
  committee_members: "Members",
  committee_role: "Your Role",
  committee_purpose: "Purpose",
  tenure: "Tenure",
  order_number: "Order Number",
  order_date: "Order Date",

  // Faculty / Appointment
  designation: "Designation",
  department: "Department",
  institution: "Institution",
  joining_date: "Joining Date",
  relieving_date: "Relieving Date",
  appointment_type: "Appointment Type",

  // Teaching
  course_name: "Course Name",
  course_code: "Course Code",
  semester: "Semester",
  academic_year: "Academic Year",
  credits: "Credits",

  // Student
  scholar_name: "Scholar Name",
  supervisor_name: "Supervisor",
  research_topic: "Research Topic",
  reporting_period: "Reporting Period",
  phd_status: "Status",

  // Finance
  invoice_number: "Invoice Number",
  invoice_amount: "Amount",
  vendor_name: "Vendor",
};

/** Convert a predicate_id to a human-readable label. */
export function friendlyFieldName(predicateId: string): string {
  return (
    FIELD_LABELS[predicateId] ??
    predicateId.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

export default FIELD_LABELS;
