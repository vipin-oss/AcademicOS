"""Unit tests for the intake pipeline helpers + DTO machinery (M1)."""
from __future__ import annotations

import pytest

from app.application.dtos.intake import (
    DEFERRED_STAGE_MILESTONES,
    ITEM_STAGE_SEQUENCE,
    KEY_INTAKE_STATUS,
    KEY_PROGRESS,
    KEY_STATISTICS,
    IntakeItemFacts,
    IntakeItemStatus,
    IntakeStage,
    intake_item_facts,
    intake_item_output,
    intake_progress_output,
    intake_session_output,
    intake_session_progress_of,
    json_encode,
    summarize_items,
)
from app.application.intake.pipeline import (
    deferred_stage_result,
    detect_extension,
    digest_of,
    finish_record,
    human_bytes,
    sanitize_relative_path,
    sanitize_segment,
    should_skip_dir,
    should_skip_file,
    sniff_mime,
    staging_key_for,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry

# ---------------------------------------------------------------- skip rules


class TestSkipRules:
    @pytest.mark.parametrize(
        "name",
        [
            ".DS_Store",
            "Thumbs.db",
            "desktop.ini",
            "~$report.docx",
            "._photo.jpg",
            ".hidden",
            "download.crdownload",
            "archive.part",
            "movie.partial",
            "video.download",
            "work.tmp",
            "swap.swp",
        ],
    )
    def test_junk_names_are_skipped(self, name: str) -> None:
        assert should_skip_file(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "paper.pdf",
            "final draft.docx",
            "~tilde-name.txt",
            "photo.jpeg",
            "archive.zip",
        ],
    )
    def test_real_files_are_kept(self, name: str) -> None:
        assert should_skip_file(name) is False

    def test_uppercase_junk_matches_case_insensitively(self) -> None:
        assert should_skip_file("DESKTOP.INI") is True
        assert should_skip_file("Movie.PART") is True

    def test_hidden_dirs_pruned(self) -> None:
        assert should_skip_dir(".git") is True
        assert should_skip_dir(".svn") is True
        assert should_skip_dir("Research") is False


# ---------------------------------------------------------------- key hygiene


class TestKeyHygiene:
    def test_sanitize_segment_replaces_unsafe(self) -> None:
        assert sanitize_segment('a/b\\c:d*e?"f<g>h|i') == "a_b_c_d_e__f_g_h_i"

    def test_sanitize_segment_caps_and_fallback(self) -> None:
        assert sanitize_segment("x" * 500) == "x" * 120
        assert sanitize_segment("///...") == "unnamed"

    def test_relative_path_normalisation(self) -> None:
        assert sanitize_relative_path("a\\b\\c.pdf") == "a/b/c.pdf"
        assert sanitize_relative_path("a/./b/../c.pdf") == "a/c.pdf"
        assert sanitize_relative_path("../../evil.pdf") == "evil.pdf"
        assert sanitize_relative_path("//double//slash//") == "double/slash"
        assert sanitize_relative_path("") == "unnamed"

    def test_staging_key_is_contained_and_deterministic(self) -> None:
        key = staging_key_for("obj:intake_session:ABC", "Sub/Rep ort.pdf")
        assert key == "intake/obj_intake_session_ABC/Sub/Rep ort.pdf"
        assert ".." not in key
        assert staging_key_for("s", "../../x") == "intake/s/x"
        assert staging_key_for("s", "a.pdf") == staging_key_for("s", "a.pdf")


# ---------------------------------------------------------------- mime + hash


class TestMimeAndHash:
    def test_magic_bytes_win(self) -> None:
        assert sniff_mime(b"%PDF-1.7 rest", "x.bin") == "application/pdf"
        assert sniff_mime(b"\x89PNG\r\n\x1a\nrest", "x") == "image/png"
        assert sniff_mime(b"\xff\xd8\xff\xe0rest", "x") == "image/jpeg"
        assert sniff_mime(b"GIF89a", "x") == "image/gif"
        assert sniff_mime(b"\x1f\x8bxx", "x") == "application/gzip"

    def test_zip_containers_refine_by_extension(self) -> None:
        docx = sniff_mime(b"PK\x03\x04rest", "report.docx")
        assert docx.endswith("wordprocessingml.document")
        xlsx = sniff_mime(b"PK\x03\x04rest", "sheet.xlsx")
        assert xlsx.endswith("spreadsheetml.sheet")
        pptx = sniff_mime(b"PK\x03\x04rest", "deck.pptx")
        assert pptx.endswith("presentationml.presentation")
        assert sniff_mime(b"PK\x03\x04rest", "bundle.zip") == "application/zip"
        assert sniff_mime(b"PK\x05\x06", "empty.zip") == "application/zip"

    def test_fallback_tables(self) -> None:
        assert sniff_mime(b"plain text here", "notes.txt") == "text/plain"
        assert sniff_mime(b"\x00\x01\x02", "mystery.xqq") == "application/octet-stream"

    def test_detect_extension(self) -> None:
        assert detect_extension("Paper.PDF") == "pdf"
        assert detect_extension("archive.tar.gz") == "gz"
        assert detect_extension("no-extension") == ""
        assert detect_extension("trailing.") == ""

    def test_digest_and_sizes(self) -> None:
        assert digest_of(b"hello world") == (
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        )
        assert human_bytes(0) == "0 B"
        assert human_bytes(512) == "512 B"
        assert human_bytes(1536) == "1.5 KB"
        assert human_bytes(5 * 1024 * 1024) == "5.0 MB"


# ---------------------------------------------------------------- stages/dtos


class TestStageVocabulary:
    def test_m1_sequence_is_hash_then_deferred_then_review(self) -> None:
        assert [s.value for s in ITEM_STAGE_SEQUENCE] == [
            "stage",
            "hash",
            "extract",
            "classify",
            "match",
            "propose",
            "review",
        ]

    def test_every_deferred_stage_names_its_milestone(self) -> None:
        # M2: EXTRACT left the deferred map when the deterministic engine landed.
        assert IntakeStage.EXTRACT not in DEFERRED_STAGE_MILESTONES
        for stage in (IntakeStage.CLASSIFY, IntakeStage.MATCH, IntakeStage.PROPOSE):
            result = deferred_stage_result(stage)
            assert result["deferred"] is True
            assert result["milestone"] == DEFERRED_STAGE_MILESTONES[stage]
        assert DEFERRED_STAGE_MILESTONES.keys() <= set(ITEM_STAGE_SEQUENCE)

    def test_stage_record_shape(self) -> None:
        record = finish_record(IntakeStage.HASH, "2026-01-01T00:00:00", {"verified": True})
        payload = record.to_dict()
        assert payload["stage"] == "hash"
        assert payload["entered_at"] == "2026-01-01T00:00:00"
        assert payload["result"] == {"verified": True}
        assert payload["exited_at"] >= payload["entered_at"]


class TestAggregation:
    def _facts(self) -> list[IntakeItemFacts]:
        return [
            IntakeItemFacts(IntakeItemStatus.AWAITING_REVIEW, IntakeStage.REVIEW, 100, "pdf", "application/pdf", True, True, "extracted"),
            IntakeItemFacts(IntakeItemStatus.AWAITING_REVIEW, IntakeStage.REVIEW, 300, "pdf", "application/pdf", True, True, "extracted"),
            IntakeItemFacts(IntakeItemStatus.ERROR, IntakeStage.STAGE, 50, "png", None, False, False, "unsupported"),
            IntakeItemFacts(IntakeItemStatus.PENDING, IntakeStage.ENUMERATE, 10, "txt", None, False, False, None),
        ]

    def test_summarize_items_counts_everything(self) -> None:
        summary = summarize_items(self._facts(), enumerated=True)
        assert summary["total_items"] == 4
        assert summary["processed_items"] == 3
        assert summary["percent"] == 75.0
        assert summary["awaiting_review"] == 2
        assert summary["errors"] == 1
        assert summary["pending"] == 1
        assert summary["hashed"] == 2
        assert summary["total_bytes"] == 460
        assert summary["by_extension"] == {"pdf": 2, "png": 1, "txt": 1}
        assert summary["by_mime"] == {"application/pdf": 2}
        assert summary["extracted_items"] == 2
        assert summary["unsupported_items"] == 1

    def test_empty_totals(self) -> None:
        assert summarize_items([], enumerated=True)["percent"] == 100.0
        assert summarize_items([], enumerated=False)["percent"] == 0.0


# ------------------------------------------------------- view builders (DTO)


def _mk_obj(object_type: ObjectType, entries: list[tuple[str, str]]) -> UniversalObject:
    return UniversalObject.create(
        object_type=object_type,
        title="fixture",
        created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(
            entries=tuple(
                MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)
                for k, v in entries
            )
        ),
    )


class TestViewBuilders:
    def _session(self) -> UniversalObject:
        return _mk_obj(
            ObjectType.INTAKE_SESSION,
            [
                (KEY_INTAKE_STATUS, "completed"),
                (KEY_PROGRESS, json_encode({"enumerated": True})),
                (
                    KEY_STATISTICS,
                    json_encode({"skipped_junk": 2, "skipped_junk_samples": [".DS_Store"]}),
                ),
            ],
        )

    def _item(self, session_id: str) -> UniversalObject:
        return _mk_obj(
            ObjectType.INTAKE_ITEM,
            [
                ("intake.session_id", session_id),
                (KEY_INTAKE_STATUS, "awaiting_review"),
                ("intake.relative_path", "Sub/paper.pdf"),
                ("intake.original_path", "/x/Sub/paper.pdf"),
                ("intake.extension", "pdf"),
                ("intake.size_bytes", "42"),
                ("intake.mime_type", "application/pdf"),
                ("intake.sha256", "ab" * 32),
                ("intake.staged_key", "intake/s/Sub/paper.pdf"),
                ("intake.stage", "review"),
                ("intake.attempts", "1"),
                ("intake.stage_history", json_encode([{"stage": "hash", "result": {"verified": True}}])),
            ],
        )

    def test_item_output_round_trip(self) -> None:
        out = intake_item_output(self._item("s1"))
        assert out.session_id == "s1"
        assert out.relative_path == "Sub/paper.pdf"
        assert out.size_bytes == 42
        assert out.sha256 == "ab" * 32
        assert out.stage_history[0]["result"]["verified"] is True
        assert intake_item_facts(self._item("s1")).has_hash is True

    def test_session_output_merges_live_items_with_seed(self) -> None:
        session = self._session()
        item = self._item(str(session.id))
        out = intake_session_output(session, [item])
        assert out.status == "completed"
        assert out.progress["total"] == 1
        assert out.progress["awaiting_review"] == 1
        assert out.statistics["skipped_junk"] == 2
        assert out.statistics["by_extension"] == {"pdf": 1}

    def test_progress_output_is_recomputed(self) -> None:
        session = self._session()
        item = self._item(str(session.id))
        out = intake_progress_output(session, [item])
        assert out.total_items == 1 and out.processed_items == 1 and out.percent == 100.0
        assert out.counts["awaiting_review"] == 1

    def test_summarize_counts_committed_as_processed(self) -> None:
        facts = [
            IntakeItemFacts(IntakeItemStatus.AWAITING_REVIEW, IntakeStage.REVIEW, 100, "pdf", "application/pdf", True, True, "extracted"),
            IntakeItemFacts(IntakeItemStatus.COMMITTED, IntakeStage.REVIEW, 200, "pdf", "application/pdf", True, True, "extracted"),
            IntakeItemFacts(IntakeItemStatus.COMMITTED, IntakeStage.REVIEW, 300, "pdf", "application/pdf", True, True, "extracted"),
            IntakeItemFacts(IntakeItemStatus.ERROR, IntakeStage.STAGE, 50, "png", None, False, False, "unsupported"),
        ]
        summary = summarize_items(facts, enumerated=True)
        assert summary["total_items"] == 4
        # Committed items left the queue: processed = awaiting + committed + error.
        assert summary["awaiting_review"] == 1
        assert summary["committed_items"] == 2
        assert summary["processed_items"] == 4
        assert summary["percent"] == 100.0
        # Progress payload mirrors the committed count (additive key).
        progress = intake_session_progress_of(
            TestViewBuilders._session(TestViewBuilders), []
        )
        assert progress["committed_items"] == 0
        assert progress["remaining_items"] == 0

    def test_committed_items_do_not_count_as_remaining(self) -> None:
        facts = [
            IntakeItemFacts(IntakeItemStatus.COMMITTED, IntakeStage.REVIEW, 100, "pdf", "application/pdf", True, True, "extracted"),
            IntakeItemFacts(IntakeItemStatus.AWAITING_REVIEW, IntakeStage.REVIEW, 200, "pdf", "application/pdf", True, True, "extracted"),
            IntakeItemFacts(IntakeItemStatus.PENDING, IntakeStage.ENUMERATE, 50, "txt", None, False, False, None),
        ]
        summary = summarize_items(facts, enumerated=True)
        # committed is processed and at rest: it must not appear as remaining.
        remaining = (
            summary["total_items"]
            - summary["awaiting_review"]
            - summary["committed_items"]
            - (summary["errors"] - summary["retryable_items"])
        )
        assert remaining == 1  # only the pending item is owed
