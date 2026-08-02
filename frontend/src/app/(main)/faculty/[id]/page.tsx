"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  Clock,
  ImagePlus,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { FacultyHeader } from "@/components/features/faculty/FacultyHeader";
import { FacultyDashboardCards } from "@/components/features/faculty/FacultyDashboardCards";
import { AcademicProfilePanel } from "@/components/features/faculty/AcademicProfilePanel";
import { ResearchPanel } from "@/components/features/faculty/ResearchPanel";
import { SupervisionPanel } from "@/components/features/faculty/SupervisionPanel";
import { TeachingLoadPanel } from "@/components/features/faculty/TeachingLoadPanel";
import {
  FacultyModal,
  type FacultySaveResult,
} from "@/components/features/faculty/FacultyModal";
import { ObjectPublications } from "@/components/features/publications/ObjectPublications";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { ChipList } from "@/components/features/publications/PublicationBadge";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useFaculty } from "@/hooks/useFaculty";
import { attachFacultyPhoto, deleteFaculty } from "@/lib/api/faculty";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDateTime, titleCase } from "@/lib/utils";

/**
 * Next.js hands the dynamic segment back percent-encoded. This is the ONE and
 * ONLY decode in the whole flow — the hook and the API layer forward the
 * decoded id untouched (same encoding contract as every module).
 */
function decodeRouteId(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] ?? "" : raw ?? "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value; // malformed escape sequence — use the raw segment
  }
}

/** The faculty workspace: header, dashboard, profile, research, supervision, teaching and lenses. */
export default function FacultyWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const facultyId = decodeRouteId(params?.id);

  const {
    faculty,
    loading,
    refreshing,
    error,
    notFound,
    applyUpdate,
    refresh,
  } = useFaculty(facultyId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [photoProgress, setPhotoProgress] = useState<number | null>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);

  const handleSaved = useCallback(
    (result: FacultySaveResult) => {
      setEditOpen(false);
      applyUpdate(result.faculty);
      show("success", "Faculty record updated successfully.");
    },
    [applyUpdate, show],
  );

  const handlePhotoPicked = useCallback(
    async (file: File | undefined) => {
      if (!faculty || !file || uploadingPhoto) return;
      setUploadingPhoto(true);
      setPhotoProgress(0);
      try {
        const updated = await attachFacultyPhoto(faculty.id, file, {
          uploadedBy: faculty.uploaded_by || "faculty:ui",
          onProgress: (progress) => setPhotoProgress(progress.percent),
        });
        applyUpdate(updated);
        show("success", "Profile photo updated.");
      } catch (err) {
        if ((err as { kind?: string })?.kind !== "aborted") {
          show("error", toErrorMessage(err, "Failed to upload the photo."));
        }
      } finally {
        setUploadingPhoto(false);
        setPhotoProgress(null);
      }
    },
    [faculty, uploadingPhoto, applyUpdate, show],
  );

  const handleDelete = useCallback(async () => {
    if (!faculty || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteFaculty(faculty.id);
      setFlash({ kind: "success", message: `"${faculty.name}" was deleted.` });
      setConfirmOpen(false);
      router.push("/faculty");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this faculty member."));
      setDeleting(false);
    }
  }, [faculty, deleting, router]);

  const actions = faculty ? (
    <>
      <button
        type="button"
        onClick={() => photoInputRef.current?.click()}
        disabled={deleting || uploadingPhoto}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {uploadingPhoto ? <Spinner /> : <ImagePlus className="h-4 w-4" aria-hidden="true" />}
        {uploadingPhoto
          ? `Uploading… ${photoProgress ?? 0}%`
          : faculty.photo_file_name
            ? "Replace photo"
            : "Add photo"}
      </button>
      <button
        type="button"
        onClick={() => setEditOpen(true)}
        disabled={deleting || uploadingPhoto}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Pencil className="h-4 w-4" aria-hidden="true" /> Edit
      </button>
      <button
        type="button"
        onClick={() => {
          setDeleteError(null);
          setConfirmOpen(true);
        }}
        disabled={deleting || uploadingPhoto}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger)] px-3 py-2 text-sm font-medium text-[var(--danger)] transition-colors hover:bg-[var(--danger-subtle)] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {deleting ? <Spinner /> : <Trash2 className="h-4 w-4" aria-hidden="true" />}
        {deleting ? "Deleting…" : "Delete"}
      </button>
    </>
  ) : null;

  return (
    <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => router.back()}
              className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--accent)]"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back
            </button>
            {faculty ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh faculty"
                title="Refresh"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
            ) : null}
          </div>

          <Breadcrumbs
            items={[
              { label: "Dashboard", href: "/" },
              { label: "Faculty", href: "/faculty" },
              { label: faculty?.name ?? (notFound ? "Not found" : "Faculty") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Faculty member not found"
                description="This faculty record may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/faculty")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Faculty
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this faculty member"
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
            ) : faculty ? (
              <div className="space-y-4">
                <FacultyHeader faculty={faculty} actions={actions} />

                {/* PART 6 dashboard cards (server-computed stats) */}
                <FacultyDashboardCards stats={faculty.stats} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <AcademicProfilePanel faculty={faculty} />

                  <ResearchPanel faculty={faculty} />

                  <SupervisionPanel
                    current={faculty.supervision?.current ?? []}
                    completed={faculty.supervision?.completed ?? []}
                  />

                  <TeachingLoadPanel faculty={faculty} />

                  <Section title="Contact & Registry">
                    <dl className="text-sm">
                      <DetailRow label="Email" value={faculty.email || "—"} />
                      <DetailRow label="Mobile" value={faculty.mobile || "—"} />
                      <DetailRow label="Office" value={faculty.office || "—"} />
                      <DetailRow label="Qualification" value={faculty.qualification || "—"} />
                      <DetailRow
                        label="Research interests"
                        value={<ChipList items={faculty.research_interests} />}
                      />
                      <DetailRow label="Notes" value={faculty.notes || "—"} />
                    </dl>
                  </Section>

                  <Section title="Committee Memberships">
                    {(faculty.links?.committees ?? []).length === 0 ? (
                      <p className="text-sm text-[var(--text-tertiary)]">
                        No committee memberships — edit the record to link committees.
                      </p>
                    ) : (
                      <ul className="space-y-1.5 text-sm">
                        {(faculty.links?.committees ?? []).map((committee) => (
                          <li key={committee.id}>
                            <Link
                              href={`/objects/${encodeURIComponent(committee.id)}`}
                              className="font-medium text-[var(--text-primary)] hover:text-[var(--accent)] hover:underline"
                            >
                              {committee.title}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Section>

                  <Section title="Publications">
                    <ObjectPublications objectId={faculty.id} />
                  </Section>

                  <Section title="Documents">
                    <ObjectDocuments objectId={faculty.id} />
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Faculty ID" value={faculty.id} mono />
                      <DetailRow label="Added by" value={faculty.uploaded_by || "—"} />
                      <DetailRow label="Added at" value={formatDateTime(faculty.created_at)} />
                      <DetailRow
                        label="Last updated"
                        value={
                          faculty.updated_at ? (
                            formatDateTime(faculty.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${faculty.version}`} />
                    </dl>
                  </Section>

                  <Section title="Audit Timeline">
                    <ol className="space-y-3 text-sm">
                      <li className="flex gap-3">
                        <Clock
                          className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-tertiary)]"
                          aria-hidden="true"
                        />
                        <div>
                          <p className="text-[var(--text-primary)]">Faculty record created</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(faculty.created_at)} ·{" "}
                            {faculty.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(faculty.events ?? []).map((event, index) => (
                        <li key={`${event}-${index}`} className="flex gap-3">
                          <ActivityIcon
                            className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-tertiary)]"
                            aria-hidden="true"
                          />
                          <p className="text-[var(--text-primary)]">{titleCase(event)}</p>
                        </li>
                      ))}
                    </ol>
                  </Section>
                </div>
              </div>
            ) : null}
          </div>
        </main>
      </div>

      {faculty ? (
        <>
          <input
            ref={photoInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            aria-label="Choose a profile photo"
            onChange={(event) => {
              void handlePhotoPicked(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <FacultyModal
            open={editOpen}
            faculty={faculty}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete faculty member?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  "{faculty.name}"
                </span>{" "}
                will be permanently removed. Their projects, grants, publications, students and
                classes are kept (links to this record simply stop resolving). This action cannot
                be undone.
              </>
            }
            confirmLabel="Delete"
            loadingLabel="Deleting…"
            loading={deleting}
            error={deleteError}
            onConfirm={handleDelete}
            onCancel={() => {
              if (!deleting) {
                setConfirmOpen(false);
                setDeleteError(null);
              }
            }}
          />
        </>
      ) : null}

      <Toast toast={toast} onClose={dismiss} />
    </div>
  );
}
