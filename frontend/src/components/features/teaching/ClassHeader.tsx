import type { ReactNode } from "react";
import { CalendarClock, MapPin, MonitorSmartphone, Presentation, Upload, Users } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { classLine, WEEKDAYS } from "@/lib/teaching/constants";
import { CLASS_MODES } from "@/lib/teaching/constants";
import { DocumentVersionBadge } from "@/components/features/documents/DocumentBadge";
import { ClassStatusBadge } from "./TeachingBadges";
import type { ClassResponse, WeeklySlot } from "@/types";

function weekdayLabel(day: string): string {
  return WEEKDAYS.find((weekday) => weekday.value === day)?.label ?? day;
}

function modeLabel(mode: string | null | undefined): string {
  return CLASS_MODES.find((entry) => entry.value === mode)?.label ?? mode ?? "";
}

/** "Mon 09:00–10:00 · Wed 09:00–10:00" — one readable schedule line. */
export function scheduleLine(schedule: WeeklySlot[]): string {
  return schedule
    .map((slot) =>
      [weekdayLabel(slot.day), slot.start && slot.end ? `${slot.start}–${slot.end}` : slot.start ?? slot.end]
        .filter(Boolean)
        .join(" "),
    )
    .join(" · ");
}

/** Class workspace header (mirrors StudentHeader, Presentation icon). */
export function ClassHeader({
  cls,
  actions,
}: {
  cls: ClassResponse;
  actions?: ReactNode;
}) {
  const schedule = scheduleLine(cls.weekly_schedule);

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm sm:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 flex-1 gap-3">
          <Presentation
            className="mt-1 h-11 w-11 shrink-0 rounded-lg bg-[var(--accent-subtle)] p-2.5 text-[var(--accent)]"
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <h1 className="break-words text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">
              {cls.title}
            </h1>
            <p className="mt-1.5 text-sm text-[var(--text-secondary)]">
              {classLine(cls) || "Class"}
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <ClassStatusBadge status={cls.status} />
              <DocumentVersionBadge version={cls.version} />
            </div>

            <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-[var(--text-secondary)]">
              <div className="flex items-center gap-1.5">
                <Users className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                <dt className="sr-only">Students enrolled</dt>
                <dd>
                  {cls.student_count} student{cls.student_count === 1 ? "" : "s"}
                </dd>
              </div>
              {cls.room ? (
                <div className="flex items-center gap-1.5">
                  <MapPin className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                  <dt className="sr-only">Room</dt>
                  <dd>{cls.room}</dd>
                </div>
              ) : null}
              {cls.class_mode ? (
                <div className="flex items-center gap-1.5">
                  <MonitorSmartphone
                    className="h-4 w-4 text-[var(--text-tertiary)]"
                    aria-hidden="true"
                  />
                  <dt className="sr-only">Class mode</dt>
                  <dd>{modeLabel(cls.class_mode)}</dd>
                </div>
              ) : null}
              {schedule ? (
                <div className="flex items-center gap-1.5">
                  <CalendarClock
                    className="h-4 w-4 text-[var(--text-tertiary)]"
                    aria-hidden="true"
                  />
                  <dt className="sr-only">Weekly schedule</dt>
                  <dd>{schedule}</dd>
                </div>
              ) : null}
              <div className="flex items-center gap-1.5">
                <Upload className="h-4 w-4 text-[var(--text-tertiary)]" aria-hidden="true" />
                <dt className="sr-only">Created by / at</dt>
                <dd>
                  {cls.uploaded_by || "—"} · {formatDate(cls.created_at)}
                </dd>
              </div>
            </dl>

            <p className="mt-2 break-all font-mono text-xs text-[var(--text-tertiary)]">{cls.id}</p>
          </div>
        </div>

        {actions ? <div className="flex flex-wrap gap-2 lg:justify-end">{actions}</div> : null}
      </div>
    </div>
  );
}
