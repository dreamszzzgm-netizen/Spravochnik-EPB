"""stage 2 contact soft delete: add deleted_at to organization_contacts

Revision ID: 0007_stage2_contact_soft_delete
Revises: 0006_stage2_organization_fields
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_stage2_contact_soft_delete"
down_revision: str | Sequence[str] | None = "0006_stage2_organization_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organization_contacts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("organization_contacts", "deleted_at")
