"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Info, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createObject, updateObject } from "@/lib/api/objects";
import type { CreateObjectPayload, UpdateObjectPayload } from "@/lib/api/objects";
import {
  allowedNextStatuses,
  CREATABLE_STATUSES,
  DEPARTMENT_METADATA_KEY,
  OBJECT_TYPES,
} from "@/lib/objects/constants";
import { useModalDismiss } from "@/hooks/useModalDismiss";
import { cn, titleCase } from "@/lib/utils";
import type { ObjectResponse, ObjectStatus } from "@/types";
import {
  MetadataEditor,
  metadataRowsToPayload,
  metadataToRows,
  validateMetadataRows,
  type MetaRow,
} from "./MetadataEditor";
import { Spinner } from "./Spinner";

export interface ObjectSaveResult {
  mode: "create" | "edit";
  object: ObjectResponse;
  /** Non-fatal note to surface to the user (e.g. unsupported metadata removal). */
  warning?: string;
}

const FIELD_CLASS =
  "w-full rounded-lg border bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60";

/**
 * Create **and** edit an Object — one modal, one code path.
 *
 * Edit mode reflects the API contract exactly: `PUT /objects/{id}` accepts
 * `updated_by`, `status` and `metadata`. Title / type / creator are therefore
 * prefilled but read-only instead of silently discarded by the server.
 */
export function CreateObjectModal({
  open,
  object,
  onClose,
  onSaved,
}: {
  open: boolean;
  object?: ObjectResponse | null;
  onClose: () => void;
  onSaved: (result: ObjectSaveResult) => void;
}) {
  const isEdit = Boolean(object);

  const [objectType, setObjectType] = useState<string>("course");
  const [title, setTitle] = useState("");
  const [createdBy, setCreatedBy] = useState("");
  const [updatedBy, setUpdatedBy] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState<ObjectStatus>("draft");
  const [rows, setRows] = useState<MetaRow[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLSelectElement | HTMLInputElement>(null);

  useModalDismiss({ open, onDismiss: onClose, disabled: submitting });

  // (Re)hydrate the form every time the modal opens or the target changes.
  useEffect(() => {
    if (!open) return;
    setFormError(null);
    setShowErrors(false);
    setSubmitting(false);
    submittingRef.current = false;

    if (object) {
      setObjectType(object.object_type);
      setTitle(object.title);
      setCreatedBy(object.created_by);
      setUpdatedBy(object.created_by || "system");
      setDepartment(object.metadata?.[DEPARTMENT_METADATA_KEY] ?? "");
      setStatus(object.status);
      setRows(metadataToRows(object.metadata));
    } else {
      setObjectType("course");
      setTitle("");
      setCreatedBy("");
      setUpdatedBy("");
      setDepartment("");
      setStatus("draft");
      setRows([]);
    }
  }, [open, object]);

  useEffect(() => {
    if (open) firstFieldRef.current?.focus();
  }, [open]);

  const metaValidation = useMemo(() => validateMetadataRows(rows), [rows]);

  const fieldErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    if (!objectType.trim()) errors.objectType = "Object type is required.";
    if (!title.trim()) errors.title = "Title is required.";
    if (!isEdit && !createdBy.trim()) errors.createdBy = "Created by is required.";
    if (isEdit && !updatedBy.trim()) errors.updatedBy = "Updated by is required.";
    return errors;
  }, [objectType, title, createdBy, updatedBy, isEdit]);

  const statusOptions = useMemo(
    () => (isEdit && object ? allowedNextStatuses(object.status) : CREATABLE_STATUSES),
    [isEdit, object],
  );

  if (!open) return null;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return; // hard guard against double submits

    setShowErrors(true);
    const firstFieldError = Object.values(fieldErrors)[0];
    if (firstFieldError || metaValidation.error) {
      setFormError(firstFieldError ?? metaValidation.error);
      return;
    }

    const metadata = metadataRowsToPayload(rows);
    if (department.trim()) {
      metadata.unshift({ key: DEPARTMENT_METADATA_KEY, value: department.trim() });
    }

    submittingRef.current = true;
    setSubmitting(true);
    setFormError(null);

    try {
      if (object) {
        const payload: UpdateObjectPayload = {
          updated_by: updatedBy.trim(),
          status,
          metadata,
        };
        const saved = await updateObject(object.id, payload);

        // The API can add/overwrite metadata but not delete keys yet — tell the
        // truth instead of pretending the removal worked.
        const requested = new Set(metadata.map((entry) => entry.key));
        const stillThere = Object.keys(object.metadata ?? {}).filter(
          (key) => !requested.has(key) && key in (saved.metadata ?? {}),
        );

        onSaved({
          mode: "edit",
          object: saved,
          warning: stillThere.length
            ? `Metadata key${stillThere.length > 1 ? "s" : ""} "${stillThere.join('", "')}" could not be removed — the API has no metadata delete endpoint yet.`
            : undefined,
        });
      } else {
        const payload: CreateObjectPayload = {
          object_type: objectType.trim(),
          title: title.trim(),
          created_by: createdBy.trim(),
          status,
          metadata,
        };
        const saved = await createObject(payload);
        onSaved({ mode: "create", object: saved });
      }
    } catch (error) {
      setFormError(toErrorMessage(error, "Failed to save the object."));
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const errorFor = (key: string) => (showErrors ? fieldErrors[key] : undefined);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submitting) onClose();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="object-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="object-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {isEdit ? "Edit Object" : "New Object"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-md p-1 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {isEdit ? (
            <p className="flex gap-2 rounded-lg bg-[var(--bg-surface-2)] px-3 py-2 text-xs text-[var(--text-secondary)]">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>
                Title, type and creator are immutable in the current API — updates apply to
                status, department and metadata.
              </span>
            </p>
          ) : null}

          <Field label="Object Type" required error={errorFor("objectType")}>
            <select
              ref={firstFieldRef as React.RefObject<HTMLSelectElement>}
              value={objectType}
              onChange={(event) => setObjectType(event.target.value)}
              disabled={submitting || isEdit}
              className={cn(FIELD_CLASS, "border-[var(--border-subtle)] focus:border-[var(--accent)]")}
            >
              {OBJECT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {titleCase(type)}
                </option>
              ))}
              {isEdit && !OBJECT_TYPES.includes(objectType as (typeof OBJECT_TYPES)[number]) ? (
                <option value={objectType}>{titleCase(objectType)}</option>
              ) : null}
            </select>
          </Field>

          <Field label="Title" required error={errorFor("title")}>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              onBlur={() => setTitle((value) => value.trim())}
              disabled={submitting || isEdit}
              placeholder="e.g. Advanced Machine Learning"
              aria-invalid={Boolean(errorFor("title"))}
              className={cn(
                FIELD_CLASS,
                errorFor("title")
                  ? "border-[var(--danger)] focus:border-[var(--danger)]"
                  : "border-[var(--border-subtle)] focus:border-[var(--accent)]",
              )}
            />
          </Field>

          <Field label="Created By" required={!isEdit} error={errorFor("createdBy")}>
            <input
              value={createdBy}
              onChange={(event) => setCreatedBy(event.target.value)}
              onBlur={() => setCreatedBy((value) => value.trim())}
              disabled={submitting || isEdit}
              placeholder="e.g. faculty:123"
              aria-invalid={Boolean(errorFor("createdBy"))}
              className={cn(
                FIELD_CLASS,
                errorFor("createdBy")
                  ? "border-[var(--danger)] focus:border-[var(--danger)]"
                  : "border-[var(--border-subtle)] focus:border-[var(--accent)]",
              )}
            />
          </Field>

          {isEdit ? (
            <Field
              label="Updated By"
              required
              error={errorFor("updatedBy")}
              hint="Recorded in the audit trail for this change."
            >
              <input
                value={updatedBy}
                onChange={(event) => setUpdatedBy(event.target.value)}
                onBlur={() => setUpdatedBy((value) => value.trim())}
                disabled={submitting}
                placeholder="e.g. faculty:123"
                aria-invalid={Boolean(errorFor("updatedBy"))}
                className={cn(
                  FIELD_CLASS,
                  errorFor("updatedBy")
                    ? "border-[var(--danger)] focus:border-[var(--danger)]"
                    : "border-[var(--border-subtle)] focus:border-[var(--accent)]",
                )}
              />
            </Field>
          ) : null}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Department" hint={`Stored as metadata."${DEPARTMENT_METADATA_KEY}"`}>
              <input
                value={department}
                onChange={(event) => setDepartment(event.target.value)}
                onBlur={() => setDepartment((value) => value.trim())}
                disabled={submitting}
                placeholder="e.g. Computer Science"
                className={cn(
                  FIELD_CLASS,
                  "border-[var(--border-subtle)] focus:border-[var(--accent)]",
                )}
              />
            </Field>

            <Field
              label="Status"
              hint={
                isEdit && statusOptions.length === 1
                  ? "This status is terminal — no further transitions."
                  : undefined
              }
            >
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as ObjectStatus)}
                disabled={submitting || statusOptions.length <= 1}
                className={cn(
                  FIELD_CLASS,
                  "border-[var(--border-subtle)] focus:border-[var(--accent)]",
                )}
              >
                {statusOptions.map((option) => (
                  <option key={option} value={option}>
                    {titleCase(option)}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          {isEdit && object ? (
            <div className="flex items-center justify-between rounded-lg bg-[var(--bg-surface-2)] px-3 py-2 text-xs">
              <span className="text-[var(--text-tertiary)]">Version</span>
              <span className="font-medium text-[var(--text-primary)]">v{object.version}</span>
            </div>
          ) : null}

          <MetadataEditor
            rows={rows}
            onChange={setRows}
            disabled={submitting}
            validation={metaValidation}
          />

          {formError ? (
            <p
              role="alert"
              className="rounded-lg border border-[var(--danger)] bg-[var(--danger-subtle)] px-3 py-2 text-sm text-[var(--danger)]"
            >
              {formError}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[var(--border-subtle)] px-5 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg border border-[var(--border-subtle)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? <Spinner /> : null}
            {submitting ? (isEdit ? "Updating…" : "Creating…") : isEdit ? "Update" : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  required,
  error,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-[var(--text-secondary)]">
        {label}
        {required ? <span className="text-[var(--danger)]"> *</span> : null}
      </span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-[var(--danger)]">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-[var(--text-tertiary)]">{hint}</span>
      ) : null}
    </label>
  );
}
