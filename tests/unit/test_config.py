from pathlib import Path

from app.core.config import Settings


def test_test_database_url_is_used_in_test_environment(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://prod",
        test_database_url="postgresql+psycopg://test",
        storage_root=tmp_path,
    )
    assert settings.effective_database_url == "postgresql+psycopg://test"
