from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import BackgroundJob, JobStatus, OutboxEvent, OutboxStatus


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def claim_next(self) -> BackgroundJob | None:
        stmt = (
            select(BackgroundJob)
            .where(BackgroundJob.status == JobStatus.PENDING)
            .order_by(BackgroundJob.created_at, BackgroundJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = self.session.scalar(stmt)
        if job is None:
            return None
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.attempt_count += 1
        self.session.flush()
        return job

    def succeed(self, job: BackgroundJob) -> None:
        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        job.last_error = None

    def fail(self, job: BackgroundJob, error: str) -> None:
        job.status = JobStatus.FAILED
        job.finished_at = datetime.now(UTC)
        job.last_error = error[:4000]


class OutboxRepository:
    def __init__(self, session: Session):
        self.session = session

    def claim_next(self) -> OutboxEvent | None:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatus.PENDING)
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        event = self.session.scalar(stmt)
        if event is None:
            return None
        event.status = OutboxStatus.PROCESSING
        event.attempt_count += 1
        self.session.flush()
        return event

    def mark_processed(self, event: OutboxEvent) -> None:
        event.status = OutboxStatus.PROCESSED
        event.processed_at = datetime.now(UTC)
        event.last_error = None

    def mark_failed(self, event: OutboxEvent, error: str) -> None:
        event.status = OutboxStatus.FAILED
        event.last_error = error[:4000]
