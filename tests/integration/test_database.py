import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database.models import BackgroundJob, JobStatus, OutboxEvent, OutboxStatus

pytestmark = pytest.mark.integration


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text("""
            TRUNCATE TABLE background_jobs, outbox_events
            RESTART IDENTITY CASCADE
        """)
        )
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def test_postgresql_is_reachable() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()


def test_job_status_persists_enum_value(db_session: Session) -> None:
    job = BackgroundJob(
        job_key="enum-test",
        job_type="test",
        status=JobStatus.PENDING,
    )
    db_session.add(job)
    db_session.commit()

    raw = db_session.execute(
        text("select status::text from background_jobs where id = :id"),
        {"id": job.id},
    ).scalar_one()

    assert raw == "pending"


def test_outbox_status_persists_enum_value(db_session: Session) -> None:
    event = OutboxEvent(
        event_type="test",
        aggregate_type="enum-regression",
        aggregate_id=None,
        payload={},
        status=OutboxStatus.PENDING,
    )
    db_session.add(event)
    db_session.commit()

    raw = db_session.execute(
        text("select status::text from outbox_events where id = :id"),
        {"id": event.id},
    ).scalar_one()

    assert raw == "pending"
