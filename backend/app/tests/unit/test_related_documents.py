"""Unit tests: RelatedDocumentsUseCase (Sprint M13.3).

Covers source handling (exists / READ / extracted text), honest degradation
(no/failed embedding or vector backend), the result contract (self-exclusion,
permission filtering, limit, deterministic ordering, zero results, stale-row
safety), and reuse of the existing search scoring convention. Uses the REAL
``ObjectPermissionEvaluator`` with ACL-restricted objects for permission
fidelity. All edges mocked — no network, no Qdrant.
"""
from __future__ import annotations

import json

import pytest

from app.application.exceptions import (
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.application.use_cases.ai.related_documents import RelatedDocumentsUseCase
from app.application.use_cases.search.search_objects import _RRF_K, _SCORE_DECIMALS
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer, Provenance
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator

SOURCE_ID = "obj:document:src"


# --------------------------------------------------------------------------- mocks


class _MockRepo:
    def __init__(self, source=None, objects=None):
        self._source = source
        self._objects = {str(o.id): o for o in (objects or [])}

    def get_by_id(self, oid):
        return self._source

    def find_by_ids(self, ids):
        return [self._objects[str(i)] for i in ids if str(i) in self._objects]


class _MockAnnotationService:
    def __init__(self, extraction=None):
        self._extraction = extraction

    def extracted_text(self, document_id, storage):
        return self._extraction


class _MockEmbedder:
    dimensions = 8

    def __init__(self, raise_exc=None):
        self.embed_calls: list[str] = []
        self._raise = raise_exc

    def embed(self, text):
        self.embed_calls.append(text)
        if self._raise:
            raise self._raise
        return [0.0] * self.dimensions


class _MockVectorRepository:
    def __init__(self, results=None, raise_exc=None):
        self._results = list(results or [])
        self._raise = raise_exc
        self.last_limit = None

    def search(self, vector, *, limit=50):
        self.last_limit = limit
        if self._raise:
            raise self._raise
        return list(self._results)


# --------------------------------------------------------------------------- helpers


def _user():
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:alice-0001"),
    )


def _doc(oid, title="Doc"):
    return UniversalObject.create(
        ObjectType.DOCUMENT, title, created_by="system", object_id=ObjectId(oid),
    )


def _restrict(obj, reader="obj:user:someone-else"):
    """Restrict READ to ``reader`` (not the test user) so the evaluator denies."""
    obj.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps([reader]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    return obj


def _vdoc(oid, title="Doc", version=1, object_type="document"):
    return VectorDocument(
        object_id=oid, object_type=object_type, title=title,
        metadata_text="", version=version, vector=(0.0,),
    )


def _project(oid, title="Project"):
    return UniversalObject.create(
        ObjectType.RESEARCH_PROJECT, title, created_by="system", object_id=ObjectId(oid),
    )


def _rrf(rank):
    return round(1.0 / (_RRF_K + rank + 1), _SCORE_DECIMALS)


def _use_case(
    *, source=None, objects=None, vector_results=None, embedder=None,
    evaluator=None, annotation=None, vector_repo=None,
):
    return RelatedDocumentsUseCase(
        _MockRepo(source=source, objects=objects),
        annotation if annotation is not None else _MockAnnotationService({"text": "source text"}),
        evaluator if evaluator is not None else ObjectPermissionEvaluator(),
        vector_repo if vector_repo is not None else _MockVectorRepository(vector_results),
        embedder if embedder is not None else _MockEmbedder(),
    )


def _run(use_case, *, limit=10):
    return use_case.execute(SOURCE_ID, _user(), storage=None, limit=limit)


# --------------------------------------------------------------------------- source handling


class TestSourceHandling:
    def test_source_not_found_raises(self):
        use_case = _use_case(source=None)
        with pytest.raises(ObjectNotFoundError):
            _run(use_case)

    def test_source_permission_denied_raises(self):
        use_case = _use_case(source=_restrict(_doc(SOURCE_ID)))
        with pytest.raises(PermissionDeniedError, match="READ"):
            _run(use_case)

    def test_no_extracted_text_raises_validation(self):
        use_case = _use_case(
            source=_doc(SOURCE_ID), annotation=_MockAnnotationService(None),
        )
        with pytest.raises(ValidationError, match="No extracted text"):
            _run(use_case)


# --------------------------------------------------------------------------- honest degradation


class TestHonestDegradation:
    def test_no_vector_repository_returns_empty(self):
        use_case = _use_case(source=_doc(SOURCE_ID), vector_repo=None)
        assert _run(use_case).items == ()

    def test_no_embedder_returns_empty(self):
        use_case = _use_case(source=_doc(SOURCE_ID), embedder=None)
        assert _run(use_case).items == ()

    def test_embedding_failure_returns_empty(self):
        emb = _MockEmbedder(raise_exc=RuntimeError("embed down"))
        use_case = _use_case(source=_doc(SOURCE_ID), embedder=emb)
        assert _run(use_case).items == ()

    def test_vector_search_failure_returns_empty(self):
        vr = _MockVectorRepository(raise_exc=RuntimeError("qdrant down"))
        use_case = _use_case(source=_doc(SOURCE_ID), vector_repo=vr)
        assert _run(use_case).items == ()


# --------------------------------------------------------------------------- result contract


class TestResultContract:
    def test_success_returns_related_items(self):
        a, b = _doc("obj:document:a", "Alpha"), _doc("obj:document:b", "Beta")
        use_case = _use_case(
            source=_doc(SOURCE_ID),
            objects=[a, b],
            vector_results=[_vdoc("obj:document:a", "Alpha"), _vdoc("obj:document:b", "Beta")],
        )
        result = _run(use_case)
        assert [i.object_id for i in result.items] == ["obj:document:a", "obj:document:b"]
        assert result.items[0].title == "Alpha"
        assert result.items[0].object_type == "document"
        assert result.items[0].version == 1
        assert result.items[0].score == _rrf(0)

    def test_source_excluded_from_results(self):
        a = _doc("obj:document:a")
        use_case = _use_case(
            source=_doc(SOURCE_ID),
            objects=[a],
            # The source is the #1 nearest neighbour (most similar to itself).
            vector_results=[_vdoc(SOURCE_ID), _vdoc("obj:document:a")],
        )
        result = _run(use_case)
        assert [i.object_id for i in result.items] == ["obj:document:a"]
        assert SOURCE_ID not in [i.object_id for i in result.items]

    def test_unreadable_result_is_filtered(self):
        a = _doc("obj:document:a", "Alpha")
        b = _restrict(_doc("obj:document:b", "Beta"))  # not readable by alice
        c = _doc("obj:document:c", "Gamma")
        use_case = _use_case(
            source=_doc(SOURCE_ID),
            objects=[a, b, c],
            vector_results=[
                _vdoc("obj:document:a"), _vdoc("obj:document:b"), _vdoc("obj:document:c"),
            ],
        )
        result = _run(use_case)
        assert [i.object_id for i in result.items] == ["obj:document:a", "obj:document:c"]

    def test_stale_index_row_never_leaks(self):
        a = _doc("obj:document:a")
        use_case = _use_case(
            source=_doc(SOURCE_ID),
            objects=[a],  # 'ghost' is in the index but not the object store
            vector_results=[_vdoc("obj:document:a"), _vdoc("obj:document:ghost")],
        )
        result = _run(use_case)
        assert [i.object_id for i in result.items] == ["obj:document:a"]

    def test_limit_is_applied_and_query_fetches_one_extra(self):
        a, b, c = _doc("obj:document:a"), _doc("obj:document:b"), _doc("obj:document:c")
        vr = _MockVectorRepository([
            _vdoc("obj:document:a"), _vdoc("obj:document:b"), _vdoc("obj:document:c"),
        ])
        use_case = _use_case(source=_doc(SOURCE_ID), objects=[a, b, c], vector_repo=vr)
        result = _run(use_case, limit=2)
        assert len(result.items) == 2
        assert vr.last_limit == 3  # limit + 1

    def test_limit_is_bounded(self):
        use_case = _use_case(source=_doc(SOURCE_ID))
        _run(use_case, limit=99999)  # must not raise; clamped internally
        # and negative/zero clamp to 1
        result = _run(use_case, limit=0)
        assert isinstance(result.items, tuple)

    def test_zero_results_is_valid(self):
        use_case = _use_case(source=_doc(SOURCE_ID), vector_results=[])
        result = _run(use_case)
        assert result.items == ()

    def test_deterministic_ordering_preserved(self):
        a, b, c = _doc("obj:document:a"), _doc("obj:document:b"), _doc("obj:document:c")
        use_case = _use_case(
            source=_doc(SOURCE_ID),
            objects=[a, b, c],
            vector_results=[_vdoc("obj:document:c"), _vdoc("obj:document:a"), _vdoc("obj:document:b")],
        )
        result = _run(use_case)
        # Order matches the vector-search rank (cosine similarity), not object_id.
        assert [i.object_id for i in result.items] == ["obj:document:c", "obj:document:a", "obj:document:b"]
        # Scores are monotonically non-increasing.
        scores = [i.score for i in result.items]
        assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------- embedder reuse


class TestEmbedderReuse:
    def test_source_text_embedded_exactly_once(self):
        emb = _MockEmbedder()
        a = _doc("obj:document:a")
        use_case = _use_case(
            source=_doc(SOURCE_ID), objects=[a],
            vector_results=[_vdoc(SOURCE_ID), _vdoc("obj:document:a")],
            embedder=emb,
        )
        _run(use_case)
        assert len(emb.embed_calls) == 1
        assert emb.embed_calls[0] == "source text"


class TestDocumentTypeRestriction:
    """M13.3.1 defect-2: related documents are documents only."""

    def test_non_document_source_rejected(self):
        use_case = _use_case(source=_project(SOURCE_ID))
        with pytest.raises(ValidationError, match="not a document"):
            _run(use_case)

    def test_non_document_candidate_excluded(self):
        proj = _project("obj:project:p1", "A Project")
        doc = _doc("obj:document:a", "A Doc")
        use_case = _use_case(
            source=_doc(SOURCE_ID),
            objects=[proj, doc],
            vector_results=[
                _vdoc("obj:project:p1", "A Project", object_type="research_project"),
                _vdoc("obj:document:a", "A Doc"),
            ],
        )
        result = _run(use_case)
        assert [i.object_id for i in result.items] == ["obj:document:a"]

    def test_document_candidate_returned_among_non_documents(self):
        proj = _project("obj:project:p1", "P1")
        doc = _doc("obj:document:a", "A")
        use_case = _use_case(
            source=_doc(SOURCE_ID),
            objects=[proj, doc],
            vector_results=[
                _vdoc("obj:project:p1", "P1", object_type="research_project"),
                _vdoc("obj:document:a", "A"),
            ],
        )
        result = _run(use_case)
        assert len(result.items) == 1
        assert result.items[0].object_id == "obj:document:a"
        assert result.items[0].object_type == "document"

    def test_permission_and_source_exclusion_still_hold_with_type_filter(self):
        # Mix: source (excluded), a restricted doc (filtered), a project
        # (filtered by type), and a readable doc (kept).
        readable = _doc("obj:document:keep", "Keep")
        restricted = _restrict(_doc("obj:document:nope", "Nope"))
        proj = _project("obj:project:p", "Proj")
        use_case = _use_case(
            source=_doc(SOURCE_ID),
            objects=[readable, restricted, proj],
            vector_results=[
                _vdoc(SOURCE_ID),                       # self -> excluded
                _vdoc("obj:document:nope", "Nope"),     # unreadable -> filtered
                _vdoc("obj:project:p", "Proj", object_type="research_project"),  # non-doc
                _vdoc("obj:document:keep", "Keep"),     # kept
            ],
        )
        result = _run(use_case)
        assert [i.object_id for i in result.items] == ["obj:document:keep"]
