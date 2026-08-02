"use client";

import { useCallback, useEffect, useState } from "react";
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
import { EventHeader } from "@/components/features/events/EventHeader";
import { ParticipationPanel } from "@/components/features/events/ParticipationPanel";
import { SchedulePanel } from "@/components/features/events/SchedulePanel";
import { SpeakersPanel } from "@/components/features/events/SpeakersPanel";
import { PresentationsPanel } from "@/components/features/events/PresentationsPanel";
import { LinkedPeoplePanel } from "@/components/features/events/LinkedPeoplePanel";
import { CertificatesPanel } from "@/components/features/events/CertificatesPanel";
import { EventLinksPanel } from "@/components/features/events/EventLinksPanel";
import {
  EventModal,
  type EventSaveResult,
} from "@/components/features/events/EventModal";
import type { PickerOption } from "@/components/features/finance/SectionPanel";
import { ParticipationRoleBadge } from "@/components/features/events/EventBadges";
import { ObjectDocuments } from "@/components/features/documents/ObjectDocuments";
import { ChipList } from "@/components/features/publications/PublicationBadge";
import { EmptyState } from "@/components/features/objects/EmptyState";
import { DetailSkeleton } from "@/components/features/objects/LoadingSkeleton";
import { ConfirmDialog } from "@/components/features/objects/ConfirmDialog";
import { Section, DetailRow } from "@/components/features/objects/DetailSection";
import { Spinner } from "@/components/features/objects/Spinner";
import { Toast, useToast } from "@/components/features/objects/Toast";
import { useEvent } from "@/hooks/useEvent";
import { useObjectDocuments } from "@/hooks/useObjectDocuments";
import { deleteEvent } from "@/lib/api/events";
import { listFaculty } from "@/lib/api/faculty";
import { listStudents } from "@/lib/api/students";
import { listPublications } from "@/lib/api/publications";
import { toErrorMessage } from "@/lib/api/client";
import { eventTypeLabel } from "@/lib/events/constants";
import { consumeFlash, setFlash } from "@/lib/objects/flash";
import { formatDate, formatDateTime, titleCase } from "@/lib/utils";

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

/**
 * The event workspace: PART 1 record, PART 2 participation, PART 3 speakers,
 * PART 4 schedule, PART 5 registration, PART 7 linked people/research,
 * PART 8 publications, certificates, documents lens and audit trail.
 */
export default function EventWorkspacePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const eventId = decodeRouteId(params?.id);

  const {
    event,
    loading,
    refreshing,
    error,
    notFound,
    applyUpdate,
    refresh,
  } = useEvent(eventId);
  const { toast, show, dismiss } = useToast();

  // Picker options for the people/publication panels (one fetch each).
  const [facultyOptions, setFacultyOptions] = useState<PickerOption[]>([]);
  const [studentOptions, setStudentOptions] = useState<PickerOption[]>([]);
  const [publicationOptions, setPublicationOptions] = useState<PickerOption[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    listFaculty({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setFacultyOptions(
          response.items.map((person) => ({ id: person.id, label: person.name })),
        ),
      )
      .catch(() => setFacultyOptions([]));
    listStudents({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setStudentOptions(
          response.items.map((student) => ({ id: student.id, label: student.name })),
        ),
      )
      .catch(() => setStudentOptions([]));
    listPublications({ pageSize: 100 }, { signal: controller.signal })
      .then((response) =>
        setPublicationOptions(
          response.items.map((publication) => ({
            id: publication.id,
            label: publication.title,
          })),
        ),
      )
      .catch(() => setPublicationOptions([]));
    return () => controller.abort();
  }, []);

  // PART 6 documents integration: pickers offer this event's documents.
  const { documents } = useObjectDocuments(event?.id);
  const documentOptions: PickerOption[] = documents.map((document) => ({
    id: document.id,
    label: document.title || document.file_name,
  }));

  // Pick up a message handed over by another page.
  useEffect(() => {
    const flash = consumeFlash();
    if (flash) show(flash.kind, flash.message);
  }, [show]);

  const [editOpen, setEditOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleSaved = useCallback(
    (result: EventSaveResult) => {
      setEditOpen(false);
      applyUpdate(result.event);
      show("success", "Event updated successfully.");
    },
    [applyUpdate, show],
  );

  const handleDelete = useCallback(async () => {
    if (!event || deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteEvent(event.id);
      setFlash({ kind: "success", message: `“${event.title}” was deleted.` });
      setConfirmOpen(false);
      router.push("/events");
      router.refresh();
    } catch (err) {
      setDeleteError(toErrorMessage(err, "Failed to delete this event."));
      setDeleting(false);
    }
  }, [event, deleting, router]);

  const actions = event ? (
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
            {event ? (
              <button
                type="button"
                onClick={refresh}
                disabled={refreshing}
                aria-label="Refresh event"
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
              { label: "Events", href: "/events" },
              { label: event?.title ?? (notFound ? "Not found" : "Event") },
            ]}
          />

          <div className="mt-4">
            {loading ? (
              <DetailSkeleton />
            ) : notFound ? (
              <EmptyState
                title="Event not found"
                description="This event may have been deleted, or the link is invalid."
                action={
                  <button
                    type="button"
                    onClick={() => router.push("/events")}
                    className="mt-3 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
                  >
                    Back to Events
                  </button>
                }
              />
            ) : error ? (
              <EmptyState
                title="Could not load this event"
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
            ) : event ? (
              <div className="space-y-4">
                <EventHeader event={event} />
                <div className="flex flex-wrap justify-end gap-2">{actions}</div>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <Section title="Event Record">
                    <dl className="text-sm">
                      <DetailRow label="Event code" value={event.event_code || "—"} />
                      <DetailRow label="Event type" value={eventTypeLabel(event.event_type)} />
                      <DetailRow label="Organizer" value={event.organizer || "—"} />
                      <DetailRow label="Co-organizer" value={event.co_organizer || "—"} />
                      <DetailRow label="Venue" value={event.venue || "—"} />
                      <DetailRow
                        label="Mode"
                        value={event.mode ? titleCase(event.mode) : "—"}
                      />
                      <DetailRow
                        label="Start date"
                        value={event.start_date ? formatDate(event.start_date) : "—"}
                      />
                      <DetailRow
                        label="End date"
                        value={event.end_date ? formatDate(event.end_date) : "—"}
                      />
                      <DetailRow label="Department" value={event.department || "—"} />
                      <DetailRow label="School" value={event.school || "—"} />
                      <DetailRow label="Description" value={event.description || "—"} />
                      <DetailRow label="Objectives" value={event.objectives || "—"} />
                      <DetailRow label="Outcome" value={event.outcome || "—"} />
                      <DetailRow label="Tags" value={<ChipList items={event.tags} />} />
                      <DetailRow label="Notes" value={event.notes || "—"} />
                    </dl>
                  </Section>

                  <Section title="Registration">
                    <dl className="text-sm">
                      <DetailRow
                        label="Expected participants"
                        value={String(event.registration?.expected_participants ?? 0)}
                      />
                      <DetailRow
                        label="Registered"
                        value={String(event.registration?.registered ?? 0)}
                      />
                      <DetailRow
                        label="Present"
                        value={String(event.registration?.present ?? 0)}
                      />
                      <DetailRow
                        label="Certificates issued"
                        value={String(event.registration?.certificates_issued ?? 0)}
                      />
                      <DetailRow
                        label="My roles"
                        value={
                          event.participation.length > 0 ? (
                            <span className="inline-flex flex-wrap gap-1">
                              {event.participation.map((row, index) =>
                                row.role ? (
                                  <ParticipationRoleBadge key={index} role={row.role} />
                                ) : null,
                              )}
                            </span>
                          ) : (
                            "—"
                          )
                        }
                      />
                    </dl>
                  </Section>

                  <ParticipationPanel
                    event={event}
                    documents={documentOptions}
                    onUpdated={applyUpdate}
                  />

                  <SpeakersPanel
                    event={event}
                    documents={documentOptions}
                    onUpdated={applyUpdate}
                  />

                  <SchedulePanel event={event} onUpdated={applyUpdate} />

                  <PresentationsPanel
                    event={event}
                    publications={publicationOptions}
                    onUpdated={applyUpdate}
                  />

                  <LinkedPeoplePanel
                    event={event}
                    group="faculty"
                    title="Linked Faculty"
                    options={facultyOptions}
                    hrefFor={(id) => `/faculty/${encodeURIComponent(id)}`}
                    onUpdated={applyUpdate}
                  />

                  <LinkedPeoplePanel
                    event={event}
                    group="students"
                    title="Linked Students"
                    options={studentOptions}
                    hrefFor={(id) => `/students/${encodeURIComponent(id)}`}
                    onUpdated={applyUpdate}
                  />

                  <CertificatesPanel event={event} />

                  <EventLinksPanel links={event.links ?? {}} />

                  <Section title="Documents">
                    <ObjectDocuments objectId={event.id} />
                  </Section>

                  <Section title="Audit Information">
                    <dl className="text-sm">
                      <DetailRow label="Event ID" value={event.id} mono />
                      <DetailRow label="Added by" value={event.uploaded_by || "—"} />
                      <DetailRow
                        label="Added at"
                        value={formatDateTime(event.created_at)}
                      />
                      <DetailRow
                        label="Last updated"
                        value={
                          event.updated_at ? (
                            formatDateTime(event.updated_at)
                          ) : (
                            <span className="text-[var(--text-tertiary)]">Not updated yet</span>
                          )
                        }
                      />
                      <DetailRow label="Current version" value={`v${event.version}`} />
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
                          <p className="text-[var(--text-primary)]">Event created</p>
                          <p className="text-xs text-[var(--text-tertiary)]">
                            {formatDateTime(event.created_at)} ·{" "}
                            {event.uploaded_by || "unknown"}
                          </p>
                        </div>
                      </li>
                      {(event.events ?? []).map((entry, index) => (
                        <li key={`${entry}-${index}`} className="flex gap-3">
                          <ActivityIcon
                            className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-tertiary)]"
                            aria-hidden="true"
                          />
                          <p className="text-[var(--text-primary)]">{titleCase(entry)}</p>
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

      {event ? (
        <>
          <EventModal
            open={editOpen}
            event={event}
            onClose={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
          <ConfirmDialog
            open={confirmOpen}
            title="Delete event?"
            description={
              <>
                <span className="font-medium text-[var(--text-primary)]">
                  “{event.title}”
                </span>{" "}
                will be permanently removed together with its participation, speakers,
                schedule and linked-publication records. Linked faculty, students,
                projects, grants, committees, publications and documents are kept. This
                action cannot be undone.
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
