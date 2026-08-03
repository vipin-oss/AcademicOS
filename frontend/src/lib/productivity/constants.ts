/**
 * Select-option catalogues for the Productivity Hub — mirror
 * `application/dtos/productivity.py` (TASK_PRIORITIES / TASK_CATEGORIES /
 * NOTIFICATION_CATEGORIES) one-to-one, same doctrine as
 * `lib/events/constants.ts`.
 */
export const TASK_PRIORITIES = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
] as const;

export const TASK_CATEGORIES = [
  { value: "research", label: "Research" },
  { value: "teaching", label: "Teaching" },
  { value: "committees", label: "Committees" },
  { value: "finance", label: "Finance" },
  { value: "events", label: "Events" },
  { value: "publications", label: "Publications" },
  { value: "personal", label: "Personal" },
  { value: "admin", label: "Administration" },
  { value: "other", label: "Other" },
] as const;

/** Calendar entries share the task category namespace (backend doctrine). */
export const ENTRY_CATEGORIES = TASK_CATEGORIES;

export const NOTIFICATION_CATEGORIES = [
  { value: "task", label: "Task" },
  { value: "deadline", label: "Deadline" },
  { value: "meeting", label: "Meeting" },
  { value: "finance", label: "Finance" },
  { value: "milestone", label: "Milestone" },
  { value: "system", label: "System" },
] as const;

export const NOTIFICATION_PRIORITIES = TASK_PRIORITIES;

export function priorityLabel(code: string | null | undefined): string {
  if (!code) return "";
  return TASK_PRIORITIES.find((option) => option.value === code)?.label ?? code;
}

export function taskCategoryLabel(code: string | null | undefined): string {
  if (!code) return "";
  return TASK_CATEGORIES.find((option) => option.value === code)?.label ?? code;
}

export function notificationCategoryLabel(code: string | null | undefined): string {
  if (!code) return "";
  return NOTIFICATION_CATEGORIES.find((option) => option.value === code)?.label ?? code;
}
