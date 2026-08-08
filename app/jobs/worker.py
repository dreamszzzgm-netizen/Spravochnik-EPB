import logging
import time

from app.core.config import get_settings
from app.core.context import correlation_id_var
from app.core.logging import configure_logging
from app.database.session import get_session_factory
from app.jobs.repository import JobRepository, OutboxRepository

logger = logging.getLogger(__name__)


def process_job(job_type: str, payload: dict | None) -> None:
    """Infrastructure dispatcher placeholder for registered Stage 1+ handlers.

    Stage 0 deliberately has no business job handlers.
    """
    logger.info("No handler registered for job_type=%s payload_present=%s", job_type, bool(payload))


def process_outbox_event(event_type: str, payload: dict) -> None:
    """Stage 0 outbox dispatcher.

    Domain/integration handlers are registered in later stages.
    """
    logger.info("Outbox event observed event_type=%s payload_keys=%s", event_type, sorted(payload))


def run_once() -> bool:
    did_work = False

    with get_session_factory().begin() as session:
        repo = OutboxRepository(session)
        event = repo.claim_next()
        if event:
            token = correlation_id_var.set(event.correlation_id)
            try:
                process_outbox_event(event.event_type, event.payload)
                repo.mark_processed(event)
            except Exception as exc:
                logger.exception("Outbox event failed id=%s", event.id)
                repo.mark_failed(event, str(exc))
            finally:
                correlation_id_var.reset(token)
            did_work = True

    with get_session_factory().begin() as session:
        repo = JobRepository(session)
        job = repo.claim_next()
        if job:
            token = correlation_id_var.set(job.correlation_id)
            try:
                process_job(job.job_type, job.payload)
                repo.succeed(job)
            except Exception as exc:
                logger.exception("Background job failed id=%s", job.id)
                repo.fail(job, str(exc))
            finally:
                correlation_id_var.reset(token)
            did_work = True

    return did_work


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Worker started")

    while True:
        if not run_once():
            time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    run()
