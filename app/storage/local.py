import contextlib
import hashlib
import os
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.storage.base import StoredObjectInfo


class StorageLimitExceeded(ValueError):
    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        super().__init__(f"storage object exceeds {max_bytes} bytes")


class LocalFileStorage:
    """Private local storage.

    Physical names are generated keys, never user supplied filenames.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, storage_key: str) -> Path:
        if not storage_key or "/" in storage_key or "\\" in storage_key:
            raise ValueError("storage_key must be a single generated path segment")
        candidate = (self.root / storage_key).resolve()
        if candidate.parent != self.root:
            raise ValueError("storage_key escapes storage root")
        return candidate

    def resolve_path(self, storage_key: str) -> Path:
        return self._safe_path(storage_key)

    def put(
        self,
        source: BinaryIO,
        *,
        storage_key: str | None = None,
        max_bytes: int | None = None,
    ) -> StoredObjectInfo:
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")

        key = storage_key or str(uuid4())
        destination = self._safe_path(key)
        if destination.exists():
            raise FileExistsError(f"storage key already exists: {key}")

        digest = hashlib.sha256()
        size = 0

        fd, tmp_name = tempfile.mkstemp(prefix=".upload-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as temp_file:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if max_bytes is not None and size > max_bytes:
                        raise StorageLimitExceeded(max_bytes)
                    digest.update(chunk)
                    temp_file.write(chunk)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(tmp_name, destination)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_name)
            raise

        return StoredObjectInfo(storage_key=key, sha256=digest.hexdigest(), size_bytes=size)

    def open(self, storage_key: str) -> BinaryIO:
        return self._safe_path(storage_key).open("rb")

    def delete(self, storage_key: str) -> None:
        self._safe_path(storage_key).unlink(missing_ok=True)

    def exists(self, storage_key: str) -> bool:
        return self._safe_path(storage_key).is_file()
