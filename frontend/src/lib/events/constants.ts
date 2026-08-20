import type {
  EventMode,
  EventPriority,
  EventStatus,
  EventType,
  ParticipationRole,
  PresentationRelation,
} from "@/types";

/**
 * Events & Academic Activities constants. The vocabularies mirror the
 * backend (`app/application/dtos/events.py`) one-to-one — keep them in sync.
 * Display casing for ad-hoc strings reuses the shared `titleCase` helper
 * (single implementation in `lib/utils`).
 */

/** PART 1 event business lifecycle (metadata vocabulary). */
export const EVENT_STATUSES: { value: EventStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "ongoing", label: "Ongoing" },
  { value: "postponed", label: "Postponed" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

/**
 * Professor-friendly event types — reduced from 19 to 10 clear categories.
 * Each maps to a broad academic activity type that professors think in.
 * The backend accepts any string, so we can evolve this independently.
 */
export const EVENT_TYPES: { value: EventType; label: string }[] = [
  { value: "conference", label: "Conference" },
  { value: "workshop", label: "Workshop" },
  { value: "seminar", label: "Seminar" },
  { value: "fdp", label: "Faculty Development Programme" },
  { value: "sttp", label: "Short-Term Training" },
  { value: "expert_lecture", label: "Invited / Expert Lecture" },
  { value: "invited_talk", label: "Invited Talk" },
  { value: "training_programme", label: "Training Programme" },
  { value: "competition", label: "Competition / Hackathon" },
  { value: "custom", label: "Other" },
];

export const EVENT_MODES: { value: EventMode; label: string }[] = [
  { value: "offline", label: "In-Person" },
  { value: "online", label: "Online" },
  { value: "hybrid", label: "Hybrid" },
];

export const EVENT_PRIORITIES: { value: EventPriority; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export const PARTICIPATION_ROLES: { value: ParticipationRole; label: string }[] = [
  { value: "organizer", label: "Organizer" },
  { value: "coordinator", label: "Coordinator" },
  { value: "convener", label: "Convener" },
  { value: "speaker", label: "Speaker" },
  { value: "session_chair", label: "Session Chair" },
  { value: "participant", label: "Participant" },
  { value: "volunteer", label: "Volunteer" },
  { value: "resource_person", label: "Resource Person" },
  { value: "chief_guest", label: "Chief Guest" },
  { value: "judge", label: "Judge" },
  { value: "attendee", label: "Attendee" },
];

export const PRESENTATION_RELATIONS: { value: PresentationRelation; label: string }[] = [
  { value: "presented_paper", label: "Presented Paper" },
  { value: "published_proceedings", label: "Published Proceedings" },
  { value: "best_paper_award", label: "Best Paper Award" },
  { value: "poster_presentation", label: "Poster Presentation" },
];

/**
 * Broader categories for the Records page grouping.
 * Maps multiple EVENT_TYPES values to a single display category.
 */
export const EVENT_TYPE_CATEGORIES: Record<string, string> = {
  conference: "Conferences",
  workshop: "Workshops & Training",
  seminar: "Seminars & Talks",
  fdp: "Workshops & Training",
  sttp: "Workshops & Training",
  expert_lecture: "Seminars & Talks",
  invited_talk: "Seminars & Talks",
  training_programme: "Workshops & Training",
  competition: "Competitions",
  custom: "Other",
  // Legacy types that may exist in data
  webinar: "Seminars & Talks",
  guest_lecture: "Seminars & Talks",
  mathematics_day: "Other",
  science_day: "Other",
  orientation_programme: "Workshops & Training",
  industry_visit: "Other",
  club_activity: "Other",
  research_colloquium: "Seminars & Talks",
  outreach_activity: "Other",
};

/** Label lookup for the vocabulary families (falls back to Title Case). */
export function eventTypeLabel(value: string | null | undefined): string {
  return EVENT_TYPES.find((option) => option.value === value)?.label ?? "—";
}

/** Get the broad category for an event type. */
export function eventTypeCategory(value: string | null | undefined): string {
  if (!value) return "Other";
  return EVENT_TYPE_CATEGORIES[value] ?? "Other";
}

/** PART 10 calendar-year filter options (newest first). */
export function yearOptions(span = 6): { value: string; label: string }[] {
  const current = new Date().getFullYear();
  return Array.from({ length: span }, (_, index) => {
    const year = String(current + 1 - index);
    return { value: year, label: year };
  });
}

export const DEFAULT_EVENT_PAGE_SIZE = 10;
