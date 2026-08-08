"""stage 2 organizations

Revision ID: 0003_stage2
Revises: 0002_stage1
"""
from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_stage2"
down_revision: str | Sequence[str] | None = "0002_stage1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

organization_type = postgresql.ENUM(
    "legal_entity", "individual_entrepreneur", "branch", "other",
    name="organization_type", create_type=False,
)
contact_type = postgresql.ENUM(
    "director", "accountant", "other",
    name="contact_type", create_type=False,
)
identifier_type = postgresql.ENUM(
    "inn", "kpp", "ogrn", "ogrnip",
    name="identifier_type", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "legal_entity", "individual_entrepreneur", "branch", "other",
        name="organization_type",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "director", "accountant", "other",
        name="contact_type",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "inn", "kpp", "ogrn", "ogrnip",
        name="identifier_type",
    ).create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_type", organization_type, nullable=False, server_default="legal_entity"),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(120)),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_organizations_legal_name", "organizations", ["legal_name"])
    op.create_index("ix_organizations_parent_id", "organizations", ["parent_id"])

    op.create_table(
        "organization_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_type", contact_type, nullable=False, server_default="other"),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("position", sa.String(255)),
        sa.Column("phone", sa.String(64)),
        sa.Column("email", sa.String(320)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_organization_contacts_organization_id", "organization_contacts", ["organization_id"])
    op.create_index(
        "uq_organization_contacts_primary",
        "organization_contacts",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    op.create_table(
        "organization_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("identifier_type", identifier_type, nullable=False),
        sa.Column("identifier_value", sa.String(40), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_organization_identifiers_organization_id", "organization_identifiers", ["organization_id"])
    op.create_unique_constraint(
        "uq_org_identifier_type_per_org", "organization_identifiers",
        ["organization_id", "identifier_type"],
    )
    op.create_unique_constraint(
        "uq_org_identifier_value", "organization_identifiers",
        ["identifier_type", "identifier_value"],
    )
    op.create_index(
        "uq_organization_identifiers_primary",
        "organization_identifiers",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    permissions_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
    )
    op.bulk_insert(
        permissions_table,
        [
            {"id": uuid.uuid4(), "code": "organizations.update", "name": "organizations.update"},
            {"id": uuid.uuid4(), "code": "organizations.manage_contacts", "name": "organizations.manage_contacts"},
            {"id": uuid.uuid4(), "code": "organizations.manage_identifiers", "name": "organizations.manage_identifiers"},
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_organization_identifiers_primary", table_name="organization_identifiers")
    op.drop_index("uq_organization_contacts_primary", table_name="organization_contacts")
    op.drop_constraint("uq_org_identifier_value", "organization_identifiers", type_="unique")
    op.drop_constraint("uq_org_identifier_type_per_org", "organization_identifiers", type_="unique")
    op.drop_index("ix_organization_identifiers_organization_id", table_name="organization_identifiers")
    op.drop_index("ix_organization_contacts_organization_id", table_name="organization_contacts")
    op.drop_index("ix_organizations_parent_id", table_name="organizations")
    op.drop_index("ix_organizations_legal_name", table_name="organizations")
    op.drop_table("organization_identifiers")
    op.drop_table("organization_contacts")
    op.drop_table("organizations")

    bind = op.get_bind()
    postgresql.ENUM(name="identifier_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="contact_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="organization_type").drop(bind, checkfirst=True)