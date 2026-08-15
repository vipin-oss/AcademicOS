"""Integration tests: M2 Part 3 extraction queue & job management (API slice).

Same harness doctrine as ``test_intake_api.py`` (file-backed SQLite, real
LocalFileStorage, per-suite IntakeJobManager with the REAL parser registry —
Puppeteer-free proves of the whole queue contract through the public API):

- mixed bulk drain: real queue counters (errors / unsupported / needs_ocr /
  extracted) and the additive live-progress fields;
- retry endpoint: attempts 2 → 3 → terminal, honest 422 matrix;
- pause → resume: finished items are NEVER restarted (stage history frozen);
- crash recovery: extracting leftovers + stale lease → foreign reconcile →
  resume completes them, seeded descriptors are REUSED (never re-parsed);
- two-manager race: a fresh foreign lease blocks duplicate drains and a
  foreign reconcile — exactly one worker ever processes a session;
- cancel: graceful — finished items stay valid, no corrupted metadata;
- storage safety: staged bytes never change; text/preview parity holds
  through every retry round.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.api.dependencies.auth import get_current_user

import hashlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.documents import get_storage
from app.api.routes.intake import get_job_manager
from app.application.dtos.intake import (
    KEY_CONTROL,
    KEY_CURRENT_STAGE,
    KEY_INTAKE_STATUS,
    KEY_LEASE,
    KEY_PROGRESS,
    KEY_SOURCE,
    KEY_STATISTICS,
    json_decode,
    json_encode,
)
from app.application.intake.jobs import IntakeJobManager
from app.application.intake.runner import IntakeRunner
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.extraction import build_document_parsers
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage
from app.main import app
from app.tests.unit.extraction_fixtures import make_pdf_bytes

API = "/api/v1/intake"


def wait_terminal(client: TestClient, sid: str, *, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"{API}/sessions/{sid}/progress").json()
        if body["status"] in ("completed", "failed", "paused", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"session {sid} did not settle in {timeout}s")


def wait_for(client: TestClient, sid: str, predicate, *, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        last = client.get(f"{API}/sessions/{sid}/progress").json()
        if predicate(last):
            return last
        time.sleep(0.05)
    raise AssertionError(f"predicate never satisfied for {sid}; last={last}")


@pytest.fixture()
def harness(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    request_session = maker()

    def factory() -> tuple[SQLAlchemyObjectRepository, object]:
        session = maker()
        return SQLAlchemyObjectRepository(session), session.close

    storage = LocalFileStorage(str(tmp_path / "storage"))
    manager = IntakeJobManager(factory, storage, build_document_parsers())

    def _override_db():
        yield request_session

    def _override_storage():
        return storage

    def _override_manager():
        return manager

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:test-user-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_storage] = _override_storage
    app.dependency_overrides[get_job_manager] = _override_manager
    with TestClient(app) as client:
        yield client, storage, manager, request_session, factory
    app.dependency_overrides.clear()
    manager.shutdown()
    request_session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def repo_of(request_session) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(request_session)


def item_objects(request_session, sid: str) -> list:
    items = [
        o
        for o in repo_of(request_session).find(object_type=ObjectType.INTAKE_ITEM)
        if (o.metadata.get_value("intake.session_id") or "") == sid
    ]
    items.sort(key=lambda i: i.metadata.get_value("intake.relative_path") or i.title)
    return items


def start_import(client: TestClient, root: Path) -> str:
    created = client.post(f"{API}/sessions", json={"source_kind": "folder", "path": str(root)})
    assert created.status_code == 201, created.text
    return created.json()["id"]


@pytest.fixture()
def mixed_root(tmp_path: Path) -> Path:
    root = tmp_path / "mixed"
    root.mkdir()
    for i in range(12):
        (root / f"note-{i:02d}.txt").write_bytes(f"queue note {i}\n".encode() * 6)
    (root / "readme.md").write_bytes(b"# Queue readme\n\nbody\n")
    for i in range(3):
        (root / f"broken-{i}.pdf").write_bytes(b"%PDF-1.7\n%%%%")  # genuinely corrupt
    (root / "scan.pdf").write_bytes(make_pdf_bytes(""))  # empty text layer → needs OCR
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\nDATA")
    (root / "img2.png").write_bytes(b"\x89PNG\r\n\x1a\nELSE")
    return root


class TestMixedDrain:
    def test_queue_counters_and_live_fields_settle(self, harness, mixed_root) -> None:
        client, storage, _manager, request_session, _factory = harness
        sid = start_import(client, mixed_root)
        progress = wait_terminal(client, sid, timeout=60.0)

        assert progress["status"] == "completed"
        assert progress["total_items"] == 19
        assert progress["counts"]["errors"] == 3
        assert progress["counts"]["unsupported"] == 2
        assert progress["counts"]["needs_ocr"] == 1
        assert progress["counts"]["extracted"] == 14  # 12 txt + md + empty-scan
        assert progress["counts"]["retryable"] == 3
        assert progress["counts"]["extracting"] == 0 and progress["counts"]["retrying"] == 0
        assert progress["current_item"] is None
        # 3 retryable failures stay honestly "remaining" until acted on.
        assert progress["remaining_items"] == 3
        assert progress["avg_seconds_per_item"] is not None
        assert progress["items_per_minute"] is not None and progress["items_per_minute"] > 0
        assert progress["eta_seconds"] == round(3 * progress["avg_seconds_per_item"])

        session = client.get(f"{API}/sessions/{sid}").json()
        stats = session["statistics"]
        assert stats["needs_ocr_items"] == 1
        assert stats["retryable_items"] == 3
        assert stats["unsupported_items"] == 2

        # every corrupt pdf failed as an item (isolation), the batch finished
        items = item_objects(request_session, sid)
        by_rel = {i.metadata.get_value("intake.relative_path"): i for i in items}
        assert [ (by_rel[f"broken-{i}.pdf"].metadata.get_value(KEY_INTAKE_STATUS)) for i in range(3) ] == ["error"] * 3
        assert by_rel["scan.pdf"].metadata.get_value(KEY_INTAKE_STATUS) == "awaiting_review"
        scan_desc = json_decode(by_rel["scan.pdf"].metadata.get_value("intake.extraction"), None)
        assert scan_desc["status"] == "extracted" and scan_desc["character_count"] == 0
        for i in range(3):
            assert (by_rel[f"broken-{i}.pdf"].metadata.get_value("intake.attempts") or "") == "1"

    @pytest.mark.slow_timing
    def test_live_progress_reports_current_item_while_running(self, harness, tmp_path) -> None:
        client, _storage, _manager, _rs, _factory = harness
        root = tmp_path / "bulk"
        root.mkdir()
        for i in range(240):
            (root / f"bulk-{i:03d}.txt").write_bytes(f"bulk {i}\n".encode())
        sid = start_import(client, root)
        seen = wait_for(
            client,
            sid,
            lambda p: p["status"] == "running" and p["current_item"] is not None,
            timeout=30.0,
        )
        assert seen["current_item"].startswith("bulk-")
        assert seen["current_stage"]
        assert seen["remaining_items"] > 0
        wait_terminal(client, sid, timeout=60.0)
        settled = client.get(f"{API}/sessions/{sid}/progress").json()
        assert settled["percent"] == 100.0 and settled["remaining_items"] == 0
        assert settled["eta_seconds"] == 0


class TestRetryEndpoint:
    def test_retry_cycles_to_terminal_then_refuses(self, harness, mixed_root) -> None:
        client, _storage, _manager, request_session, _factory = harness
        sid = start_import(client, mixed_root)
        wait_terminal(client, sid, timeout=60.0)

        first = client.post(f"{API}/sessions/{sid}/retry")
        assert first.status_code == 200 and first.json()["status"] == "queued", first.text
        wait_terminal(client, sid, timeout=60.0)
        items = item_objects(request_session, sid)
        attempts = {i.metadata.get_value("intake.relative_path"): int(i.metadata.get_value("intake.attempts") or "0") for i in items}
        assert [attempts[f"broken-{i}.pdf"] for i in range(3)] == [2, 2, 2]
        session = client.get(f"{API}/sessions/{sid}").json()
        assert session["statistics"]["retryable_items"] == 3

        second = client.post(f"{API}/sessions/{sid}/retry")
        assert second.status_code == 200
        wait_terminal(client, sid, timeout=60.0)
        items = item_objects(request_session, sid)
        attempts = {i.metadata.get_value("intake.relative_path"): int(i.metadata.get_value("intake.attempts") or "0") for i in items}
        assert [attempts[f"broken-{i}.pdf"] for i in range(3)] == [3, 3, 3]
        session = client.get(f"{API}/sessions/{sid}").json()
        assert session["statistics"]["retryable_items"] == 0  # terminal

        third = client.post(f"{API}/sessions/{sid}/retry")
        assert third.status_code == 422
        assert "attempts left" in third.json()["detail"] or "retry limit" in third.json()["detail"]
        items = item_objects(request_session, sid)
        attempts = {i.metadata.get_value("intake.relative_path"): int(i.metadata.get_value("intake.attempts") or "0") for i in items}
        assert [attempts[f"broken-{i}.pdf"] for i in range(3)] == [3, 3, 3]  # untouched

    @pytest.mark.slow_timing
    def test_retry_matrix_and_404(self, harness, tmp_path) -> None:
        client, _storage, _manager, _rs, _factory = harness
        root = tmp_path / "clean"
        root.mkdir()
        (root / "fine.txt").write_bytes(b"fine\n")
        sid = start_import(client, root)
        wait_terminal(client, sid, timeout=60.0)
        assert client.post(f"{API}/sessions/{sid}/retry").status_code == 422  # nothing failed
        assert client.post(f"{API}/sessions/obj:intake_session:DOESNOTEXIST/retry").status_code == 404

        root2 = tmp_path / "cancel-me"
        root2.mkdir()
        for i in range(200):
            (root2 / f"c-{i:03d}.txt").write_bytes(b"x\n")
        sid2 = start_import(client, root2)
        wait_for(client, sid2, lambda p: p["status"] == "running", timeout=30.0)
        # queued/running: retry is not a valid transition (it is Resume's job)
        running = client.post(f"{API}/sessions/{sid2}/retry").status_code
        assert running == 422, running
        assert client.post(f"{API}/sessions/{sid2}/cancel").status_code == 200
        wait_terminal(client, sid2, timeout=60.0)
        cancelled = client.post(f"{API}/sessions/{sid2}/retry").status_code
        assert cancelled == 422  # cancelled is terminal

    @pytest.mark.slow_timing
    def test_paused_sessions_are_resume_business_not_retry(self, harness, tmp_path) -> None:
        client, _storage, _manager, _rs, _factory = harness
        root = tmp_path / "pause-me"
        root.mkdir()
        # Corpus sized so the drain outlives contended request latency on
        # slow/loaded machines — the pause must land mid-drain, every time.
        for i in range(600):
            (root / f"p-{i:03d}.txt").write_bytes(b"y\n")
        sid = start_import(client, root)
        wait_for(client, sid, lambda p: p["status"] == "running", timeout=60.0)
        client.post(f"{API}/sessions/{sid}/pause")
        paused = wait_terminal(client, sid, timeout=60.0)
        assert paused["status"] == "paused"
        assert client.post(f"{API}/sessions/{sid}/retry").status_code == 422
        client.post(f"{API}/sessions/{sid}/resume")
        settled = wait_terminal(client, sid, timeout=120.0)
        assert settled["status"] == "completed" and settled["percent"] == 100.0


class TestPauseResumeRestart:
    @pytest.mark.slow_timing
    def test_finished_items_are_never_restarted(self, harness, tmp_path) -> None:
        client, _storage, _manager, request_session, _factory = harness
        root = tmp_path / "resume-me"
        root.mkdir()
        total = 900  # drain outlives contended request latency on loaded machines
        for i in range(total):
            (root / f"r-{i:03d}.txt").write_bytes(f"resume {i}\n".encode())
        sid = start_import(client, root)
        wait_for(client, sid, lambda p: p["processed_items"] >= 20, timeout=60.0)
        client.post(f"{API}/sessions/{sid}/pause")
        paused = wait_terminal(client, sid, timeout=60.0)
        assert paused["status"] == "paused"
        done_before = {
            i.metadata.get_value("intake.relative_path"): len(json_decode(i.metadata.get_value("intake.stage_history"), []))
            for i in item_objects(request_session, sid)
            if (i.metadata.get_value(KEY_INTAKE_STATUS) or "") == "awaiting_review"
        }
        assert 0 < len(done_before) < total

        client.post(f"{API}/sessions/{sid}/resume")
        settled = wait_terminal(client, sid, timeout=180.0)
        assert settled["status"] == "completed" and settled["percent"] == 100.0
        after = item_objects(request_session, sid)
        by_rel = {i.metadata.get_value("intake.relative_path"): i for i in after}
        for rel, history_len in done_before.items():
            assert len(json_decode(by_rel[rel].metadata.get_value("intake.stage_history"), [])) == history_len, rel
        assert all((i.metadata.get_value(KEY_INTAKE_STATUS) or "") == "awaiting_review" for i in after)
        # Honest invariants for every item (pause may freeze one mid-attempt;
        # its resume legitimately appends idempotent re-runs — the truth is
        # append-only):
        for item in after:
            records = json_decode(item.metadata.get_value("intake.stage_history"), [])
            stages = [r["stage"] for r in records]
            assert stages[0] == "enumerate" and stages[-1] == "review"
            real_parses = [
                r for r in records
                if r["stage"] == "extract" and not (r["result"] or {}).get("reused")
            ]
            # parsed exactly once across the whole pause/resume cycle; any
            # further extract records are the reuse short-circuit, never work.
            assert len(real_parses) == 1, item.title

    @pytest.mark.slow_timing
    def test_double_resume_stays_single_drain(self, harness, tmp_path) -> None:
        client, _storage, _manager, request_session, _factory = harness
        root = tmp_path / "double"
        root.mkdir()
        for i in range(400):
            (root / f"d-{i:03d}.txt").write_bytes(b"z\n")
        sid = start_import(client, root)
        wait_for(client, sid, lambda p: p["status"] == "running", timeout=60.0)
        client.post(f"{API}/sessions/{sid}/pause")
        paused = wait_terminal(client, sid, timeout=60.0)
        assert paused["status"] == "paused"
        first = client.post(f"{API}/sessions/{sid}/resume")
        # Raced duplicate: the first resume already flipped the session to
        # queued, so the second is refused politely — never a second drain.
        second = client.post(f"{API}/sessions/{sid}/resume")
        assert first.status_code == 200
        assert second.status_code == 422
        settled = wait_terminal(client, sid, timeout=120.0)
        assert settled["status"] == "completed"
        for item in item_objects(request_session, sid):
            stages = [r["stage"] for r in json_decode(item.metadata.get_value("intake.stage_history"), [])]
            assert stages[:8] == ["enumerate", "stage", "hash", "extract", "classify", "match", "propose", "review"]
            assert len(item.metadata.get_value("intake.stage_history") or "") > 0

    def test_crash_recovery_via_stale_lease_and_reuse(self, harness, tmp_path) -> None:
        client, storage, _manager, request_session, factory = harness
        root = tmp_path / "crash"
        root.mkdir()
        for i in range(3):
            (root / f"pre-{i}.txt").write_bytes(f"pre {i}\n".encode())
        (root / "survivor.pdf").write_bytes(make_pdf_bytes("crash-survived text layer"))

        # Fabricate the crash state deterministically, straight into the DB —
        # nothing is POSTed, so no live dispatcher ever races the fabrication.
        # The story: a dead worker leased the session mid-drain; survivor.pdf
        # froze as "extracting" AFTER its descriptor + text blob were durably
        # written by its first attempt; the three txt files never started.
        repo = repo_of(request_session)
        sid = str(ObjectId.generate(ObjectType.INTAKE_SESSION))

        def put(obj, key, value) -> None:
            obj.set_metadata(
                MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
                actor="intake",
            )

        session_obj = UniversalObject.create(
            object_type=ObjectType.INTAKE_SESSION,
            title="Crash victim",
            created_by="intake",
            object_id=ObjectId(sid),
            status=ObjectStatus.ACTIVE,
        )
        put(session_obj, KEY_INTAKE_STATUS, "running")
        put(session_obj, KEY_SOURCE, json_encode({"kind": "folder", "path": str(root), "display": str(root)}))
        put(session_obj, KEY_PROGRESS, json_encode({"enumerated": True}))
        put(session_obj, KEY_STATISTICS, json_encode({"skipped_junk": 0, "skipped_junk_samples": []}))
        put(session_obj, KEY_CONTROL, json_encode({"pause": False, "cancel": False}))
        put(session_obj, KEY_CURRENT_STAGE, "extract")
        put(session_obj, KEY_LEASE, json_encode({
            "owner": "ghost-host:99999:deadbeef",
            "acquired_at": "2026-08-04T07:59:00+00:00",
            "heartbeat_at": "2026-08-04T07:59:05+00:00",  # long stale
        }))
        repo.save(session_obj)

        helper = IntakeRunner(repo, storage, sid, lambda: "go", build_document_parsers())
        for i in range(3):
            source = root / f"pre-{i}.txt"
            helper._create_item(session_obj, str(source), source.name, source.stat().st_size)
        helper._create_item(
            session_obj,
            str(root / "survivor.pdf"),
            "survivor.pdf",
            (root / "survivor.pdf").stat().st_size,
        )
        items = item_objects(request_session, sid)
        by_rel = {i.metadata.get_value("intake.relative_path"): i for i in items}
        assert set(by_rel) == {"pre-0.txt", "pre-1.txt", "pre-2.txt", "survivor.pdf"}
        survivor = by_rel["survivor.pdf"]
        # Stage + hash + extract the survivor honestly — precisely the work
        # its first attempt finished before the worker died.
        helper._stage_blob(survivor)
        helper._verify_and_sniff(survivor)
        record = helper._extraction.extract_item(survivor, storage, session_id=sid)
        assert record["status"] == "extracted"
        seeded = json_decode(survivor.metadata.get_value("intake.extraction"), None)
        seeded_extracted_at = seeded["extracted_at"]
        assert storage.exists(seeded["text_key"])
        put(survivor, KEY_INTAKE_STATUS, "extracting")  # froze post-extract
        put(survivor, "intake.attempts", "1")
        repo.save(survivor)

        # A foreign manager reconciles: the stale orphan becomes resumable.
        foreign = IntakeJobManager(factory, storage, build_document_parsers())
        try:
            assert foreign.reconcile_interrupted() == 1
            check, check_cleanup = factory()
            try:
                session_after = check.get_by_id(ObjectId(sid))
                assert (session_after.metadata.get_value(KEY_INTAKE_STATUS) or "") == "failed"
                assert json_decode(session_after.metadata.get_value(KEY_LEASE), "x") is None
            finally:
                check_cleanup()

            resumed = client.post(f"{API}/sessions/{sid}/resume")
            assert resumed.status_code == 200, resumed.text
            settled = wait_terminal(client, sid, timeout=60.0)
            assert settled["status"] == "completed" and settled["percent"] == 100.0
        finally:
            foreign.shutdown()

        # Post-drain truth through a fresh repository session: the seeded
        # descriptor is REUSED (extracted_at untouched — never re-parsed).
        verify, verify_cleanup = factory()
        try:
            survivor_after = verify.get_by_id(ObjectId(str(survivor.id)))
        finally:
            verify_cleanup()
        desc = json_decode(survivor_after.metadata.get_value("intake.extraction"), None)
        assert desc["extracted_at"] == seeded_extracted_at
        assert (survivor_after.metadata.get_value(KEY_INTAKE_STATUS) or "") == "awaiting_review"
        extract_steps = [
            r for r in json_decode(survivor_after.metadata.get_value("intake.stage_history"), [])
            if r["stage"] == "extract"
        ]
        assert any(s.get("result") == {"reused": True, "status": "extracted"} for s in extract_steps)
        # The untouched files ran the full pipeline exactly once.
        for item in item_objects(request_session, sid):
            if item.metadata.get_value("intake.relative_path") == "survivor.pdf":
                continue
            stages = [r["stage"] for r in json_decode(item.metadata.get_value("intake.stage_history"), [])]
            assert stages == ["enumerate", "stage", "hash", "extract", "classify", "match", "propose", "review"]


class TestConcurrencyGuards:
    @pytest.mark.slow_timing
    def test_foreign_manager_can_neither_drain_nor_reconcile_a_leased_session(
        self, harness, tmp_path
    ) -> None:
        client, storage, manager, request_session, factory = harness
        root = tmp_path / "race"
        root.mkdir()
        for i in range(400):
            (root / f"race-{i:03d}.txt").write_bytes(f"race {i}\n".encode())
        sid = start_import(client, root)
        wait_for(client, sid, lambda p: p["status"] == "running", timeout=60.0)
        assert manager.is_active(sid) is True

        foreign = IntakeJobManager(factory, storage, build_document_parsers())
        try:
            assert foreign.reconcile_interrupted() == 0  # fresh lease blocks it
            foreign.enqueue(sid)  # drains nothing: acquire refuses politely
            deadline = time.monotonic() + 30.0
            while foreign.queued_count() > 0 and time.monotonic() < deadline:
                time.sleep(0.05)
            assert foreign.queued_count() == 0
            # A manager that never holds a lease never claims activity.
            assert foreign.active_session() is None
            session_state = client.get(f"{API}/sessions/{sid}").json()
            assert session_state["status"] in ("queued", "running", "completed")  # never failed
        finally:
            foreign.shutdown()

        settled = wait_terminal(client, sid, timeout=120.0)
        assert settled["status"] == "completed" and settled["percent"] == 100.0
        # exactly one pass over every item — a duplicate drain would append
        for item in item_objects(request_session, sid):
            stages = tuple(
                r["stage"] for r in json_decode(item.metadata.get_value("intake.stage_history"), [])
            )
            assert stages == ("enumerate", "stage", "hash", "extract", "classify", "match", "propose", "review"), item.title


class TestGracefulCancel:
    @pytest.mark.slow_timing
    def test_cancel_leaves_finished_work_valid_and_metadata_coherent(
        self, harness, tmp_path
    ) -> None:
        client, _storage, manager, request_session, _factory = harness
        root = tmp_path / "cancel-t"
        root.mkdir()
        for i in range(320):
            (root / f"x-{i:03d}.txt").write_bytes(f"cancel {i}\n".encode() * 4)
        sid = start_import(client, root)
        wait_for(client, sid, lambda p: p["processed_items"] >= 10, timeout=30.0)
        client.post(f"{API}/sessions/{sid}/cancel")
        cancelled = wait_terminal(client, sid, timeout=60.0)
        assert cancelled["status"] == "cancelled"
        assert cancelled["current_item"] is None  # cleared, always coherent

        session = client.get(f"{API}/sessions/{sid}").json()
        assert "Cancelled" in (session["summary"] or "")
        items = item_objects(request_session, sid)
        finished = [i for i in items if (i.metadata.get_value(KEY_INTAKE_STATUS) or "") == "awaiting_review"]
        assert len(finished) >= 10
        for item in finished:
            stages = [
                r["stage"] for r in json_decode(item.metadata.get_value("intake.stage_history"), [])
            ]
            assert stages[:8] == ["enumerate", "stage", "hash", "extract", "classify", "match", "propose", "review"]
            descriptor = json_decode(item.metadata.get_value("intake.extraction"), None)
            assert descriptor and descriptor["status"] == "extracted"
            assert descriptor.get("extracted_at")
        unfinished = [
            i for i in items
            if (i.metadata.get_value(KEY_INTAKE_STATUS) or "") in ("pending", "staged", "extracting", "retrying")
        ]
        for item in unfinished:
            descriptor = json_decode(item.metadata.get_value("intake.extraction"), None)
            assert descriptor is None or descriptor["status"] in ("extracted", "unsupported")
        assert manager.is_active(sid) is False


class TestStorageSafetyAcrossFlows:
    def test_staged_bytes_and_text_parity_survive_retries(self, harness, mixed_root) -> None:
        client, storage, _manager, request_session, _factory = harness
        sid = start_import(client, mixed_root)
        wait_terminal(client, sid, timeout=60.0)
        # two retry rounds over the corrupt pdfs
        for _ in range(2):
            client.post(f"{API}/sessions/{sid}/retry")
            wait_terminal(client, sid, timeout=60.0)

        source_bytes = {p.name: p.read_bytes() for p in sorted(mixed_root.iterdir()) if p.is_file()}
        for item in item_objects(request_session, sid):
            rel = item.metadata.get_value("intake.relative_path") or ""
            staged_key = item.metadata.get_value("intake.staged_key")
            blob = storage.read(staged_key)
            assert hashlib.sha256(blob).hexdigest() == item.metadata.get_value("intake.sha256")
            assert blob == source_bytes[rel]  # staged copy == source, never rewritten
            descriptor = json_decode(item.metadata.get_value("intake.extraction"), None)
            if descriptor and descriptor["status"] == "extracted":
                text = storage.read(descriptor["text_key"]).decode("utf-8")
                preview = descriptor.get("preview_text") or ""
                assert text.startswith(preview)
                assert len(text.encode("utf-8")) == descriptor["text_bytes"]
            else:
                text_key = item.metadata.get_value("intake.extracted_key") or ""
                assert descriptor is None or descriptor["status"] == "unsupported" or text_key == ""
