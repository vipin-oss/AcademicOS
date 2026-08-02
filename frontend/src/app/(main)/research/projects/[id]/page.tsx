"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  Clock,
  Pencil,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Breadcrumbs } from "@/components/features/objects/Breadcrumbs";
import { ProjectHeader } from "@/components/features/research/ProjectHeader";
import { BudgetSummaryCard } from "@/components/features/research/BudgetSummaryCard";
import { TeamPanel } from "@/components/features/research/TeamPanel";
import { GrantsPanel } from "@/components/features/research/GrantsPanel";
import { TimelinePanel } from "@/components/features/research/TimelinePanel";
import {
  ProjectModal,
  type ProjectSaveResult,
} from "@/components/features/research/ProjectModal";
import {
  GrantModal,
  type GrantSaveResult,
} from "@/components/features/research/GrantModal";
import { MilestoneModal } from "@/components/features/research/MilestoneModal";
import { ProgressUpdateModal } from "@/components/features/research/ProgressUpdateModal";
import { ObjectPublications } from "@/components/features/publications/ObjectPublications";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { ObjectStudents } from "@/components/features/students/ObjectStudents";
import { ChipList } from "@/components/features/publications/PublicationBadge";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useProject } from "@/hooks/useProject";
import { deleteProject } from "@/lib/api/research";
import { toErrorMessage } from "@/lib/api/client";
import { setFlash } from "@/lib/objects/flash";
import { formatDateTime, titleCase } from "@/lib/utils";
import type { ProjectResponse } from "@/types";

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

/** The project workspace: header, budget, team, grants, timeline and lenses. */
export default function ProjectWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = decodeRouteId(params?.id);

  const {
    project,
    loading,
    refreshing,
    error,
    notFound,
    applyUpdate,
    refresh,
  } = useProject(projectId);
  const { toast, show, dismiss } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [grantOpen, setGrantOpen] = useState(false);
  const [milestoneOpen, setMilestoneOpen] = useState(false);
  const [updateOpen, setUpdateOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  // GrantsPanel owns its fetch — remounting it reloads the lens after a
  // grant is registered from this workspace.
  const [grantsPanelKey, setGrantsPanelKey] = useState(0);

  const handleSaved = useCallback(
    (result: ProjectSaveResult) => {
      setEditOpen(false);
      applyUpdate(result.project);
      show("success", "Project updated successfully.");
    },
    [applyUpdate, show],
  );

  const handleGrantSaved = useCallback(
    (result: GrantSaveResult) => {
      setGrantOpen(false);
      setGrantsPanelKey((key) => key + 1);
      refresh(); // budget.grants_released derives from the linked grants
      show(
        "success",
        `“${result.grant.title}” ${result.mode === "edit" ? "updated" : "registered"} successfully.`,
      );
    },
    [refresh, show],
  );

  const handleProgressSaved = useCallback(
    (updated: ProjectResponse) => {
      setUpdateOpen(false);
      applyUpdate(updated); // the API returns the enriched project
      show("success", "Progress update logged.");
    },
    [applyUpdate, show],
  );

  const handleTimelineChanged = useCallback(() => {
    setMilestoneOpen(false);
    refresh();
  }, [refresh]);

  const handleDelete = useCallback(async () => {
    if (!project || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteProject(project.id);
      setFlash({ kind: "success", message: `“${project.title}” was deleted.` });
      setConfirmOpen(false);
      router.push("/research");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this project."));
      setDeleting(false);
    }
  }, [project, deleting, router]);

  const actions = project ? (
    <>
      <button
        type="button"
        onClick={() => setEditOpen(true)}
        disabled={deleting}
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
        disabled={deleting}
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
            {project ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh project"
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
              { label: "Research", href: "/research" },
              { label: project?.title ?? (notFound ? "Not found" : "Project") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Project not found"
                description="This project may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/research")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Research
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this project"
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
            ) : project ? (
              <div className="space-y-4">
                <ProjectHeader project={project} actions={actions} />

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <BudgetSummaryCard budget={project.budget ?? {
                    approved: project.budget_approved ?? null,
                    grants_released: null,
                    utilized: project.budget_utilized ?? null,
                    remaining: null,
                  }} />

                  <TeamPanel project={project} />

                  <GrantsPanel
                    key={grantsPanelKey}
                    projectId={project.id}
                    onNewGrant={() => setGrantOpen(true)}
                  />

                  <Section title="Research Content">
                    <dl className="text-sm">
                      <DetailRow label="Abstract" value={project.abstract || "—"} />
                      <DetailRow
                        label="Keywords"
                        value={<ChipList items={project.keywords} />}
                      />
                      <DetailRow label="Notes" value={project.notes || "—"} />
                    </dl>
                  </Section>

                  <Section title="Publications">
                    <ObjectPublications objectId={project.id} />
                  </Section>

                  <Section title="Students">
                    <ObjectStudents objectId={project.id} />
                  </Section>

                  <Section title="Documents">
                    <ObjectDocuments objectId={project.id} />
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Project ID" value={project.id} mono />
                      <DetailRow label="Added by" value={project.uploaded_by || "—"} />
                      <DetailRow label="Added at" value={formatDateTime(project.created_at)} />
                      <DetailRow
                        label="Last updated"
                        value={
                          project.updated_at ? (
                            formatDateTime(project.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${project.version}`} />
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
                          <p className="text-[var(--text-primary)]">Project registered</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(project.created_at)} ·{" "}
                            {project.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(project.events ?? []).map((event, index) => (
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

                <TimelinePanel
                  project={project}
                  onAddMilestone={() => setMilestoneOpen(true)}
                  onLogUpdate={() => setUpdateOpen(true)}
                  onChanged={refresh}
                />
              </div>
            ) : null}
          </div>
        </main>
      </div>

      {project ? (
        <>
          <ProjectModal
            open={editOpen}
            project={project}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <GrantModal
            open={grantOpen}
            defaultProjectIds={[project.id]}
            onClose={() => setGrantOpen(false)}
            onSaved={handleGrantSaved}
          />
          <MilestoneModal
            open={milestoneOpen}
            projectId={project.id}
            onClose={() => setMilestoneOpen(false)}
            onSaved={handleTimelineChanged}
          />
          <ProgressUpdateModal
            open={updateOpen}
            projectId={project.id}
            onClose={() => setUpdateOpen(false)}
            onSaved={handleProgressSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete project?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{project.title}”
                </span>{" "}
                will be permanently removed together with its milestones. Grants, publications
                and team members are kept. This action cannot be undone.
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
