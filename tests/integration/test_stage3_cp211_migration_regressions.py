import os
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from alembic import command

pytestmark = pytest.mark.integration

STAGE3_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
CURRENT_HEAD = "0011_stage4_contracts_core"


def _config() -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["TEST_DATABASE_URL"])
    return cfg


def _run_alembic(action: str, revision: str) -> None:
    url = os.environ["TEST_DATABASE_URL"]
    previous_db_url = os.environ.get("DATABASE_URL")
    previous_app_env = os.environ.get("APP_ENV")
    os.environ["DATABASE_URL"] = url
    os.environ["APP_ENV"] = "test"
    try:
        cfg = _config()
        if action == "upgrade":
            command.upgrade(cfg, revision)
        elif action == "downgrade":
            command.downgrade(cfg, revision)
        else:
            raise ValueError(f"Unsupported Alembic action: {action}")
    finally:
        if previous_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db_url
        if previous_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = previous_app_env


def _reset_to(revision: str) -> None:
    _run_alembic("downgrade", "base")
    _run_alembic("upgrade", revision)


def _engine() -> Engine:
    return create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)


def _insert_organization(conn, *, org_id: uuid.UUID, name: str) -> None:
    conn.execute(
        text(
            "INSERT INTO organizations "
            "(id, legal_name, short_name, organization_type) "
            "VALUES (:id, :name, :short_name, 'legal_entity')"
        ),
        {"id": org_id, "name": name, "short_name": name[:20]},
    )


def _insert_opo(
    conn,
    *,
    opo_id: uuid.UUID,
    owner_id: uuid.UUID,
    operator_id: uuid.UUID,
    registration_number: str,
) -> None:
    conn.execute(
        text(
            "INSERT INTO opo "
            "(id, name, registration_number, hazard_class, address, registration_date, "
            "owner_organization_id, operating_organization_id) "
            "VALUES (:id, :name, :registration_number, 'hazard_class_2', 'Addr', "
            "'2024-01-15', :owner_id, :operator_id)"
        ),
        {
            "id": opo_id,
            "name": f"OPO {registration_number}",
            "registration_number": registration_number,
            "owner_id": owner_id,
            "operator_id": operator_id,
        },
    )


def _column_exists(conn, table: str, column: str) -> bool:
    count = conn.execute(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table "
            "AND column_name = :column"
        ),
        {"table": table, "column": column},
    ).scalar_one()
    return bool(count)


def _update_rule(conn, constraint_name: str) -> str:
    return conn.execute(
        text(
            "SELECT update_rule FROM information_schema.referential_constraints "
            "WHERE constraint_schema = 'public' AND constraint_name = :constraint_name"
        ),
        {"constraint_name": constraint_name},
    ).scalar_one()


@pytest.mark.parametrize(
    ("reference_table", "junction_table", "fk_column", "code"),
    [
        ("hazard_signs", "opo_hazard_signs", "hazard_sign_id", "flammable"),
        ("activity_types", "opo_activity_types", "activity_type_id", "production"),
    ],
)
def test_0008_seeded_junction_follows_deterministic_pk(
    reference_table: str,
    junction_table: str,
    fk_column: str,
    code: str,
) -> None:
    _reset_to("0008_stage3")
    expected_id = uuid.uuid5(STAGE3_NS, code)
    org_id = uuid.uuid4()
    opo_id = uuid.uuid4()

    engine = _engine()
    with engine.begin() as conn:
        _insert_organization(conn, org_id=org_id, name=f"Seeded {code}")
        _insert_opo(
            conn,
            opo_id=opo_id,
            owner_id=org_id,
            operator_id=org_id,
            registration_number=f"SEED-{code}",
        )
        old_id = conn.execute(
            text(f"SELECT id FROM {reference_table} WHERE code = :code"),
            {"code": code},
        ).scalar_one()
        assert old_id != expected_id, "0008 fixture must exercise an actual PK change"
        conn.execute(
            text(
                f"INSERT INTO {junction_table} (opo_id, {fk_column}) "
                f"VALUES (:opo_id, :reference_id)"
            ),
            {"opo_id": opo_id, "reference_id": old_id},
        )
    engine.dispose()

    _run_alembic("upgrade", "head")

    engine = _engine()
    with engine.connect() as conn:
        actual_id = conn.execute(
            text(f"SELECT id FROM {reference_table} WHERE code = :code"),
            {"code": code},
        ).scalar_one()
        assert actual_id == expected_id
        junction_id = conn.execute(
            text(
                f"SELECT {fk_column} FROM {junction_table} "
                "WHERE opo_id = :opo_id"
            ),
            {"opo_id": opo_id},
        ).scalar_one()
        assert junction_id == expected_id
    engine.dispose()


@pytest.mark.parametrize(
    ("table", "type_column"),
    [
        ("technical_devices", "device_type"),
        ("buildings", "building_type"),
    ],
)
def test_0010_ambiguous_backfill_leaves_null(
    table: str,
    type_column: str,
) -> None:
    _reset_to("0009_stage3")
    owner_id = uuid.uuid4()
    operator_id = uuid.uuid4()
    opo_id = uuid.uuid4()
    row_id = uuid.uuid4()

    engine = _engine()
    with engine.begin() as conn:
        _insert_organization(conn, org_id=owner_id, name=f"Owner {table}")
        _insert_organization(conn, org_id=operator_id, name=f"Operator {table}")
        _insert_opo(
            conn,
            opo_id=opo_id,
            owner_id=owner_id,
            operator_id=operator_id,
            registration_number=f"AMB-{table}",
        )
        conn.execute(
            text(
                f"INSERT INTO {table} "
                f"(id, name, {type_column}, opo_id, created_at, updated_at) "
                "VALUES (:id, :name, 'other', :opo_id, now(), now())"
            ),
            {"id": row_id, "name": f"Ambiguous {table}", "opo_id": opo_id},
        )
    engine.dispose()

    # Migration should succeed, not fail
    _run_alembic("upgrade", "head")

    # After migration, organization_id should be NULL (ambiguous ownership)
    engine = _engine()
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == CURRENT_HEAD
        assert _column_exists(conn, "technical_devices", "organization_id")
        assert _column_exists(conn, "buildings", "organization_id")
        assert _column_exists(conn, "opo", "comment")
        org_id = conn.execute(
            text(f"SELECT organization_id FROM {table} WHERE id = :id"),
            {"id": row_id},
        ).scalar_one()
        assert org_id is None, f"organization_id must be NULL for ambiguous ownership, got {org_id}"
    engine.dispose()


@pytest.mark.parametrize(
    ("table", "type_column"),
    [
        ("technical_devices", "device_type"),
        ("buildings", "building_type"),
    ],
)
def test_0010_standalone_backfill_leaves_null(
    table: str,
    type_column: str,
) -> None:
    _reset_to("0009_stage3")
    row_id = uuid.uuid4()

    engine = _engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {table} "
                f"(id, name, {type_column}, opo_id, created_at, updated_at) "
                "VALUES (:id, :name, 'other', NULL, now(), now())"
            ),
            {"id": row_id, "name": f"Standalone {table}"},
        )
    engine.dispose()

    # Migration should succeed, not fail
    _run_alembic("upgrade", "head")

    # After migration, organization_id should be NULL (no OPO to backfill from)
    engine = _engine()
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == CURRENT_HEAD
        assert _column_exists(conn, "technical_devices", "organization_id")
        assert _column_exists(conn, "buildings", "organization_id")
        assert _column_exists(conn, "opo", "comment")
        org_id = conn.execute(
            text(f"SELECT organization_id FROM {table} WHERE id = :id"),
            {"id": row_id},
        ).scalar_one()
        assert org_id is None, f"organization_id must be NULL for standalone record, got {org_id}"
    engine.dispose()


def test_real_downgrade_0010_to_revised_0009_preserves_cascade_state() -> None:
    _reset_to("head")

    _run_alembic("downgrade", "0009_stage3")

    engine = _engine()
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == "0009_stage3"
        assert not _column_exists(conn, "technical_devices", "organization_id")
        assert not _column_exists(conn, "buildings", "organization_id")
        assert not _column_exists(conn, "opo", "comment")
        assert _update_rule(conn, "opo_hazard_signs_hazard_sign_id_fkey") == "CASCADE"
        assert _update_rule(conn, "opo_activity_types_activity_type_id_fkey") == "CASCADE"
    engine.dispose()

    _run_alembic("upgrade", "head")

    engine = _engine()
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == CURRENT_HEAD
        assert _column_exists(conn, "technical_devices", "organization_id")
        assert _column_exists(conn, "buildings", "organization_id")
        assert _column_exists(conn, "opo", "comment")
    engine.dispose()
