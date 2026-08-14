from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration

LATEST_HEAD = "0020_identifier_constraints"
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


def _database_url() -> str:
    return os.environ["TEST_DATABASE_URL"]


def _current_revision(database_url: str) -> str | None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()


def _run_alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        check=True,
        env=os.environ.copy(),
    )


def test_task_enums_are_exact() -> None:
    from app.modules.tasks.enums import TaskPriority, TaskStatus

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
    from app.modules.comments.models import Comment, CommentTask
    from app.modules.tasks.models import Task

    assert Task.__tablename__ == "tasks"
    assert Comment.__tablename__ == "comments"
    assert CommentTask.__tablename__ == "comment_tasks"


def test_stage5_tables_and_indexes_exist() -> None:
    engine = create_engine(_database_url())
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


def test_stage5_postgres_enums_are_exact() -> None:
    engine = create_engine(_database_url())
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


def test_stage5_migration_round_trip() -> None:
    database_url = _database_url()
    assert _current_revision(database_url) == LATEST_HEAD

    try:
        _run_alembic("downgrade", PARENT_HEAD)
        assert _current_revision(database_url) == PARENT_HEAD

        _run_alembic("upgrade", CURRENT_HEAD)
        assert _current_revision(database_url) == CURRENT_HEAD
    finally:
        _run_alembic("upgrade", "head")
