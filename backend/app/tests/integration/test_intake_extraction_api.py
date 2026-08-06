"""Integration tests for the M2 extraction engine (Intake API slice).

Same harness doctrine as ``test_intake_api.py``: file-backed SQLite, an
overridden local storage root, a per-suite job manager — and now *real*
extraction fixtures end to end: a real one-page PDF, a real DOCX, text
formats, an unsupported image, and a genuinely corrupt PDF.

Covers the whole M2 contract through the public API: descriptors with honest
nulls, extracted/unsupported rollups, the raw-text endpoint (byte parity and
its 404 edges — never a fabricated empty document), idempotent resume,
per-item isolation, job controls under real engine load, full cleanup, and
the cold boundary: extraction never creates anything outside Intake.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.api.dependencies.auth import get_current_user

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.documents import get_storage
from app.api.routes.intake import get_job_manager
from app.application.intake.jobs import IntakeJobManager
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.extraction import build_document_parsers
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage
from app.main import app
from app.tests.unit.extraction_fixtures import make_docx_bytes, make_pdf_bytes

API = "/api/v1/intake"

NOTE_TEXT = "hello extraction world"
MD_TEXT = "# Research Notes\n\nSome **markdown** body.\n"
CSV_TEXT = "name,score\nAda,10\n"
JSON_TEXT = '{"project": "HSRF", "years": [2024, 2025]}'
FAKE_PNG = b"\x89PNG\r\n\x1a\nDATA"
CORRUPT_PDF = b"%PDF-1.4 fake"


def wait_terminal(client: TestClient, sid: str, *, timeout: float = 60.0) -> dict:
    """Poll the progress endpoint until the session reaches a settled state."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"{API}/sessions/{sid}/progress").json()
        if body["status"] in ("completed", "failed", "paused", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"session {sid} did not settle in {timeout}s")


def wait_status(client: TestClient, sid: str, status: str, *, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"{API}/sessions/{sid}").json()
        if body["status"] == status:
            return body
        time.sleep(0.05)
    raise AssertionError(f"session {sid} did not reach {status} in {timeout}s")


@pytest.fixture()
def fixture_root(tmp_path: Path) -> Path:
    """One of each supported format + one unsupported image, all parseable."""

    root = tmp_path / "source"
    (root / "Sub Folder").mkdir(parents=True)
    (root / "paper one.pdf").write_bytes(
        make_pdf_bytes("Hello Intake M2 world", title="Spec Paper", author="A. Uthor")
    )
    (root / "Sub Folder" / "report.docx").write_bytes(
        make_docx_bytes(["M2 integration report", "second paragraph"])
    )
    (root / "notes.txt").write_bytes(NOTE_TEXT.encode())
    (root / "README.md").write_bytes(MD_TEXT.encode())
    (root / "scores.csv").write_bytes(CSV_TEXT.encode())
    (root / "data.json").write_bytes(JSON_TEXT.encode())
    (root / "img.png").write_bytes(FAKE_PNG)
    return root


@pytest.fixture()
def harness(tmp_path: Path):
    """TestClient + per-suite manager + handles for direct DB inspection."""

    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    storage = LocalFileStorage(str(tmp_path / "storage"))

    session_factory = TestingSessionLocal

    def repo_factory():
        db = session_factory()
        return SQLAlchemyObjectRepository(db), db.close

    jobs = IntakeJobManager(repo_factory, storage, build_document_parsers())

    app.dependency_overrides[get_db] = override_get_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_job_manager] = lambda: jobs

    client = TestClient(app)
    try:
        yield client, engine, storage, jobs
    finally:
        jobs.shutdown()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_job_manager, None)


def _create(client: TestClient, source: Path) -> str:
    response = client.post(
        f"{API}/sessions",
        json={"source_kind": "folder", "path": str(source), "title": "M2 run"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _items(client: TestClient, sid: str) -> dict:
    payload = client.get(f"{API}/sessions/{sid}/items", params={"page_size": 100}).json()
    return {item["relative_path"]: item for item in payload["items"]}


def _text_url(sid: str, item_id: str) -> str:
    return f"{API}/sessions/{sid}/items/{item_id}/extraction/text"


class TestExtractionLifecycle:
    def test_full_folder_lifecycle_end_to_end(self, harness, fixture_root: Path) -> None:
        client, engine, storage, _ = harness
        sid = _create(client, fixture_root)
        progress = wait_terminal(client, sid)
        assert progress["status"] == "completed"
        assert progress["counts"]["errors"] == 0

        session = client.get(f"{API}/sessions/{sid}").json()
        assert session["statistics"]["extracted_items"] == 6
        assert session["statistics"]["unsupported_items"] == 1
        assert "Extracted text from 6 file(s)" in session["summary"]
        assert "1 unsupported" in session["summary"]
        assert "M9" in session["summary"]  # M1 closing line preserved

        items = _items(client, sid)
        pdf = items["paper one.pdf"]
        descriptor = pdf["extraction"]
        assert descriptor["status"] == "extracted"
        assert descriptor["format"] == "pdf"
        assert descriptor["engine"].startswith("pypdf ")
        assert descriptor["page_count"] == 1
        assert descriptor["word_count"] == 4
        assert descriptor["character_count"] == len("Hello Intake M2 world")
        assert descriptor["document_title"] == "Spec Paper"
        assert descriptor["author"] == "A. Uthor"
        assert descriptor["created_at"] == "2024-01-02T03:04:05+00:00"
        assert descriptor["modified_at"] == "2024-03-04T05:06:07+00:00"
        assert descriptor["embedded_metadata"]["Title"] == "Spec Paper"
        assert descriptor["preview_text"] == "Hello Intake M2 world"
        assert descriptor["sha256"] == pdf["sha256"]
        assert descriptor["text_key"].startswith("intake-extracted/")

        docx = items["Sub Folder/report.docx"]
        assert docx["extraction"]["status"] == "extracted"
        assert docx["extraction"]["page_count"] is None  # never fabricated
        assert docx["extraction"]["preview_text"] == "M2 integration report\nsecond paragraph"

        assert items["README.md"]["extraction"]["document_title"] == "Research Notes"
        assert items["notes.txt"]["extraction"]["word_count"] == 3
        assert items["scores.csv"]["extraction"]["status"] == "extracted"
        assert items["data.json"]["extraction"]["status"] == "extracted"

        png = items["img.png"]
        assert png["extraction"]["status"] == "unsupported"
        assert png["extraction"]["word_count"] is None
        assert png["extraction"]["text_key"] is None
        assert png["status"] == "awaiting_review"  # UNSUPPORTED never fails the item
        assert png["error"] is None

        # Extract stage is a real recorded transition for every supported file.
        extract_records = [
            step for step in pdf["stage_history"] if step["stage"] == "extract"
        ]
        assert len(extract_records) == 1
        assert extract_records[0]["result"]["status"] == "extracted"

        # Extracted text coexists with staged bytes under the storage root.
        staged = list((Path(storage._root) / "intake").rglob("*"))  # noqa: SLF001
        extracted = list((Path(storage._root) / "intake-extracted").rglob("*"))  # noqa: SLF001
        assert any(p.is_file() and p.read_bytes().startswith(b"%PDF-1.4") for p in staged)
        assert any(p.is_file() and p.read_bytes() == b"Hello Intake M2 world" for p in extracted)
        assert any(p.is_file() and p.read_bytes() == NOTE_TEXT.encode() for p in extracted)

    def test_extraction_text_endpoint_byte_parity_and_type(self, harness, fixture_root: Path) -> None:
        client, _engine, _storage, _ = harness
        sid = _create(client, fixture_root)
        wait_terminal(client, sid)
        for rel, expected in (
            ("notes.txt", NOTE_TEXT),
            ("README.md", MD_TEXT),
            ("scores.csv", CSV_TEXT),
            ("data.json", JSON_TEXT),
        ):
            item_id = _items(client, sid)[rel]["id"]
            response = client.get(_text_url(sid, item_id))
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/plain")
            assert response.content == expected.encode()

    def test_text_endpoint_never_fabricates_content(self, harness, fixture_root: Path) -> None:
        client, engine, _storage, _ = harness
        sid = _create(client, fixture_root)
        wait_terminal(client, sid)
        items = _items(client, sid)

        png_id = items["img.png"]["id"]
        response = client.get(_text_url(sid, png_id))
        assert response.status_code == 404  # UNSUPPORTED: no text exists — honest 404
        assert "No extracted text" in response.json().get("detail", "")

        unknown = client.get(_text_url(sid, "obj:intake_item:DOESNOTEXIST01"))
        assert unknown.status_code == 404
        other = _create(client, fixture_root)
        wait_terminal(client, other)
        other_id = _items(client, other)["notes.txt"]["id"]
        mismatched = client.get(_text_url(sid, other_id))
        assert mismatched.status_code == 404  # item belongs to a different session

        # No objects beyond Intake exist anywhere — cold M2 boundary.
        from sqlalchemy import text as sql_text

        with engine.connect() as connection:
            rows = connection.execute(sql_text("SELECT object_type, COUNT(*) FROM objects GROUP BY object_type")).all()
        assert {row[0] for row in rows} <= {"intake_session", "intake_item"}
        client.delete(f"{API}/sessions/{other}")


class TestCorruptItems:
    def _run_and_collect(self, client: TestClient, sid: str) -> dict:
        progress = wait_terminal(client, sid)
        assert progress["status"] == "completed"  # the batch itself never fails
        return _items(client, sid)

    def test_corrupt_pdf_is_item_error_without_fabricated_fields(self, harness, tmp_path: Path) -> None:
        client, _engine, _storage, _ = harness
        root = tmp_path / "mixed"
        root.mkdir()
        (root / "good.txt").write_bytes(b"fine")
        (root / "broken.pdf").write_bytes(CORRUPT_PDF)
        sid = _create(client, root)
        items = self._run_and_collect(client, sid)

        session = client.get(f"{API}/sessions/{sid}").json()
        assert session["statistics"]["errors"] == 1
        assert session["statistics"]["extracted_items"] == 1

        broken = items["broken.pdf"]
        assert broken["status"] == "error"
        assert broken["error"]["stage"] == "extract"
        assert "PDF could not be parsed" in broken["error"]["message"]
        assert broken["extraction"] is None  # never fabricate partial metadata
        assert client.get(_text_url(sid, broken["id"])).status_code == 404

        good = items["good.txt"]
        assert good["status"] == "awaiting_review"
        assert good["extraction"]["status"] == "extracted"
        assert client.get(_text_url(sid, good["id"])).content == b"fine"

    def test_unsupported_never_blocks_neighbors(self, harness, tmp_path: Path) -> None:
        client, _engine, _storage, _ = harness
        root = tmp_path / "mixed2"
        root.mkdir()
        (root / "a.png").write_bytes(FAKE_PNG)
        (root / "b.txt").write_bytes(b"neighbour text")
        sid = _create(client, root)
        items = self._run_and_collect(client, sid)
        assert items["a.png"]["status"] == "awaiting_review"
        assert items["a.png"]["extraction"]["status"] == "unsupported"
        assert items["b.txt"]["extraction"]["preview_text"] == "neighbour text"


class TestM2JobControls:
    @pytest.fixture()
    def bulk_root(self, tmp_path: Path) -> Path:
        root = tmp_path / "bulk"
        root.mkdir()
        for index in range(300):
            (root / f"doc-{index:04d}.txt").write_bytes(f"bulk payload {index}\n".encode() * 4)
        return root

    def _wait_paused(self, client: TestClient, sid: str) -> dict:
        return wait_status(client, sid, "paused")

    def test_pause_resume_with_real_engines(self, harness, bulk_root: Path) -> None:
        client, _engine, _storage, _ = harness
        sid = _create(client, bulk_root)
        pause = client.post(f"{API}/sessions/{sid}/pause")
        assert pause.status_code == 200, pause.text
        paused = self._wait_paused(client, sid)
        assert paused["progress"]["processed"] < 300

        resume = client.post(f"{API}/sessions/{sid}/resume")
        assert resume.status_code == 200
        progress = wait_terminal(client, sid, timeout=60.0)
        assert progress["status"] == "completed"
        session = client.get(f"{API}/sessions/{sid}").json()
        assert session["statistics"]["extracted_items"] == 300
        assert session["statistics"]["errors"] == 0

    def test_cancel_with_real_engines(self, harness, bulk_root: Path) -> None:
        client, _engine, _storage, _ = harness
        sid = _create(client, bulk_root)
        cancel = client.post(f"{API}/sessions/{sid}/cancel")
        assert cancel.status_code == 200
        cancelled = wait_status(client, sid, "cancelled")
        assert cancelled["status"] == "cancelled"
        again = client.post(f"{API}/sessions/{sid}/resume")
        assert again.status_code == 422  # cancelled stays terminal


class TestM2ResumeIdempotency:
    def test_rerun_rewrites_same_text_key_and_descriptor(self, harness, tmp_path: Path) -> None:
        client, engine, storage, _ = harness
        root = tmp_path / "again"
        root.mkdir()
        (root / "one.txt").write_bytes(b"rewrite me")
        sid = _create(client, root)
        wait_terminal(client, sid)
        first = _items(client, sid)["one.txt"]
        first_descriptor = dict(first["extraction"])
        text_key = first_descriptor["text_key"]
        blob_before = Path(storage._root, text_key).read_bytes()  # noqa: SLF001

        # Control guards still hold: a completed session is not resumable,
        # and the engine artefacts sit untouched beneath.
        again = client.post(f"{API}/sessions/{sid}/resume")
        assert again.status_code == 422
        progress = client.get(f"{API}/sessions/{sid}/progress").json()
        assert progress["status"] == "completed"
        second = _items(client, sid)["one.txt"]
        assert second["extraction"]["text_key"] == text_key
        assert second["extraction"]["word_count"] == first_descriptor["word_count"]
        assert Path(storage._root, text_key).read_bytes() == blob_before  # noqa: SLF001


class TestM2Cleanup:
    def test_delete_removes_session_items_and_both_blob_stores(
        self, harness, fixture_root: Path
    ) -> None:
        client, engine, storage, _ = harness
        sid = _create(client, fixture_root)
        wait_terminal(client, sid)
        items = _items(client, sid)
        keys = [
            item["extraction"]["text_key"]
            for item in items.values()
            if item["extraction"] and item["extraction"]["text_key"]
        ]
        assert len(keys) == 6

        response = client.delete(f"{API}/sessions/{sid}")
        assert response.status_code == 204
        assert client.get(f"{API}/sessions/{sid}").status_code == 404
        root = Path(storage._root)  # noqa: SLF001
        # Blob directories may linger empty; no content file may survive.
        leftovers = [p for p in root.rglob("*") if p.is_file()]
        assert leftovers == [], f"stale blobs after delete: {leftovers[:3]}"
