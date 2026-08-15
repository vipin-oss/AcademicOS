"""L2 container safety policy tests (ADR-029)."""

from __future__ import annotations

import pytest

from app.application.services.container_policy import (
    ContainerPolicyError,
    assert_member_size,
    assert_safe_expansion,
    assert_safe_member_path,
)
from app.application.services.extraction_limits import (
    MAX_CONTAINER_DEPTH,
    MAX_MEMBER_BYTES,
    MAX_MEMBERS,
    MAX_PACKAGE_TOTAL_BYTES,
)


def test_path_traversal_rejected():
    for bad in ("../evil", "a/../../evil", "/abs", "\\abs", "a\\..\\b"):
        with pytest.raises(ContainerPolicyError):
            assert_safe_member_path(bad)


def test_safe_path_allowed():
    assert_safe_member_path("dir/file.pdf")  # no raise
    assert_safe_member_path("a/b/c.txt")


def test_depth_limit():
    with pytest.raises(ContainerPolicyError):
        assert_safe_expansion(total_uncompressed=10, compressed_size=10, member_count=1, depth=MAX_CONTAINER_DEPTH + 1)


def test_member_count_limit():
    with pytest.raises(ContainerPolicyError):
        assert_safe_expansion(total_uncompressed=10, compressed_size=10, member_count=MAX_MEMBERS + 1, depth=1)


def test_total_size_limit():
    with pytest.raises(ContainerPolicyError):
        assert_safe_expansion(
            total_uncompressed=MAX_PACKAGE_TOTAL_BYTES + 1, compressed_size=1000,
            member_count=1, depth=1,
        )


def test_compression_bomb_rejected():
    with pytest.raises(ContainerPolicyError):
        # uncompressed far exceeds compressed -> suspicious ratio
        assert_safe_expansion(
            total_uncompressed=10_000_000, compressed_size=100, member_count=1, depth=1
        )


def test_member_size_limit():
    with pytest.raises(ContainerPolicyError):
        assert_member_size(MAX_MEMBER_BYTES + 1)
