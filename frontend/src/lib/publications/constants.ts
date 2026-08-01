import type {
  BibliographyFormat,
  CitationStyle,
  PipelineStage,
  PublicationAuthor,
  PublicationLinkGroup,
  PublicationResponse,
  PublicationTypeValue,
  Quartile,
} from "@/types";

/** Every publication type the UI knows how to label (FR-PUB vocabulary). */
export const PUBLICATION_TYPES: PublicationTypeValue[] = [
  "journal_article",
  "conference_paper",
  "book_chapter",
  "book",
  "patent",
  "technical_report",
  "thesis",
  "preprint",
  "other",
];

/** FR-PUB-001 lifecycle, in order. */
export const PIPELINE_STAGES: PipelineStage[] = [
  "idea",
  "draft",
  "internal_review",
  "submitted",
  "under_review",
  "revision",
  "accepted",
  "published",
  "post_publication",
];

export const QUARTILES: Quartile[] = ["Q1", "Q2", "Q3", "Q4"];

export const CITATION_STYLES: { value: CitationStyle; label: string }[] = [
  { value: "apa", label: "APA" },
  { value: "ieee", label: "IEEE" },
  { value: "vancouver", label: "Vancouver" },
  { value: "chicago", label: "Chicago" },
  { value: "harvard", label: "Harvard" },
  { value: "bibtex", label: "BibTeX" },
];

export const BIBLIOGRAPHY_FORMATS: {
  value: BibliographyFormat;
  label: string;
  extension: string;
}[] = [
  { value: "bibtex", label: "BibTeX", extension: ".bib" },
  { value: "ris", label: "RIS", extension: ".ris" },
  { value: "csv", label: "CSV", extension: ".csv" },
];

/** The 7 reference-manager link panes, with human labels. */
export const LINK_GROUPS: { value: PublicationLinkGroup; label: string }[] = [
  { value: "projects", label: "Projects" },
  { value: "grants", label: "Grants" },
  { value: "students", label: "Students" },
  { value: "faculty", label: "Faculty" },
  { value: "departments", label: "Departments" },
  { value: "events", label: "Events" },
  { value: "committees", label: "Committees" },
];

/**
 * Which Object types belong in each link-group picker (the inverse of the
 * backend's `_TYPE_TO_GROUP`). Filtering the picker keeps it short and stops
 * semantically wrong edges at the UI boundary (the backend validates anyway).
 */
export const LINK_GROUP_OBJECT_TYPES: Record<PublicationLinkGroup, string[]> = {
  projects: ["research_project"],
  grants: ["grant"],
  students: ["student"],
  faculty: ["faculty"],
  departments: ["space", "research_area", "laboratory"],
  events: ["event"],
  committees: ["committee"],
};

/** Rows per page on the Publications list (mirrors the Documents list). */
export const DEFAULT_PUB_PAGE_SIZE = 12;

/** Where a DOI resolves. */
export const DOI_URL = "https://doi.org/";

/** Where an ORCID iD resolves. */
export const ORCID_URL = "https://orcid.org/";

/**
 * One-line author summary for dense UI (table rows, cards):
 *   "Gupta, Vipin; Sharma, Asha"      (<= 3 authors)
 *   "Gupta, Vipin et al. (5)"         (> 3 authors)
 */
export function formatAuthorsShort(authors: PublicationAuthor[]): string {
  const names = (authors ?? [])
    .map((author) => author?.name?.trim())
    .filter((name): name is string => Boolean(name));
  if (names.length === 0) return "—";
  if (names.length <= 3) return names.join("; ");
  return `${names[0]} et al. (${names.length})`;
}

/** The venue line: journal for articles, conference for papers, else publisher. */
export function venueOf(
  publication: Pick<PublicationResponse, "journal" | "conference" | "publisher">,
): string {
  return (
    publication.journal?.trim() ||
    publication.conference?.trim() ||
    publication.publisher?.trim() ||
    "—"
  );
}

/** Compact bibliographic locator: "7(3), 201–214" — em dash when empty. */
export function locatorOf(
  publication: Pick<PublicationResponse, "volume" | "issue" | "pages">,
): string {
  const volume = publication.volume?.trim() ?? "";
  const issue = publication.issue?.trim() ?? "";
  const pages = publication.pages?.trim() ?? "";
  const volIssue = volume ? (issue ? `${volume}(${issue})` : volume) : "";
  const parts = [volIssue, pages].filter(Boolean);
  return parts.length ? parts.join(", ") : "—";
}
