"use client";

import { useState } from "react";
import { FolderInput } from "lucide-react";
import { toErrorMessage } from "@/lib/api/client";
import { createIntakeSession } from "@/lib/api/intake";
import type { IntakeSourceKind } from "@/types";
import { cn } from "@/lib/utils";

/**
 * Start-import panel. Source is a path on this machine (AcademicOS is a
 * local, single-user OS — the backend reads the filesystem directly, exactly
 * like a desktop file picker would hand paths to the OS).
 */
export function CreateSessionForm({
  onCreated,
}: {
  onCreated: (sessionId: string) => void;
}) {
  const [kind, setKind] = useState<IntakeSourceKind>("folder");
  const [path, setPath] = useState("");
  const [pathsText, setPathsText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filePaths = pathsText
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const canSubmit =
    !submitting && (kind === "folder" ? path.trim().length > 0 : filePaths.length > 0);

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const session = await createIntakeSession(
        kind === "folder"
          ? { source_kind: "folder", path: path.trim(), actor: "me" }
          : { source_kind: "files", paths: filePaths, actor: "me" },
      );
      setPath("");
      setPathsText("");
      onCreated(session.id);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      aria-label="New import"
      className="flex flex-col gap-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5"
    >
      <div className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-subtle)] text-[var(--accent)]">
          <FolderInput className="h-4 w-4" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">New import</h2>
          <p className="text-xs text-[var(--text-tertiary)]">
            Drop a folder path or a list of files — the pipeline walks, stages and hashes
            everything, then holds for your review.
          </p>
        </div>
      </div>

      <div className="flex gap-2" role="radiogroup" aria-label="Import source">
        {(
          [
            ["folder", "Source folder"],
            ["files", "Source files"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={kind === value}
            aria-label={label}
            onClick={() => setKind(value)}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
              kind === value
                ? "border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]"
                : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]",
            )}
          >
            {value === "folder" ? "Folder" : "Files"}
          </button>
        ))}
      </div>

      {kind === "folder" ? (
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="intake-folder-path"
            className="text-xs font-medium text-[var(--text-secondary)]"
          >
            Folder path on this machine
          </label>
          <input
            id="intake-folder-path"
            aria-label="Folder path"
            type="text"
            value={path}
            onChange={(event) => setPath(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void submit();
            }}
            placeholder="/Users/me/Documents/Research Papers"
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
          />
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="intake-file-paths"
            className="text-xs font-medium text-[var(--text-secondary)]"
          >
            File paths — one per line
          </label>
          <textarea
            id="intake-file-paths"
            aria-label="File paths"
            rows={4}
            value={pathsText}
            onChange={(event) => setPathsText(event.target.value)}
            placeholder={"/Users/me/Documents/grant-letter.pdf\n/Users/me/Pictures/certificate.png"}
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-3 py-2 font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:outline-none"
          />
          <p className="text-xs text-[var(--text-tertiary)]" aria-live="polite">
            {filePaths.length > 0 ? `${filePaths.length} file(s) queued` : "No files yet"}
          </p>
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm text-[var(--danger)]">
          {error}
        </p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label="Start import"
          disabled={!canSubmit}
          onClick={() => void submit()}
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors",
            canSubmit
              ? "bg-[var(--accent)] hover:bg-[var(--accent-strong,#1d4ed8)]"
              : "cursor-not-allowed bg-[var(--border-strong)]",
          )}
        >
          {submitting ? "Starting…" : "Start import"}
        </button>
        <p className="text-xs text-[var(--text-tertiary)]">
          Nothing is committed automatically — every file waits in the review queue.
        </p>
      </div>
    </section>
  );
}
