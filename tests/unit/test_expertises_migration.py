from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_expertises_migration_is_linear_and_defines_all_tables() -> None:
    migration_path = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0017_expertises.py"
    )
    spec = spec_from_file_location("expertises_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "0017_expertises"
    assert migration.down_revision == "0016_documents"
    source = migration_path.read_text(encoding="utf-8")
    assert '"expertises"' in source
    assert '"expertise_subjects"' in source
    assert '"expertise_contract_items"' in source
    assert '"expertise_status_history"' in source
    assert "ck_expertise_subjects_single_subject" in source
    assert 'ForeignKey("contracts.id", ondelete="RESTRICT")' in source
