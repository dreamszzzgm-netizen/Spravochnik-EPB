"""stage 4 cp4.2: contract lifecycle and addenda

Revision ID: 0012_stage4_contract_lifecycle
Revises: 0011_stage4_contracts_core
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_stage4_contract_lifecycle"
down_revision: str | Sequence[str] | None = "0011_stage4_contracts_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADDENDUM_STATUS_VALUES = (
    "draft",
    "approval",
    "signed",
    "cancelled",
)


def upgrade() -> None:
    bind = op.get_bind()
    addendum_status = postgresql.ENUM(
        *ADDENDUM_STATUS_VALUES,
        name="contract_addendum_status",
        create_type=False,
    )
    addendum_status.create(bind, checkfirst=True)

    op.add_column(
        "contracts",
        sa.Column("original_end_date", sa.Date(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE contracts
            SET original_end_date = end_date
            WHERE original_end_date IS NULL
              AND status IN (
                  'signed'::contract_status,
                  'in_progress'::contract_status,
                  'suspended'::contract_status,
                  'completed'::contract_status,
                  'terminated'::contract_status,
                  'archived'::contract_status
              )
            """
        )
    )

    op.create_table(
        "contract_suspensions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            name="fk_contract_suspensions_contract_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_contract_suspensions_created_by",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_contract_suspensions_contract_id",
        "contract_suspensions",
        ["contract_id"],
    )
    op.create_index(
        "uq_contract_suspensions_one_open",
        "contract_suspensions",
        ["contract_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    op.create_table(
        "contract_addenda",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.String(length=120), nullable=False),
        sa.Column("addendum_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            addendum_status,
            nullable=False,
            server_default=sa.text("'draft'::contract_addendum_status"),
        ),
        sa.Column("amount_delta", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'RUB'"),
        ),
        sa.Column("new_end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            name="fk_contract_addenda_contract_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_contract_addenda_created_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name="fk_contract_addenda_updated_by",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_contract_addenda_contract_id",
        "contract_addenda",
        ["contract_id"],
    )
    op.create_index("ix_contract_addenda_status", "contract_addenda", ["status"])
    op.create_index(
        "ix_contract_addenda_deleted_at",
        "contract_addenda",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_contract_addenda_deleted_at", table_name="contract_addenda")
    op.drop_index("ix_contract_addenda_status", table_name="contract_addenda")
    op.drop_index("ix_contract_addenda_contract_id", table_name="contract_addenda")
    op.drop_table("contract_addenda")

    op.drop_index(
        "uq_contract_suspensions_one_open",
        table_name="contract_suspensions",
    )
    op.drop_index(
        "ix_contract_suspensions_contract_id",
        table_name="contract_suspensions",
    )
    op.drop_table("contract_suspensions")

    op.drop_column("contracts", "original_end_date")

    addendum_status = postgresql.ENUM(
        *ADDENDUM_STATUS_VALUES,
        name="contract_addendum_status",
        create_type=False,
    )
    addendum_status.drop(op.get_bind(), checkfirst=True)
