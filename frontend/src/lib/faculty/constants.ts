import type { FacultyEmploymentType } from "@/types";

/** Designation vocabulary (PART 1 — guidance, not a closed enum; free text allowed). */
export const DESIGNATIONS = [
  "Professor",
  "Associate Professor",
  "Assistant Professor",
  "Senior Lecturer",
  "Lecturer",
  "Professor of Practice",
  "Research Scientist",
  "Postdoctoral Fellow",
];

/** The 4 employment types, with human labels (PART 1). */
export const EMPLOYMENT_TYPES: {
  value: FacultyEmploymentType;
  label: string;
}[] = [
  { value: "regular", label: "Regular" },
  { value: "contract", label: "Contract" },
  { value: "visiting", label: "Visiting" },
  { value: "adjunct", label: "Adjunct" },
];

export function employmentTypeLabel(value: string | null | undefined): string {
  const found = EMPLOYMENT_TYPES.find((type) => type.value === value);
  if (found) return found.label;
  return (value ?? "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ") || "—";
}

/**
 * The six academic profile sections (PART 2) with their field tuples —
 * the backend stores each as a JSON list-of-dicts and renders exactly these
 * keys. The modal's rows editor is generated from this config (single source).
 */
export interface ProfileSectionField {
  key: string;
  label: string;
  placeholder?: string;
}

export interface ProfileSectionConfig {
  /** The metadata key / FacultyResponse property. */
  key:
    | "degrees"
    | "experience"
    | "awards"
    | "memberships"
    | "certifications"
    | "admin_positions";
  label: string;
  fields: ProfileSectionField[];
}

export const PROFILE_SECTIONS: ProfileSectionConfig[] = [
  {
    key: "degrees",
    label: "Degrees",
    fields: [
      { key: "degree", label: "Degree", placeholder: "Ph.D." },
      { key: "institution", label: "Institution", placeholder: "IIT Delhi" },
      { key: "year", label: "Year", placeholder: "2012" },
    ],
  },
  {
    key: "experience",
    label: "Experience",
    fields: [
      { key: "role", label: "Role", placeholder: "Assistant Professor" },
      { key: "organization", label: "Organization", placeholder: "University" },
      { key: "from", label: "From", placeholder: "2015" },
      { key: "to", label: "To", placeholder: "2021" },
      { key: "note", label: "Note" },
    ],
  },
  {
    key: "awards",
    label: "Awards & Honours",
    fields: [
      { key: "title", label: "Title", placeholder: "Young Scientist Award" },
      { key: "year", label: "Year", placeholder: "2019" },
      { key: "by", label: "Awarded by", placeholder: "INSA" },
    ],
  },
  {
    key: "memberships",
    label: "Professional Memberships",
    fields: [
      { key: "body", label: "Body", placeholder: "Indian Physics Association" },
      { key: "year", label: "Year", placeholder: "2018" },
      { key: "note", label: "Note" },
    ],
  },
  {
    key: "certifications",
    label: "Certifications",
    fields: [
      { key: "title", label: "Title", placeholder: "Nano-fabrication" },
      { key: "issuer", label: "Issuer", placeholder: "INI" },
      { key: "year", label: "Year", placeholder: "2020" },
    ],
  },
  {
    key: "admin_positions",
    label: "Administrative Positions",
    fields: [
      { key: "position", label: "Position", placeholder: "PhD Coordinator" },
      { key: "unit", label: "Unit", placeholder: "Physics" },
      { key: "from", label: "From", placeholder: "2023" },
      { key: "to", label: "To" },
    ],
  },
];

export const DEFAULT_FACULTY_PAGE_SIZE = 20;
