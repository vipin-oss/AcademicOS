"use client";

/**
 * PART 1 — User Profile: name / email / designation / department /
 * institution / biography plus the profile photo (multipart upload →
 * FileStorage port, binary preview, remove). Saves via
 * `PUT /settings/profile`; the photo buttons talk to /settings/profile/photo
 * directly and then ask the workspace to re-fetch the document.
 */
import { useRef, useState } from "react";
import { UserRound } from "lucide-react";

import { toErrorMessage } from "@/lib/api/client";
import { deleteProfilePhoto, profilePhotoUrl, uploadProfilePhoto } from "@/lib/api/settings";
import { PHOTO_ACCEPT, PHOTO_MAX_BYTES } from "@/lib/settings/constants";
import type { ProfileSection as ProfileValues } from "@/types";
import {
  Field,
  GHOST_BUTTON_CLASS,
  SaveBar,
  SectionCard,
  TextArea,
  TextInput,
  useSyncedDraft,
} from "./SettingsShared";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function ProfileSection({
  values,
  hasPhoto,
  photoName,
  photoVersion,
  onSave,
  onPhotoChanged,
}: {
  values: ProfileValues;
  hasPhoto: boolean;
  photoName: string | null;
  photoVersion: string;
  onSave: (values: ProfileValues) => Promise<void>;
  onPhotoChanged: () => void;
}) {
  const { draft, update, dirty } = useSyncedDraft(values);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [photoMessage, setPhotoMessage] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const edit = (patch: Partial<ProfileValues>) => {
    setSaved(false);
    setError(null);
    update(patch);
  };

  const handleSave = async () => {
    if (saving) return;
    setError(null);
    setSaved(false);
    if (draft.email.trim() && !EMAIL_RE.test(draft.email.trim())) {
      setError("Enter a valid email address, or leave it empty.");
      return;
    }
    setSaving(true);
    try {
      await onSave(draft);
      setSaved(true);
    } catch (err) {
      setError(toErrorMessage(err, "Could not save the profile."));
    } finally {
      setSaving(false);
    }
  };

  const handlePhotoFile = async (file: File | undefined) => {
    if (!file || photoBusy) return;
    setPhotoError(null);
    setPhotoMessage(null);
    if (!PHOTO_ACCEPT.split(",").includes(file.type)) {
      setPhotoError("The photo must be a PNG, JPEG, WebP or GIF image.");
      return;
    }
    if (file.size > PHOTO_MAX_BYTES) {
      setPhotoError("The photo must be at most 2 MB.");
      return;
    }
    setPhotoBusy(true);
    try {
      await uploadProfilePhoto(file);
      setPhotoMessage("Photo updated.");
      onPhotoChanged();
    } catch (err) {
      setPhotoError(toErrorMessage(err, "Could not upload the photo."));
    } finally {
      setPhotoBusy(false);
    }
  };

  const handleRemovePhoto = async () => {
    if (photoBusy) return;
    setPhotoError(null);
    setPhotoMessage(null);
    setPhotoBusy(true);
    try {
      await deleteProfilePhoto();
      setPhotoMessage("Photo removed.");
      onPhotoChanged();
    } catch (err) {
      setPhotoError(toErrorMessage(err, "Could not remove the photo."));
    } finally {
      setPhotoBusy(false);
    }
  };

  return (
    <SectionCard
      title="Profile"
      description="Who you are in AcademicOS. This is preference/profile information only — it does not duplicate records from the Faculty or People modules."
      footer={
        <SaveBar
          saveAriaLabel="Save profile"
          statusAriaLabel="Profile status"
          saving={saving}
          saved={saved}
          error={error}
          disabled={!dirty}
          onSave={handleSave}
        />
      }
    >
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface-2)]">
          {hasPhoto ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              aria-label="Profile photo preview"
              alt="Profile photo"
              className="h-full w-full object-cover"
              src={profilePhotoUrl(photoVersion)}
            />
          ) : (
            <UserRound
              aria-label="Profile photo placeholder"
              className="h-7 w-7 text-[var(--text-tertiary)]"
            />
          )}
        </div>
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              aria-label="Profile photo file"
              accept={PHOTO_ACCEPT}
              className="hidden"
              onChange={(event) => {
                void handlePhotoFile(event.target.files?.[0]);
                event.target.value = "";
              }}
            />
            <button
              type="button"
              aria-label="Upload photo"
              className={GHOST_BUTTON_CLASS}
              disabled={photoBusy}
              onClick={() => fileInputRef.current?.click()}
            >
              {photoBusy ? "Working…" : hasPhoto ? "Change photo" : "Upload photo"}
            </button>
            {hasPhoto ? (
              <button
                type="button"
                aria-label="Remove profile photo"
                className={GHOST_BUTTON_CLASS}
                disabled={photoBusy}
                onClick={() => void handleRemovePhoto()}
              >
                Remove
              </button>
            ) : null}
          </div>
          <p className="text-xs text-[var(--text-tertiary)]">
            PNG, JPEG, WebP or GIF — at most 2 MB.
            {hasPhoto && photoName ? ` Current file: ${photoName}.` : ""}
          </p>
          <span role="status" aria-live="polite" aria-label="Profile photo status" className="block text-sm text-[var(--success)]">
            {photoMessage ?? ""}
          </span>
          {photoError ? (
            <span role="alert" className="block text-sm text-[var(--danger)]">
              {photoError}
            </span>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name">
          <TextInput
            ariaLabel="Profile name"
            value={draft.name}
            placeholder="e.g. Dr. Ananya Sharma"
            onChange={(value) => edit({ name: value })}
          />
        </Field>
        <Field label="Email">
          <TextInput
            ariaLabel="Profile email"
            type="email"
            value={draft.email}
            placeholder="name@institution.edu"
            onChange={(value) => edit({ email: value })}
          />
        </Field>
        <Field label="Designation">
          <TextInput
            ariaLabel="Profile designation"
            value={draft.designation}
            placeholder="e.g. Associate Professor"
            onChange={(value) => edit({ designation: value })}
          />
        </Field>
        <Field label="Department">
          <TextInput
            ariaLabel="Profile department"
            value={draft.department}
            placeholder="e.g. Computer Science"
            onChange={(value) => edit({ department: value })}
          />
        </Field>
        <Field label="Institution">
          <TextInput
            ariaLabel="Profile institution"
            value={draft.institution}
            placeholder="e.g. Delhi University"
            onChange={(value) => edit({ institution: value })}
          />
        </Field>
      </div>
      <Field label="Biography" hint="A short note about you — at most 1000 characters.">
        <TextArea
          ariaLabel="Profile biography"
          value={draft.biography}
          rows={4}
          placeholder="Research interests, teaching focus, …"
          onChange={(value) => edit({ biography: value })}
        />
      </Field>
    </SectionCard>
  );
}
