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

export const EVENT_TYPES: { value: EventType; label: string }[] = [
  { value: "conference", label: "Conference" },
  { value: "workshop", label: "Workshop" },
  { value: "seminar", label: "Seminar" },
  { value: "webinar", label: "Webinar" },
  { value: "fdp", label: "Faculty Development Programme (FDP)" },
  { value: "sttp", label: "Short Term Training Programme (STTP)" },
  { value: "expert_lecture", label: "Expert Lecture" },
  { value: "guest_lecture", label: "Guest Lecture" },
  { value: "invited_talk", label: "Invited Talk" },
  { value: "mathematics_day", label: "Mathematics Day" },
  { value: "science_day", label: "Science Day" },
  { value: "orientation_programme", label: "Orientation Programme" },
  { value: "training_programme", label: "Training Programme" },
  { value: "industry_visit", label: "Industry Visit" },
  { value: "club_activity", label: "Club Activity" },
  { value: "research_colloquium", label: "Research Colloquium" },
  { value: "outreach_activity", label: "Outreach Activity" },
  { value: "competition", label: "Competition" },
  { value: "custom", label: "Custom Event" },
];

export const EVENT_MODES: { value: EventMode; label: string }[] = [
  { value: "offline", label: "Offline" },
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

/** Label lookup for the vocabulary families (falls back to Title Case). */
export function eventTypeLabel(value: string | null | undefined): string {
  return EVENT_TYPES.find((option) => option.value === value)?.label ?? "—";
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
