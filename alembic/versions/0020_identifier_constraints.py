"""relax INN global uniqueness, add OGRN/OGRNIP partial unique indexes

Revision ID: 0020_identifier_constraints
Revises: 0019_import_sessions
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_identifier_constraints"
down_revision: str | Sequence[str] | None = "0019_import_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_org_identifier_value", "organization_identifiers", type_="unique")

    op.create_index(
        "uq_org_identifier_ogrn",
        "organization_identifiers",
        ["identifier_value"],
        unique=True,
        postgresql_where=sa.text("identifier_type = 'ogrn'"),
    )
    op.create_index(
        "uq_org_identifier_ogrnip",
        "organization_identifiers",
        ["identifier_value"],
        unique=True,
        postgresql_where=sa.text("identifier_type = 'ogrnip'"),
    )


def downgrade() -> None:
    op.drop_index("uq_org_identifier_ogrnip", table_name="organization_identifiers")
    op.drop_index("uq_org_identifier_ogrn", table_name="organization_identifiers")

    op.create_unique_constraint(
        "uq_org_identifier_value",
        "organization_identifiers",
        ["identifier_type", "identifier_value"],
    )
