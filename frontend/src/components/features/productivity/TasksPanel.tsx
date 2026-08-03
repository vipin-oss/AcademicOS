"use client";

/**
 * Personal Tasks panel (PART 3 + PART 8 task list): server-side filters
 * (search / priority / category / status / overdue), in-place complete & pin
 * toggles, create/edit via TaskModal, delete with confirm.
 */
import { useMemo, useState } from "react";
import {
  AlarmClock,
  Check,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Trash2,
} from "lucide-react";

import { toErrorMessage } from "@/lib/api/client";
import { deleteTask, updateTask, type TaskFilters } from "@/lib/api/productivity";
import { useTasks } from "@/hooks/useProductivity";
import {
  TASK_CATEGORIES,
  TASK_PRIORITIES,
  priorityLabel,
  taskCategoryLabel,
} from "@/lib/productivity/constants";
import { Spinner } from "@/components/features/objects/Spinner";
import { CardSkeleton } from "@/components/features/objects/LoadingSkeleton";
import type { ProductivityTask } from "@/types";

import { TaskModal, type TaskSaveResult } from "./TaskModal";
import { todayIso } from "./calendar-utils";

const FILTER_CLASS =
  "rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent)] focus:outline-none";

const ACTION_BUTTON_CLASS =
  "rounded-lg p-1.5 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50";

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

function TaskRow({
  task,
  busy,
  onToggleComplete,
  onTogglePinned,
  onEdit,
  onDelete,
}: {
  task: ProductivityTask;
  busy: boolean;
  onToggleComplete: (task: ProductivityTask) => void;
  onTogglePinned: (task: ProductivityTask) => void;
  onEdit: (task: ProductivityTask) => void;
  onDelete: (task: ProductivityTask) => void;
}) {
  const today = todayIso();
  const overdue = !task.completed && task.due_date !== null && task.due_date < today;
  return (
    <li
      aria-label={task.title}
      className="flex flex-wrap items-start gap-3 px-4 py-3 sm:flex-nowrap sm:items-center"
    >
      <button
        type="button"
        disabled={busy}
        onClick={() => onToggleComplete(task)}
        aria-label={task.completed ? `Mark open: ${task.title}` : `Mark done: ${task.title}`}
        title={task.completed ? "Mark open" : "Mark done"}
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors sm:mt-0 ${
          task.completed
            ? "border-[var(--success)] bg-[var(--success)] text-white"
            : "border-[var(--border-subtle)] bg-[var(--bg-app)] hover:border-[var(--accent)]"
        }`}
      >
        {task.completed ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : null}
      </button>

      <button
        type="button"
        disabled={busy}
        onClick={() => onTogglePinned(task)}
        aria-label={task.pinned ? `Unpin: ${task.title}` : `Pin: ${task.title}`}
        title={task.pinned ? "Unpin" : "Pin"}
        className={ACTION_BUTTON_CLASS}
      >
        {task.pinned ? (
          <PinOff className="h-4 w-4 text-[var(--accent)]" aria-hidden="true" />
        ) : (
          <Pin className="h-4 w-4" aria-hidden="true" />
        )}
      </button>

      <div className="min-w-0 flex-1">
        <p
          className={`truncate text-sm font-medium ${
            task.completed
              ? "text-[var(--text-tertiary)] line-through"
              : "text-[var(--text-primary)]"
          }`}
        >
          {task.title}
        </p>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-[var(--text-tertiary)]">
          {task.due_date ? (
            <span className={overdue ? "font-semibold text-[var(--danger)]" : undefined}>
              {overdue ? "Overdue · " : "Due "}
              {task.due_date}
            </span>
          ) : (
            <span>No due date</span>
          )}
          {task.reminder ? (
            <span className="inline-flex items-center gap-1">
              <AlarmClock className="h-3 w-3" aria-hidden="true" />
              {task.reminder}
            </span>
          ) : null}
          {task.completion_date ? <span>Done {task.completion_date}</span> : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <PriorityBadge priority={task.priority} />
        {task.category ? (
          <span className="rounded-full bg-[var(--bg-app)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]">
            {taskCategoryLabel(task.category)}
          </span>
        ) : null}
        {task.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full border border-[var(--border-subtle)] px-2 py-0.5 text-[11px] text-[var(--text-tertiary)]"
          >
            #{tag}
          </span>
        ))}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          disabled={busy}
          onClick={() => onEdit(task)}
          aria-label={`Edit: ${task.title}`}
          title="Edit"
          className={ACTION_BUTTON_CLASS}
        >
          <Pencil className="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDelete(task)}
          aria-label={`Delete: ${task.title}`}
          title="Delete"
          className={ACTION_BUTTON_CLASS}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </li>
  );
}

export function TasksPanel() {
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState<"" | "open" | "completed">("");
  const [overdueOnly, setOverdueOnly] = useState(false);

  const filters: TaskFilters = useMemo(
    () => ({
      q: search.trim() || undefined,
      priority: priority || undefined,
      category: category || undefined,
      completed: status === "" ? undefined : status === "completed",
      overdue: overdueOnly || undefined,
    }),
    [search, priority, category, status, overdueOnly],
  );

  const { tasks, loading, error, refresh } = useTasks(filters);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ProductivityTask | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const runAction = async (taskId: string, action: () => Promise<unknown>) => {
    setBusyId(taskId);
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

  const handleToggleComplete = (task: ProductivityTask) =>
    runAction(task.id, () => updateTask(task.id, { completed: !task.completed }));

  const handleTogglePinned = (task: ProductivityTask) =>
    runAction(task.id, () => updateTask(task.id, { pinned: !task.pinned }));

  const handleDelete = (task: ProductivityTask) => {
    if (!window.confirm(`Delete task "${task.title}"?`)) return;
    void runAction(task.id, () => deleteTask(task.id));
  };

  const handleSaved = (_result: TaskSaveResult) => {
    setModalOpen(false);
    setEditing(null);
    refresh();
  };

  return (
    <section aria-label="Personal tasks" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={search}
          onChange={(change) => setSearch(change.target.value)}
          aria-label="Search tasks"
          placeholder="Search tasks…"
          className={`${FILTER_CLASS} min-w-40 flex-1 sm:flex-none`}
        />
        <select
          value={priority}
          onChange={(change) => setPriority(change.target.value)}
          aria-label="Filter by priority"
          className={FILTER_CLASS}
        >
          <option value="">All priorities</option>
          {TASK_PRIORITIES.map((option) => (
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
          {TASK_CATEGORIES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(change) => setStatus(change.target.value as "" | "open" | "completed")}
          aria-label="Filter by status"
          className={FILTER_CLASS}
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="completed">Completed</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <input
            type="checkbox"
            checked={overdueOnly}
            onChange={(change) => setOverdueOnly(change.target.checked)}
            aria-label="Overdue only"
            className="h-4 w-4 rounded border-[var(--border-subtle)] accent-[var(--danger)]"
          />
          Overdue only
        </label>
        <div className="ms-auto">
          <button
            type="button"
            onClick={() => {
              setEditing(null);
              setModalOpen(true);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)]"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            New task
          </button>
        </div>
      </div>

      {actionError ? (
        <p
          role="alert"
          className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
        >
          {actionError}
        </p>
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
      ) : tasks && tasks.items.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
          <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-4 py-2">
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">
              {tasks.total_count} task{tasks.total_count === 1 ? "" : "s"}
            </p>
            {busyId ? <Spinner className="h-3.5 w-3.5" label="Updating task" /> : null}
          </div>
          <ul aria-label="Task list" className="divide-y divide-[var(--border-subtle)]">
            {tasks.items.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                busy={busyId === task.id}
                onToggleComplete={(target) => void handleToggleComplete(target)}
                onTogglePinned={(target) => void handleTogglePinned(target)}
                onEdit={(target) => {
                  setEditing(target);
                  setModalOpen(true);
                }}
                onDelete={handleDelete}
              />
            ))}
          </ul>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-[var(--border-subtle)] px-4 py-8 text-center text-sm text-[var(--text-tertiary)]">
          No tasks match — create your first personal task to see it here.
        </p>
      )}

      <TaskModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditing(null);
        }}
        onSaved={handleSaved}
        task={editing}
      />
    </section>
  );
}
