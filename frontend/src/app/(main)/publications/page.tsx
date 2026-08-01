"use client";

import { useCallback, useEffect, useState } from "react";
import { FileDown, FileUp, Filter, Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { PublicationTable } from "@/components/features/publications/PublicationTable";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import {
  PublicationModal,
  type PublicationSaveResult,
} from "@/components/features/publications/PublicationModal";
import { ImportModal } from "@/components/features/publications/ImportModal";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { usePublications } from "@/hooks/usePublications";
import { exportPublicationsUrl } from "@/lib/api/publications";
import {
  BIBLIOGRAPHY_FORMATS,
  DEFAULT_PUB_PAGE_SIZE,
  PIPELINE_STAGES,
  PUBLICATION_TYPES,
  QUARTILES,
} from "@/lib/publications/constants";
import { consumeFlash } from "@/lib/objects/flash";
import { titleCase } from "@/lib/utils";
import type {
  PipelineStage,
  PublicationTypeValue,
  Quartile,
} from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

export default function PublicationsPage() {
  const [search, setSearch] = useState("");
  const [type, setType] = useState<PublicationTypeValue | "all">("all");
  const [quartile, setQuartile] = useState<Quartile | "all">("all");
  const [stage, setStage] = useState<PipelineStage | "all">("all");
  const [yearText, setYearText] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const { toast, show, dismiss } = useToast();

  const year = yearText.trim() && /^\d{4}$/.test(yearText.trim()) ? Number(yearText.trim()) : null;

  const {
    items,
    total,
    page,
    pageSize,
    loading,
    refreshing,
    error,
    isSearching,
    searchActive,
    filterActive,
    setPage,
    refresh,
  } = usePublications({
    pageSize: DEFAULT_PUB_PAGE_SIZE,
    search,
    type: type === "all" ? null : type,
    quartile: quartile === "all" ? null : quartile,
    pipelineStage: stage === "all" ? null : stage,
    year,
  });

  // Pick up a message handed over by another page (e.g. "publication deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: PublicationSaveResult) => {
      setModalOpen(false);
      refresh();
      show(
        "success",
        `“${result.publication.title}” ${result.mode === "edit" ? "updated" : "added"} successfully.`,
      );
    },
    [refresh, show],
  );

  const showTable = loading || items.length > 0;
  const filtering = searchActive || filterActive;

  /** "Export what I see": the current search + filters ride the export URL. */
  const exportFilters = {
    q: search.trim() || undefined,
    publicationType: type === "all" ? null : type,
    quartile: quartile === "all" ? null : quartile,
    pipelineStage: stage === "all" ? null : stage,
    year,
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs
            items={[{ label: "Dashboard", href: "/" }, { label: "Publications" }]}
          />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Publications</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} publication${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search title, author, DOI, journal…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={loading || refreshing}
                  aria-label="Refresh publications"
                  title="Refresh"
                  className="inline-flex items-center justify-center rounded-lg border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                    aria-hidden="true"
                  />
                </button>
                <button
                  type="button"
                  onClick={() => setImportOpen(true)}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                >
                  <FileUp className="h-4 w-4" aria-hidden="true" /> Import
                </button>
                <button
                  type="button"
                  onClick={() => setModalOpen(true)}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] sm:flex-none"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" /> Add Publication
                </button>
              </div>
            </div>
          </div>

          {/* Filters + export */}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" aria-hidden="true" /> Filters:
            </div>
            <select
              value={type}
              onChange={(event) => setType(event.target.value as PublicationTypeValue | "all")}
              aria-label="Filter by publication type"
              className={SELECT_CLASS}
            >
              <option value="all">All types</option>
              {PUBLICATION_TYPES.map((option) => (
                <option key={option} value={option}>
                  {titleCase(option)}
                </option>
              ))}
            </select>
            <select
              value={quartile}
              onChange={(event) => setQuartile(event.target.value as Quartile | "all")}
              aria-label="Filter by quartile"
              className={SELECT_CLASS}
            >
              <option value="all">All quartiles</option>
              {QUARTILES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <select
              value={stage}
              onChange={(event) => setStage(event.target.value as PipelineStage | "all")}
              aria-label="Filter by pipeline stage"
              className={SELECT_CLASS}
            >
              <option value="all">All stages</option>
              {PIPELINE_STAGES.map((option) => (
                <option key={option} value={option}>
                  {titleCase(option)}
                </option>
              ))}
            </select>
            <input
              type="number"
              inputMode="numeric"
              value={yearText}
              onChange={(event) => setYearText(event.target.value)}
              placeholder="Year"
              aria-label="Filter by year"
              className="w-24 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
            />

            <span className="mx-1 hidden h-5 w-px bg-[var(--border-subtle)] sm:inline-block" aria-hidden="true" />
            <span className="inline-flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <FileDown className="h-4 w-4" aria-hidden="true" /> Export:
            </span>
            {BIBLIOGRAPHY_FORMATS.map(({ value, label }) => (
              <a
                key={value}
                href={exportPublicationsUrl(value, exportFilters)}
                download={`publications.${value === "bibtex" ? "bib" : value}`}
                aria-label={`Export as ${label}`}
                title={filtering ? `Export filtered list as ${label}` : `Export all as ${label}`}
                className="rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
              >
                {label}
              </a>
            ))}
          </div>

          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load publications"
                description={error}
                action={
                  <button
                    type="button"
                    onClick={refresh}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" /> Try again
                  </button>
                }
              />
            ) : showTable ? (
              <>
                <PublicationTable publications={items} loading={loading} refreshing={refreshing} />
                {!loading ? (
                  <Pagination
                    page={page}
                    pageSize={pageSize}
                    total={total}
                    onPageChange={setPage}
                    disabled={refreshing}
                  />
                ) : null}
              </>
            ) : filtering ? (
              <EmptyState
                title="No matching publications"
                description="Nothing matches your search and filters. Try different terms or clear them."
                action={
                  <button
                    type="button"
                    onClick={() => {
                      setSearch("");
                      setType("all");
                      setQuartile("all");
                      setStage("all");
                      setYearText("");
                    }}
                    className="mt-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                  >
                    Clear filters
                  </button>
                }
              />
            ) : (
              <EmptyState
                title="No publications yet"
                description="Add your first publication, or import your library as BibTeX, RIS, or CSV."
                action={
                  <div className="mt-3 flex flex-wrap justify-center gap-2">
                    <button
                      type="button"
                      onClick={() => setModalOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                    >
                      <Plus className="h-4 w-4" aria-hidden="true" /> Add Publication
                    </button>
                    <button
                      type="button"
                      onClick={() => setImportOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                    >
                      <FileUp className="h-4 w-4" aria-hidden="true" /> Import
                    </button>
                  </div>
                }
              />
            )}
          </div>
        </main>
      </div>

      <PublicationModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
      />
      <ImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={(report) => {
          refresh();
          if (report.created.length > 0) {
            show(
              "success",
              `Imported ${report.created.length} publication${report.created.length === 1 ? "" : "s"}` +
                (report.duplicates.length ? ` (${report.duplicates.length} duplicate${report.duplicates.length === 1 ? "" : "s"} skipped)` : "") +
                ".",
            );
          } else if (report.duplicates.length > 0) {
            show("warning", `Nothing imported — ${report.duplicates.length} duplicate${report.duplicates.length === 1 ? "" : "s"} skipped.`);
          }
        }}
      />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
