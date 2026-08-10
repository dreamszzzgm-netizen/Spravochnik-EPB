"""stage 3 cp2: deterministic UUIDs for seeded reference data

Revision ID: 0009_stage3
Revises: 0008_stage3
"""
import uuid
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "0009_stage3"
down_revision: str | Sequence[str] | None = "0008_stage3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGE3_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _uuid5(code: str) -> str:
    return str(uuid.uuid5(STAGE3_NS, code))


def _update_ids(conn, table: str, code_id_pairs: list[tuple[str, str]]) -> None:
    for code, new_id in code_id_pairs:
        old = conn.execute(
            text(f"SELECT id FROM {table} WHERE code = :code"),
            {"code": code},
        ).scalar_one_or_none()
        if old is not None and str(old) != new_id:
            conn.execute(
                text(f"UPDATE {table} SET id = :new_id WHERE code = :code"),
                {"new_id": new_id, "code": code},
            )


def upgrade() -> None:
    conn = op.get_bind()

    # Before changing PKs, make junction FKs CASCADE so existing N:M rows survive
    for table, fk_col, ref_table, fk_name in [
        ("opo_hazard_signs", "hazard_sign_id", "hazard_signs",
         "opo_hazard_signs_hazard_sign_id_fkey"),
        ("opo_activity_types", "activity_type_id", "activity_types",
         "opo_activity_types_activity_type_id_fkey"),
    ]:
        conn.execute(
            text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fk_name}")
        )
        conn.execute(
            text(
                f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} "
                f"FOREIGN KEY ({fk_col}) REFERENCES {ref_table}(id) "
                f"ON DELETE RESTRICT ON UPDATE CASCADE"
            )
        )

    hazard_pairs = [(code, _uuid5(code)) for code in [
        "flammable", "oxidizing", "combustible", "explosive",
        "toxic", "highly_toxic", "environmental",
    ]]
    activity_pairs = [(code, _uuid5(code)) for code in [
        "production", "storage", "processing", "transportation", "destruction",
    ]]
    _update_ids(conn, "hazard_signs", hazard_pairs)
    _update_ids(conn, "activity_types", activity_pairs)


def downgrade() -> None:
    pass

