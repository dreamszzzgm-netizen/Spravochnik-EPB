import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration


def test_migrations_build_stage0_schema() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)

    # env.py reads settings; expose the same URL to it.
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        engine = create_engine(url)
        try:
            names = set(inspect(engine).get_table_names())
            assert {"stored_files", "background_jobs", "outbox_events"} <= names
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 1
        finally:
            engine.dispose()
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
