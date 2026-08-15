"""Unit tests for the embedder port + T0 adapter (Sprint-5 M2).

The port contract is determinism: same text -> same vector, always; the
adapter must be CI-safe (no model, no network).
"""
from __future__ import annotations

import pytest

from app.application.ports.embedder import Embedder
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder


def test_adapter_implements_the_port():
    assert isinstance(HashingEmbedder(), Embedder)
    assert HashingEmbedder().dimensions == 256


def test_dimensions_are_configurable():
    assert HashingEmbedder(dimensions=64).dimensions == 64
    with pytest.raises(ValueError):
        HashingEmbedder(dimensions=0)


def test_same_text_same_vector():
    embedder = HashingEmbedder()
    first = embedder.embed("Quantum physics notes")
    second = embedder.embed("Quantum physics notes")
    assert first == second
    assert len(first) == 256


def test_deterministic_across_instances():
    # Deterministic by contract: two independent embedders agree.
    a = HashingEmbedder().embed("machine learning")
    b = HashingEmbedder().embed("machine learning")
    assert a == b


def test_different_texts_differ():
    assert HashingEmbedder().embed("physics") != HashingEmbedder().embed("history")


def test_case_and_whitespace_insensitive():
    # Normalized tokens: casing and spacing do not change the vector.
    embedder = HashingEmbedder()
    assert embedder.embed("Quantum Physics") == embedder.embed("quantum physics")
    assert embedder.embed("a  b") == embedder.embed("a b")


def test_vectors_are_l2_normalized():
    vector = HashingEmbedder().embed("some longer text with many tokens")
    norm = sum(v * v for v in vector) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_empty_text_is_zero_vector():
    vector = HashingEmbedder().embed("")
    assert vector == [0.0] * 256


def test_no_network_no_model():
    """The adapter is pure stdlib math — importable and callable without
    any network or model infrastructure."""
    import inspect

    source = inspect.getsource(HashingEmbedder)
    for forbidden in ("socket", "requests", "http", "open("):
        assert forbidden not in source
