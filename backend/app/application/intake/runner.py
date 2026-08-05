"""IntakeRunner — executes one session through the M1 pipeline stages.

The runner is the *only* engine that advances items. Its discipline:

- **Idempotent everywhere.** A finished step is detectable from item metadata
  (``staged_key`` present, ``sha256`` present), so a resumed drain never
  redoes finished work — and rewrites the *same* staging key, never a second
  blob.
- **Cooperative control.** Between steps it probes the job manager's control
  flags; pause/cancel are persisted to the session *before* the runner
  yields, so a paused dashboard chip always reflects durable state. Deletion
  underneath a live run aborts without writing back (rows are gone).
- **Per-item isolation.** One unreadable/oversized file becomes an item
  ``error`` with an actionable message; the batch continues. Only systemic
  failures (source folder vanished, enumeration crash) fail the session.
- **Deferred stages are real.** EXTRACT/CLASSIFY/MATCH/PROPOSE record a typed
  transition with the milestone that will own their logic; nothing is a stub
  left to rot.

Depends only on the ``ObjectRepository`` / ``FileStorage`` ports and the
intake pipeline helpers — no FastAPI, no SQLAlchemy, no threading here (the
job manager owns the thread).
"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from app.application.dtos.intake import (
    HISTORY_LIMIT,
    INTAKE_ACTOR,
    ITEM_STAGE_SEQUENCE,
    KEY_ATTEMPTS,
    KEY_CONTROL,
    KEY_CURRENT_ITEM,
    KEY_CURRENT_STAGE,
    KEY_ENDED_AT,
    KEY_ERROR,
    KEY_EXTENSION,
    KEY_INTAKE_STATUS,
    KEY_ITEM_STAGE,
    KEY_MIME_TYPE,
    KEY_ORIGINAL_PATH,
    KEY_PROGRESS,
    KEY_RELATIVE_PATH,
    KEY_SESSION_ID,
    KEY_SHA256,
    KEY_SIZE_BYTES,
    KEY_SOURCE,
    KEY_STAGE_HISTORY,
    KEY_STAGED_KEY,
    KEY_STATISTICS,
    KEY_SUMMARY,
    MAX_FILE_BYTES,
    RETRY_LIMIT,
    IntakeItemStatus,
    IntakeSessionStatus,
    IntakeSourceKind,
    IntakeStage,
    intake_item_facts,
    json_decode,
    json_encode,
    summarize_items,
)
from app.application.intake.extraction.service import ExtractionService
from app.application.intake.pipeline import (
    _CHUNK,
    ItemStageError,
    deferred_stage_result,
    detect_extension,
    digest_of,
    finish_record,
    human_bytes,
    new_hasher,
    should_skip_dir,
    should_skip_file,
    sniff_mime,
    staging_key_for,
    utcnow_iso,
)
from app.application.ports.document_parser import DocumentParsers
from app.application.ports.file_storage import FileStorage
from app.domain.entities.object import UniversalObject
from app.domain.exceptions import OptimisticConcurrencyError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId

# Control probe outcomes (kept as plain strings — the manager vocabulary).
_GO = "go"
_PAUSE = "pause"
_CANCEL = "cancel"
_DELETED = "deleted"


def _entry(key: str, value: str) -> MetadataEntry:
    """All intake writes are system facts: L1 layer, SYSTEM provenance."""

    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


def _put(obj: UniversalObject, key: str, value: str) -> None:
    obj.set_metadata(_entry(key, value), actor=INTAKE_ACTOR)


class RunAborted(Exception):
    """Cooperative stop requested between steps."""

    def __init__(self, outcome: str, *, persist: bool = True) -> None:
        super().__init__(outcome)
        self.outcome = outcome
        self.persist = persist


class IntakeSessionError(Exception):
    """Systemic run failure (the session itself cannot continue)."""


class IntakeRunner:
    """Drain one session: enumerate -> per-item stage machine -> finalize."""

    def __init__(
        self,
        repository: ObjectRepository,
        storage: FileStorage,
        session_id: str,
        control: Callable[[], str],
        parsers: DocumentParsers,
        on_item: Callable[[UniversalObject], None] | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._session_id = session_id
        self._control = control
        # M2: deterministic extraction over the injected parser registry
        # (infrastructure adapters — application code never imports readers).
        self._extraction = ExtractionService(parsers)
        # M2.3: the job manager's lease heartbeat — folded into the per-item
        # session save (zero extra writes, fresh-by-construction).
        self._on_item = on_item

    # -------------------------------------------------------------- main
    def run(self) -> None:
        """Drive the session to a durable terminal/intermediate state."""

        session = self._load_session()
        if session is None:
            return  # deleted before the dispatcher picked it up
        while True:
            try:
                self._checkpoint()
                self._mark_running(session)
                self._enumerate(session)
                self._process_items(session)
                self._complete(session)
                return
            except RunAborted as abort:
                if abort.persist:
                    self._persist_abort(session, abort.outcome)
                return
            except OptimisticConcurrencyError:
                # R3 — a concurrent control write (pause/cancel) landed on the
                # session row mid-drain, so this instance is stale. The row is
                # authoritative: re-load and let the cooperative checkpoint
                # decide. The drain is resumable by design (stage/item work is
                # idempotent), so a restart repeats no work and a stale write
                # never fails the session.
                session = self._load_session()
                if session is None:
                    return  # deleted underneath — nothing left to annotate
            except Exception as exc:  # noqa: BLE001 — systemic failure is session-level
                self._fail(session, exc)
                return

    # ------------------------------------------------------ session verbs
    def _load_session(self) -> UniversalObject | None:
        obj = self._repository.get_by_id(ObjectId(self._session_id))
        if obj is None or obj.object_type is not ObjectType.INTAKE_SESSION:
            return None
        return obj

    def _items(self) -> list[UniversalObject]:
        items = self._repository.find(object_type=ObjectType.INTAKE_ITEM)
        mine = [
            i
            for i in items
            if (i.metadata.get_value(KEY_SESSION_ID) or "") == self._session_id
        ]
        mine.sort(key=lambda i: (i.metadata.get_value(KEY_RELATIVE_PATH) or i.title).lower())
        return mine

    def _checkpoint(self) -> None:
        outcome = self._control()
        if outcome == _GO:
            return
        if outcome == _DELETED:
            raise RunAborted(_CANCEL, persist=False)
        if outcome == _PAUSE:
            raise RunAborted(_PAUSE)
        raise RunAborted(_CANCEL)

    def _mark_running(self, session: UniversalObject) -> None:
        _put(session, KEY_INTAKE_STATUS, IntakeSessionStatus.RUNNING.value)
        _put(session, KEY_CURRENT_STAGE, IntakeStage.ENUMERATE.value)
        _put(session, KEY_CONTROL, json_encode({"pause": False, "cancel": False}))
        self._repository.save(session)

    # ---------------------------------------------------------- enumerate
    def _enumerate(self, session: UniversalObject) -> None:
        progress = json_decode(session.metadata.get_value(KEY_PROGRESS), {})
        if progress.get("enumerated"):
            return  # resume: the walk already happened

        source = json_decode(session.metadata.get_value(KEY_SOURCE), {})
        kind = source.get("kind")
        discovered: list[tuple[str, str, int]] = []  # (abs path, rel path, size)
        skipped = 0
        samples: list[str] = []

        def note_skip(reason: str) -> None:
            nonlocal skipped
            skipped += 1
            if len(samples) < 10:
                samples.append(reason)

        if kind == IntakeSourceKind.FOLDER.value:
            root = Path(source.get("path") or "")
            if not root.is_dir():
                raise IntakeSessionError(f"Source folder no longer exists: {root}")
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if not should_skip_dir(d))
                for name in sorted(filenames):
                    if should_skip_file(name):
                        note_skip(name)
                        continue
                    absolute = Path(dirpath) / name
                    try:
                        size = absolute.stat().st_size
                    except OSError:
                        note_skip(f"{absolute} (unreadable)")
                        continue
                    rel = absolute.relative_to(root).as_posix()
                    discovered.append((str(absolute), rel, size))
        else:
            for raw in source.get("paths") or []:
                absolute = Path(raw)
                try:
                    size = absolute.stat().st_size
                except OSError:
                    note_skip(f"{absolute} (unreadable)")
                    continue
                discovered.append((str(absolute), absolute.name, size))

        discovered.sort(key=lambda entry: entry[1].lower())

        # Idempotent re-walk: a paused/failed session whose progress flag never
        # flipped is re-enumerated on resume; items are unique per relative
        # path, so finished discovery is never duplicated.
        existing = {
            (item.metadata.get_value(KEY_RELATIVE_PATH) or item.title)
            for item in self._items()
        }
        for index, (abs_path, rel, size) in enumerate(discovered):
            if index % 25 == 0:
                self._checkpoint()  # pause/cancel/delete takes effect mid-walk
            if rel in existing:
                continue
            self._create_item(session, abs_path, rel, size)

        statistics = json_decode(session.metadata.get_value(KEY_STATISTICS), {})
        statistics["skipped_junk"] = skipped
        statistics["skipped_junk_samples"] = samples
        _put(session, KEY_STATISTICS, json_encode(statistics))
        progress["enumerated"] = True
        _put(session, KEY_PROGRESS, json_encode(progress))
        self._repository.save(session)

    def _create_item(
        self, session: UniversalObject, abs_path: str, rel: str, size: int
    ) -> None:
        filename = rel.rsplit("/", 1)[-1]
        record = finish_record(IntakeStage.ENUMERATE, utcnow_iso(), {"discovered": True})
        entries = [
            _entry(KEY_SESSION_ID, self._session_id),
            _entry(KEY_INTAKE_STATUS, IntakeItemStatus.PENDING.value),
            _entry(KEY_ORIGINAL_PATH, abs_path),
            _entry(KEY_RELATIVE_PATH, rel),
            _entry(KEY_EXTENSION, detect_extension(filename)),
            _entry(KEY_SIZE_BYTES, str(size)),
            _entry(KEY_ITEM_STAGE, IntakeStage.ENUMERATE.value),
            _entry(KEY_STAGE_HISTORY, json_encode([record.to_dict()])),
            _entry(KEY_ATTEMPTS, "0"),
        ]
        item = UniversalObject.create(
            object_type=ObjectType.INTAKE_ITEM,
            title=filename,
            created_by=INTAKE_ACTOR,
            object_id=ObjectId.generate(ObjectType.INTAKE_ITEM),
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=tuple(entries)),
        )
        # Structural edge: the item is part of this session (system-asserted).
        item.add_relationship(
            session.id, RelationshipKind.PART_OF, Provenance.SYSTEM, actor=INTAKE_ACTOR
        )
        self._repository.save(item)

    # -------------------------------------------------------- item stages
    def _process_items(self, session: UniversalObject) -> None:
        work = [item for item in self._items() if self._needs_work(item)]
        for item in work:
            self._checkpoint()
            self._run_item(session, item)

    @staticmethod
    def _attempts(item: UniversalObject) -> int:
        raw = item.metadata.get_value(KEY_ATTEMPTS)
        try:
            return int(raw) if raw is not None else 0
        except ValueError:
            return 0

    def _needs_work(self, item: UniversalObject) -> bool:
        status = item.metadata.get_value(KEY_INTAKE_STATUS) or IntakeItemStatus.PENDING.value
        if status in (
            IntakeItemStatus.PENDING.value,
            IntakeItemStatus.STAGED.value,
            # M2.3: crash/pause leftovers — an item frozen mid-attempt always
            # resumes (its already-finished steps detect themselves idempotently).
            IntakeItemStatus.EXTRACTING.value,
            IntakeItemStatus.RETRYING.value,
        ):
            return True
        if status == IntakeItemStatus.ERROR.value:
            # Retry discipline: retrying stops at RETRY_LIMIT attempts; the
            # item is then terminally Failed and the batch simply moves on.
            return self._attempts(item) < RETRY_LIMIT
        return False

    def _run_item(self, session: UniversalObject, item: UniversalObject) -> None:
        attempts = self._attempts(item) + 1
        _put(item, KEY_ATTEMPTS, str(attempts))
        _put(item, KEY_ERROR, json_encode(None))
        # M2.3: the visible attempt status — first run ``extracting``, every
        # later attempt ``retrying``. Persisted before work starts so the
        # queue view is always live (and a crash leaves a resumable state).
        _put(
            item,
            KEY_INTAKE_STATUS,
            IntakeItemStatus.EXTRACTING.value
            if attempts == 1
            else IntakeItemStatus.RETRYING.value,
        )
        self._repository.save(item)
        rel = item.metadata.get_value(KEY_RELATIVE_PATH) or item.title
        # "Currently processing" is live from the item's first checkpoint.
        _put(session, KEY_CURRENT_ITEM, json_encode(rel))
        self._repository.save(session)
        stage = IntakeStage.STAGE
        try:
            for stage in ITEM_STAGE_SEQUENCE:
                self._checkpoint()
                entered = utcnow_iso()
                result = self._execute_stage(item, stage)
                self._record_step(item, stage, entered, result)
                self._repository.save(item)
            _put(item, KEY_INTAKE_STATUS, IntakeItemStatus.AWAITING_REVIEW.value)
            self._repository.save(item)
        except ItemStageError as exc:
            self._record_step(item, stage, utcnow_iso(), {"error": str(exc)})
            _put(item, KEY_ERROR, json_encode({"stage": stage.value, "message": str(exc)}))
            _put(item, KEY_INTAKE_STATUS, IntakeItemStatus.ERROR.value)
            self._repository.save(item)
        # M2.3 live foreground: the stage cursor plus the manager's lease
        # heartbeat — all folded into the one session row update.
        _put(session, KEY_CURRENT_STAGE, stage.value)
        if self._on_item is not None:
            try:
                self._on_item(session)
            except Exception:  # noqa: BLE001 — a lease hiccup must never
                pass  # corrupt the item that just finished safely.
        self._repository.save(session)

    def _execute_stage(self, item: UniversalObject, stage: IntakeStage) -> dict:
        if stage is IntakeStage.STAGE:
            return self._stage_blob(item)
        if stage is IntakeStage.HASH:
            return self._verify_and_sniff(item)
        if stage is IntakeStage.EXTRACT:
            # M2: real deterministic extraction (descriptor + text blob).
            return self._extraction.extract_item(item, self._storage, session_id=self._session_id)
        if stage is IntakeStage.REVIEW:
            return {"awaiting": "human review", "commit": "M9 (commit engine)"}
        return deferred_stage_result(stage)

    def _record_step(
        self, item: UniversalObject, stage: IntakeStage, entered_at: str, result: dict
    ) -> None:
        record = finish_record(stage, entered_at, result)
        history = json_decode(item.metadata.get_value(KEY_STAGE_HISTORY), [])
        history = (history + [record.to_dict()])[-HISTORY_LIMIT:]
        _put(item, KEY_ITEM_STAGE, stage.value)
        _put(item, KEY_STAGE_HISTORY, json_encode(history))

    # --------------------------------------------------------- stage work
    def _stage_blob(self, item: UniversalObject) -> dict:
        """Copy source bytes into the staging prefix while hashing them.

        Byte-oriented because the frozen ``FileStorage`` port is byte-oriented
        (one ``save(key, content)``); the V2 storage milestone may add chunked
        streaming behind the same port without changing this call site.
        """

        rel = item.metadata.get_value(KEY_RELATIVE_PATH) or item.title
        key = staging_key_for(self._session_id, rel)
        existing = item.metadata.get_value(KEY_STAGED_KEY)
        if existing == key and self._storage.exists(key):
            return {"reused": True, "key": key}

        declared = item.metadata.get_value(KEY_SIZE_BYTES)
        if declared and int(declared) > MAX_FILE_BYTES:
            raise ItemStageError(f"File exceeds the {human_bytes(MAX_FILE_BYTES)} intake cap.")

        src = item.metadata.get_value(KEY_ORIGINAL_PATH) or ""
        hasher = new_hasher()
        buffer = bytearray()
        try:
            with open(src, "rb") as handle:
                while True:
                    chunk = handle.read(_CHUNK)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    buffer.extend(chunk)
                    if len(buffer) > MAX_FILE_BYTES:
                        raise ItemStageError(
                            f"File exceeds the {human_bytes(MAX_FILE_BYTES)} intake cap."
                        )
        except ItemStageError:
            raise
        except OSError as exc:
            raise ItemStageError(f"Cannot read source file: {exc.strerror or exc}.") from exc

        digest = hasher.hexdigest()
        try:
            self._storage.save(key, bytes(buffer))
        except Exception as exc:
            raise ItemStageError(f"Cannot write the staged copy: {exc}.") from exc

        _put(item, KEY_STAGED_KEY, key)
        _put(item, KEY_SHA256, digest)
        _put(item, KEY_SIZE_BYTES, str(len(buffer)))
        _put(item, KEY_INTAKE_STATUS, IntakeItemStatus.STAGED.value)
        return {"bytes": len(buffer), "sha256": digest, "key": key}

    def _verify_and_sniff(self, item: UniversalObject) -> dict:
        """Re-read the staged blob: integrity check + MIME sniff (magic bytes)."""

        key = item.metadata.get_value(KEY_STAGED_KEY)
        if not key or not self._storage.exists(key):
            raise ItemStageError("Staged copy is missing; the stage step must rerun.")
        try:
            blob = self._storage.read(key)
        except Exception as exc:
            raise ItemStageError(f"Cannot read the staged copy: {exc}.") from exc

        expected = item.metadata.get_value(KEY_SHA256)
        actual = digest_of(blob)
        if expected and actual != expected:
            raise ItemStageError("Integrity check failed: staged bytes changed after copy.")

        mime = sniff_mime(blob[:512], item.title)
        _put(item, KEY_MIME_TYPE, mime)
        return {"verified": True, "mime": mime, "bytes": len(blob)}

    # --------------------------------------------------------- finalizers
    def _persist_abort(self, session: UniversalObject, outcome: str) -> None:
        fresh = self._load_session()
        if fresh is None:
            return  # deleted mid-abort — nothing left to annotate
        _put(fresh, KEY_CURRENT_ITEM, json_encode(None))
        if outcome == _PAUSE:
            _put(fresh, KEY_INTAKE_STATUS, IntakeSessionStatus.PAUSED.value)
        else:
            _put(fresh, KEY_INTAKE_STATUS, IntakeSessionStatus.CANCELLED.value)
            _put(fresh, KEY_ENDED_AT, utcnow_iso())
            facts = [intake_item_facts(i) for i in self._items()]
            live = summarize_items(facts, enumerated=True)
            _put(
                fresh,
                KEY_SUMMARY,
                f"Cancelled — {live['processed_items']}/{live['total_items']} files processed. "
                "Start a new session to import the rest.",
            )
        self._repository.save(fresh)

    def _complete(self, session: UniversalObject) -> None:
        source = json_decode(session.metadata.get_value(KEY_SOURCE), {})
        display = source.get("display") or source.get("path") or "the drop"
        items = self._items()
        facts = [intake_item_facts(i) for i in items]
        live = summarize_items(facts, enumerated=True)

        total = live["total_items"]
        ok = live["awaiting_review"]
        errors = live["errors"]
        if total == 0:
            summary = f"No supported files found in {display}."
        else:
            summary = (
                f"Imported {ok}/{total} files ({human_bytes(live['total_bytes'])}) from {display}"
                f" — {errors} error(s)."
            )
            if errors == 0:
                summary = summary.replace(" — 0 error(s).", ".")
            # M2: extraction rollups are part of the honest completion story.
            extracted = live["extracted_items"]
            unsupported = live["unsupported_items"]
            if extracted + unsupported > 0:
                summary += (
                    f" Extracted text from {extracted} file(s)"
                    + (f"; {unsupported} unsupported (kept staged)" if unsupported else "")
                    + "."
                )
            summary += " Files await your review; commit arrives with the proposal engine (M9)."

        stored = json_decode(session.metadata.get_value(KEY_STATISTICS), {})
        # Cooperative control wins the finish line: every other boundary in
        # the run lifecycle probes the control flags; this rollup is the only
        # blind spot. A pause/cancel accepted while completion work ran must
        # persist as the control state — the terminal write never swallows it.
        outcome = self._control()
        if outcome == _DELETED:
            return  # deleted underneath the completion rollup — persist nothing
        if outcome in (_PAUSE, _CANCEL):
            self._persist_abort(session, outcome)
            return
        _put(session, KEY_STATISTICS, json_encode({**live, **{"skipped_junk": stored.get("skipped_junk", 0), "skipped_junk_samples": stored.get("skipped_junk_samples", [])}}))
        _put(session, KEY_SUMMARY, summary)
        _put(session, KEY_CURRENT_ITEM, json_encode(None))
        _put(session, KEY_CURRENT_STAGE, IntakeStage.REVIEW.value)
        _put(session, KEY_ENDED_AT, utcnow_iso())
        _put(session, KEY_INTAKE_STATUS, IntakeSessionStatus.COMPLETED.value)
        self._repository.save(session)

    def _fail(self, session: UniversalObject, exc: Exception) -> None:
        stage = session.metadata.get_value(KEY_CURRENT_STAGE) or IntakeStage.ENUMERATE.value
        message = f"{type(exc).__name__}: {exc}"
        _put(session, KEY_CURRENT_ITEM, json_encode(None))
        _put(session, KEY_ERROR, json_encode({"stage": stage, "message": message}))
        _put(session, KEY_SUMMARY, f"Import failed at the {stage} step: {message} — resume to retry.")
        _put(session, KEY_ENDED_AT, utcnow_iso())
        _put(session, KEY_INTAKE_STATUS, IntakeSessionStatus.FAILED.value)
        self._repository.save(session)
