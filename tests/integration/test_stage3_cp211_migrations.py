import os
import uuid as _uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command

pytestmark = pytest.mark.integration

STAGE3_NS = _uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _uuid5(code: str) -> str:
    return str(_uuid.uuid5(STAGE3_NS, code))


def _migrate_to(revision: str) -> create_engine:
    url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    previous_db_url = os.environ.get("DATABASE_URL")
    previous_app_env = os.environ.get("APP_ENV")
    os.environ["DATABASE_URL"] = url
    os.environ["APP_ENV"] = "test"
    try:
        command.downgrade(cfg, "base")
        command.upgrade(cfg, revision)
    finally:
        if previous_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db_url
        if previous_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = previous_app_env
    return create_engine(url)


def _upgrade_to(revision: str) -> create_engine:
    url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    previous_db_url = os.environ.get("DATABASE_URL")
    previous_app_env = os.environ.get("APP_ENV")
    os.environ["DATABASE_URL"] = url
    os.environ["APP_ENV"] = "test"
    try:
        command.upgrade(cfg, revision)
    finally:
        if previous_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db_url
        if previous_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = previous_app_env
    return create_engine(url)


# ---------------------------------------------------------------------------
# Test 1: 0008 with existing OPO-hazard relation survives upgrade to head
# ---------------------------------------------------------------------------
def test_0008_with_opo_hazard_relation_survives_upgrade_to_head() -> None:
    engine = _migrate_to("0008_stage3")

    # Seed: organizations
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text(
                "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
                "VALUES (gen_random_uuid(), 'Test Org', 'TO', 'legal_entity')"
            ))
        rows = conn.execute(text("SELECT id FROM organizations")).fetchall()
        org_id = rows[0][0]

        # Seed: OPO
        opo_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO opo (id, name, registration_number, hazard_class, address, "
            "registration_date, owner_organization_id, operating_organization_id) "
            "VALUES (:id, 'Test OPO', 'REG-001', 'hazard_class_2', 'Addr', "
            "'2024-01-15', :org, :org)"
        ), {"id": opo_id, "org": org_id})

        # Seed: hazard_sign (not seeded data)
        hs_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO hazard_signs (id, code, name) VALUES (:id, 'test-hs', 'Test Sign')"
        ), {"id": hs_id})

        # Seed: junction
        conn.execute(text(
            "INSERT INTO opo_hazard_signs (opo_id, hazard_sign_id) VALUES (:opo, :hs)"
        ), {"opo": opo_id, "hs": hs_id})
        conn.commit()

    engine.dispose()

    # Now upgrade to head
    engine2 = _upgrade_to("head")

    # Verify junction still exists
    with engine2.connect() as conn:
        row = conn.execute(text(
            "SELECT opo_id, hazard_sign_id FROM opo_hazard_signs "
            "WHERE opo_id = :opo AND hazard_sign_id = :hs"
        ), {"opo": opo_id, "hs": hs_id}).fetchone()
        assert row is not None, "junction row must survive 0008 -> head upgrade"
    engine2.dispose()


# ---------------------------------------------------------------------------
# Test 2: 0008 with existing OPO-activity relation survives upgrade to head
# ---------------------------------------------------------------------------
def test_0008_with_opo_activity_relation_survives_upgrade_to_head() -> None:
    engine = _migrate_to("0008_stage3")

    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text(
                "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
                "VALUES (gen_random_uuid(), 'Test Org', 'TO', 'legal_entity')"
            ))
        rows = conn.execute(text("SELECT id FROM organizations")).fetchall()
        org_id = rows[0][0]

        opo_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO opo (id, name, registration_number, hazard_class, address, "
            "registration_date, owner_organization_id, operating_organization_id) "
            "VALUES (:id, 'Test OPO', 'REG-002', 'hazard_class_2', 'Addr', "
            "'2024-01-15', :org, :org)"
        ), {"id": opo_id, "org": org_id})

        at_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO activity_types (id, code, name) VALUES (:id, 'test-at', 'Test AT')"
        ), {"id": at_id})

        conn.execute(text(
            "INSERT INTO opo_activity_types (opo_id, activity_type_id) VALUES (:opo, :at)"
        ), {"opo": opo_id, "at": at_id})
        conn.commit()

    engine.dispose()

    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        row = conn.execute(text(
            "SELECT opo_id, activity_type_id FROM opo_activity_types "
            "WHERE opo_id = :opo AND activity_type_id = :at"
        ), {"opo": opo_id, "at": at_id}).fetchone()
        assert row is not None, "junction row must survive 0008 -> head upgrade"
    engine2.dispose()


# ---------------------------------------------------------------------------
# Test 3: 0010 backfills org_id correctly when owner == operator
# ---------------------------------------------------------------------------
def test_0010_backfills_when_owner_equals_operator() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text(
                "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
                "VALUES (gen_random_uuid(), 'Same Org', 'SO', 'legal_entity')"
            ))
        rows = conn.execute(text("SELECT id FROM organizations")).fetchall()
        org_id = rows[0][0]

        opo_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO opo (id, name, registration_number, hazard_class, address, "
            "registration_date, owner_organization_id, operating_organization_id) "
            "VALUES (:id, 'SameOwnerOpO', 'BK-001', 'hazard_class_2', 'Addr', "
            "'2024-01-15', :org, :org)"
        ), {"id": opo_id, "org": org_id})

        td_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO technical_devices (id, name, device_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Dev', 'other', :opo, now(), now())"
        ), {"id": td_id, "opo": opo_id})
        conn.commit()

    engine.dispose()

    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        result = conn.execute(text(
            "SELECT organization_id FROM technical_devices WHERE id = :id"
        ), {"id": td_id}).scalar()
        assert result == org_id, f"expected {org_id}, got {result}"
    engine2.dispose()


# ---------------------------------------------------------------------------
# Test 4: 0010 fails safely when owner != operator (TD)
# ---------------------------------------------------------------------------
def test_0010_fails_safely_on_owner_not_equal_operator_td() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text(
                "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
                "VALUES (gen_random_uuid(), 'Owner Org', 'OO', 'legal_entity')"
            ))
            conn.execute(text(
                "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
                "VALUES (gen_random_uuid(), 'Operator Org', 'OP', 'legal_entity')"
            ))
        rows = conn.execute(text("SELECT id FROM organizations ORDER BY short_name")).fetchall()
        op_org = rows[0][0]
        owner_org = rows[1][0]

        opo_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO opo (id, name, registration_number, hazard_class, address, "
            "registration_date, owner_organization_id, operating_organization_id) "
            "VALUES (:id, 'Ambiguous OPO', 'AMB-001', 'hazard_class_2', 'Addr', "
            "'2024-01-15', :owner, :op)"
        ), {"id": opo_id, "owner": owner_org, "op": op_org})

        td_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO technical_devices (id, name, device_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Ambiguous TD', 'other', :opo, now(), now())"
        ), {"id": td_id, "opo": opo_id})
        conn.commit()

    engine.dispose()

    with pytest.raises(Exception, match="owner.*operator"):
        _upgrade_to("head")


# ---------------------------------------------------------------------------
# Test 5: 0010 fails safely when owner != operator (Building)
# ---------------------------------------------------------------------------
def test_0010_fails_safely_on_owner_not_equal_operator_building() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text(
                "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
                "VALUES (gen_random_uuid(), 'Owner Org B', 'OOB', 'legal_entity')"
            ))
            conn.execute(text(
                "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
                "VALUES (gen_random_uuid(), 'Operator Org B', 'OPB', 'legal_entity')"
            ))
        rows = conn.execute(text("SELECT id FROM organizations ORDER BY short_name")).fetchall()
        op_org = rows[1][0]
        owner_org = rows[0][0]

        opo_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO opo (id, name, registration_number, hazard_class, address, "
            "registration_date, owner_organization_id, operating_organization_id) "
            "VALUES (:id, 'Ambiguous OPO B', 'AMB-002', 'hazard_class_2', 'Addr', "
            "'2024-01-15', :owner, :op)"
        ), {"id": opo_id, "owner": owner_org, "op": op_org})

        building_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO buildings (id, name, building_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Ambiguous Bld', 'other', :opo, now(), now())"
        ), {"id": building_id, "opo": opo_id})
        conn.commit()

    engine.dispose()

    with pytest.raises(Exception, match="owner.*operator"):
        _upgrade_to("head")


# ---------------------------------------------------------------------------
# Test 6: Standalone TD/Building fail-fast before 0010
# ---------------------------------------------------------------------------
def test_0010_fails_on_standalone_td() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn:
        td_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO technical_devices (id, name, device_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Standalone', 'other', NULL, now(), now())"
        ), {"id": td_id})
        conn.commit()

    engine.dispose()

    with pytest.raises(Exception, match="standalone"):
        _upgrade_to("head")


def test_0010_fails_on_standalone_building() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn:
        building_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO buildings (id, name, building_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Standalone Bld', 'other', NULL, now(), now())"
        ), {"id": building_id})
        conn.commit()

    engine.dispose()

    with pytest.raises(Exception, match="standalone"):
        _upgrade_to("head")


# ---------------------------------------------------------------------------
# Test 7: Fresh database base -> head succeeds
# ---------------------------------------------------------------------------
def test_fresh_database_base_to_head_succeeds() -> None:
    engine = _migrate_to("head")

    with engine.connect() as conn:
        names = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )).fetchall()
        names_set = {n[0] for n in names}
        expected = {"organizations", "opo", "technical_devices", "buildings", "hazard_signs",
                    "activity_types", "opo_hazard_signs", "opo_activity_types",
                    "alembic_version"}
        assert expected <= names_set, f"missing tables: {expected - names_set}"

        count = conn.execute(text("SELECT count(*) FROM alembic_version")).scalar()
        assert count == 1

    engine.dispose()


# ---------------------------------------------------------------------------
# Test 8: Safe downgrade/upgrade 0010 -> 0009 -> 0010
# ---------------------------------------------------------------------------
def test_downgrade_0010_to_0009_and_back() -> None:
    engine = _migrate_to("head")

    # Seed data suitable for downgrade (owner == operator so 0010 works)
    org_id = _uuid.uuid4()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
            "VALUES (:id, 'Stable Org', 'STB', 'legal_entity')"
        ), {"id": org_id})

        opo_id = _uuid.uuid4()
        conn.execute(text(
            "INSERT INTO opo (id, name, registration_number, hazard_class, address, "
            "registration_date, owner_organization_id, operating_organization_id, comment) "
            "VALUES (:id, 'Stable OPO', 'STB-001', 'hazard_class_1', 'Addr', "
            "'2024-01-15', :org, :org, 'test comment')"
        ), {"id": opo_id, "org": org_id})
        conn.commit()

    engine.dispose()

    # Downgrade to 0009, then back to head
    engine2 = _migrate_to("0009_stage3")

    # Verify org columns are gone
    with engine2.connect() as conn:
        cols = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'technical_devices' AND "
            "column_name = 'organization_id'"
        )).fetchall()
        assert len(cols) == 0, "organization_id should be gone at 0009"

    engine2.dispose()

    # Upgrade back
    engine3 = _upgrade_to("head")

    with engine3.connect() as conn:
        cols2 = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'technical_devices' AND "
            "column_name = 'organization_id'"
        )).fetchall()
        assert len(cols2) == 1, "organization_id should be back at head"

    engine3.dispose()

