from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
import pytest
from sqlalchemy import create_engine, inspect, text

from app.modules.comments.models import Comment, CommentTask
from app.modules.tasks.enums import TaskPriority, TaskStatus
from app.modules.tasks.models import Task

pytestmark = pytest.mark.integration

CURRENT_HEAD = "0013_stage5_tasks_core"
PARENT_HEAD = "0012_stage4_contract_lifecycle"
EXPECTED_TABLES = {
    "tasks",
    "task_assignees",
    "task_organizations",
    "task_contracts",
    "task_contract_items",
    "task_technical_devices",
    "task_buildings",
    "task_opos",
    "comments",
    "comment_tasks",
}


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _current_revision(database_url: str) -> str | None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def test_task_enums_are_exact() -> None:
    assert [item.value for item in TaskStatus] == [
        "new",
        "in_progress",
        "completed",
        "cancelled",
    ]
    assert [item.value for item in TaskPriority] == [
        "low",
        "normal",
        "high",
        "urgent",
    ]


def test_task_models_use_expected_tables() -> None:
    assert Task.__tablename__ == "tasks"
    assert Comment.__tablename__ == "comments"
    assert CommentTask.__tablename__ == "comment_tasks"


def test_stage5_tables_and_indexes_exist(test_database_url: str) -> None:
    engine = create_engine(test_database_url)
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= EXPECTED_TABLES

        task_indexes = {item["name"] for item in inspector.get_indexes("tasks")}
        assert {
            "ix_tasks_creator_employee_id",
            "ix_tasks_status",
            "ix_tasks_due_date",
            "ix_tasks_deleted_at",
        } <= task_indexes

        assignee_indexes = {
            item["name"] for item in inspector.get_indexes("task_assignees")
        }
        assert "ix_task_assignees_employee_id" in assignee_indexes
    finally:
        engine.dispose()


def test_stage5_postgres_enums_are_exact(test_database_url: str) -> None:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT t.typname, e.enumlabel
                    FROM pg_type AS t
                    JOIN pg_enum AS e ON e.enumtypid = t.oid
                    WHERE t.typname IN ('task_status', 'task_priority')
                    ORDER BY t.typname, e.enumsortorder
                    """
                )
            ).all()
    finally:
        engine.dispose()

    grouped: dict[str, list[str]] = {"task_priority": [], "task_status": []}
    for enum_name, enum_value in rows:
        grouped[enum_name].append(enum_value)

    assert grouped["task_status"] == ["new", "in_progress", "completed", "cancelled"]
    assert grouped["task_priority"] == ["low", "normal", "high", "urgent"]


def test_stage5_migration_round_trip(test_database_url: str) -> None:
    config = _alembic_config(test_database_url)
    assert _current_revision(test_database_url) == CURRENT_HEAD

    command.downgrade(config, PARENT_HEAD)
    assert _current_revision(test_database_url) == PARENT_HEAD

    command.upgrade(config, CURRENT_HEAD)
    assert _current_revision(test_database_url) == CURRENT_HEAD
