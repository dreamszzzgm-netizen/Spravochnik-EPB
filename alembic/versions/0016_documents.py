"""organization documents and completeness requirements

Revision ID: 0016_documents
Revises: 0015_org_legal_form_fields
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016_documents"
down_revision: str | Sequence[str] | None = "0015_org_legal_form_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_type", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("applicability", sa.String(32), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("expiry_required", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "document_type", "applicability", name="uq_document_requirement_type_scope"
        ),
        sa.CheckConstraint(
            "applicability IN ('all', 'has_opo')",
            name="ck_document_requirements_applicability",
        ),
    )
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


def downgrade() -> None:
    op.drop_index("ix_organization_documents_deleted_at", table_name="organization_documents")
    op.drop_index("ix_organization_documents_document_type", table_name="organization_documents")
    op.drop_index(
        "ix_organization_documents_organization_id", table_name="organization_documents"
    )
    op.drop_table("organization_documents")
    op.drop_table("document_requirements")
