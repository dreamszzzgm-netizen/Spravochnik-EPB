"""parallel organizations: IP profile fields

Revision ID: 0014_parallel_org_ip_profile
Revises: 0013_stage5_tasks_core
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_parallel_org_ip_profile"
down_revision: str | Sequence[str] | None = "0013_stage5_tasks_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("residence_address", sa.String(500)))
    op.add_column("organizations", sa.Column("passport_series", sa.String(16)))
    op.add_column("organizations", sa.Column("passport_number", sa.String(32)))
    op.add_column("organizations", sa.Column("passport_issued_by", sa.String(500)))
    op.add_column("organizations", sa.Column("passport_issue_date", sa.Date()))
    op.add_column("organizations", sa.Column("passport_department_code", sa.String(32)))
    op.add_column("organizations", sa.Column("bank_name", sa.String(255)))
    op.add_column("organizations", sa.Column("bank_bik", sa.String(20)))
    op.add_column("organizations", sa.Column("bank_account", sa.String(64)))
    op.add_column("organizations", sa.Column("correspondent_account", sa.String(64)))


def downgrade() -> None:
    op.drop_column("organizations", "correspondent_account")
    op.drop_column("organizations", "bank_account")
    op.drop_column("organizations", "bank_bik")
    op.drop_column("organizations", "bank_name")
    op.drop_column("organizations", "passport_department_code")
    op.drop_column("organizations", "passport_issue_date")
    op.drop_column("organizations", "passport_issued_by")
    op.drop_column("organizations", "passport_number")
    op.drop_column("organizations", "passport_series")
    op.drop_column("organizations", "residence_address")
