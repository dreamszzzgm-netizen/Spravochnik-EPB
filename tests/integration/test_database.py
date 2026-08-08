import os

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration


def test_postgresql_is_reachable() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()
