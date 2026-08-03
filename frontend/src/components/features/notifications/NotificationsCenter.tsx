"use client";

/**
 * Notification Center (PART 4): state tabs (active / unread / read / pinned /
 * snoozed / archived / all), priority + category filters, per-card actions
 * (read, pin, archive, snooze, delete), manual notes, and the PART 5 engine
 * refresh sweep (idempotent by design).
 */
import { useMemo, useState } from "react";
import {
  Archive,
  ArchiveRestore,
  BellPlus,
  Check,
  ExternalLink,
  Pin,
  PinOff,
  RefreshCw,
  Trash2,
  Undo2,
  AlarmClock,
} from "lucide-react";

import { toErrorMessage } from "@/lib/api/client";
import {
  createNotification,
  deleteNotification,
  refreshNotifications,
  updateNotification,
  type NotificationFilters,
} from "@/lib/api/productivity";
import { useNotifications } from "@/hooks/useProductivity";
import {
  NOTIFICATION_CATEGORIES,
  NOTIFICATION_PRIORITIES,
  notificationCategoryLabel,
  priorityLabel,
} from "@/lib/productivity/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import type { NotificationState, ProductivityNotification } from "@/types";

import { addDays, todayIso } from "../productivity/calendar-utils";

const FILTER_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none";

const FIELD_CLASS =
  "w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none";

const ACTION_BUTTON_CLASS =
  "rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50";

const STATE_TABS: { value: NotificationState | ""; label: string }[] = [
  { value: "", label: "Active" },
  { value: "unread", label: "Unread" },
  { value: "read", label: "Read" },
  { value: "pinned", label: "Pinned" },
  { value: "snoozed", label: "Snoozed" },
  { value: "archived", label: "Archived" },
  { value: "all", label: "All" },
];

function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return null;
  const tone =
    priority === "high"
      ? "border-[var(--danger)] text-[var(--danger)]"
      : priority === "medium"
        ? "border-[var(--warning)] text-[var(--warning)]"
        : "border-[var(--border-subtle)] text-[var(--text-tertiary)]";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}>
      {priorityLabel(priority)}
    </span>
  );
}

function NotificationCard({
  notification,
  busy,
  onAction,
  onSnooze,
  onDelete,
}: {
  notification: ProductivityNotification;
  busy: boolean;
  onAction: (id: string, patch: Parameters<typeof updateNotification>[1]) => void;
  onSnooze: (notification: ProductivityNotification) => void;
  onDelete: (notification: ProductivityNotification) => void;
}) {
  const createdDay = notification.created_at.slice(0, 10);
  return (
    <li
      aria-label={notification.title}
      className={`flex flex-wrap items-start gap-3 px-4 py-3 sm:flex-nowrap ${
        notification.is_read ? "" : "bg-[var(--bg-app)]"
      }`}
    >
      <span
        aria-hidden="true"
        title={notification.is_read ? "Read" : "Unread"}
        className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${
          notification.is_read ? "bg-[var(--border-subtle)]" : "bg-[var(--accent)]"
        }`}
      />

      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span
            className={`truncate ${
              notification.is_read
                ? "text-[var(--text-secondary)]"
                : "font-semibold text-[var(--text-primary)]"
            }`}
          >
            {notification.title}
          </span>
          {notification.pinned ? (
            <Pin className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" aria-label="Pinned" />
          ) : null}
        </p>
        {notification.body ? (
          <p className="mt-0.5 line-clamp-2 text-xs text-[var(--text-secondary)]">{notification.body}</p>
        ) : null}
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-[var(--text-tertiary)]">
          <span>{createdDay}</span>
          {notification.source_module ? <span>via {notification.source_module}</span> : null}
          {notification.generated_by === "reminder_engine" ? <span>auto-reminder</span> : null}
          {notification.snoozed ? (
            <span className="font-medium text-[var(--warning)]">
              Snoozed until {notification.snoozed_until}
            </span>
          ) : null}
          {notification.archived ? <span className="font-medium">Archived</span> : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <PriorityBadge priority={notification.priority} />
        {notification.category ? (
          <span className="rounded-full bg-[var(--bg-surface)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]">
            {notificationCategoryLabel(notification.category)}
          </span>
        ) : null}
        {notification.link ? (
          <a
            href={notification.link}
            aria-label={`Open link: ${notification.title}`}
            title={notification.link}
            className={ACTION_BUTTON_CLASS}
          >
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
          </a>
        ) : null}
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-1">
        <button
          type="button"
          disabled={busy}
          onClick={() => onAction(notification.id, { is_read: !notification.is_read })}
          aria-label={
            notification.is_read
              ? `Mark unread: ${notification.title}`
              : `Mark read: ${notification.title}`
          }
          title={notification.is_read ? "Mark unread" : "Mark read"}
          className={ACTION_BUTTON_CLASS}
        >
          {notification.is_read ? (
            <Undo2 className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Check className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onAction(notification.id, { pinned: !notification.pinned })}
          aria-label={
            notification.pinned ? `Unpin: ${notification.title}` : `Pin: ${notification.title}`
          }
          title={notification.pinned ? "Unpin" : "Pin"}
          className={ACTION_BUTTON_CLASS}
        >
          {notification.pinned ? (
            <PinOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Pin className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
        {notification.snoozed ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => onAction(notification.id, { snoozed_until: "" })}
            aria-label={`Unsnooze: ${notification.title}`}
            title="Unsnooze"
            className={ACTION_BUTTON_CLASS}
          >
            <AlarmClock className="h-4 w-4 text-[var(--warning)]" aria-hidden="true" />
          </button>
        ) : (
          <button
            type="button"
            disabled={busy || notification.archived}
            onClick={() => onSnooze(notification)}
            aria-label={`Snooze: ${notification.title}`}
            title="Snooze"
            className={ACTION_BUTTON_CLASS}
          >
            <AlarmClock className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() => onAction(notification.id, { archived: !notification.archived })}
          aria-label={
            notification.archived
              ? `Unarchive: ${notification.title}`
              : `Archive: ${notification.title}`
          }
          title={notification.archived ? "Unarchive" : "Archive"}
          className={ACTION_BUTTON_CLASS}
        >
          {notification.archived ? (
            <ArchiveRestore className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Archive className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDelete(notification)}
          aria-label={`Delete: ${notification.title}`}
          title="Delete"
          className={ACTION_BUTTON_CLASS}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </li>
  );
}

export function NotificationsCenter() {
  const [state, setState] = useState<NotificationState | "">("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");

  const filters: NotificationFilters = useMemo(
    () => ({
      state: state || undefined,
      priority: priority || undefined,
      category: category || undefined,
    }),
    [state, priority, category],
  );

  const { notifications, loading, error, refresh } = useNotifications(filters);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshInfo, setRefreshInfo] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formTitle, setFormTitle] = useState("");
  const [formBody, setFormBody] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [formPriority, setFormPriority] = useState("");
  const [formLink, setFormLink] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [formBusy, setFormBusy] = useState(false);

  const runAction = async (id: string, action: () => Promise<unknown>) => {
    setBusyId(id);
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(toErrorMessage(err));
    } finally {
      setBusyId(null);
      refresh();
    }
  };

  const handleAction = (id: string, patch: Parameters<typeof updateNotification>[1]) =>
    void runAction(id, () => updateNotification(id, patch));

  const handleSnooze = (notification: ProductivityNotification) => {
    const suggestion = addDays(todayIso(), 1);
    const answer = window.prompt("Snooze until (YYYY-MM-DD):", suggestion);
    if (answer === null) return;
    const until = answer.trim() || suggestion;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(until)) {
      setActionError("Snooze date must be an ISO date (YYYY-MM-DD).");
      return;
    }
    void runAction(notification.id, () =>
      updateNotification(notification.id, { snoozed_until: until }),
    );
  };

  const handleDelete = (notification: ProductivityNotification) => {
    if (!window.confirm(`Delete notification "${notification.title}"?`)) return;
    void runAction(notification.id, () => deleteNotification(notification.id));
  };

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setRefreshInfo(null);
    setActionError(null);
    try {
      const result = await refreshNotifications();
      setRefreshInfo(
        `Reminder sweep: ${result.created} new, ${result.skipped_existing} already shown. Automatic reminders only — nothing is emailed or pushed.`,
      );
      refresh();
    } catch (err) {
      setActionError(toErrorMessage(err));
    } finally {
      setRefreshing(false);
    }
  };

  const handleCreate = async (formEvent: React.FormEvent) => {
    formEvent.preventDefault();
    if (formBusy) return;
    setFormError(null);
    if (!formTitle.trim()) {
      setFormError("Notification title must not be empty.");
      return;
    }
    setFormBusy(true);
    try {
      await createNotification({
        title: formTitle.trim(),
        body: formBody.trim() || undefined,
        category: formCategory || undefined,
        priority: formPriority || undefined,
        link: formLink.trim() || undefined,
      });
      setFormTitle("");
      setFormBody("");
      setFormCategory("");
      setFormPriority("");
      setFormLink("");
      setFormOpen(false);
      refresh();
    } catch (err) {
      setFormError(toErrorMessage(err));
    } finally {
      setFormBusy(false);
    }
  };

  return (
    <section aria-label="Notification center" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div
          role="tablist"
          aria-label="Notification state"
          className="flex flex-wrap rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-0.5"
        >
          {STATE_TABS.map((tab) => (
            <button
              key={tab.label}
              type="button"
              role="tab"
              aria-selected={state === tab.value}
              onClick={() => setState(tab.value)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                state === tab.value
                  ? "bg-[var(--accent)] text-white"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
              }`}
            >
              {tab.label}
              {tab.value === "unread" && notifications ? (
                <span className="ml-1 rounded-full bg-black/20 px-1.5 text-[10px] tabular-nums">
                  {notifications.unread_count}
                </span>
              ) : null}
            </button>
          ))}
        </div>
        <select
          value={priority}
          onChange={(change) => setPriority(change.target.value)}
          aria-label="Filter by priority"
          className={FILTER_CLASS}
        >
          <option value="">All priorities</option>
          {NOTIFICATION_PRIORITIES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={category}
          onChange={(change) => setCategory(change.target.value)}
          aria-label="Filter by category"
          className={FILTER_CLASS}
        >
          <option value="">All categories</option>
          {NOTIFICATION_CATEGORIES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <div className="ms-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => setFormOpen((open) => !open)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
          >
            <BellPlus className="h-4 w-4" aria-hidden="true" />
            New note
          </button>
          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={refreshing}
            aria-label="Refresh notifications"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:opacity-60"
          >
            {refreshing ? (
              <Spinner className="h-4 w-4" label="Refreshing" />
            ) : (
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            )}
            Refresh
          </button>
        </div>
      </div>

      {refreshInfo ? (
        <p className="rounded-lg border border-[var(--success)] bg-[var(--success-subtle,var(--bg-surface))] px-3 py-2 text-sm text-[var(--success)]">
          {refreshInfo}
        </p>
      ) : null}
      {actionError ? (
        <p
          role="alert"
          className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
        >
          {actionError}
        </p>
      ) : null}

      {formOpen ? (
        <form
          aria-label="New notification"
          onSubmit={handleCreate}
          className="space-y-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-3"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input
              type="text"
              value={formTitle}
              onChange={(change) => setFormTitle(change.target.value)}
              aria-label="Notification title"
              placeholder="Title *"
              className={FIELD_CLASS}
            />
            <input
              type="text"
              value={formLink}
              onChange={(change) => setFormLink(change.target.value)}
              aria-label="Notification link"
              placeholder="Link (optional path or URL)"
              className={FIELD_CLASS}
            />
            <select
              value={formCategory}
              onChange={(change) => setFormCategory(change.target.value)}
              aria-label="Notification category"
              className={FIELD_CLASS}
            >
              <option value="">— category —</option>
              {NOTIFICATION_CATEGORIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={formPriority}
              onChange={(change) => setFormPriority(change.target.value)}
              aria-label="Notification priority"
              className={FIELD_CLASS}
            >
              <option value="">— priority —</option>
              {NOTIFICATION_PRIORITIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <textarea
            value={formBody}
            onChange={(change) => setFormBody(change.target.value)}
            aria-label="Notification body"
            placeholder="Body (optional)"
            rows={2}
            className={FIELD_CLASS}
          />
          {formError ? (
            <p role="alert" className="text-sm text-[var(--danger)]">
              {formError}
            </p>
          ) : null}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setFormOpen(false)}
              className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={formBusy}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-60"
            >
              {formBusy ? <Spinner /> : null}
              Add note
            </button>
          </div>
        </form>
      ) : null}

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <CardSkeleton key={index} />
          ))}
        </div>
      ) : error ? (
        <p
          role="alert"
          className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
        >
          {error}
        </p>
      ) : notifications && notifications.items.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
          <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-2">
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
              {notifications.total_count} notification{notifications.total_count === 1 ? "" : "s"} ·{" "}
              {notifications.unread_count} unread
            </p>
            {busyId ? <Spinner className="h-3.5 w-3.5" label="Updating notification" /> : null}
          </div>
          <ul aria-label="Notification list" className="divide-y divide-[var(--border-subtle)]">
            {notifications.items.map((notification) => (
              <NotificationCard
                key={notification.id}
                notification={notification}
                busy={busyId === notification.id}
                onAction={handleAction}
                onSnooze={handleSnooze}
                onDelete={handleDelete}
              />
            ))}
          </ul>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-[var(--border-subtle)] px-4 py-8 text-center text-sm text-[var(--text-tertiary)]">
          Nothing here — you are all caught up.
        </p>
      )}
    </section>
  );
}
