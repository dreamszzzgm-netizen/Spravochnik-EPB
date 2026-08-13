import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

pytestmark = pytest.mark.integration


def _alembic_config(url: str) -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _with_database_url(url: str):
    class _DatabaseUrlContext:
        def __enter__(self):
            self.previous = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = url
            return self

        def __exit__(self, exc_type, exc, tb):
            if self.previous is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = self.previous

    return _DatabaseUrlContext()


def _assert_cp52_schema(url: str) -> None:
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {
            "workflow_templates",
            "workflow_template_versions",
            "workflow_task_templates",
        } <= tables

        task_columns = {column["name"] for column in inspector.get_columns("tasks")}
        assert {
            "source_workflow_template_version_id",
            "source_workflow_task_template_id",
        } <= task_columns

        task_foreign_keys = inspector.get_foreign_keys("tasks")
        provenance_fks = {
            tuple(fk["constrained_columns"]): tuple(fk["referred_columns"])
            for fk in task_foreign_keys
        }
        assert (
            "source_workflow_task_template_id",
            "source_workflow_template_version_id",
        ) in provenance_fks
        assert provenance_fks[
            (
                "source_workflow_task_template_id",
                "source_workflow_template_version_id",
            )
        ] == ("id", "workflow_template_version_id")

        version_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("workflow_template_versions")
        }
        assert ("workflow_template_id", "version_number") in version_uniques

        task_template_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("workflow_task_templates")
        }
        assert ("workflow_template_version_id", "sort_order") in task_template_uniques
        assert ("id", "workflow_template_version_id") in task_template_uniques
    finally:
        engine.dispose()


def test_cp52_workflow_schema_and_task_provenance() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    cfg = _alembic_config(url)

    with _with_database_url(url):
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        _assert_cp52_schema(url)


def test_cp52_migration_round_trip() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    cfg = _alembic_config(url)

    with _with_database_url(url):
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        _assert_cp52_schema(url)

        command.downgrade(cfg, "0013_stage5_tasks_core")
        engine = create_engine(url)
        try:
            inspector = inspect(engine)
            assert "workflow_templates" not in set(inspector.get_table_names())
            task_columns = {column["name"] for column in inspector.get_columns("tasks")}
            assert "source_workflow_template_version_id" not in task_columns
            assert "source_workflow_task_template_id" not in task_columns
        finally:
            engine.dispose()

        command.upgrade(cfg, "head")
        _assert_cp52_schema(url)
