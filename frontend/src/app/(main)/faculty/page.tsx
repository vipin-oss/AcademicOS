"use client";

import { useCallback, useEffect, useState } from "react";
import { Filter, Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import {
  FacultyModal,
  type FacultySaveResult,
} from "@/components/features/faculty/FacultyModal";
import { FacultyTable } from "@/components/features/faculty/FacultyTable";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useFaculties } from "@/hooks/useFaculties";
import {
  DEFAULT_FACULTY_PAGE_SIZE,
  DESIGNATIONS,
  EMPLOYMENT_TYPES,
} from "@/lib/faculty/constants";
import { consumeFlash } from "@/lib/objects/flash";
import type { FacultyEmploymentType, ResearchObjectStatus } from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

const INPUT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

/**
 * The Faculty directory (PART 1 registry + PART 7 search & filters).
 */
export default function FacultyPage() {
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [designation, setDesignation] = useState("");
  const [employmentType, setEmploymentType] = useState<FacultyEmploymentType | "all">("all");
  const [status, setStatus] = useState<ResearchObjectStatus | "all">("all");
  const [modalOpen, setModalOpen] = useState(false);
  const { toast, show, dismiss } = useToast();

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
  } = useFaculties({
    pageSize: DEFAULT_FACULTY_PAGE_SIZE,
    search,
    department: department.trim() || null,
    designation: designation || null,
    employmentType: employmentType === "all" ? null : employmentType,
    status: status === "all" ? null : status,
  });

  // Pick up a message handed over by another page (e.g. "faculty deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: FacultySaveResult) => {
      setModalOpen(false);
      refresh();
      show(
        "success",
        `"${result.faculty.name}" ${result.mode === "edit" ? "updated" : "added"} successfully.`,
      );
    },
    [refresh, show],
  );

  const showTable = loading || items.length > 0;
  const filtering = searchActive || filterActive;

  const clearFilters = () => {
    setSearch("");
    setDepartment("");
    setDesignation("");
    setEmploymentType("all");
    setStatus("all");
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Faculty" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Faculty Directory</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} faculty member${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search name, specialization, research area…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={loading || refreshing}
                  aria-label="Refresh faculty"
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
                  onClick={() => setModalOpen(true)}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] sm:flex-none"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" /> New Faculty
                </button>
              </div>
            </div>
          </div>

          {/* PART 7 filters */}
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-sm text-[var(--text-tertiary)]">
              <Filter className="h-4 w-4" aria-hidden="true" /> Filters:
            </div>
            <input
              type="text"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              placeholder="Department"
              aria-label="Filter by department"
              className={`${INPUT_CLASS} w-40`}
            />
            <select
              value={designation}
              onChange={(event) => setDesignation(event.target.value)}
              aria-label="Filter by designation"
              className={SELECT_CLASS}
            >
              <option value="">All designations</option>
              {DESIGNATIONS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <select
              value={employmentType}
              onChange={(event) =>
                setEmploymentType(event.target.value as FacultyEmploymentType | "all")
              }
              aria-label="Filter by employment type"
              className={SELECT_CLASS}
            >
              <option value="all">All employment types</option>
              {EMPLOYMENT_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as ResearchObjectStatus | "all")
              }
              aria-label="Filter by status"
              className={SELECT_CLASS}
            >
              <option value="all">All statuses</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          {/* Faculty directory */}
          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load faculty"
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
                <FacultyTable items={items} loading={loading} />
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
                title="No matching faculty"
                description="Nothing matches your search and filters. Try different terms or clear them."
                action={
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="mt-3 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                  >
                    Clear filters
                  </button>
                }
              />
            ) : (
              <EmptyState
                title="No faculty members yet"
                description="Add your first faculty member — the directory powers supervision, teaching load, research teams and accreditation reports."
                action={
                  <button
                    type="button"
                    onClick={() => setModalOpen(true)}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> New Faculty
                  </button>
                }
              />
            )}
          </div>
        </main>
      </div>

      <FacultyModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
