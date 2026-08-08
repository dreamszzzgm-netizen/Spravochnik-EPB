"""stage 2 R2 enums: drop organization_type 'other', add identifier_type 'external_id'

Revision ID: 0004_stage2_r2_enums
Revises: 0003_stage2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_r2_enums"
down_revision: str | Sequence[str] | None = "0003_stage2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if _type_has_value(bind, "organization_type", "other"):
        _rebuild_enum(
            bind,
            type_name="organization_type",
            labels=["legal_entity", "individual_entrepreneur", "branch"],
            columns=[("organizations", "organization_type")],
        )
    if not _type_has_value(bind, "identifier_type", "external_id"):
        bind.execute(sa.text("ALTER TYPE identifier_type ADD VALUE 'external_id'"))


def downgrade() -> None:
    bind = op.get_bind()
    if not _type_has_value(bind, "organization_type", "other"):
        _rebuild_enum(
            bind,
            type_name="organization_type",
            labels=["legal_entity", "individual_entrepreneur", "branch", "other"],
            columns=[("organizations", "organization_type")],
        )
    if _type_has_value(bind, "identifier_type", "external_id"):
        _rebuild_enum(
            bind,
            type_name="identifier_type",
            labels=["inn", "kpp", "ogrn", "ogrnip"],
            columns=[("organization_identifiers", "identifier_type")],
        )


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


def _rebuild_enum(bind, type_name: str, labels: list[str], columns: list[tuple[str, str]]) -> None:
    new_type = f"{type_name}_new"
    defaults: dict[tuple[str, str], str | None] = {}
    for table, column in columns:
        default = bind.execute(
            sa.text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).scalar()
        defaults[(table, column)] = default
        if default is not None:
            bind.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT"))
    bind.execute(sa.text(f"CREATE TYPE {new_type} AS ENUM ({', '.join(repr(x) for x in labels)})"))
    for table, column in columns:
        bind.execute(
            sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {column} "
                f"TYPE {new_type} USING {column}::text::{new_type}"
            )
        )
    bind.execute(sa.text(f"DROP TYPE {type_name}"))
    bind.execute(sa.text(f"ALTER TYPE {new_type} RENAME TO {type_name}"))
    for (table, column), default in defaults.items():
        if default is not None:
            bind.execute(
                sa.text(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default}")
            )
