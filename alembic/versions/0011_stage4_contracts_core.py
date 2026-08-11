"""stage 4 cp4.1: contracts core foundation

Revision ID: 0011_stage4_contracts_core
Revises: 0010_stage3
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_stage4_contracts_core"
down_revision: str | Sequence[str] | None = "0010_stage3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BUILDING_EXPERTISE_TYPE_ID = uuid.UUID("0312543b-b525-530e-ac8d-efa8e8b2391d")
TECHNICAL_DEVICE_EXPERTISE_TYPE_ID = uuid.UUID(
    "c79c5348-2ee9-53a6-9417-224e63de5a74"
)

CONTRACT_STATUS_VALUES = (
    "draft",
    "approval",
    "signed",
    "in_progress",
    "suspended",
    "completed",
    "terminated",
    "archived",
)


def upgrade() -> None:
    bind = op.get_bind()
    contract_status = postgresql.ENUM(
        *CONTRACT_STATUS_VALUES,
        name="contract_status",
        create_type=False,
    )
    contract_status.create(bind, checkfirst=True)

    expertise_types = op.create_table(
        "expertise_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.UniqueConstraint("code", name="uq_expertise_types_code"),
    )

    op.bulk_insert(
        expertise_types,
        [
            {
                "id": BUILDING_EXPERTISE_TYPE_ID,
                "code": "building_epb",
                "name": "ЭПБ здания/сооружения",
                "is_active": True,
            },
            {
                "id": TECHNICAL_DEVICE_EXPERTISE_TYPE_ID,
                "code": "technical_device_epb",
                "name": "ЭПБ технического устройства",
                "is_active": True,
            },
        ],
    )

    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("number", sa.String(length=120), nullable=False),
        sa.Column("contract_date", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'RUB'"),
        ),
        sa.Column(
            "status",
            contract_status,
            nullable=False,
            server_default=sa.text("'draft'::contract_status"),
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.CheckConstraint("amount >= 0", name="ck_contracts_amount_nonnegative"),
        sa.CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
            name="ck_contracts_dates",
        ),
        sa.ForeignKeyConstraint(
            ["customer_organization_id"],
            ["organizations.id"],
            name="fk_contracts_customer_organization_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_contact_id"],
            ["organization_contacts.id"],
            name="fk_contracts_customer_contact_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_contracts_created_by",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_contracts_customer_organization_id",
        "contracts",
        ["customer_organization_id"],
    )
    op.create_index("ix_contracts_customer_contact_id", "contracts", ["customer_contact_id"])
    op.create_index("ix_contracts_number", "contracts", ["number"])
    op.create_index("ix_contracts_status", "contracts", ["status"])
    op.create_index("ix_contracts_deleted_at", "contracts", ["deleted_at"])

    op.create_table(
        "contract_responsibles",
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_note", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            name="fk_contract_responsibles_contract_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_contract_responsibles_employee_id",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "contract_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("expertise_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'RUB'"),
        ),
        sa.Column("comment", sa.Text(), nullable=True),
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
        sa.CheckConstraint("price >= 0", name="ck_contract_items_price_nonnegative"),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            name="fk_contract_items_contract_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["expertise_type_id"],
            ["expertise_types.id"],
            name="fk_contract_items_expertise_type_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_contract_items_contract_id", "contract_items", ["contract_id"])
    op.create_index(
        "ix_contract_items_expertise_type_id",
        "contract_items",
        ["expertise_type_id"],
    )
    op.create_index("ix_contract_items_deleted_at", "contract_items", ["deleted_at"])

    op.create_table(
        "contract_item_technical_devices",
        sa.Column("contract_item_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("technical_device_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.ForeignKeyConstraint(
            ["contract_item_id"],
            ["contract_items.id"],
            name="fk_contract_item_technical_devices_item_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["technical_device_id"],
            ["technical_devices.id"],
            name="fk_contract_item_technical_devices_device_id",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "contract_item_buildings",
        sa.Column("contract_item_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("building_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.ForeignKeyConstraint(
            ["contract_item_id"],
            ["contract_items.id"],
            name="fk_contract_item_buildings_item_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["building_id"],
            ["buildings.id"],
            name="fk_contract_item_buildings_building_id",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("contract_item_buildings")
    op.drop_table("contract_item_technical_devices")

    op.drop_index("ix_contract_items_deleted_at", table_name="contract_items")
    op.drop_index("ix_contract_items_expertise_type_id", table_name="contract_items")
    op.drop_index("ix_contract_items_contract_id", table_name="contract_items")
    op.drop_table("contract_items")

    op.drop_table("contract_responsibles")

    op.drop_index("ix_contracts_deleted_at", table_name="contracts")
    op.drop_index("ix_contracts_status", table_name="contracts")
    op.drop_index("ix_contracts_number", table_name="contracts")
    op.drop_index("ix_contracts_customer_contact_id", table_name="contracts")
    op.drop_index("ix_contracts_customer_organization_id", table_name="contracts")
    op.drop_table("contracts")

    op.drop_table("expertise_types")

    contract_status = postgresql.ENUM(
        *CONTRACT_STATUS_VALUES,
        name="contract_status",
        create_type=False,
    )
    contract_status.drop(op.get_bind(), checkfirst=True)
