"""expertises domain

Revision ID: 0017_expertises
Revises: 0016_documents
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017_expertises"
down_revision: str | Sequence[str] | None = "0016_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPERTISE_STATUS_VALUES = (
    "preparation",
    "document_collection",
    "inspection",
    "conclusion_preparation",
    "internal_approval",
    "ready_for_registration",
    "rtn_review",
    "rtn_rework",
    "registered",
    "received_by_customer",
    "completed",
)


def upgrade() -> None:
    bind = op.get_bind()
    expertise_status = postgresql.ENUM(
        *EXPERTISE_STATUS_VALUES,
        name="expertise_status",
        create_type=False,
    )
    expertise_status.create(bind, checkfirst=True)

    op.create_table(
        "expertises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "expertise_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expertise_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            expertise_status,
            nullable=False,
            server_default=sa.text("'preparation'::expertise_status"),
        ),
        sa.Column("internal_number", sa.String(120)),
        sa.Column(
            "responsible_expert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("comment", sa.Text()),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("ix_expertises_contract_id", "expertises", ["contract_id"])
    op.create_index("ix_expertises_expertise_type_id", "expertises", ["expertise_type_id"])
    op.create_index("ix_expertises_status", "expertises", ["status"])
    op.create_index(
        "ix_expertises_responsible_expert_id", "expertises", ["responsible_expert_id"]
    )
    op.create_index("ix_expertises_deleted_at", "expertises", ["deleted_at"])

    op.create_table(
        "expertise_subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "expertise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expertises.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "technical_device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technical_devices.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "building_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("buildings.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "(technical_device_id IS NOT NULL AND building_id IS NULL) OR "
            "(technical_device_id IS NULL AND building_id IS NOT NULL)",
            name="ck_expertise_subjects_single_subject",
        ),
    )

    op.create_table(
        "expertise_contract_items",
        sa.Column(
            "expertise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expertises.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "contract_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract_items.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    op.create_table(
        "expertise_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "expertise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expertises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", expertise_status, nullable=True),
        sa.Column("to_status", expertise_status, nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "changed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text()),
    )
    op.create_index(
        "ix_expertise_status_history_expertise_id",
        "expertise_status_history",
        ["expertise_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_expertise_status_history_expertise_id", table_name="expertise_status_history"
    )
    op.drop_table("expertise_status_history")
    op.drop_table("expertise_contract_items")
    op.drop_table("expertise_subjects")
    op.drop_index("ix_expertises_deleted_at", table_name="expertises")
    op.drop_index("ix_expertises_responsible_expert_id", table_name="expertises")
    op.drop_index("ix_expertises_status", table_name="expertises")
    op.drop_index("ix_expertises_expertise_type_id", table_name="expertises")
    op.drop_index("ix_expertises_contract_id", table_name="expertises")
    op.drop_table("expertises")
    bind = op.get_bind()
    postgresql.ENUM(name="expertise_status", create_type=False).drop(bind, checkfirst=True)
