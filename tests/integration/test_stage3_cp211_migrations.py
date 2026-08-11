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


def _alembic_cfg():
    url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _migrate_to(revision: str) -> create_engine:
    url = os.environ["TEST_DATABASE_URL"]
    cfg = _alembic_cfg()
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
    cfg = _alembic_cfg()
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


def _seed_org(conn, legal_name: str, short_name: str) -> str:
    org_id = str(_uuid.uuid4())
    conn.execute(text(
        "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
        "VALUES (:id, :legal_name, :short_name, 'legal_entity')"
    ), {"id": org_id, "legal_name": legal_name, "short_name": short_name})
    return org_id


def _seed_opo(conn, reg_num: str, owner_org: str, op_org: str, name: str = "") -> str:
    opo_id = str(_uuid.uuid4())
    conn.execute(text(
        "INSERT INTO opo (id, name, registration_number, hazard_class, address, "
        "registration_date, owner_organization_id, operating_organization_id) "
        "VALUES (:id, :name, :reg_num, 'hazard_class_2', 'Addr', "
        "'2024-01-15', :owner, :op)"
    ), {"id": opo_id, "name": name or f"OPO {reg_num}", "reg_num": reg_num,
        "owner": owner_org, "op": op_org})
    return opo_id


# ============================================================================
# Case A — OPO with seeded hazard_signs and activity_types survive 0008 → head
# ============================================================================
def test_0008_seeded_hazard_sign_junction_survives() -> None:
    engine = _migrate_to("0008_stage3")

    with engine.connect() as conn, conn.begin():
        org_id = _seed_org(conn, "SeededHS Org", "SHS")
        opo_id = _seed_opo(conn, "SEED-HS-001", org_id, org_id)

        flammable_id = conn.execute(text(
            "SELECT id FROM hazard_signs WHERE code = 'flammable'"
        )).scalar()
        conn.execute(text(
            "INSERT INTO opo_hazard_signs (opo_id, hazard_sign_id) VALUES (:opo, :hs)"
        ), {"opo": opo_id, "hs": flammable_id})
        conn.commit()

    engine.dispose()
    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        expected_hs_id = _uuid5("flammable")
        row = conn.execute(text(
            "SELECT opo_id, hazard_sign_id FROM opo_hazard_signs "
            "WHERE opo_id = :opo AND hazard_sign_id = :hs"
        ), {"opo": opo_id, "hs": expected_hs_id}).fetchone()
        assert row is not None, (
            "junction to seeded hazard_sign must survive 0008 → head "
            "with deterministic UUID transition"
        )

        row2 = conn.execute(text(
            "SELECT code FROM hazard_signs WHERE id = :hs"
        ), {"hs": expected_hs_id}).fetchone()
        assert row2 is not None
        assert row2[0] == "flammable"
    engine2.dispose()


def test_0008_seeded_activity_type_junction_survives() -> None:
    engine = _migrate_to("0008_stage3")

    with engine.connect() as conn, conn.begin():
        org_id = _seed_org(conn, "SeededAT Org", "SAT")
        opo_id = _seed_opo(conn, "SEED-AT-001", org_id, org_id)

        prod_id = conn.execute(text(
            "SELECT id FROM activity_types WHERE code = 'production'"
        )).scalar()
        conn.execute(text(
            "INSERT INTO opo_activity_types (opo_id, activity_type_id) VALUES (:opo, :at)"
        ), {"opo": opo_id, "at": prod_id})
        conn.commit()

    engine.dispose()
    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        expected_at_id = _uuid5("production")
        row = conn.execute(text(
            "SELECT opo_id, activity_type_id FROM opo_activity_types "
            "WHERE opo_id = :opo AND activity_type_id = :at"
        ), {"opo": opo_id, "at": expected_at_id}).fetchone()
        assert row is not None, (
            "junction to seeded activity_type must survive 0008 → head "
            "with deterministic UUID transition"
        )
    engine2.dispose()


def test_0008_seeded_custom_and_multiple_links_survive() -> None:
    engine = _migrate_to("0008_stage3")

    with engine.connect() as conn, conn.begin():
        org_id = _seed_org(conn, "MultiHS Org", "MHS")
        opo_id = _seed_opo(conn, "MUL-HS-001", org_id, org_id)

        flammable_id = conn.execute(text(
            "SELECT id FROM hazard_signs WHERE code = 'flammable'"
        )).scalar()
        explosive_id = conn.execute(text(
            "SELECT id FROM hazard_signs WHERE code = 'explosive'"
        )).scalar()
        custom_hs_id = str(_uuid.uuid4())
        conn.execute(text(
            "INSERT INTO hazard_signs (id, code, name) VALUES (:id, 'custom-hs', 'Custom')"
        ), {"id": custom_hs_id})

        conn.execute(text(
            "INSERT INTO opo_hazard_signs (opo_id, hazard_sign_id) VALUES (:opo, :hs)"
        ), {"opo": opo_id, "hs": flammable_id})
        conn.execute(text(
            "INSERT INTO opo_hazard_signs (opo_id, hazard_sign_id) VALUES (:opo, :hs)"
        ), {"opo": opo_id, "hs": explosive_id})
        conn.execute(text(
            "INSERT INTO opo_hazard_signs (opo_id, hazard_sign_id) VALUES (:opo, :hs)"
        ), {"opo": opo_id, "hs": custom_hs_id})
        conn.commit()

    engine.dispose()
    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        count = conn.execute(text(
            "SELECT count(*) FROM opo_hazard_signs WHERE opo_id = :opo"
        ), {"opo": opo_id}).scalar()
        assert count == 3, f"all 3 hazard_sign links must survive, got {count}"

        expected_flammable = _uuid5("flammable")
        expected_explosive = _uuid5("explosive")
        links = conn.execute(text(
            "SELECT hazard_sign_id FROM opo_hazard_signs WHERE opo_id = :opo"
        ), {"opo": opo_id}).fetchall()
        link_ids = {str(r[0]) for r in links}
        assert expected_flammable in link_ids, "seeded flammable UUID must be updated"
        assert expected_explosive in link_ids, "seeded explosive UUID must be updated"
        assert custom_hs_id in link_ids, "custom hazard_sign UUID must be preserved"
    engine2.dispose()


# ============================================================================
# Case B — owner == operator: backfill works correctly
# ============================================================================
def test_0010_backfills_when_owner_equals_operator() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn, conn.begin():
        org_id = _seed_org(conn, "Same Org", "SO")
        opo_id = _seed_opo(conn, "BK-001", org_id, org_id, name="SameOwnerOpO")

        td_id = str(_uuid.uuid4())
        conn.execute(text(
            "INSERT INTO technical_devices "
            "(id, name, device_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Dev', 'other', :opo, now(), now())"
        ), {"id": td_id, "opo": opo_id})

        bld_id = str(_uuid.uuid4())
        conn.execute(text(
            "INSERT INTO buildings (id, name, building_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Bld', 'other', :opo, now(), now())"
        ), {"id": bld_id, "opo": opo_id})
        conn.commit()

    engine.dispose()
    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        result_td = conn.execute(text(
            "SELECT organization_id FROM technical_devices WHERE id = :id"
        ), {"id": td_id}).scalar()
        assert str(result_td) == org_id, (
            f"TD backfill: expected {org_id}, got {result_td}"
        )

        result_bld = conn.execute(text(
            "SELECT organization_id FROM buildings WHERE id = :id"
        ), {"id": bld_id}).scalar()
        assert str(result_bld) == org_id, (
            f"Building backfill: expected {org_id}, got {result_bld}"
        )
    engine2.dispose()


# ============================================================================
# Case C - owner != operator: backfill does NOT occur, organization_id stays NULL
# ============================================================================
def test_0010_backfills_null_when_owner_differs_from_operator() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn, conn.begin():
        owner_org = _seed_org(conn, "Owner Org", "OWN")
        op_org = _seed_org(conn, "Operator Org", "OPR")
        opo_id = _seed_opo(conn, "AMB-001", owner_org, op_org, name="Ambiguous OPO")

        td_id = str(_uuid.uuid4())
        conn.execute(text(
            "INSERT INTO technical_devices (id, name, device_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Ambiguous TD', 'other', :opo, now(), now())"
        ), {"id": td_id, "opo": opo_id})
        conn.commit()

    engine.dispose()
    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        result = conn.execute(text(
            "SELECT organization_id FROM technical_devices WHERE id = :id"
        ), {"id": td_id}).scalar()
        assert result is None, (
            f"when owner != operator, organization_id must remain NULL, got {result}"
        )
    engine2.dispose()



# ============================================================================
# Case D — TD without OPO survives with NULL organization_id
# ============================================================================
def test_0010_td_without_opo_survives_with_null_org() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn:
        td_id = str(_uuid.uuid4())
        conn.execute(text(
            "INSERT INTO technical_devices (id, name, device_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Standalone', 'other', NULL, now(), now())"
        ), {"id": td_id})
        conn.commit()

    engine.dispose()

    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        row = conn.execute(text(
            "SELECT id, opo_id, organization_id FROM technical_devices WHERE id = :id"
        ), {"id": td_id}).fetchone()
        assert row is not None, "standalone TD must survive migration"
        assert row[1] is None, "opo_id must stay NULL"
        assert row[2] is None, "organization_id must stay NULL — no source for backfill"
    engine2.dispose()


# ============================================================================
# Case E — Building without OPO survives with NULL organization_id
# ============================================================================
def test_0010_building_without_opo_survives_with_null_org() -> None:
    engine = _migrate_to("0009_stage3")

    with engine.connect() as conn:
        bld_id = str(_uuid.uuid4())
        conn.execute(text(
            "INSERT INTO buildings (id, name, building_type, opo_id, created_at, updated_at) "
            "VALUES (:id, 'Standalone Bld', 'other', NULL, now(), now())"
        ), {"id": bld_id})
        conn.commit()

    engine.dispose()

    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        row = conn.execute(text(
            "SELECT id, opo_id, organization_id FROM buildings WHERE id = :id"
        ), {"id": bld_id}).fetchone()
        assert row is not None, "standalone Building must survive migration"
        assert row[1] is None, "opo_id must stay NULL"
        assert row[2] is None, "organization_id must stay NULL — no source for backfill"
    engine2.dispose()


# ============================================================================
# Case F — nullable relations check
# ============================================================================
def test_0010_nullable_relations_after_migration() -> None:
    engine = _migrate_to("head")

    with engine.connect() as conn:
        for col_name in ["organization_id", "opo_id"]:
            cols = conn.execute(text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'technical_devices' AND column_name = :col"
            ), {"col": col_name}).fetchone()
            assert cols is not None
            assert cols[0] == "YES", (
                f"technical_devices.{col_name} must be nullable after migration"
            )

            cols_b = conn.execute(text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'buildings' AND column_name = :col"
            ), {"col": col_name}).fetchone()
            assert cols_b is not None
            assert cols_b[0] == "YES", (
                f"buildings.{col_name} must be nullable after migration"
            )
    engine.dispose()


# ============================================================================
# Original tests — updated for new semantics
# ============================================================================
def test_0008_with_custom_hazard_relation_survives() -> None:
    engine = _migrate_to("0008_stage3")

    with engine.connect() as conn, conn.begin():
        org_id = _seed_org(conn, "CustomHS Org", "CHS")
        opo_id = _seed_opo(conn, "REG-001", org_id, org_id)
        hs_id = str(_uuid.uuid4())
        conn.execute(text(
            "INSERT INTO hazard_signs (id, code, name) VALUES (:id, 'test-hs', 'Test Sign')"
        ), {"id": hs_id})
        conn.execute(text(
            "INSERT INTO opo_hazard_signs (opo_id, hazard_sign_id) VALUES (:opo, :hs)"
        ), {"opo": opo_id, "hs": hs_id})
        conn.commit()

    engine.dispose()
    engine2 = _upgrade_to("head")

    with engine2.connect() as conn:
        row = conn.execute(text(
            "SELECT opo_id, hazard_sign_id FROM opo_hazard_signs "
            "WHERE opo_id = :opo AND hazard_sign_id = :hs"
        ), {"opo": opo_id, "hs": hs_id}).fetchone()
        assert row is not None, "custom hazard_sign junction must survive 0008→head"
    engine2.dispose()


def test_0008_with_custom_activity_relation_survives() -> None:
    engine = _migrate_to("0008_stage3")

    with engine.connect() as conn, conn.begin():
        org_id = _seed_org(conn, "CustomAT Org", "CAT")
        opo_id = _seed_opo(conn, "REG-002", org_id, org_id)
        at_id = str(_uuid.uuid4())
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
        assert row is not None, "custom activity_type junction must survive 0008→head"
    engine2.dispose()


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

        org_cols = conn.execute(text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'technical_devices' AND column_name = 'organization_id'"
        )).fetchone()
        assert org_cols[0] == "YES", "organization_id must be nullable on fresh DB"

    engine.dispose()


def test_downgrade_0010_to_0009_and_back() -> None:
    engine = _migrate_to("head")

    org_id = str(_uuid.uuid4())
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO organizations (id, legal_name, short_name, organization_type) "
            "VALUES (:id, 'Stable Org', 'STB', 'legal_entity')"
        ), {"id": org_id})

        opo_id = str(_uuid.uuid4())
        conn.execute(text(
            "INSERT INTO opo (id, name, registration_number, hazard_class, address, "
            "registration_date, owner_organization_id, operating_organization_id, comment) "
            "VALUES (:id, 'Stable OPO', 'STB-001', 'hazard_class_1', 'Addr', "
            "'2024-01-15', :org, :org, 'test comment')"
        ), {"id": opo_id, "org": org_id})
        conn.commit()

    engine.dispose()

    engine2 = _migrate_to("0009_stage3")

    with engine2.connect() as conn:
        cols = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'technical_devices' AND "
            "column_name = 'organization_id'"
        )).fetchall()
        assert len(cols) == 0, "organization_id should be gone at 0009"

    engine2.dispose()

    engine3 = _upgrade_to("head")

    with engine3.connect() as conn:
        cols2 = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'technical_devices' AND "
            "column_name = 'organization_id'"
        )).fetchall()
        assert len(cols2) == 1, "organization_id should be back at head"
    engine3.dispose()
