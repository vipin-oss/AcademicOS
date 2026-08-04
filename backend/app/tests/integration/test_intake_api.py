"""Integration tests for the Intake Foundations API (v2 slice).

Mirrors ``test_documents_api.py``: a file-backed SQLite database (the drain
thread and the request thread need genuinely separate connections), an
overridden local storage root, and a per-suite job manager wired through
``dependency_overrides`` — no PostgreSQL, no leftover disk state.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.documents import get_storage
from app.api.routes.intake import get_job_manager
from app.application.intake.jobs import IntakeJobManager
from app.application.use_cases.intake.helpers import set_system_metadata
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage
from app.main import app

API = "/api/v1/intake"


def wait_terminal(client: TestClient, sid: str, *, timeout: float = 20.0) -> dict:
    """Poll the progress endpoint until the session reaches a settled state."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"{API}/sessions/{sid}/progress").json()
        if body["status"] in ("completed", "failed", "paused", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"session {sid} did not settle in {timeout}s")


@pytest.fixture()
def fixture_root(tmp_path: Path) -> Path:
    """A structured source folder: nested dirs, junk, real magic bytes."""

    root = tmp_path / "source"
    (root / "Sub Folder").mkdir(parents=True)
    (root / "notes.txt").write_bytes(b"hello world")
    (root / "paper one.pdf").write_bytes(b"%PDF-1.4 fake")
    (root / "img.png").write_bytes(b"\x89PNG\r\n\x1a\nDATA")
    (root / "Sub Folder" / "report.docx").write_bytes(b"PK\x03\x04zip-data")
    (root / ".DS_Store").write_bytes(b"junk")
    (root / "~$lock.docx").write_bytes(b"junk")
    (root / "movie.part").write_bytes(b"junk")
    (root / ".hidden-dir").mkdir()
    (root / ".hidden-dir" / "ghost.txt").write_bytes(b"junk")
    return root


@pytest.fixture()
def big_root(tmp_path: Path) -> Path:
    """A larger drop used for pause/resume/cancel timing."""

    root = tmp_path / "big"
    root.mkdir()
    for i in range(500):
        (root / f"file-{i:04d}.txt").write_bytes(f"payload-{i}\n".encode() * 8)
    return root


@pytest.fixture()
def harness(tmp_path: Path):
    """TestClient + per-suite manager + handles for direct DB inspection."""

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
    manager = IntakeJobManager(factory, storage)

    def _override_db():
        yield request_session

    def _override_storage():
        return storage

    def _override_manager():
        return manager

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_storage] = _override_storage
    app.dependency_overrides[get_job_manager] = _override_manager
    with TestClient(app) as client:
        yield client, storage, manager, request_session
    app.dependency_overrides.clear()
    manager.shutdown()
    request_session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


# ------------------------------------------------------------------- create


class TestCreateValidation:
    def test_create_happy_folder_starts_queued(self, harness, fixture_root: Path) -> None:
        client, *_ = harness
        res = client.post(f"{API}/sessions", json={"source_kind": "folder", "path": str(fixture_root)})
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["status"] in ("queued", "running", "paused", "completed")
        assert body["source"]["kind"] == "folder"
        assert body["source"]["path"] == str(fixture_root)
        assert body["current_stage"] in ("enumerate", "stage", "hash", "review")

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"source_kind": "zip", "path": "/x"},
            {"source_kind": "folder"},
            {"source_kind": "folder", "path": ""},
            {"source_kind": "files", "paths": []},
            {"source_kind": "files", "paths": [""]},
            {"source_kind": "files", "paths": ["/definitely/missing.pdf"]},
            {"source_kind": "folder", "path": "/definitely/missing"},
            {"source_kind": "folder", "path": "/x", "surprise": True},
        ],
    )
    def test_create_rejects_bad_payloads(self, harness, payload: dict) -> None:
        client, *_ = harness
        res = client.post(f"{API}/sessions", json=payload)
        assert res.status_code == 422, (payload, res.status_code)

    def test_folder_must_be_directory(self, harness, fixture_root: Path) -> None:
        client, *_ = harness
        a_file = fixture_root / "notes.txt"
        res = client.post(f"{API}/sessions", json={"source_kind": "folder", "path": str(a_file)})
        assert res.status_code == 422

    def test_storage_overlap_rejected(self, harness, tmp_path: Path) -> None:
        client, storage, *_ = harness
        overlap = Path(storage._root)  # noqa: SLF001 — точкa of truth for the key root
        incoming = overlap / "incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        res = client.post(f"{API}/sessions", json={"source_kind": "folder", "path": str(incoming)})
        assert res.status_code == 422

    def test_files_drop_happy(self, harness, fixture_root: Path) -> None:
        client, *_ = harness
        files = [str(fixture_root / "notes.txt"), str(fixture_root / "Sub Folder" / "report.docx")]
        res = client.post(
            f"{API}/sessions",
            json={"source_kind": "files", "paths": files, "actor": "tester"},
        )
        assert res.status_code == 201
        sid = res.json()["id"]
        progress = wait_terminal(client, sid)
        assert progress["status"] == "completed"
        assert progress["total_items"] == 2


# ---------------------------------------------------------------- lifecycle


class TestFullLifecycle:
    def test_folder_import_end_to_end(self, harness, fixture_root: Path) -> None:
        client, storage, *_ = harness
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(fixture_root)}
        ).json()["id"]

        progress = wait_terminal(client, sid)
        assert progress["status"] == "completed"
        assert progress["total_items"] == 4  # junk and hidden dirs never become items
        assert progress["processed_items"] == 4
        assert progress["percent"] == 100.0
        assert progress["counts"] == {
            "pending": 0,
            "staged": 0,
            "hashed": 4,
            "awaiting_review": 4,
            "errors": 0,
        }

        session = client.get(f"{API}/sessions/{sid}").json()
        assert session["current_stage"] == "review"
        assert session["statistics"]["skipped_junk"] == 3
        assert session["statistics"]["by_extension"]["txt"] == 1
        assert session["statistics"]["total_bytes"] > 0
        assert "Imported 4/4 files" in session["summary"]
        assert "M9" in session["summary"]

        items = client.get(f"{API}/sessions/{sid}/items").json()
        assert items["total_count"] == 4
        by_rel = {i["relative_path"]: i for i in items["items"]}
        assert list(by_rel) == sorted(by_rel, key=str.lower)
        docx = by_rel["Sub Folder/report.docx"]
        assert docx["extension"] == "docx"
        assert docx["mime_type"].endswith("wordprocessingml.document")
        assert docx["sha256"] and len(docx["sha256"]) == 64
        assert docx["status"] == "awaiting_review"
        assert docx["stage"] == "review"
        assert docx["staged_key"].startswith(f"intake/{sid.replace(':', '_')}/")
        stages = [h["stage"] for h in docx["stage_history"]]
        assert stages == ["enumerate", "stage", "hash", "extract", "classify", "match", "propose", "review"]
        assert by_rel["img.png"]["mime_type"] == "image/png"
        assert by_rel["notes.txt"]["mime_type"] == "text/plain"

        # Staged bytes landed under the storage root via the FileStorage port.
        stored = list(Path(storage._root).rglob("*"))  # noqa: SLF001
        assert any(p.is_file() and p.read_bytes() == b"%PDF-1.4 fake" for p in stored)

    def test_items_pagination(self, harness, fixture_root: Path) -> None:
        client, *_ = harness
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(fixture_root)}
        ).json()["id"]
        wait_terminal(client, sid)
        page1 = client.get(f"{API}/sessions/{sid}/items", params={"page": 1, "page_size": 3}).json()
        page2 = client.get(f"{API}/sessions/{sid}/items", params={"page": 2, "page_size": 3}).json()
        assert page1["total_count"] == 4
        assert len(page1["items"]) == 3 and len(page2["items"]) == 1
        assert page2["page"] == 2

    def test_empty_folder_completes_cleanly(self, harness, tmp_path: Path) -> None:
        client, *_ = harness
        empty = tmp_path / "empty"
        empty.mkdir()
        (empty / ".DS_Store").write_bytes(b"junk")
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(empty)}
        ).json()["id"]
        progress = wait_terminal(client, sid)
        assert progress["status"] == "completed"
        assert progress["total_items"] == 0
        assert progress["percent"] == 100.0
        assert "No supported files" in client.get(f"{API}/sessions/{sid}").json()["summary"]

    def test_unknown_ids_are_404(self, harness) -> None:
        client, *_ = harness
        ghost = "obj:intake_session:0000000000000000"
        assert client.get(f"{API}/sessions/{ghost}").status_code == 404
        assert client.get(f"{API}/sessions/{ghost}/progress").status_code == 404
        assert client.get(f"{API}/sessions/{ghost}/items").status_code == 404
        assert client.post(f"{API}/sessions/{ghost}/pause").status_code == 404
        assert client.post(f"{API}/sessions/{ghost}/resume").status_code == 404
        assert client.post(f"{API}/sessions/{ghost}/cancel").status_code == 404
        assert client.delete(f"{API}/sessions/{ghost}").status_code == 404


# ------------------------------------------------------------ pause/resume


class TestControlFlow:
    def test_pause_resume_completes_exactly_all_items(self, harness, big_root: Path) -> None:
        client, *_ = harness
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(big_root)}
        ).json()["id"]

        paused = None
        for _ in range(200):
            res = client.post(f"{API}/sessions/{sid}/pause")
            if res.status_code == 200:
                paused = wait_terminal(client, sid)
                if paused["status"] == "paused":
                    break
            progress = client.get(f"{API}/sessions/{sid}/progress").json()
            if progress["status"] in ("completed", "failed"):
                paused = progress
                break
            time.sleep(0.02)
        assert paused is not None and paused["status"] == "paused", paused
        assert 0 <= paused["processed_items"] < 500

        resumed = client.post(f"{API}/sessions/{sid}/resume")
        assert resumed.status_code == 200
        final = wait_terminal(client, sid)
        assert final["status"] == "completed"
        assert final["total_items"] == 500
        assert final["processed_items"] == 500
        assert final["counts"]["awaiting_review"] == 500

    def test_cancel_is_terminal(self, harness, big_root: Path) -> None:
        client, *_ = harness
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(big_root)}
        ).json()["id"]
        res = client.post(f"{API}/sessions/{sid}/cancel")
        assert res.status_code == 200
        progress = wait_terminal(client, sid)
        assert progress["status"] in ("cancelled", "completed")
        assert client.post(f"{API}/sessions/{sid}/pause").status_code == 422
        assert client.post(f"{API}/sessions/{sid}/resume").status_code == 422
        assert client.post(f"{API}/sessions/{sid}/cancel").status_code == 422

    def test_cancel_while_paused_persists_immediately(self, harness, big_root: Path) -> None:
        client, *_ = harness
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(big_root)}
        ).json()["id"]
        paused = None
        for _ in range(200):
            if client.post(f"{API}/sessions/{sid}/pause").status_code == 200:
                paused = wait_terminal(client, sid)
                if paused["status"] == "paused":
                    break
            time.sleep(0.02)
        assert paused and paused["status"] == "paused"
        out = client.post(f"{API}/sessions/{sid}/cancel")
        assert out.status_code == 200
        assert out.json()["status"] == "cancelled"
        assert "Cancelled while paused" in out.json()["summary"]


# ------------------------------------------------------------------- delete


class TestDelete:
    def test_delete_removes_session_items_and_blobs(
        self, harness, fixture_root: Path, tmp_path: Path
    ) -> None:
        client, storage, _, db = harness
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(fixture_root)}
        ).json()["id"]
        wait_terminal(client, sid)
        assert any(p.is_file() for p in Path(storage._root).rglob("*"))  # noqa: SLF001

        assert client.delete(f"{API}/sessions/{sid}").status_code == 204
        assert client.get(f"{API}/sessions/{sid}").status_code == 404
        assert client.get(f"{API}/sessions/{sid}/items").status_code == 404
        storage_files = [p for p in Path(storage._root).rglob("*") if p.is_file()]  # noqa: SLF001
        assert storage_files == []

        repo = SQLAlchemyObjectRepository(db)
        leftovers = repo.find(object_type=ObjectType.INTAKE_ITEM)
        assert leftovers == []

    def test_delete_mid_run_leaves_no_orphan_writes(self, harness, big_root: Path) -> None:
        client, storage, *_ = harness
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(big_root)}
        ).json()["id"]
        res = client.delete(f"{API}/sessions/{sid}")
        assert res.status_code == 204
        assert client.get(f"{API}/sessions/{sid}").status_code == 404
        time.sleep(0.5)  # a live drain must have aborted without write-back
        leftovers = [p for p in Path(storage._root).rglob("*") if p.is_file()]  # noqa: SLF001
        assert leftovers == []


# ---------------------------------------------------------------- reconcile


class TestReconcile:
    def test_interrupted_sessions_fail_closed_and_resume(self, harness, fixture_root: Path) -> None:
        client, storage, manager, db = harness
        sid = client.post(
            f"{API}/sessions", json={"source_kind": "folder", "path": str(fixture_root)}
        ).json()["id"]
        wait_terminal(client, sid)

        # Simulate a crash: force the persisted state back to "running" with no
        # worker alive, then reconcile as the next process would on boot.
        repo = SQLAlchemyObjectRepository(db)
        obj = repo.get_by_id(ObjectId(sid))
        set_system_metadata(obj, "intake.status", "running")
        set_system_metadata(obj, "intake.progress", '{"enumerated": false}')
        repo.save(obj)

        stale = IntakeJobManager(lambda: (SQLAlchemyObjectRepository(db), lambda: None), storage)
        try:
            assert stale.reconcile_interrupted() == 1
        finally:
            stale.shutdown()

        session = client.get(f"{API}/sessions/{sid}").json()
        assert session["status"] == "failed"
        assert "restart" in session["error"]["message"]

        assert client.post(f"{API}/sessions/{sid}/resume").status_code == 200
        final = wait_terminal(client, sid)
        assert final["status"] == "completed"
        assert final["total_items"] == 4
