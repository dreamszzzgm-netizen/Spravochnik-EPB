"""stage 2 organization fields: add legal_address, actual_address, director_name, phone, email, comment

Revision ID: 0006_stage2_organization_fields
Revises: 0005_stage2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_stage2_organization_fields"
down_revision: str | Sequence[str] | None = "0005_stage2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("legal_address", sa.String(500), nullable=True))
    op.add_column("organizations", sa.Column("actual_address", sa.String(500), nullable=True))
    op.add_column("organizations", sa.Column("director_name", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("phone", sa.String(64), nullable=True))
    op.add_column("organizations", sa.Column("email", sa.String(320), nullable=True))
    op.add_column("organizations", sa.Column("comment", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "comment")
    op.drop_column("organizations", "email")
    op.drop_column("organizations", "phone")
    op.drop_column("organizations", "director_name")
    op.drop_column("organizations", "actual_address")
    op.drop_column("organizations", "legal_address")
