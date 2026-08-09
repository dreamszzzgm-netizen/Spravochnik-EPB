"""stage 2 contacts and org fields: add chief_engineer, pb_specialist to contact_type enum

Revision ID: 0005_stage2
Revises: 0004_r2_enums
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_stage2"
down_revision: str | Sequence[str] | None = "0004_r2_enums"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if not _type_has_value(bind, "contact_type", "chief_engineer"):
        bind.execute(sa.text("ALTER TYPE contact_type ADD VALUE 'chief_engineer'"))
    if not _type_has_value(bind, "contact_type", "pb_specialist"):
        bind.execute(sa.text("ALTER TYPE contact_type ADD VALUE 'pb_specialist'"))


def downgrade() -> None:
    # Undoing enum additions requires rebuilding the type,
    # but dropping values is destructive and not safe in downgrade.
    # The new values are harmless if left.
    pass


def _type_has_value(bind, type_name: str, value: str) -> bool:
    rows = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_enum je "
            "JOIN pg_type jt ON jt.oid = je.enumtypid "
            "WHERE jt.typname = :type_name AND je.enumlabel = :value"
        ),
        {"type_name": type_name, "value": value},
    ).fetchone()
    return rows is not None
