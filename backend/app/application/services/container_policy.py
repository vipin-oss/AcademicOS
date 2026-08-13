"""L2 container safety policy (ADR-029).

Deterministic validation of one container expansion decision: path traversal,
compression bombs, member counts, per-member and total sizes, nesting depth, and
duplicates. Pure logic (no zipfile) so it is testable and application-layer
safe.
"""

from __future__ import annotations

import os

from app.application.services.extraction_limits import (
    MAX_COMPRESSION_RATIO,
    MAX_CONTAINER_DEPTH,
    MAX_MEMBER_BYTES,
    MAX_MEMBERS,
    MAX_PACKAGE_TOTAL_BYTES,
)


class ContainerPolicyError(Exception):
    """The container violates a safety boundary."""


def assert_safe_member_path(member_path: str) -> None:
    """Reject absolute paths and path traversal (``..`` / symlink risk)."""
    if os.path.isabs(member_path) or member_path.startswith(("/", "\\")):
        raise ContainerPolicyError(f"Absolute member path not allowed: {member_path!r}")
    norm = os.path.normpath(member_path)
    if norm.startswith("..") or "/.." in f"/{norm}" or "\\.." in norm.replace("/", "\\"):
        raise ContainerPolicyError(f"Path traversal not allowed: {member_path!r}")
    if norm in ("", "."):
        raise ContainerPolicyError("Empty member path not allowed.")


def assert_safe_expansion(
    *,
    total_uncompressed: int,
    compressed_size: int,
    member_count: int,
    depth: int,
) -> None:
    """Validate aggregate container limits before/all during expansion."""
    if depth > MAX_CONTAINER_DEPTH:
        raise ContainerPolicyError(
            f"Container nesting exceeds max depth {MAX_CONTAINER_DEPTH}."
        )
    if member_count > MAX_MEMBERS:
        raise ContainerPolicyError(
            f"Member count {member_count} exceeds max {MAX_MEMBERS}."
        )
    if total_uncompressed > MAX_PACKAGE_TOTAL_BYTES:
        raise ContainerPolicyError("Container total uncompressed size exceeds limit.")
    if compressed_size > 0:
        ratio = total_uncompressed / compressed_size
        if ratio > MAX_COMPRESSION_RATIO:
            raise ContainerPolicyError(
                f"Compression ratio {ratio:.0f} exceeds max {MAX_COMPRESSION_RATIO} "
                "(possible decompression bomb)."
            )


def assert_member_size(data_len: int) -> None:
    if data_len > MAX_MEMBER_BYTES:
        raise ContainerPolicyError(f"Member size {data_len} exceeds max.")


def pick_duplicate(existing_path: str, incoming_path: str) -> bool:
    """Deterministic duplicate policy: keep the first, warn on later.

    Returns True if the incoming duplicate should be kept (first-wins => False
    keeps the existing; the caller records a warning).
    """
    # First-wins by stable path order.
    return existing_path > incoming_path
