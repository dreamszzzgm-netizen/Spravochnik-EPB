"""add bank_details to organizations

Revision ID: 0018_cp_n1_bank_details
Revises: 0017_expertises
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_cp_n1_bank_details"
down_revision: str | Sequence[str] | None = "0017_expertises"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("bank_details", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "bank_details")
