"""stage 3 cp2.1: domain integrity — organization ownership, comment, FK cascade

Revision ID: 0010_stage3
Revises: 0009_stage3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0010_stage3"
down_revision: str | Sequence[str] | None = "0009_stage3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add nullable organization_id to technical_devices
    op.add_column("technical_devices", sa.Column("organization_id", UUID(), nullable=True))
    op.create_foreign_key(
        "fk_technical_devices_organization_id",
        "technical_devices",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_technical_devices_organization_id"),
        "technical_devices",
        ["organization_id"],
    )

    # 2. Add nullable organization_id to buildings
    op.add_column("buildings", sa.Column("organization_id", UUID(), nullable=True))
    op.create_foreign_key(
        "fk_buildings_organization_id",
        "buildings",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_buildings_organization_id"),
        "buildings",
        ["organization_id"],
    )

    # 3. Add comment to OPO
    op.add_column("opo", sa.Column("comment", sa.Text(), nullable=True))

    # 4. Backfill organization_id from OPO for linked devices/buildings
    for table in ["technical_devices", "buildings"]:
        orphan_rows = conn.execute(
            text(
                f"SELECT {table}.id FROM {table} "
                f"LEFT JOIN opo ON opo.id = {table}.opo_id "
                f"WHERE opo.id IS NULL AND {table}.opo_id IS NOT NULL"
            )
        ).fetchall()
        if orphan_rows:
            ids = [str(r[0]) for r in orphan_rows[:5]]
            raise ValueError(
                f"{table} rows reference non-existent OPOs: {ids}. "
                "Cannot backfill organization_id. Fix data first."
            )

        standalone_count = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE opo_id IS NULL")
        ).scalar()
        if standalone_count and standalone_count > 0:
            raise ValueError(
                f"{table} has {standalone_count} standalone rows (opo_id IS NULL). "
                "Cannot backfill organization_id automatically. "
                "Assign an organization to every standalone device/building "
                "before upgrading."
            )

        conn.execute(
            text(
                f"UPDATE {table} SET organization_id = opo.owner_organization_id "
                f"FROM opo WHERE opo.id = {table}.opo_id AND {table}.opo_id IS NOT NULL"
            )
        )

    # 5. Now set NOT NULL on organization_id
    op.alter_column("technical_devices", "organization_id", nullable=False)
    op.alter_column("buildings", "organization_id", nullable=False)

    # 6. Fix FK cascade for migration 0009: add ON UPDATE CASCADE
    conn.execute(
        text("""
        ALTER TABLE opo_hazard_signs
        DROP CONSTRAINT IF EXISTS opo_hazard_signs_hazard_sign_id_fkey
    """)
    )
    conn.execute(
        text("""
        ALTER TABLE opo_hazard_signs
        ADD CONSTRAINT opo_hazard_signs_hazard_sign_id_fkey
        FOREIGN KEY (hazard_sign_id) REFERENCES hazard_signs(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
    """)
    )
    conn.execute(
        text("""
        ALTER TABLE opo_activity_types
        DROP CONSTRAINT IF EXISTS opo_activity_types_activity_type_id_fkey
    """)
    )
    conn.execute(
        text("""
        ALTER TABLE opo_activity_types
        ADD CONSTRAINT opo_activity_types_activity_type_id_fkey
        FOREIGN KEY (activity_type_id) REFERENCES activity_types(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
    """)
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        text("""
        ALTER TABLE opo_hazard_signs
        DROP CONSTRAINT IF EXISTS opo_hazard_signs_hazard_sign_id_fkey
    """)
    )
    conn.execute(
        text("""
        ALTER TABLE opo_hazard_signs
        ADD CONSTRAINT opo_hazard_signs_hazard_sign_id_fkey
        FOREIGN KEY (hazard_sign_id) REFERENCES hazard_signs(id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
    """)
    )
    conn.execute(
        text("""
        ALTER TABLE opo_activity_types
        DROP CONSTRAINT IF EXISTS opo_activity_types_activity_type_id_fkey
    """)
    )
    conn.execute(
        text("""
        ALTER TABLE opo_activity_types
        ADD CONSTRAINT opo_activity_types_activity_type_id_fkey
        FOREIGN KEY (activity_type_id) REFERENCES activity_types(id)
        ON DELETE RESTRICT ON UPDATE RESTRICT
    """)
    )

    conn.execute(
        text("""ALTER TABLE buildings DROP CONSTRAINT IF EXISTS fk_buildings_organization_id""")
    )
    conn.execute(
        text(
            "ALTER TABLE technical_devices "
            "DROP CONSTRAINT IF EXISTS fk_technical_devices_organization_id"
        )
    )

    op.drop_index(op.f("ix_technical_devices_organization_id"), table_name="technical_devices")
    op.drop_column("technical_devices", "organization_id")

    op.drop_index(op.f("ix_buildings_organization_id"), table_name="buildings")
    op.drop_column("buildings", "organization_id")

    op.drop_column("opo", "comment")
