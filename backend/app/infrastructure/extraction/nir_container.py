"""L2 container expander (ADR-029).

Safe stdlib ``zipfile`` expansion with path-traversal, bomb, member-count,
per-member, total-size, ratio and depth enforcement. Corrupt/unsupported
members are returned with ``ok=False`` and an explicit error — never silently
dropped. The container itself raising ``ContainerExpandError`` indicates an
unsafe whole-package condition.
"""

from __future__ import annotations

import hashlib
import zipfile

from app.application.ports.container_expander import (
    ContainerExpander,
    ContainerExpandError,
    ContainerMember,
)
from app.application.services.container_policy import (
    ContainerPolicyError,
    assert_member_size,
    assert_safe_expansion,
    assert_safe_member_path,
    pick_duplicate,
)
from app.application.services.extraction_limits import MAX_CONTAINER_DEPTH


class ZipContainerExpander(ContainerExpander):
    def expand(self, data: bytes, *, depth: int = 1) -> list[ContainerMember]:
        return self._expand(data, depth)

    def _expand(self, data: bytes, depth: int) -> list[ContainerMember]:
        try:
            zf = zipfile.ZipFile(__import__("io").BytesIO(data))
        except (zipfile.BadZipFile, Exception) as exc:  # noqa: BLE001
            raise ContainerExpandError(f"Corrupt container: {exc}") from exc

        infos = []
        try:
            infos = zf.infolist()
        except Exception as exc:  # noqa: BLE001
            raise ContainerExpandError(f"Container listing failed: {exc}") from exc

        total_uncompressed = 0
        member_count = 0
        seen: dict[str, bytes] = {}
        members: list[ContainerMember] = []

        for info in infos:
            member_count += 1
            assert_safe_expansion(
                total_uncompressed=total_uncompressed + info.file_size,
                compressed_size=len(data),
                member_count=member_count,
                depth=depth,
            )

            name = info.filename
            try:
                assert_safe_member_path(name)
            except ContainerPolicyError as exc:
                # Traversal/unsafe path -> whole package unsafe (reject).
                raise ContainerExpandError(str(exc)) from exc

            # duplicate handling (first-wins by path order)
            if name in seen:
                if pick_duplicate(name, name):
                    continue  # keep existing
            try:
                content = zf.read(info)
            except (zipfile.BadZipFile, RuntimeError) as exc:
                members.append(
                    ContainerMember(
                        path=name, data=b"", sha256=_sha256(b""), ok=False,
                        error=f"corrupt member: {exc}", nested=depth > 1,
                    )
                )
                continue
            except Exception as exc:  # noqa: BLE001
                members.append(
                    ContainerMember(
                        path=name, data=b"", sha256=_sha256(b""), ok=False,
                        error=f"unreadable member: {exc}", nested=depth > 1,
                    )
                )
                continue

            try:
                assert_member_size(len(content))
            except ContainerPolicyError as exc:
                members.append(
                    ContainerMember(
                        path=name, data=b"", sha256=_sha256(b""), ok=False,
                        error=str(exc), nested=depth > 1,
                    )
                )
                continue

            seen[name] = content
            total_uncompressed += len(content)
            members.append(
                ContainerMember(
                    path=name, data=content, sha256=_sha256(content),
                    ok=True, nested=depth > 1,
                )
            )

        return members


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


__all__ = ["MAX_CONTAINER_DEPTH", "ZipContainerExpander"]
