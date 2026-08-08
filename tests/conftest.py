import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("TEST_DATABASE_URL"):
        return

    skip_pg = pytest.mark.skip(
        reason="TEST_DATABASE_URL is not set; PostgreSQL integration test skipped"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_pg)
