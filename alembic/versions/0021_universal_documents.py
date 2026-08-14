"""universal documents core

Revision ID: 0021_universal_documents
Revises: 0020_identifier_constraints
"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021_universal_documents"
down_revision: str | Sequence[str] | None = "0020_identifier_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MIGRATION_NAMESPACE = uuid.UUID("f98f5d8d-2d26-4d2a-b955-9664647f0d9d")


def _version_id(document_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(_MIGRATION_NAMESPACE, f"{document_id}:v1")


def _organization_link_id(document_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(_MIGRATION_NAMESPACE, f"{document_id}:organization-link")


def _create_universal_tables() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_type", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="working"),
        sa.Column("issued_at", sa.Date()),
        sa.Column("expires_at", sa.Date()),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "deleted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "status IN ('draft', 'working', 'final', 'archived')",
            name="ck_documents_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_documents_version_positive"),
    )
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])

    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(255)),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "document_id", "version_number", name="uq_document_versions_document_number"
        ),
        sa.UniqueConstraint(
            "document_id", "id", name="uq_document_versions_document_id_id"
        ),
        sa.CheckConstraint(
            "version_number >= 1", name="ck_document_versions_number_positive"
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_document_versions_size_nonnegative"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])

    op.create_foreign_key(
        "fk_documents_current_version",
        "documents",
        "document_versions",
        ["id", "current_version_id"],
        ["document_id", "id"],
        ondelete="RESTRICT",
        use_alter=True,
    )

    op.create_table(
        "document_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "opo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opo.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "technical_device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technical_devices.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "building_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("buildings.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "expertise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expertises.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "num_nonnulls(organization_id, opo_id, technical_device_id, building_id, "
            "contract_id, expertise_id, task_id) = 1",
            name="ck_document_links_exactly_one_target",
        ),
    )
    op.create_index("ix_document_links_document_id", "document_links", ["document_id"])
    for target in (
        "organization",
        "opo",
        "technical_device",
        "building",
        "contract",
        "expertise",
        "task",
    ):
        column = f"{target}_id"
        op.create_index(
            f"uq_document_links_document_{target}",
            "document_links",
            ["document_id", column],
            unique=True,
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )


def _migrate_legacy_rows() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, organization_id, document_type, title,
                   original_filename, content_type, storage_key,
                   sha256, size_bytes, issued_at, expires_at, deleted_at,
                   created_at, updated_at
            FROM organization_documents
            ORDER BY id
            """
        )
    ).mappings().all()

    for row in rows:
        document_id = row["id"]
        version_id = _version_id(document_id)
        link_id = _organization_link_id(document_id)
        connection.execute(
            sa.text(
                """
                INSERT INTO documents (
                    id, document_type, title, status, issued_at, expires_at,
                    current_version_id, created_by, deleted_by,
                    created_at, updated_at, deleted_at, version
                ) VALUES (
                    :id, :document_type, :title, 'working', :issued_at, :expires_at,
                    NULL, NULL, NULL, :created_at, :updated_at, :deleted_at, 1
                )
                """
            ),
            dict(row),
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO document_versions (
                    id, document_id, version_number, original_filename,
                    content_type, storage_key, sha256, size_bytes, created_by, created_at
                ) VALUES (
                    :version_id, :document_id, 1, :original_filename,
                    :content_type, :storage_key, :sha256, :size_bytes, NULL, :created_at
                )
                """
            ),
            {**dict(row), "version_id": version_id, "document_id": document_id},
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO document_links (
                    id, document_id, organization_id, created_at
                ) VALUES (:link_id, :document_id, :organization_id, :created_at)
                """
            ),
            {
                "link_id": link_id,
                "document_id": document_id,
                "organization_id": row["organization_id"],
                "created_at": row["created_at"],
            },
        )
        connection.execute(
            sa.text(
                "UPDATE documents SET current_version_id = :version_id WHERE id = :document_id"
            ),
            {"version_id": version_id, "document_id": document_id},
        )


def upgrade() -> None:
    _create_universal_tables()
    _migrate_legacy_rows()
    op.drop_index("ix_organization_documents_deleted_at", table_name="organization_documents")
    op.drop_index("ix_organization_documents_document_type", table_name="organization_documents")
    op.drop_index(
        "ix_organization_documents_organization_id", table_name="organization_documents"
    )
    op.drop_table("organization_documents")


def _assert_lossless_downgrade() -> None:
    connection = op.get_bind()
    impossible = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM documents d
                WHERE d.status <> 'working'
                   OR d.version <> 1
                   OR d.created_by IS NOT NULL
                   OR d.deleted_by IS NOT NULL
                   OR (
                        SELECT count(*) FROM document_versions v
                        WHERE v.document_id = d.id
                   ) <> 1
                   OR (
                        SELECT count(*) FROM document_links l
                        WHERE l.document_id = d.id
                   ) <> 1
                   OR d.current_version_id IS DISTINCT FROM (
                        SELECT v.id FROM document_versions v
                        WHERE v.document_id = d.id
                        LIMIT 1
                   )
                   OR EXISTS (
                        SELECT 1 FROM document_versions v
                        WHERE v.document_id = d.id
                          AND v.size_bytes > 2147483647
                   )
                   OR EXISTS (
                        SELECT 1 FROM document_links l
                        WHERE l.document_id = d.id
                          AND (
                            l.organization_id IS NULL
                            OR l.opo_id IS NOT NULL
                            OR l.technical_device_id IS NOT NULL
                            OR l.building_id IS NOT NULL
                            OR l.contract_id IS NOT NULL
                            OR l.expertise_id IS NOT NULL
                            OR l.task_id IS NOT NULL
                          )
                   )
            )
            """
        )
    ).scalar_one()
    if impossible:
        raise RuntimeError("universal documents cannot be downgraded losslessly")


def _restore_legacy_table() -> None:
    op.create_table(
        "organization_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(255)),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.Date()),
        sa.Column("expires_at", sa.Date()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_organization_documents_organization_id",
        "organization_documents",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_documents_document_type",
        "organization_documents",
        ["document_type"],
    )
    op.create_index(
        "ix_organization_documents_deleted_at", "organization_documents", ["deleted_at"]
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO organization_documents (
                id, organization_id, document_type, title,
                original_filename, content_type, storage_key, sha256, size_bytes,
                issued_at, expires_at, deleted_at, created_at, updated_at
            )
            SELECT d.id, l.organization_id, d.document_type, d.title,
                   v.original_filename, v.content_type, v.storage_key, v.sha256,
                   CAST(v.size_bytes AS INTEGER), d.issued_at, d.expires_at,
                   d.deleted_at, d.created_at, d.updated_at
            FROM documents d
            JOIN document_versions v ON v.id = d.current_version_id
            JOIN document_links l ON l.document_id = d.id
            """
        )
    )


def downgrade() -> None:
    _assert_lossless_downgrade()
    _restore_legacy_table()

    for target in reversed(
        (
            "organization",
            "opo",
            "technical_device",
            "building",
            "contract",
            "expertise",
            "task",
        )
    ):
        op.drop_index(f"uq_document_links_document_{target}", table_name="document_links")
    op.drop_index("ix_document_links_document_id", table_name="document_links")
    op.drop_table("document_links")

    op.drop_constraint("fk_documents_current_version", "documents", type_="foreignkey")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_table("documents")
