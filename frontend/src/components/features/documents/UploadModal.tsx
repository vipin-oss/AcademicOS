"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Info, Upload, X } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import {
  updateDocument,
  uploadDocument,
  type UploadProgress,
} from "@/lib/api/documents";
import { listObjects } from "@/lib/api/objects";
import {
  DOCUMENT_STATUSES,
  DOCUMENT_TYPES,
  MAX_UPLOAD_BYTES,
  documentTypeFromFileName,
  formatFileSize,
} from "@/lib/documents/constants";
import { useModalDismiss } from "@/hooks/useModalDismiss";
import { cn, titleCase } from "@/lib/utils";
import type { DocumentResponse, DocumentStatus, ObjectResponse } from "@/types";
import { Spinner } from "@/components/features/objects/Spinner";

export interface DocumentSaveResult {
  mode: "create" | "edit";
  document: DocumentResponse;
  warning?: string;
}

const FIELD_CLASS =
  "w-full rounded-lg border bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60";

/**
 * Create **and** edit a Document — one modal, one code path.
 *
 * Create sends a multipart upload (file + metadata) via `uploadDocument`,
 * which reports real upload progress. Edit sends a JSON `PUT` (no re-upload);
 * only metadata/link/status change.
 */
export function UploadModal({
  open,
  document,
  onClose,
  onSaved,
}: {
  open: boolean;
  document?: DocumentResponse | null;
  onClose: () => void;
  onSaved: (result: DocumentSaveResult) => void;
}) {
  const isEdit = Boolean(document);

  const [title, setTitle] = useState("");
  const [objectId, setObjectId] = useState<string>("");
  const [documentType, setDocumentType] = useState<string>("pdf");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagDraft, setTagDraft] = useState("");
  const [uploadedBy, setUploadedBy] = useState("");
  const [status, setStatus] = useState<DocumentStatus>("draft");
  const [file, setFile] = useState<File | null>(null);
  const [objects, setObjects] = useState<ObjectResponse[]>([]);

  const [formError, setFormError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const submittingRef = useRef(false);
  const firstFieldRef = useRef<HTMLInputElement>(null);

  useModalDismiss({ open, onDismiss: onClose, disabled: submitting });

  // (Re)hydrate the form + load the object picker every time the modal opens.
  useEffect(() => {
    if (!open) return;
    setFormError(null);
    setShowErrors(false);
    setSubmitting(false);
    setProgress(null);
    submittingRef.current = false;
    setTags([]);
    setTagDraft("");
    setFile(null);

    if (document) {
      setTitle(document.title);
      setObjectId(document.object_id ?? "");
      setDocumentType(document.document_type);
      setDescription(document.description ?? "");
      setTags(document.tags ?? []);
      setStatus(document.status);
      setUploadedBy(document.uploaded_by || "system");
    } else {
      setTitle("");
      setObjectId("");
      setDocumentType("pdf");
      setDescription("");
      setStatus("draft");
      setUploadedBy("");
    }

    // Populate the "Object" select with professor-relevant types only.
    const ALLOWED_TYPES = new Set(["event", "publication", "research_project", "committee", "student", "faculty"]);
    listObjects({ pageSize: 100 })
      .then((response) => {
        const filtered = (response.items ?? []).filter(
          (o) => ALLOWED_TYPES.has(o.object_type)
        );
        setObjects(filtered);
      })
      .catch(() => setObjects([]));
  }, [open, document]);

  useEffect(() => {
    if (open) firstFieldRef.current?.focus();
  }, [open]);

  const fieldErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    if (!title.trim()) errors.title = "Document title is required.";
    if (!documentType) errors.documentType = "Document type is required.";
    if (!isEdit && !uploadedBy.trim()) errors.uploadedBy = "Uploaded by is required.";
    if (!isEdit && !file) errors.file = "Please choose a file to upload.";
    return errors;
  }, [title, documentType, uploadedBy, file, isEdit]);

  if (!open) return null;

  const addTag = (raw: string) => {
    const value = raw.trim();
    if (!value) return;
    setTags((current) =>
      current.some((tag) => tag.toLowerCase() === value.toLowerCase())
        ? current
        : [...current, value],
    );
    setTagDraft("");
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return; // hard guard against double submits

    setShowErrors(true);
    const firstFieldError = Object.values(fieldErrors)[0];
    if (firstFieldError) {
      setFormError(firstFieldError);
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    setFormError(null);
    setProgress(isEdit ? null : 0);

    try {
      if (document) {
        const saved = await updateDocument(document.id, {
          title: title.trim(),
          object_id: objectId || null,
          document_type: documentType as DocumentResponse["document_type"],
          description: description.trim() || undefined,
          tags,
          status,
        });
        onSaved({ mode: "edit", document: saved });
      } else if (file) {
        if (file.size > MAX_UPLOAD_BYTES) {
          setFormError(
            `This file is ${formatFileSize(file.size)} — the upload limit is ${formatFileSize(MAX_UPLOAD_BYTES)}.`,
          );
          return;
        }
        const saved = await uploadDocument(
          {
            title: title.trim(),
            object_id: objectId || null,
            document_type: documentType as DocumentResponse["document_type"],
            description: description.trim() || undefined,
            tags,
            uploaded_by: uploadedBy.trim(),
            file,
          },
          {
            onProgress: (value: UploadProgress) => setProgress(value.percent),
          },
        );
        onSaved({ mode: "create", document: saved });
      }
    } catch (error) {
      setFormError(toErrorMessage(error, "Failed to save the document."));
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
      setProgress(null);
    }
  };

  const errorFor = (key: string) => (showErrors ? fieldErrors[key] : undefined);

  const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    // Auto-detect the type from the file name when creating.
    if (selected && !isEdit) {
      setDocumentType(documentTypeFromFileName(selected.name));
    }
  };

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
        aria-labelledby="document-modal-title"
        onSubmit={handleSubmit}
        className="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] px-5 py-4">
          <h2
            id="document-modal-title"
            className="text-base font-semibold text-[var(--text-primary)]"
          >
            {isEdit ? "Edit Document" : "Upload Document"}
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
          <Field label="Document Title" required error={errorFor("title")}>
            <input
              ref={firstFieldRef}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              onBlur={() => setTitle((value) => value.trim())}
              disabled={submitting}
              placeholder="e.g. CS101 Syllabus"
              aria-invalid={Boolean(errorFor("title"))}
              className={cn(
                FIELD_CLASS,
                errorFor("title")
                  ? "border-[var(--danger)] focus:border-[var(--danger)]"
                  : "border-[var(--border-subtle)] focus:border-[var(--accent)]",
              )}
            />
          </Field>

          <Field label="Object" hint="Link this document to an existing object.">
            <select
              value={objectId}
              onChange={(event) => setObjectId(event.target.value)}
              disabled={submitting}
              className={cn(FIELD_CLASS, "border-[var(--border-subtle)] focus:border-[var(--accent)]")}
            >
              <option value="">— No linked object —</option>
              {objects.map((object) => (
                <option key={object.id} value={object.id}>
                  {object.title}
                </option>
              ))}
            </select>
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Document Type" required error={errorFor("documentType")}>
              <select
                value={documentType}
                onChange={(event) => setDocumentType(event.target.value)}
                disabled={submitting}
                className={cn(
                  FIELD_CLASS,
                  "border-[var(--border-subtle)] focus:border-[var(--accent)]",
                )}
              >
                {DOCUMENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {titleCase(type)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Status">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as DocumentStatus)}
                disabled={submitting}
                className={cn(
                  FIELD_CLASS,
                  "border-[var(--border-subtle)] focus:border-[var(--accent)]",
                )}
              >
                {DOCUMENT_STATUSES.map((option) => (
                  <option key={option} value={option}>
                    {titleCase(option)}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={submitting}
              rows={2}
              placeholder="Optional notes about this document…"
              className={cn(
                FIELD_CLASS,
                "resize-none border-[var(--border-subtle)] focus:border-[var(--accent)]",
              )}
            />
          </Field>

          <Field label="Tags" hint="Press Enter or comma to add a tag.">
            <div
              className={cn(
                "flex flex-wrap items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1.5 focus-within:border-[var(--accent)]",
              )}
            >
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-hover)] px-2 py-0.5 text-xs text-[var(--text-secondary)]"
                >
                  {tag}
                  <button
                    type="button"
                    onClick={() => setTags((current) => current.filter((t) => t !== tag))}
                    disabled={submitting}
                    aria-label={`Remove tag ${tag}`}
                    className="text-[var(--text-tertiary)] hover:text-[var(--danger)]"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
              <input
                value={tagDraft}
                onChange={(event) => setTagDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === ",") {
                    event.preventDefault();
                    addTag(tagDraft);
                  } else if (event.key === "Backspace" && !tagDraft && tags.length) {
                    setTags((current) => current.slice(0, -1));
                  }
                }}
                disabled={submitting}
                placeholder={tags.length ? "" : "e.g. syllabus, fall-2026"}
                className="min-w-[8rem] flex-1 bg-transparent py-0.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none"
              />
            </div>
          </Field>

          {!isEdit ? (
            <>
              <Field label="Choose File" required error={errorFor("file")}>
                <label
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-lg border border-dashed px-3 py-3 text-sm transition-colors",
                    errorFor("file")
                      ? "border-[var(--danger)]"
                      : "border-[var(--border-strong)] hover:border-[var(--accent)]",
                    submitting && "cursor-not-allowed opacity-60",
                  )}
                >
                  <Upload className="h-5 w-5 text-[var(--text-tertiary)]" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate text-[var(--text-secondary)]">
                    {file ? file.name : "Click to choose a file…"}
                  </span>
                  <input
                    type="file"
                    onChange={onFileChange}
                    disabled={submitting}
                    className="sr-only"
                  />
                </label>
              </Field>

              <Field label="Uploaded By" required error={errorFor("uploadedBy")}>
                <input
                  value={uploadedBy}
                  onChange={(event) => setUploadedBy(event.target.value)}
                  onBlur={() => setUploadedBy((value) => value.trim())}
                  disabled={submitting}
                  placeholder="e.g. faculty:123"
                  aria-invalid={Boolean(errorFor("uploadedBy"))}
                  className={cn(
                    FIELD_CLASS,
                    errorFor("uploadedBy")
                      ? "border-[var(--danger)] focus:border-[var(--danger)]"
                      : "border-[var(--border-subtle)] focus:border-[var(--accent)]",
                  )}
                />
              </Field>

              {progress !== null ? (
                <div
                  className="h-2 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]"
                  role="progressbar"
                  aria-valuenow={progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="h-full rounded-full bg-[var(--accent)] transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              ) : null}
            </>
          ) : null}

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
            {submitting
              ? isEdit
                ? "Saving…"
                : progress !== null
                  ? `Uploading… ${progress}%`
                  : "Uploading…"
              : isEdit
                ? "Save changes"
                : "Upload"}
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
