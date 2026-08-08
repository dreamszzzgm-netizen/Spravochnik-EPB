from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class StoredObjectInfo:
    storage_key: str
    sha256: str
    size_bytes: int


class Storage(Protocol):
    def put(self, source: BinaryIO, *, storage_key: str | None = None) -> StoredObjectInfo: ...
    def open(self, storage_key: str) -> BinaryIO: ...
    def delete(self, storage_key: str) -> None: ...
    def exists(self, storage_key: str) -> bool: ...
    def resolve_path(self, storage_key: str) -> Path: ...
