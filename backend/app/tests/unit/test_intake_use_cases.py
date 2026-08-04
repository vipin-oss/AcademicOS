"""Unit tests for intake use cases + the runner engine (in-memory fakes)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.application.commands.control_intake_session import ControlIntakeSessionCommand
from app.application.commands.create_intake_session import CreateIntakeSessionCommand
from app.application.commands.delete_intake_session import DeleteIntakeSessionCommand
from app.application.dtos.intake import (
    CreateIntakeSessionInput,
    IntakeSourceKind,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.intake.runner import IntakeRunner
from app.application.queries.get_intake_session import GetIntakeSessionQuery
from app.application.queries.list_intake_sessions import ListIntakeSessionsQuery
from app.application.use_cases.intake.control_session import (
    CancelIntakeSessionUseCase,
    PauseIntakeSessionUseCase,
    ResumeIntakeSessionUseCase,
)
from app.application.use_cases.intake.create_session import CreateIntakeSessionUseCase
from app.application.use_cases.intake.delete_session import DeleteIntakeSessionUseCase
from app.application.use_cases.intake.get_session import GetIntakeSessionUseCase
from app.application.use_cases.intake.list_sessions import ListIntakeSessionsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


# ---------------------------------------------------------------- fakes
class FakeRepo:
    def __init__(self) -> None:
        self.store: dict[str, UniversalObject] = {}

    def save(self, entity: UniversalObject) -> None:
        self.store[str(entity.id)] = entity

    def get_by_id(self, id) -> UniversalObject | None:
        return self.store.get(str(id))

    def exists(self, id) -> bool:
        return str(id) in self.store

    def delete(self, id) -> None:
        self.store.pop(str(id), None)

    def find(self, *, object_type=None, **_kwargs) -> list[UniversalObject]:
        return [
            obj for obj in self.store.values() if object_type is None or obj.object_type is object_type
        ]


class FakeStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def save(self, key: str, content: bytes) -> None:
        self.blobs[key] = bytes(content)

    def read(self, key: str) -> bytes:
        return self.blobs[key]

    def exists(self, key: str) -> bool:
        return key in self.blobs

    def delete(self, key: str) -> None:
        self.blobs.pop(key, None)


class FakeJobs:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request_pause(self, sid: str) -> None:
        self.calls.append(("pause", sid))

    def request_cancel(self, sid: str) -> None:
        self.calls.append(("cancel", sid))

    def mark_deleted(self, sid: str) -> None:
        self.calls.append(("deleted", sid))

    def enqueue(self, sid: str) -> None:
        self.calls.append(("enqueue", sid))


def _mk_fixture_folder(root: Path) -> None:
    (root / "Sub").mkdir(parents=True)
    (root / "a.txt").write_bytes(b"alpha")
    (root / "Sub" / "b.pdf").write_bytes(b"%PDF-1.4 two")
    (root / ".DS_Store").write_bytes(b"junk")


def _mk_session(repo: FakeRepo, storage_root: Path, source: Path, **kwargs) -> str:
    out = CreateIntakeSessionUseCase(repo, str(storage_root)).execute(
        CreateIntakeSessionCommand(
            input=CreateIntakeSessionInput(
                source_kind=IntakeSourceKind.FOLDER, path=str(source), actor="t", **kwargs
            )
        )
    )
    return out.id


def _run(repo: FakeRepo, storage: FakeStorage, sid: str, control=lambda: "go") -> None:
    IntakeRunner(repo, storage, sid, control).run()


def _status(repo: FakeRepo, sid: str) -> str:
    return repo.store[sid].metadata.get_value("intake.status")


def _items(repo: FakeRepo, sid: str) -> list[UniversalObject]:
    return [
        i
        for i in repo.find(object_type=ObjectType.INTAKE_ITEM)
        if (i.metadata.get_value("intake.session_id") or "") == sid
    ]


# ------------------------------------------------------------- create rules
class TestCreateValidation:
    def test_missing_folder_path_is_422(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="path is required"):
            _mk_session_with(FakeRepo(), tmp_path, CreateIntakeSessionInput(
                source_kind=IntakeSourceKind.FOLDER, path=None, actor="t"))

    def test_nonexistent_folder_is_422(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="does not exist"):
            _mk_session(FakeRepo(), tmp_path, tmp_path / "nope")

    def test_file_given_as_folder_is_422(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        f = source / "a.txt"
        f.write_bytes(b"x")
        with pytest.raises(ValidationError, match="not a directory"):
            _mk_session(FakeRepo(), tmp_path, f)

    def test_storage_overlap_rejected(self, tmp_path: Path) -> None:
        storage_root = tmp_path / "storage"
        source = tmp_path / "storage" / "incoming"
        source.mkdir(parents=True)
        with pytest.raises(ValidationError, match="overlap"):
            _mk_session(FakeRepo(), storage_root, source)

    def test_files_drop_requires_existing_files(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="at least one file"):
            CreateIntakeSessionUseCase(FakeRepo(), str(tmp_path)).execute(
                CreateIntakeSessionCommand(
                    input=CreateIntakeSessionInput(source_kind=IntakeSourceKind.FILES, actor="t")
                )
            )
        with pytest.raises(ValidationError, match="not a regular file"):
            CreateIntakeSessionUseCase(FakeRepo(), str(tmp_path)).execute(
                CreateIntakeSessionCommand(
                    input=CreateIntakeSessionInput(
                        source_kind=IntakeSourceKind.FILES,
                        paths=(str(tmp_path / "ghost.pdf"),),
                        actor="t",
                    )
                )
            )

    def test_happy_folder_session_seeds_metadata(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        repo = FakeRepo()
        sid = _mk_session(repo, tmp_path / "storage", source)
        obj = repo.store[sid]
        assert obj.object_type is ObjectType.INTAKE_SESSION
        assert obj.metadata.get_value("intake.status") == "queued"
        assert obj.metadata.get_value("intake.current_stage") == "enumerate"
        assert "Folder import — src" == obj.title

    def test_files_drop_title_and_paths(self, tmp_path: Path) -> None:
        f1 = tmp_path / "one.pdf"
        f1.write_bytes(b"1%PDF-")
        repo = FakeRepo()
        out = CreateIntakeSessionUseCase(repo, str(tmp_path / "st")).execute(
            CreateIntakeSessionCommand(
                input=CreateIntakeSessionInput(
                    source_kind=IntakeSourceKind.FILES, paths=(str(f1),), actor="t"
                )
            )
        )
        assert out.title == "File drop — 1 files"
        assert out.source["paths"] == [str(f1)]


def _mk_session_with(repo, storage_root, data) -> None:
    CreateIntakeSessionUseCase(repo, str(storage_root)).execute(
        CreateIntakeSessionCommand(input=data)
    )


# -------------------------------------------------------------- lifecycle
class TestLifecycleUseCases:
    def test_get_404_for_wrong_type(self, tmp_path: Path) -> None:
        repo = FakeRepo()
        doc = UniversalObject.create(object_type=ObjectType.DOCUMENT, title="d", created_by="t")
        repo.save(doc)
        with pytest.raises(ObjectNotFoundError):
            GetIntakeSessionUseCase(repo).execute(GetIntakeSessionQuery(session_id=str(doc.id)))

    def test_pause_resume_cancel_guards(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        repo, jobs = FakeRepo(), FakeJobs()
        sid = _mk_session(repo, tmp_path / "storage", source)

        # queued -> pause ok (flag recorded on the persisted control json)
        out = PauseIntakeSessionUseCase(repo, jobs).execute(ControlIntakeSessionCommand(session_id=sid))
        assert ("pause", sid) in jobs.calls
        assert '"pause":true' in repo.store[sid].metadata.get_value("intake.control")

        # paused -> resume ok (status back to queued, enqueue called)
        obj = repo.store[sid]
        from app.application.use_cases.intake.helpers import set_system_metadata
        set_system_metadata(obj, "intake.status", "paused")
        repo.save(obj)
        out = ResumeIntakeSessionUseCase(repo, jobs).execute(ControlIntakeSessionCommand(session_id=sid))
        assert out.status == "queued"
        assert ("enqueue", sid) in jobs.calls

        # queued -> cancel ok (flag set at dispatcher boundary)
        out = CancelIntakeSessionUseCase(repo, jobs).execute(ControlIntakeSessionCommand(session_id=sid))
        assert ("cancel", sid) in jobs.calls

        # terminal states reject further control
        set_system_metadata(repo.store[sid], "intake.status", "cancelled")
        with pytest.raises(ValidationError, match="Cannot pause"):
            PauseIntakeSessionUseCase(repo, jobs).execute(ControlIntakeSessionCommand(session_id=sid))
        with pytest.raises(ValidationError, match="Cannot resume"):
            ResumeIntakeSessionUseCase(repo, jobs).execute(ControlIntakeSessionCommand(session_id=sid))

    def test_pause_after_completed_is_422(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.txt").write_bytes(b"a")
        repo, storage, jobs = FakeRepo(), FakeStorage(), FakeJobs()
        sid = _mk_session(repo, tmp_path / "st", source)
        _run(repo, storage, sid)
        assert _status(repo, sid) == "completed"
        with pytest.raises(ValidationError, match="Cannot pause"):
            PauseIntakeSessionUseCase(repo, jobs).execute(ControlIntakeSessionCommand(session_id=sid))

    def test_resume_from_paused_persists_clean_control(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        repo, jobs = FakeRepo(), FakeJobs()
        sid = _mk_session(repo, tmp_path / "st", source)
        from app.application.use_cases.intake.helpers import set_system_metadata
        set_system_metadata(repo.store[sid], "intake.status", "failed")
        set_system_metadata(repo.store[sid], "intake.error", '{"stage":"session","message":"x"}')
        out = ResumeIntakeSessionUseCase(repo, jobs).execute(ControlIntakeSessionCommand(session_id=sid))
        assert out.status == "queued"
        assert out.error is None

    def test_delete_cascades_items_and_blobs(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.txt").write_bytes(b"alpha")
        repo, storage, jobs = FakeRepo(), FakeStorage(), FakeJobs()
        sid = _mk_session(repo, tmp_path / "st", source)
        _run(repo, storage, sid)
        assert storage.blobs, "expected staged blobs"
        assert _items(repo, sid), "expected items"
        DeleteIntakeSessionUseCase(repo, storage, jobs).execute(
            DeleteIntakeSessionCommand(session_id=sid)
        )
        assert sid not in repo.store
        assert _items(repo, sid) == []
        assert storage.blobs == {}
        assert ("cancel", sid) in jobs.calls and ("deleted", sid) in jobs.calls
        with pytest.raises(ObjectNotFoundError):
            GetIntakeSessionUseCase(repo).execute(GetIntakeSessionQuery(session_id=sid))

    def test_list_sessions_newest_first_with_live_progress(self, tmp_path: Path) -> None:
        repo = FakeRepo()
        for name in ("one", "two"):
            source = tmp_path / name
            source.mkdir()
            _mk_session(repo, tmp_path / "st", source)
        result = ListIntakeSessionsUseCase(repo).execute(ListIntakeSessionsQuery(page=1, page_size=10))
        assert result.total_count == 2
        assert result.items[0].created_at >= result.items[1].created_at
        assert all(i.progress["total"] == 0 for i in result.items)


# ---------------------------------------------------------------- runner
class TestRunner:
    def test_full_run_stages_hashes_and_reviews(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir(parents=True)
        _mk_fixture_folder(source)
        repo, storage = FakeRepo(), FakeStorage()
        sid = _mk_session(repo, tmp_path / "st", source)
        _run(repo, storage, sid)
        assert _status(repo, sid) == "completed"

        items = _items(repo, sid)
        assert len(items) == 2  # junk never becomes an item
        by_rel = {i.metadata.get_value("intake.relative_path"): i for i in items}
        assert set(by_rel) == {"a.txt", "Sub/b.pdf"}
        pdf = by_rel["Sub/b.pdf"]
        assert pdf.metadata.get_value("intake.mime_type") == "application/pdf"
        assert pdf.metadata.get_value("intake.status") == "awaiting_review"
        assert pdf.metadata.get_value("intake.sha256")
        key = pdf.metadata.get_value("intake.staged_key")
        from app.application.intake.pipeline import staging_key_for
        assert key == staging_key_for(sid, "Sub/b.pdf")
        assert ".." not in key and ":" not in key
        assert storage.blobs[key] == b"%PDF-1.4 two"

        history = pdf.metadata.get_value("intake.stage_history")
        for stage in ("enumerate", "stage", "hash", "extract", "classify", "match", "propose", "review"):
            assert f'"stage":"{stage}"' in history
        assert "M5" in history and "M7" in history  # deferred milestones recorded

        stats = repo.store[sid].metadata.get_value("intake.statistics")
        assert '"skipped_junk":1' in stats
        assert repo.store[sid].metadata.get_value("intake.current_stage") == "review"

    def test_resume_is_idempotent_and_skips_finished_work(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.txt").write_bytes(b"alpha")
        repo, storage = FakeRepo(), FakeStorage()
        sid = _mk_session(repo, tmp_path / "st", source)
        _run(repo, storage, sid)
        blob_before = dict(storage.blobs)
        _run(repo, storage, sid)  # second drain on a completed session
        assert storage.blobs == blob_before  # nothing rewritten
        assert _status(repo, sid) == "completed"

    def test_pause_persists_and_resume_continues(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        for i in range(5):
            (source / f"f{i}.txt").write_bytes(f"file-{i}".encode())
        repo, storage = FakeRepo(), FakeStorage()
        sid = _mk_session(repo, tmp_path / "st", source)

        calls = {"n": 0}

        def pause_on_third() -> str:
            calls["n"] += 1
            return "pause" if calls["n"] >= 4 else "go"

        _run(repo, storage, sid, control=pause_on_third)
        assert _status(repo, sid) == "paused"
        done = sum(1 for i in _items(repo, sid) if i.metadata.get_value("intake.status") == "awaiting_review")
        assert done < 5

        _run(repo, storage, sid)  # resume with clear control
        assert _status(repo, sid) == "completed"
        remaining = [i for i in _items(repo, sid) if i.metadata.get_value("intake.status") == "awaiting_review"]
        assert len(remaining) == 5

    def test_cancel_persists_cancelled(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.txt").write_bytes(b"a")
        repo, storage = FakeRepo(), FakeStorage()
        sid = _mk_session(repo, tmp_path / "st", source)
        _run(repo, storage, sid, control=lambda: "cancel")
        assert _status(repo, sid) == "cancelled"
        assert repo.store[sid].metadata.get_value("intake.ended_at")

    def test_deleted_abort_never_writes_back(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.txt").write_bytes(b"a")
        repo, storage = FakeRepo(), FakeStorage()
        sid = _mk_session(repo, tmp_path / "st", source)
        repo.delete(ObjectId(sid))  # delete before drain pops the job
        _run(repo, storage, sid)  # must simply no-op, never crash
        assert sid not in repo.store

    def test_item_error_is_isolated_and_retried(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        good = source / "good.txt"
        good.write_bytes(b"good")
        repo, storage = FakeRepo(), FakeStorage()
        sid = _mk_session(repo, tmp_path / "st", source)

        # Stage 1: vanish the file after enumeration -> item error, session completes.
        runner = IntakeRunner(repo, storage, sid, lambda: "go")
        session = runner._load_session()
        runner._mark_running(session)
        runner._enumerate(session)
        good.unlink()
        runner._process_items(session)
        runner._complete(session)
        items = _items(repo, sid)
        assert items[0].metadata.get_value("intake.status") == "error"
        assert "Cannot read source file" in items[0].metadata.get_value("intake.error")
        assert items[0].metadata.get_value("intake.attempts") == "1"
        assert _status(repo, sid) == "completed"

        # Stage 2: restore the file; a resume-style drain retries the item.
        good.write_bytes(b"good-again")
        _run(repo, storage, sid)
        assert items[0].metadata.get_value("intake.status") == "awaiting_review"
        assert items[0].metadata.get_value("intake.sha256")

    def test_oversize_file_capped_cleanly(self, tmp_path: Path, monkeypatch) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "big.bin").write_bytes(b"x" * 64)
        repo, storage = FakeRepo(), FakeStorage()
        sid = _mk_session(repo, tmp_path / "st", source)
        monkeypatch.setattr("app.application.intake.runner.MAX_FILE_BYTES", 10)
        _run(repo, storage, sid)
        (item,) = _items(repo, sid)
        assert item.metadata.get_value("intake.status") == "error"
        assert "intake cap" in item.metadata.get_value("intake.error")
        assert storage.blobs == {}

    def test_integrity_tamper_detected(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.txt").write_bytes(b"alpha")
        repo = FakeRepo()
        sid = _mk_session(repo, tmp_path / "st", source)

        class TamperStorage(FakeStorage):
            def read(self, key: str) -> bytes:
                return super().read(key) + b"tampered"

        _run(repo, TamperStorage(), sid)
        (item,) = _items(repo, sid)
        assert item.metadata.get_value("intake.status") == "error"
        assert "Integrity check failed" in item.metadata.get_value("intake.error")

    def test_empty_folder_completes_with_friendly_summary(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        (source / ".DS_Store").write_bytes(b"junk")
        repo, storage = FakeRepo(), FakeStorage()
        sid = _mk_session(repo, tmp_path / "st", source)
        _run(repo, storage, sid)
        assert _status(repo, sid) == "completed"
        summary = GetIntakeSessionUseCase(repo).execute(GetIntakeSessionQuery(session_id=sid)).summary
        assert "No supported files" in summary
