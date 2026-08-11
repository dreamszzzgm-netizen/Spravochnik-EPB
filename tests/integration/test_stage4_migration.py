import sqlalchemy as sa


EXPECTED_STAGE4_TABLES = {
    "contracts",
    "contract_responsibles",
    "expertise_types",
    "contract_items",
    "contract_item_technical_devices",
    "contract_item_buildings",
}


def _table_names(db_session) -> set[str]:
    return set(sa.inspect(db_session.get_bind()).get_table_names())


def test_stage4_contract_tables_exist(db_session) -> None:
    assert _table_names(db_session) >= EXPECTED_STAGE4_TABLES


def test_stage4_contract_scalar_checks_exist(db_session) -> None:
    table_names = _table_names(db_session)
    assert "contracts" in table_names
    assert "contract_items" in table_names

    inspector = sa.inspect(db_session.get_bind())
    contract_checks = {
        item["name"] for item in inspector.get_check_constraints("contracts")
    }
    item_checks = {
        item["name"] for item in inspector.get_check_constraints("contract_items")
    }

    assert "ck_contracts_amount_nonnegative" in contract_checks
    assert "ck_contracts_dates" in contract_checks
    assert "ck_contract_items_price_nonnegative" in item_checks


def test_stage4_subject_junctions_have_real_foreign_keys(db_session) -> None:
    table_names = _table_names(db_session)
    assert "contract_item_technical_devices" in table_names
    assert "contract_item_buildings" in table_names

    inspector = sa.inspect(db_session.get_bind())

    td_targets = {
        (fk["referred_table"], tuple(fk["referred_columns"]))
        for fk in inspector.get_foreign_keys("contract_item_technical_devices")
    }
    building_targets = {
        (fk["referred_table"], tuple(fk["referred_columns"]))
        for fk in inspector.get_foreign_keys("contract_item_buildings")
    }

    assert ("contract_items", ("id",)) in td_targets
    assert ("technical_devices", ("id",)) in td_targets
    assert ("contract_items", ("id",)) in building_targets
    assert ("buildings", ("id",)) in building_targets


def test_stage4_contract_status_enum_is_complete(db_session) -> None:
    assert "contracts" in _table_names(db_session)
    values = db_session.execute(
        sa.text(
            """
            SELECT enumlabel
            FROM pg_enum
            JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
            WHERE pg_type.typname = 'contract_status'
            ORDER BY enumsortorder
            """
        )
    ).scalars().all()

    assert values == [
        "draft",
        "approval",
        "signed",
        "in_progress",
        "suspended",
        "completed",
        "terminated",
        "archived",
    ]


def test_stage4_expertise_type_seed_is_deterministic(db_session) -> None:
    assert "expertise_types" in _table_names(db_session)
    rows = db_session.execute(
        sa.text("SELECT id::text, code, name FROM expertise_types ORDER BY code")
    ).all()

    assert rows == [
        (
            "0312543b-b525-530e-ac8d-efa8e8b2391d",
            "building_epb",
            "ЭПБ здания/сооружения",
        ),
        (
            "c79c5348-2ee9-53a6-9417-224e63de5a74",
            "technical_device_epb",
            "ЭПБ технического устройства",
        ),
    ]
