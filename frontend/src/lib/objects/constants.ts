/**
 * Frontend mirror of the Object contract exposed by the backend.
 *
 * Single source of truth for the values the UI is allowed to send, so the
 * modal, the badges and the filters can never drift apart. Mirrors:
 *   - `app/domain/value_objects/enums.py`      (ObjectType, ObjectStatus)
 *   - `app/domain/entities/object.py`          (_STATUS_TRANSITIONS)
 *   - `app/application/validators/object.py`   (creatable statuses, page size)
 */
import type { ObjectStatus } from "@/types";

/** Every `ObjectType` the backend enum accepts. Sending anything else = 422. */
export const OBJECT_TYPES = [
  "faculty",
  "student",
  "course",
  "research_project",
  "publication",
  "grant",
  "meeting",
  "committee",
  "event",
  "task",
  "purchase",
  "budget",
  "document",
  "journal",
  "conference",
  "dataset",
  "software",
  "laboratory",
  "research_area",
  "space",
  "note",
  "message",
  "integration",
  "workspace",
  "workflow_template",
  "workflow_instance",
  "proactive_insight",
  "memory_artifact",
] as const;

export type ObjectTypeValue = (typeof OBJECT_TYPES)[number];

export const OBJECT_STATUSES: ObjectStatus[] = ["draft", "active", "archived", "superseded"];

/** Statuses accepted for a brand-new object (`validate_create_object_input`). */
export const CREATABLE_STATUSES: ObjectStatus[] = ["draft", "active", "archived"];

/** Base lifecycle transitions enforced by the domain aggregate. */
export const STATUS_TRANSITIONS: Record<ObjectStatus, ObjectStatus[]> = {
  draft: ["active", "archived"],
  active: ["archived", "superseded"],
  archived: ["active"],
  superseded: [],
};

/**
 * Statuses that may be selected while editing: the current one (no-op) plus
 * every legal transition. Blocking illegal transitions client-side keeps the
 * user out of a backend `InvalidStateTransitionError`.
 */
export function allowedNextStatuses(current: ObjectStatus): ObjectStatus[] {
  return [current, ...(STATUS_TRANSITIONS[current] ?? [])];
}

/** Department is a first-class field in the UI but a metadata key on the wire. */
export const DEPARTMENT_METADATA_KEY = "department";

/** Rows per page in the Objects list. */
export const DEFAULT_PAGE_SIZE = 12;

/**
 * The backend has no `q` parameter yet, so search filters client-side over a
 * single "window" of objects. 100 = the backend's `page_size` ceiling.
 */
export const SEARCH_WINDOW_SIZE = 100;
