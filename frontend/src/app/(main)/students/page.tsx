"use client";

import { useCallback, useEffect, useState } from "react";
import { FileDown, FileUp, Filter, Plus, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { SearchBar } from "@/components/features/objects/SearchBar";
import { Pagination } from "@/components/features/objects/Pagination";
import { EmptyState } from "@/components/features/objects/EmptyState";
import {
  StudentModal,
  type StudentSaveResult,
} from "@/components/features/students/StudentModal";
import { ImportStudentsModal } from "@/components/features/students/ImportStudentsModal";
import { StudentTable } from "@/components/features/students/StudentTable";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useStudents } from "@/hooks/useStudents";
import { studentsExportUrl } from "@/lib/api/students";
import {
  DEFAULT_STUDENT_PAGE_SIZE,
  STUDENT_TYPES,
} from "@/lib/students/constants";
import { consumeFlash } from "@/lib/objects/flash";
import { titleCase } from "@/lib/utils";
import type { StudentStatus, StudentTypeValue } from "@/types";

const SELECT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] focus:border-[var(--accent)] focus:outline-none";

const INPUT_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

const STATUSES: StudentStatus[] = ["draft", "active", "archived"];

export default function StudentsPage() {
  const [search, setSearch] = useState("");
  const [studentType, setStudentType] = useState<StudentTypeValue | "all">("all");
  const [programme, setProgramme] = useState("");
  const [semesterText, setSemesterText] = useState("");
  const [section, setSection] = useState("");
  const [status, setStatus] = useState<StudentStatus | "all">("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const { toast, show, dismiss } = useToast();

  const semester =
    semesterText.trim() && /^\d+$/.test(semesterText.trim()) ? Number(semesterText.trim()) : null;

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
  } = useStudents({
    pageSize: DEFAULT_STUDENT_PAGE_SIZE,
    search,
    studentType: studentType === "all" ? null : studentType,
    programme: programme.trim() || null,
    semester,
    section: section.trim() || null,
    status: status === "all" ? null : status,
  });

  // Pick up a message handed over by another page (e.g. "student deleted").
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const handleSaved = useCallback(
    (result: StudentSaveResult) => {
      setModalOpen(false);
      refresh();
      show(
        "success",
        `“${result.student.name}” ${result.mode === "edit" ? "updated" : "admitted"} successfully.`,
      );
    },
    [refresh, show],
  );

  const showTable = loading || items.length > 0;
  const filtering = searchActive || filterActive;

  /** "Export what I see": the current search + filters ride the export URL. */
  const exportFilters = {
    q: search.trim() || undefined,
    studentType: studentType === "all" ? null : studentType,
    programme: programme.trim() || null,
    semester,
    section: section.trim() || null,
    status: status === "all" ? null : status,
  };

  const clearFilters = () => {
    setSearch("");
    setStudentType("all");
    setProgramme("");
    setSemesterText("");
    setSection("");
    setStatus("all");
  };

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <Breadcrumbs items={[{ label: "Dashboard", href: "/" }, { label: "Students" }]} />

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div>
              <h1 className="text-xl font-semibold">Students</h1>
              <p className="text-sm text-[var(--text-tertiary)]" aria-live="polite">
                {loading
                  ? "Loading…"
                  : error
                    ? "Unavailable"
                    : filtering
                      ? `${total} match${total === 1 ? "" : "es"}`
                      : `${total} student${total === 1 ? "" : "s"}`}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <SearchBar
                value={search}
                onChange={setSearch}
                busy={isSearching}
                placeholder="Search name, roll no, email…"
              />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  disabled={loading || refreshing}
                  aria-label="Refresh students"
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
                  <Plus className="h-4 w-4" aria-hidden="true" /> Add Student
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
              value={studentType}
              onChange={(event) =>
                setStudentType(event.target.value as StudentTypeValue | "all")
              }
              aria-label="Filter by student type"
              className={SELECT_CLASS}
            >
              <option value="all">All types</option>
              {STUDENT_TYPES.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={programme}
              onChange={(event) => setProgramme(event.target.value)}
              placeholder="Programme"
              aria-label="Filter by programme"
              className={`${INPUT_CLASS} w-44`}
            />
            <input
              type="number"
              inputMode="numeric"
              value={semesterText}
              onChange={(event) => setSemesterText(event.target.value)}
              placeholder="Sem"
              aria-label="Filter by semester"
              className={`${INPUT_CLASS} w-20`}
            />
            <input
              type="text"
              value={section}
              onChange={(event) => setSection(event.target.value)}
              placeholder="Section"
              aria-label="Filter by section"
              className={`${INPUT_CLASS} w-24`}
            />
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as StudentStatus | "all")}
              aria-label="Filter by status"
              className={SELECT_CLASS}
            >
              <option value="all">All statuses</option>
              {STATUSES.map((option) => (
                <option key={option} value={option}>
                  {titleCase(option)}
                </option>
              ))}
            </select>

            <span
              className="mx-1 hidden h-5 w-px bg-[var(--border-subtle)] sm:inline-block"
              aria-hidden="true"
            />
            <a
              href={studentsExportUrl(exportFilters)}
              download="students.csv"
              aria-label="Export students as CSV"
              title={filtering ? "Export filtered list as CSV" : "Export all students as CSV"}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
            >
              <FileDown className="h-4 w-4" aria-hidden="true" /> Export CSV
            </a>
          </div>

          <div className="mt-6 space-y-4">
            {error ? (
              <EmptyState
                title="Could not load students"
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
                <StudentTable students={items} loading={loading} />
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
                title="No matching students"
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
                title="No students yet"
                description="Admit your first student, or import the whole class list as CSV — headers auto-map (Roll No, Name, Email, Section, Programme, Semester)."
                action={
                  <div className="mt-3 flex flex-wrap justify-center gap-2">
                    <button
                      type="button"
                      onClick={() => setModalOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                    >
                      <Plus className="h-4 w-4" aria-hidden="true" /> Add Student
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

      <StudentModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={handleSaved} />
      <ImportStudentsModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={(report) => {
          refresh();
          if (report.created.length > 0) {
            show(
              "success",
              `Imported ${report.created.length} student${report.created.length === 1 ? "" : "s"}` +
                (report.skipped_duplicates.length
                  ? ` (${report.skipped_duplicates.length} duplicate${report.skipped_duplicates.length === 1 ? "" : "s"} skipped)`
                  : "") +
                ".",
            );
          } else if (report.skipped_duplicates.length > 0) {
            show(
              "warning",
              `Nothing imported — ${report.skipped_duplicates.length} duplicate${report.skipped_duplicates.length === 1 ? "" : "s"} skipped.`,
            );
          }
        }}
      />
      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
