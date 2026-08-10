"""stage 3 domain foundation: OPO, technical devices, buildings, custom fields

Revision ID: 0008_stage3
Revises: 0007_stage2_contact_soft_delete
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_stage3"
down_revision: str | Sequence[str] | None = "0007_stage2_contact_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

hazard_class_enum = postgresql.ENUM(
    "hazard_class_1",
    "hazard_class_2",
    "hazard_class_3",
    "hazard_class_4",
    name="hazard_class",
    create_type=False,
)
technical_device_type_enum = postgresql.ENUM(
    "pressure_vessel",
    "pipeline",
    "lifting_mechanism",
    "other",
    name="technical_device_type",
    create_type=False,
)
building_type_enum = postgresql.ENUM(
    "industrial",
    "warehouse",
    "administrative",
    "other",
    name="building_type",
    create_type=False,
)
custom_field_type_enum = postgresql.ENUM(
    "text",
    "number",
    "date",
    "boolean",
    name="custom_field_type",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "hazard_class_1",
        "hazard_class_2",
        "hazard_class_3",
        "hazard_class_4",
        name="hazard_class",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "pressure_vessel",
        "pipeline",
        "lifting_mechanism",
        "other",
        name="technical_device_type",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "industrial",
        "warehouse",
        "administrative",
        "other",
        name="building_type",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "text",
        "number",
        "date",
        "boolean",
        name="custom_field_type",
    ).create(bind, checkfirst=True)

    # OPO (hazardous production facilities)
    op.create_table(
        "opo",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("registration_number", sa.String(100), nullable=False, unique=True),
        sa.Column("hazard_class", hazard_class_enum, nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column(
            "owner_organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "operating_organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_opo_registration_number", "opo", ["registration_number"])
    op.create_index("ix_opo_owner_organization_id", "opo", ["owner_organization_id"])
    op.create_index("ix_opo_operating_organization_id", "opo", ["operating_organization_id"])

    # Hazard signs (reference data)
    op.create_table(
        "hazard_signs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
    )

    # OPO ↔ hazard signs N:M
    op.create_table(
        "opo_hazard_signs",
        sa.Column(
            "opo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opo.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "hazard_sign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hazard_signs.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    # Activity types (reference data)
    op.create_table(
        "activity_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
    )

    # OPO ↔ activity types N:M
    op.create_table(
        "opo_activity_types",
        sa.Column(
            "opo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opo.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "activity_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_types.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    # Technical devices
    op.create_table(
        "technical_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("device_type", technical_device_type_enum, nullable=False),
        sa.Column("serial_number", sa.String(100)),
        sa.Column(
            "opo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opo.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_technical_devices_opo_id", "technical_devices", ["opo_id"])

    # Buildings
    op.create_table(
        "buildings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("building_type", building_type_enum, nullable=False),
        sa.Column(
            "opo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opo.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_buildings_opo_id", "buildings", ["opo_id"])

    # Custom field definitions
    op.create_table(
        "custom_field_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("field_type", custom_field_type_enum, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_custom_field_def_code_entity",
        "custom_field_definitions",
        ["code", "entity_type"],
    )

    # Custom field values
    op.create_table(
        "custom_field_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "field_definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("custom_field_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value_text", sa.Text),
        sa.Column("value_number", sa.Numeric),
        sa.Column("value_date", sa.Date),
        sa.Column("value_boolean", sa.Boolean),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_custom_field_value_per_entity",
        "custom_field_values",
        ["field_definition_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_custom_field_values_entity",
        "custom_field_values",
        ["entity_type", "entity_id"],
    )

    # Seed reference data: hazard signs
    hazard_signs_table = sa.table(
        "hazard_signs",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )
    op.bulk_insert(
        hazard_signs_table,
        [
            {"id": uuid.uuid4(), "code": "flammable", "name": "Воспламеняющиеся вещества"},
            {"id": uuid.uuid4(), "code": "oxidizing", "name": "Окисляющие вещества"},
            {"id": uuid.uuid4(), "code": "combustible", "name": "Горючие вещества"},
            {"id": uuid.uuid4(), "code": "explosive", "name": "Взрывчатые вещества"},
            {"id": uuid.uuid4(), "code": "toxic", "name": "Токсичные вещества"},
            {"id": uuid.uuid4(), "code": "highly_toxic", "name": "Высокотоксичные вещества"},
            {
                "id": uuid.uuid4(),
                "code": "environmental",
                "name": "Вещества, опасные для окружающей среды",
            },
        ],
    )

    # Seed reference data: activity types
    activity_types_table = sa.table(
        "activity_types",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )
    op.bulk_insert(
        activity_types_table,
        [
            {"id": uuid.uuid4(), "code": "production", "name": "Производство"},
            {"id": uuid.uuid4(), "code": "storage", "name": "Хранение"},
            {"id": uuid.uuid4(), "code": "processing", "name": "Переработка"},
            {"id": uuid.uuid4(), "code": "transportation", "name": "Транспортирование"},
            {"id": uuid.uuid4(), "code": "destruction", "name": "Уничтожение"},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_custom_field_values_entity", table_name="custom_field_values")
    op.drop_constraint("uq_custom_field_value_per_entity", "custom_field_values", type_="unique")
    op.drop_constraint(
        "uq_custom_field_def_code_entity", "custom_field_definitions", type_="unique"
    )
    op.drop_table("custom_field_values")
    op.drop_table("custom_field_definitions")

    op.drop_index("ix_buildings_opo_id", table_name="buildings")
    op.drop_table("buildings")

    op.drop_index("ix_technical_devices_opo_id", table_name="technical_devices")
    op.drop_table("technical_devices")

    op.drop_table("opo_activity_types")
    op.drop_table("activity_types")

    op.drop_table("opo_hazard_signs")
    op.drop_table("hazard_signs")

    op.drop_index("ix_opo_operating_organization_id", table_name="opo")
    op.drop_index("ix_opo_owner_organization_id", table_name="opo")
    op.drop_index("ix_opo_registration_number", table_name="opo")
    op.drop_table("opo")

    bind = op.get_bind()
    postgresql.ENUM(name="custom_field_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="building_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="technical_device_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="hazard_class").drop(bind, checkfirst=True)
