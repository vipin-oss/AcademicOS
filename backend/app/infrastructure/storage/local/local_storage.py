"""Local-filesystem adapter for the FileStorage port.

The first concrete adapter in the pre-planned ``infrastructure/storage`` slot
(the architecture reserves sibling slots for ``google_drive`` and
``onedrive``). Blobs live under a configurable root directory; every key is
containment-checked so a stored key can never escape the root. No domain
logic here — only persistence plumbing.
"""
from __future__ import annotations

from pathlib import Path

from app.application.ports.file_storage import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self, root: str) -> None:
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        """Resolve ``key`` inside the root, refusing traversal outside it."""
        path = (self._root / key).resolve()
        if path != self._root and self._root not in path.parents:
            raise ValueError(f"Unsafe storage key: {key!r}")
        return path

    def save(self, key: str, content: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)
        # Prune now-empty parent directories (never the root itself).
        parent = path.parent
        while parent != self._root and parent.is_dir():
            try:
                parent.rmdir()
            except OSError:  # not empty
                break
            parent = parent.parent
