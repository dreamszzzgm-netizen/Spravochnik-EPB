from io import BytesIO
from pathlib import Path

import pytest

from app.storage.local import LocalFileStorage, StorageLimitExceeded


def test_put_calculates_sha256_and_preserves_bytes(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    info = storage.put(BytesIO(b"spravoshnik"))

    assert info.size_bytes == 11
    assert len(info.sha256) == 64
    assert storage.exists(info.storage_key)
    with storage.open(info.storage_key) as stored:
        assert stored.read() == b"spravoshnik"


def test_put_rejects_stream_over_limit_without_persisting(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)

    with pytest.raises(StorageLimitExceeded):
        storage.put(BytesIO(b"123456"), max_bytes=5)

    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


@pytest.mark.parametrize("key", ["../secret", "a/b", r"a\\b", ""])
def test_storage_key_cannot_escape_root(tmp_path: Path, key: str) -> None:
    storage = LocalFileStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.resolve_path(key)
