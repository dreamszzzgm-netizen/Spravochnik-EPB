import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_config(url: str) -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _set_database_url(url: str) -> tuple[str | None, str | None]:
    previous_database = os.environ.get("DATABASE_URL")
    previous_test_database = os.environ.get("TEST_DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    os.environ["TEST_DATABASE_URL"] = url
    return previous_database, previous_test_database


def _restore_database_url(previous: tuple[str | None, str | None]) -> None:
    previous_database, previous_test_database = previous
    if previous_database is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_database
    if previous_test_database is None:
        os.environ.pop("TEST_DATABASE_URL", None)
    else:
        os.environ["TEST_DATABASE_URL"] = previous_test_database


def test_universal_document_migration_preserves_legacy_rows() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    cfg = _alembic_config(url)
    previous = _set_database_url(url)
    engine = create_engine(url)
    organization_id = uuid.uuid4()
    active_id = uuid.uuid4()
    deleted_id = uuid.uuid4()
    deleted_at = datetime(2026, 8, 1, 10, 30, tzinfo=UTC)

    try:
        command.downgrade(cfg, "0020_identifier_constraints")
        with engine.begin() as connection:
            connection.execute(sa.text("TRUNCATE TABLE organization_documents, organizations CASCADE"))
            connection.execute(
                sa.text(
                    """
                    INSERT INTO organizations (id, organization_type, legal_name)
                    VALUES (:id, 'legal_entity', 'Legacy Documents LLC')
                    """
                ),
                {"id": organization_id},
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO organization_documents (
                        id, organization_id, document_type, title,
                        original_filename, content_type, storage_key,
                        sha256, size_bytes, issued_at, expires_at, deleted_at
                    ) VALUES (
                        :id, :organization_id, 'insurance', 'Insurance 2026',
                        'legacy.pdf', 'application/pdf', :storage_key,
                        :sha256, 17, DATE '2026-01-01', DATE '2026-12-31', NULL
                    )
                    """
                ),
                {
                    "id": active_id,
                    "organization_id": organization_id,
                    "storage_key": f"legacy/{active_id}.pdf",
                    "sha256": "a" * 64,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO organization_documents (
                        id, organization_id, document_type, title,
                        original_filename, content_type, storage_key,
                        sha256, size_bytes, deleted_at
                    ) VALUES (
                        :id, :organization_id, 'other', 'Deleted legacy',
                        'deleted.pdf', 'application/pdf', :storage_key,
                        :sha256, 9, :deleted_at
                    )
                    """
                ),
                {
                    "id": deleted_id,
                    "organization_id": organization_id,
                    "storage_key": f"legacy/{deleted_id}.pdf",
                    "sha256": "b" * 64,
                    "deleted_at": deleted_at,
                },
            )

        command.upgrade(cfg, "0021_universal_documents")

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"documents", "document_versions", "document_links"} <= tables
        assert "organization_documents" not in tables

        with engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    """
                    SELECT d.id, d.document_type, d.title, d.issued_at, d.expires_at,
                           d.deleted_at, d.current_version_id,
                           v.original_filename, v.content_type, v.storage_key,
                           v.sha256, v.size_bytes, v.version_number,
                           l.organization_id
                    FROM documents d
                    JOIN document_versions v ON v.id = d.current_version_id
                    JOIN document_links l ON l.document_id = d.id
                    WHERE d.id = :legacy_id
                    """
                ),
                {"legacy_id": active_id},
            ).mappings().one()
            assert row["id"] == active_id
            assert row["document_type"] == "insurance"
            assert row["title"] == "Insurance 2026"
            assert row["original_filename"] == "legacy.pdf"
            assert row["storage_key"] == f"legacy/{active_id}.pdf"
            assert row["sha256"] == "a" * 64
            assert row["size_bytes"] == 17
            assert row["version_number"] == 1
            assert row["organization_id"] == organization_id

            migrated_deleted_at = connection.execute(
                sa.text("SELECT deleted_at FROM documents WHERE id = :id"),
                {"id": deleted_id},
            ).scalar_one()
            assert migrated_deleted_at == deleted_at
    finally:
        engine.dispose()
        _restore_database_url(previous)
