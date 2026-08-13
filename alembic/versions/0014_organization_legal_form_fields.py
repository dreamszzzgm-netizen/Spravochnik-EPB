"""organization legal form fields

Revision ID: 0014_org_legal_form_fields
Revises: 0013_stage5_tasks_core
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_org_legal_form_fields"
down_revision: str | Sequence[str] | None = "0013_stage5_tasks_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("residence_address", sa.String(500)))
    op.add_column("organizations", sa.Column("passport_details", sa.Text()))


def downgrade() -> None:
    op.drop_column("organizations", "passport_details")
    op.drop_column("organizations", "residence_address")
