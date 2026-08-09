import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command

pytestmark = pytest.mark.integration


def test_stage2_migration_builds_organization_schema() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        engine = create_engine(url)
        try:
            names = set(inspect(engine).get_table_names())
            assert {
                "organizations",
                "organization_contacts",
                "organization_identifiers",
            } <= names

            with engine.connect() as connection:
                org_rows = connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'organizations'"
                    )
                ).scalars()
                assert {
                    "id",
                    "organization_type",
                    "legal_name",
                    "short_name",
                    "parent_id",
                    "deleted_at",
                    "created_at",
                    "updated_at",
                } <= set(org_rows)

                contact_rows = connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'organization_contacts'"
                    )
                ).scalars()
                assert {
                    "id",
                    "organization_id",
                    "contact_type",
                    "full_name",
                    "phone",
                    "email",
                    "is_primary",
                } <= set(contact_rows)

                identifier_rows = connection.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_name = 'organization_identifiers'"
                    )
                ).scalars()
                assert {
                    "id",
                    "organization_id",
                    "identifier_type",
                    "identifier_value",
                    "is_primary",
                } <= set(identifier_rows)

                fk_count = connection.scalar(
                    text(
                        "select count(*) from information_schema.table_constraints "
                        "where constraint_type = 'FOREIGN KEY' "
                        "and table_name in "
                        "('organizations', 'organization_contacts', 'organization_identifiers')"
                    )
                )
                assert fk_count >= 3

                rows = connection.execute(
                    text(
                        "select t.typname, e.enumlabel "
                        "from pg_type t join pg_enum e on e.enumtypid = t.oid "
                        "where t.typname in "
                        "('organization_type', 'contact_type', 'identifier_type') "
                        "order by t.typname, e.enumsortorder"
                    )
                ).all()
                type_map: dict[str, list[str]] = {}
                for type_name, label in rows:
                    type_map.setdefault(type_name, []).append(label)
                assert type_map["organization_type"] == [
                    "legal_entity",
                    "individual_entrepreneur",
                    "branch",
                ]
                assert type_map["contact_type"] == [
                    "director",
                    "accountant",
                    "other",
                    "chief_engineer",
                    "pb_specialist",
                ]
                assert type_map["identifier_type"] == [
                    "inn",
                    "kpp",
                    "ogrn",
                    "ogrnip",
                    "external_id",
                ]

                permission_count = connection.scalar(
                    text(
                        "select count(*) from permissions "
                        "where code in "
                        "('organizations.update', 'organizations.manage_contacts', "
                        "'organizations.manage_identifiers')"
                    )
                )
                assert permission_count == 3
        finally:
            engine.dispose()
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
