"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Crosshair, Plus, Star, Trash2, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import {
  createPublication,
  lookupDoi,
  updatePublication,
} from "@/lib/api/publications";
import { listObjects } from "@/lib/api/objects";
import {
  LINK_GROUPS,
  LINK_GROUP_OBJECT_TYPES,
  PIPELINE_STAGES,
  PUBLICATION_TYPES,
  QUARTILES,
} from "@/lib/publications/constants";
import { useModalDismiss } from "@/hooks/useModalDismiss";
import { cn, titleCase } from "@/lib/utils";
import type {
  DoiLookupRecord,
  ObjectResponse,
  PipelineStage,
  PublicationAuthor,
  PublicationLinkGroup,
  PublicationResponse,
  PublicationStatus,
  PublicationTypeValue,
  Quartile,
} from "@/types";
import { Spinner } from "@/components/features/objects/Spinner";

export interface PublicationSaveResult {
  mode: "create" | "edit";
  publication: PublicationResponse;
}

const FIELD_CLASS =
  "w-full rounded-lg border bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60";

const DOI_RE = /^10\.\d{4,9}\/\S+$/;
const ORCID_RE = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/;
const URL_RE = /^https?:\/\/\S+$/;

function fieldClass(error?: string): string {
  return cn(
    FIELD_CLASS,
    error
      ? "border-[var(--danger)]"
      : "border-[var(--border-subtle)] focus:border-[var(--accent)]",
  );
}

function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {error ? (
        <p role="alert" className="mt-1 text-xs text-[var(--danger)]">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</p>
      ) : null}
    </div>
  );
}

/** "a, b, c" <-> ["a", "b", "c"] */
function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function normalizeAuthors(raw: DoiLookupRecord["authors"]): PublicationAuthor[] {
  return (raw ?? [])
    .map((entry) =>
      typeof entry === "string" ? { name: entry } : { ...entry },
    )
    .filter((entry) => entry.name?.trim());
}

interface AuthorRow {
  name: string;
  orcid: string;
  affiliation: string;
  corresponding: boolean;
}

const EMPTY_AUTHOR: AuthorRow = { name: "", orcid: "", affiliation: "", corresponding: false };

const EMPTY_LINKS: Record<PublicationLinkGroup, string[]> = {
  projects: [],
  grants: [],
  students: [],
  faculty: [],
  departments: [],
  events: [],
  committees: [],
};

/**
 * Create **and** edit a Publication — one modal, one code path (mirrors the
 * Documents UploadModal). Covers manual entry and DOI-assisted entry
 * (Crossref pre-fill): the fetched record only fills fields that are still
 * blank so it never clobbers something the user typed.
 */
export function PublicationModal({
  open,
  publication,
  onClose,
  onSaved,
}: {
  open: boolean;
  publication?: PublicationResponse | null;
  onClose: () => void;
  onSaved: (result: PublicationSaveResult) => void;
}) {
  const isEdit = Boolean(publication);

  const [title, setTitle] = useState("");
  const [publicationType, setPublicationType] = useState<PublicationTypeValue>("journal_article");
  const [pipelineStage, setPipelineStage] = useState<PipelineStage | "">("");
  const [status, setStatus] = useState<PublicationStatus>("draft");
  const [uploadedBy, setUploadedBy] = useState("");

  const [authors, setAuthors] = useState<AuthorRow[]>([{ ...EMPTY_AUTHOR }]);
  const [affiliationsCsv, setAffiliationsCsv] = useState("");
  const [abstract, setAbstract] = useState("");
  const [keywordsCsv, setKeywordsCsv] = useState("");

  const [doi, setDoi] = useState("");
  const [isbn, setIsbn] = useState("");
  const [issn, setIssn] = useState("");
  const [publisher, setPublisher] = useState("");
  const [journal, setJournal] = useState("");
  const [conference, setConference] = useState("");
  const [volume, setVolume] = useState("");
  const [issue, setIssue] = useState("");
  const [pages, setPages] = useState("");
  const [year, setYear] = useState("");
  const [date, setDate] = useState("");
  const [language, setLanguage] = useState("");

  const [citationCount, setCitationCount] = useState("");
  const [impactFactor, setImpactFactor] = useState("");
  const [quartile, setQuartile] = useState<Quartile | "">("");
  const [indexingCsv, setIndexingCsv] = useState("");
  const [publisherUrl, setPublisherUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [tagsCsv, setTagsCsv] = useState("");
  const [collectionsCsv, setCollectionsCsv] = useState("");

  const [linkSelections, setLinkSelections] =
    useState<Record<PublicationLinkGroup, string[]>>(EMPTY_LINKS);
  const touchedGroups = useRef<Set<PublicationLinkGroup>>(new Set());
  const [objects, setObjects] = useState<ObjectResponse[]>([]);

  const [lookupState, setLookupState] = useState<
    { kind: "idle" } | { kind: "loading" } | { kind: "error" | "found"; message: string }
  >({ kind: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useModalDismiss({ open, onDismiss: onClose, disabled: submitting });

  // (Re)hydrate the form + load the object pickers every time the modal opens.
  useEffect(() => {
    if (!open) return;
    setFormError(null);
    setShowErrors(false);
    setSubmitting(false);
    setLookupState({ kind: "idle" });
    submittingRef.current = false;
    touchedGroups.current = new Set();

    if (publication) {
      setTitle(publication.title);
      setPublicationType(publication.publication_type);
      setPipelineStage(publication.pipeline_stage ?? "");
      setStatus(publication.status);
      setUploadedBy(publication.uploaded_by || "system");
      setAuthors(
        publication.authors.length
          ? publication.authors.map((author) => ({
              name: author.name ?? "",
              orcid: author.orcid ?? "",
              affiliation: author.affiliation ?? "",
              corresponding: Boolean(author.corresponding),
            }))
          : [{ ...EMPTY_AUTHOR }],
      );
      setAffiliationsCsv(publication.affiliations.join(", "));
      setAbstract(publication.abstract ?? "");
      setKeywordsCsv(publication.keywords.join(", "));
      setDoi(publication.doi ?? "");
      setIsbn(publication.isbn ?? "");
      setIssn(publication.issn ?? "");
      setPublisher(publication.publisher ?? "");
      setJournal(publication.journal ?? "");
      setConference(publication.conference ?? "");
      setVolume(publication.volume ?? "");
      setIssue(publication.issue ?? "");
      setPages(publication.pages ?? "");
      setYear(publication.year != null ? String(publication.year) : "");
      setDate(publication.date ?? "");
      setLanguage(publication.language ?? "");
      setCitationCount(String(publication.citation_count ?? 0));
      setImpactFactor(publication.impact_factor != null ? String(publication.impact_factor) : "");
      setQuartile(publication.quartile ?? "");
      setIndexingCsv(publication.indexing.join(", "));
      setPublisherUrl(publication.publisher_url ?? "");
      setNotes(publication.notes ?? "");
      setTagsCsv(publication.tags.join(", "));
      setCollectionsCsv(publication.collections.join(", "));
      setLinkSelections({
        projects: (publication.links?.projects ?? []).map((entry) => entry.id),
        grants: (publication.links?.grants ?? []).map((entry) => entry.id),
        students: (publication.links?.students ?? []).map((entry) => entry.id),
        faculty: (publication.links?.faculty ?? []).map((entry) => entry.id),
        departments: (publication.links?.departments ?? []).map((entry) => entry.id),
        events: (publication.links?.events ?? []).map((entry) => entry.id),
        committees: (publication.links?.committees ?? []).map((entry) => entry.id),
      });
    } else {
      setTitle("");
      setPublicationType("journal_article");
      setPipelineStage("");
      setStatus("draft");
      setUploadedBy("");
      setAuthors([{ ...EMPTY_AUTHOR }]);
      setAffiliationsCsv("");
      setAbstract("");
      setKeywordsCsv("");
      setDoi("");
      setIsbn("");
      setIssn("");
      setPublisher("");
      setJournal("");
      setConference("");
      setVolume("");
      setIssue("");
      setPages("");
      setYear("");
      setDate("");
      setLanguage("");
      setCitationCount("");
      setImpactFactor("");
      setQuartile("");
      setIndexingCsv("");
      setPublisherUrl("");
      setNotes("");
      setTagsCsv("");
      setCollectionsCsv("");
      setLinkSelections(EMPTY_LINKS);
    }

    // Populate the link pickers from the existing objects.
    listObjects({ pageSize: 100 })
      .then((response) => setObjects(response.items ?? []))
      .catch(() => setObjects([]));
  }, [open, publication]);

  useEffect(() => {
    if (open) firstFieldRef.current?.focus();
  }, [open]);

  const fieldErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    if (!title.trim()) errors.title = "Title is required.";
    if (!isEdit && !uploadedBy.trim()) errors.uploadedBy = "Added by is required.";
    const trimmedDoi = doi.trim();
    if (trimmedDoi && !DOI_RE.test(trimmedDoi)) errors.doi = "A DOI looks like 10.1038/….";
    const yearNumber = year.trim() ? Number.parseInt(year.trim(), 10) : null;
    if (yearNumber != null && (Number.isNaN(yearNumber) || yearNumber < 1000 || yearNumber > 2100)) {
      errors.year = "Year must be between 1000 and 2100.";
    }
    if (citationCount.trim() && Number.parseInt(citationCount.trim(), 10) < 0) {
      errors.citationCount = "Citation count must not be negative.";
    }
    if (impactFactor.trim() && Number.parseFloat(impactFactor.trim()) < 0) {
      errors.impactFactor = "Impact factor must not be negative.";
    }
    if (publisherUrl.trim() && !URL_RE.test(publisherUrl.trim())) {
      errors.publisherUrl = "Must be an http(s) URL.";
    }
    authors.forEach((author, index) => {
      const blank = !author.name.trim() && !author.orcid.trim() && !author.affiliation.trim();
      if (!blank && !author.name.trim()) {
        errors[`author-${index}`] = "This author needs a name (or clear the row).";
      }
      if (author.orcid.trim() && !ORCID_RE.test(author.orcid.trim())) {
        errors[`author-${index}`] = "ORCID iDs look like 0000-0002-1825-0097.";
      }
    });
    return errors;
  }, [title, uploadedBy, doi, year, citationCount, impactFactor, publisherUrl, authors, isEdit]);

  if (!open) return null;

  const errorFor = (key: string) => (showErrors ? fieldErrors[key] : undefined);

  const setAuthor = (index: number, patch: Partial<AuthorRow>) => {
    setAuthors((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const markTouched = (group: PublicationLinkGroup) => {
    touchedGroups.current.add(group);
  };

  const optionsFor = (group: PublicationLinkGroup): ObjectResponse[] => {
    const allowed = new Set(LINK_GROUP_OBJECT_TYPES[group]);
    const selected = new Set(linkSelections[group]);
    // Type-filtered picker; preselected ids are kept visible regardless so an
    // edit never silently hides (and then drops) an existing edge.
    return objects.filter(
      (object) => allowed.has(object.object_type) || selected.has(object.id),
    );
  };

  /** Crossref-assisted entry: fill ONLY blank fields from the DOI record. */
  const handleDoiLookup = async () => {
    const trimmed = doi.trim();
    if (!trimmed || lookupState.kind === "loading") return;
    setLookupState({ kind: "loading" });
    try {
      const record = await lookupDoi(trimmed);
      let filled = 0;
      const fill = (current: string, value: string | null | undefined, set: (v: string) => void) => {
        if (!current.trim() && value) {
          set(String(value));
          filled += 1;
        }
      };
      fill(title, record.title, setTitle);
      fill(journal, record.journal, setJournal);
      fill(conference, record.conference, setConference);
      fill(publisher, record.publisher, setPublisher);
      fill(issn, record.issn, setIssn);
      fill(isbn, record.isbn, setIsbn);
      fill(volume, record.volume, setVolume);
      fill(issue, record.issue, setIssue);
      fill(pages, record.pages, setPages);
      fill(date, record.date, setDate);
      fill(abstract, record.abstract, setAbstract);
      fill(publisherUrl, record.publisher_url ?? (record.doi ? `https://doi.org/${record.doi}` : null), setPublisherUrl);
      if (!year.trim() && record.year != null) {
        setYear(String(record.year));
        filled += 1;
      }
      const fetchedAuthors = normalizeAuthors(record.authors);
      const formBlank = authors.every(
        (row) => !row.name.trim() && !row.orcid.trim() && !row.affiliation.trim(),
      );
      if (formBlank && fetchedAuthors.length) {
        setAuthors(
          fetchedAuthors.map((author) => ({
            name: author.name,
            orcid: author.orcid ?? "",
            affiliation: author.affiliation ?? "",
            corresponding: Boolean(author.corresponding),
          })),
        );
        filled += 1;
      }
      if (record.publication_type && PUBLICATION_TYPES.includes(record.publication_type as PublicationTypeValue)) {
        setPublicationType(record.publication_type as PublicationTypeValue);
      }
      setLookupState({
        kind: "found",
        message: filled
          ? `Crossref record found — filled ${filled} blank field${filled === 1 ? "" : "s"} (existing entries kept).`
          : "Crossref record found — nothing to fill (all fields already set).",
      });
    } catch (error) {
      setLookupState({
        kind: "error",
        message: toErrorMessage(error, "Could not fetch metadata for this DOI."),
      });
    }
  };

  const buildAuthorsPayload = (): PublicationAuthor[] | undefined => {
    const cleaned = authors
      .filter((row) => row.name.trim() || row.orcid.trim() || row.affiliation.trim())
      .map((row) => ({
        name: row.name.trim(),
        ...(row.orcid.trim() ? { orcid: row.orcid.trim() } : {}),
        ...(row.affiliation.trim() ? { affiliation: row.affiliation.trim() } : {}),
        corresponding: row.corresponding,
      }));
    return cleaned.length ? cleaned : [];
  };

  const buildLinksPayload = ():
    | Partial<Record<PublicationLinkGroup, string[]>>
    | undefined => {
    const links: Partial<Record<PublicationLinkGroup, string[]>> = {};
    let any = false;
    for (const { value: group } of LINK_GROUPS) {
      if (isEdit && !touchedGroups.current.has(group)) continue; // absent = untouched
      if (linkSelections[group].length || isEdit) {
        links[group] = linkSelections[group];
        any = true;
      }
    }
    return any ? links : undefined;
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;

    const firstFieldError = Object.values(fieldErrors)[0];
    if (firstFieldError) {
      setShowErrors(true);
      setFormError(firstFieldError);
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    setFormError(null);

    const yearValue = year.trim() ? Number.parseInt(year.trim(), 10) : null;
    const citationValue = citationCount.trim() ? Number.parseInt(citationCount.trim(), 10) : null;
    const factorValue = impactFactor.trim() ? Number.parseFloat(impactFactor.trim()) : null;
    const authorsPayload = buildAuthorsPayload();
    const linksPayload = buildLinksPayload();
    // Scalars: present keys replace on PUT — the edit form is a full overwrite
    // of every visible field (cleared inputs intentionally clear the field).
    const scalar = (value: string) => (value.trim() ? value.trim() : null);

    try {
      if (publication) {
        const saved = await updatePublication(publication.id, {
          title: title.trim(),
          publication_type: publicationType,
          status,
          pipeline_stage: pipelineStage || null,
          authors: authorsPayload,
          affiliations: csvToList(affiliationsCsv),
          abstract: scalar(abstract),
          keywords: csvToList(keywordsCsv),
          doi: scalar(doi),
          isbn: scalar(isbn),
          issn: scalar(issn),
          publisher: scalar(publisher),
          journal: scalar(journal),
          conference: scalar(conference),
          volume: scalar(volume),
          issue: scalar(issue),
          pages: scalar(pages),
          year: yearValue,
          date: scalar(date),
          language: scalar(language),
          citation_count: citationValue,
          impact_factor: factorValue,
          quartile: quartile || null,
          indexing: csvToList(indexingCsv),
          publisher_url: scalar(publisherUrl),
          notes: scalar(notes),
          tags: csvToList(tagsCsv),
          collections: csvToList(collectionsCsv),
          ...(linksPayload ? { links: linksPayload } : {}),
        });
        onSaved({ mode: "edit", publication: saved });
      } else {
        const saved = await createPublication({
          title: title.trim(),
          publication_type: publicationType,
          uploaded_by: uploadedBy.trim(),
          ...(pipelineStage ? { pipeline_stage: pipelineStage } : {}),
          ...(authorsPayload?.length ? { authors: authorsPayload } : {}),
          affiliations: csvToList(affiliationsCsv),
          ...(abstract.trim() ? { abstract: abstract.trim() } : {}),
          keywords: csvToList(keywordsCsv),
          ...(doi.trim() ? { doi: doi.trim() } : {}),
          ...(isbn.trim() ? { isbn: isbn.trim() } : {}),
          ...(issn.trim() ? { issn: issn.trim() } : {}),
          ...(publisher.trim() ? { publisher: publisher.trim() } : {}),
          ...(journal.trim() ? { journal: journal.trim() } : {}),
          ...(conference.trim() ? { conference: conference.trim() } : {}),
          ...(volume.trim() ? { volume: volume.trim() } : {}),
          ...(issue.trim() ? { issue: issue.trim() } : {}),
          ...(pages.trim() ? { pages: pages.trim() } : {}),
          ...(yearValue != null ? { year: yearValue } : {}),
          ...(date.trim() ? { date: date.trim() } : {}),
          ...(language.trim() ? { language: language.trim() } : {}),
          ...(citationValue != null ? { citation_count: citationValue } : {}),
          ...(factorValue != null ? { impact_factor: factorValue } : {}),
          ...(quartile ? { quartile } : {}),
          indexing: csvToList(indexingCsv),
          ...(publisherUrl.trim() ? { publisher_url: publisherUrl.trim() } : {}),
          ...(notes.trim() ? { notes: notes.trim() } : {}),
          tags: csvToList(tagsCsv),
          collections: csvToList(collectionsCsv),
          ...(linksPayload ? { links: linksPayload } : {}),
        });
        onSaved({ mode: "create", publication: saved });
      }
    } catch (error) {
      setFormError(toErrorMessage(error, "Failed to save the publication."));
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const selectClass = fieldClass(undefined);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submitting) onClose();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="publication-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-2xl flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="publication-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {isEdit ? "Edit Publication" : "Add Publication"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {formError ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}

          {/* ---------------------------------------------------------- basics */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Basics
            </legend>
            <Field label="Title *" error={errorFor("title")}>
              <input
                ref={firstFieldRef}
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Deep Learning for Catalysis"
                aria-invalid={Boolean(errorFor("title"))}
                className={fieldClass(errorFor("title"))}
              />
            </Field>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Publication type *">
                <select
                  value={publicationType}
                  onChange={(event) => setPublicationType(event.target.value as PublicationTypeValue)}
                  aria-label="Publication type"
                  className={selectClass}
                >
                  {PUBLICATION_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {titleCase(type)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Pipeline stage">
                <select
                  value={pipelineStage}
                  onChange={(event) => setPipelineStage(event.target.value as PipelineStage | "")}
                  aria-label="Pipeline stage"
                  className={selectClass}
                >
                  <option value="">—</option>
                  {PIPELINE_STAGES.map((stage) => (
                    <option key={stage} value={stage}>
                      {titleCase(stage)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Year" error={errorFor("year")}>
                <input
                  type="number"
                  inputMode="numeric"
                  value={year}
                  onChange={(event) => setYear(event.target.value)}
                  placeholder="2026"
                  aria-invalid={Boolean(errorFor("year"))}
                  className={fieldClass(errorFor("year"))}
                />
              </Field>
            </div>

            <Field
              label="DOI"
              error={errorFor("doi")}
              hint={isEdit ? undefined : "Paste a DOI and fetch Crossref metadata to pre-fill the form."}
            >
              <div className="flex gap-2">
                <input
                  type="text"
                  value={doi}
                  onChange={(event) => setDoi(event.target.value)}
                  placeholder="10.1038/s41586-020-2649-2"
                  aria-invalid={Boolean(errorFor("doi"))}
                  className={cn(fieldClass(errorFor("doi")), "font-mono")}
                />
                <button
                  type="button"
                  onClick={handleDoiLookup}
                  disabled={!doi.trim() || lookupState.kind === "loading"}
                  title="Fetch metadata from Crossref"
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {lookupState.kind === "loading" ? <Spinner /> : <Crosshair className="h-4 w-4" aria-hidden="true" />}
                  Fetch
                </button>
              </div>
            </Field>
            {lookupState.kind === "found" || lookupState.kind === "error" ? (
              <p
                role="status"
                className={cn(
                  "rounded-lg px-3 py-2 text-xs",
                  lookupState.kind === "found"
                    ? "bg-[var(--success-subtle)] text-[var(--success)]"
                    : "bg-[var(--danger-subtle)] text-[var(--danger)]",
                )}
              >
                {lookupState.message}
              </p>
            ) : null}
          </fieldset>

          {/* --------------------------------------------------------- authors */}
          <fieldset className="space-y-2">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Authors
            </legend>
            {authors.map((author, index) => {
              const rowError = errorFor(`author-${index}`);
              return (
                <div key={index} className="rounded-lg border border-[var(--border-subtle)] p-2.5">
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_auto]">
                    <input
                      type="text"
                      value={author.name}
                      onChange={(event) => setAuthor(index, { name: event.target.value })}
                      placeholder="Family, Given"
                      aria-label={`Author ${index + 1} name`}
                      aria-invalid={Boolean(rowError)}
                      className={fieldClass(rowError)}
                    />
                    <input
                      type="text"
                      value={author.orcid}
                      onChange={(event) => setAuthor(index, { orcid: event.target.value })}
                      placeholder="ORCID 0000-0002-1825-0097 (optional)"
                      aria-label={`Author ${index + 1} ORCID`}
                      aria-invalid={Boolean(rowError)}
                      className={cn(fieldClass(rowError), "font-mono")}
                    />
                    <div className="flex items-center gap-2">
                      <label
                        className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-[var(--text-secondary)]"
                        title="Corresponding author"
                      >
                        <input
                          type="checkbox"
                          checked={author.corresponding}
                          onChange={(event) => setAuthor(index, { corresponding: event.target.checked })}
                          className="h-3.5 w-3.5 accent-[var(--accent)]"
                        />
                        <Star
                          className={cn("h-3.5 w-3.5", author.corresponding ? "fill-[var(--warning)] text-[var(--warning)]" : "text-[var(--text-tertiary)]")}
                          aria-hidden="true"
                        />
                        Corr.
                      </label>
                      <button
                        type="button"
                        onClick={() => setAuthors((rows) => rows.filter((_, i) => i !== index))}
                        disabled={authors.length <= 1}
                        aria-label={`Remove author ${index + 1}`}
                        className="rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--danger)] disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                  <input
                    type="text"
                    value={author.affiliation}
                    onChange={(event) => setAuthor(index, { affiliation: event.target.value })}
                    placeholder="Affiliation (optional)"
                    aria-label={`Author ${index + 1} affiliation`}
                    className={cn(fieldClass(undefined), "mt-2")}
                  />
                  {rowError ? (
                    <p role="alert" className="mt-1 text-xs text-[var(--danger)]">
                      {rowError}
                    </p>
                  ) : null}
                </div>
              );
            })}
            <button
              type="button"
              onClick={() => setAuthors((rows) => [...rows, { ...EMPTY_AUTHOR }])}
              className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-[var(--border-strong)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add author
            </button>
          </fieldset>

          {/* ----------------------------------------------------------- venue */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Venue &amp; publication details
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Journal">
                <input type="text" value={journal} onChange={(event) => setJournal(event.target.value)} placeholder="Nature Catalysis" className={selectClass} />
              </Field>
              <Field label="Conference">
                <input type="text" value={conference} onChange={(event) => setConference(event.target.value)} placeholder="ICML 2026" className={selectClass} />
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Volume">
                <input type="text" value={volume} onChange={(event) => setVolume(event.target.value)} placeholder="7" className={selectClass} />
              </Field>
              <Field label="Issue">
                <input type="text" value={issue} onChange={(event) => setIssue(event.target.value)} placeholder="3" className={selectClass} />
              </Field>
              <Field label="Pages">
                <input type="text" value={pages} onChange={(event) => setPages(event.target.value)} placeholder="201-214" className={selectClass} />
              </Field>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Publication date" hint="YYYY, YYYY-MM, or YYYY-MM-DD">
                <input type="text" value={date} onChange={(event) => setDate(event.target.value)} placeholder="2026-03-15" className={cn(selectClass, "font-mono")} />
              </Field>
              <Field label="Language">
                <input type="text" value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="en" className={selectClass} />
              </Field>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="ISSN">
                <input type="text" value={issn} onChange={(event) => setIssn(event.target.value)} placeholder="2520-1158" className={cn(selectClass, "font-mono")} />
              </Field>
              <Field label="ISBN">
                <input type="text" value={isbn} onChange={(event) => setIsbn(event.target.value)} placeholder="978-3-16-148410-0" className={cn(selectClass, "font-mono")} />
              </Field>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Publisher">
                <input type="text" value={publisher} onChange={(event) => setPublisher(event.target.value)} placeholder="Springer Nature" className={selectClass} />
              </Field>
              <Field label="Publisher URL" error={errorFor("publisherUrl")}>
                <input type="url" value={publisherUrl} onChange={(event) => setPublisherUrl(event.target.value)} placeholder="https://doi.org/…" aria-invalid={Boolean(errorFor("publisherUrl"))} className={fieldClass(errorFor("publisherUrl"))} />
              </Field>
            </div>
          </fieldset>

          {/* ---------------------------------------------------------- metrics */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Metrics &amp; indexing
            </legend>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Quartile">
                <select value={quartile} onChange={(event) => setQuartile(event.target.value as Quartile | "")} className={selectClass}>
                  <option value="">—</option>
                  {QUARTILES.map((q) => (
                    <option key={q} value={q}>
                      {q}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Citations" error={errorFor("citationCount")}>
                <input type="number" inputMode="numeric" value={citationCount} onChange={(event) => setCitationCount(event.target.value)} placeholder="0" aria-invalid={Boolean(errorFor("citationCount"))} className={fieldClass(errorFor("citationCount"))} />
              </Field>
              <Field label="Impact factor" error={errorFor("impactFactor")}>
                <input type="text" inputMode="decimal" value={impactFactor} onChange={(event) => setImpactFactor(event.target.value)} placeholder="37.8" aria-invalid={Boolean(errorFor("impactFactor"))} className={fieldClass(errorFor("impactFactor"))} />
              </Field>
            </div>
            <Field label="Indexing" hint="Comma-separated: SCOPUS, WOS, PubMed">
              <input type="text" value={indexingCsv} onChange={(event) => setIndexingCsv(event.target.value)} placeholder="SCOPUS, WOS" className={selectClass} />
            </Field>
          </fieldset>

          {/* ----------------------------------------------------- organisation */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Organisation
            </legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Field label="Keywords" hint="Comma-separated">
                <input type="text" value={keywordsCsv} onChange={(event) => setKeywordsCsv(event.target.value)} placeholder="catalysis, deep learning" className={selectClass} />
              </Field>
              <Field label="Tags" hint="Comma-separated">
                <input type="text" value={tagsCsv} onChange={(event) => setTagsCsv(event.target.value)} placeholder="ml" className={selectClass} />
              </Field>
              <Field label="Collections" hint="Comma-separated">
                <input type="text" value={collectionsCsv} onChange={(event) => setCollectionsCsv(event.target.value)} placeholder="Catalysis Papers" className={selectClass} />
              </Field>
            </div>
            <Field label="Affiliations" hint="Comma-separated, used on reports">
              <input type="text" value={affiliationsCsv} onChange={(event) => setAffiliationsCsv(event.target.value)} placeholder="Gurugram University" className={selectClass} />
            </Field>
            <Field label="Abstract">
              <textarea rows={3} value={abstract} onChange={(event) => setAbstract(event.target.value)} className={cn(selectClass, "resize-y")} />
            </Field>
            <Field label="Notes">
              <textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Private notes — e.g. include in the 2026 annual report" className={cn(selectClass, "resize-y")} />
            </Field>
          </fieldset>

          {/* ------------------------------------------------------ linked objects */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              Linked objects
            </legend>
            <p className="text-xs text-[var(--text-tertiary)]">
              Powers object-centric lenses (“papers funded by Grant X”). Ctrl/Cmd-click to
              select several; only groups you change are sent on edit.
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {LINK_GROUPS.map(({ value: group, label }) => {
                const options = optionsFor(group);
                return (
                  <Field key={group} label={label} hint={options.length ? undefined : "No matching objects yet"}>
                    <select
                      multiple
                      size={3}
                      value={linkSelections[group]}
                      onChange={(event) => {
                        markTouched(group);
                        setLinkSelections((previous) => ({
                          ...previous,
                          [group]: Array.from(event.target.selectedOptions).map((option) => option.value),
                        }));
                      }}
                      aria-label={`Linked ${label.toLowerCase()}`}
                      className={cn(selectClass, "h-auto")}
                    >
                      {options.map((object) => (
                        <option key={object.id} value={object.id}>
                          {object.title}
                        </option>
                      ))}
                    </select>
                  </Field>
                );
              })}
            </div>
          </fieldset>

          {/* ----------------------------------------------------- housekeeping */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              {isEdit ? "Status" : "Attribution"}
            </legend>
            {isEdit ? (
              <Field label="Status">
                <select value={status} onChange={(event) => setStatus(event.target.value as PublicationStatus)} className={cn(selectClass, "sm:max-w-xs")}>
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="archived">Archived</option>
                </select>
              </Field>
            ) : (
              <Field label="Added by *" error={errorFor("uploadedBy")} hint="Your identity on the record, e.g. faculty:1">
                <input type="text" value={uploadedBy} onChange={(event) => setUploadedBy(event.target.value)} placeholder="faculty:1" aria-invalid={Boolean(errorFor("uploadedBy"))} className={cn(fieldClass(errorFor("uploadedBy")), "sm:max-w-xs")} />
              </Field>
            )}
          </fieldset>
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[var(--border-subtle)] px-5 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? <Spinner /> : null}
            {submitting ? "Saving…" : isEdit ? "Save changes" : "Add publication"}
          </button>
        </div>
      </form>
    </div>
  );
}
