from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_documents_migration_is_linear_and_defines_both_tables() -> None:
    migration_path = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0016_documents.py"
    )
    spec = spec_from_file_location("documents_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "0016_documents"
    assert migration.down_revision == "0015_org_legal_form_fields"
    source = migration_path.read_text(encoding="utf-8")
    assert '"document_requirements"' in source
    assert '"organization_documents"' in source
    assert "uq_document_requirement_type_scope" in source
    assert "ck_document_requirements_applicability" in source
    assert 'ForeignKey("organizations.id", ondelete="CASCADE")' in source
