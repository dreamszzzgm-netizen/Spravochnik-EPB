import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def tick() -> None:
    """Scheduler extension point.

    Stage 0 must not create business jobs. Future stages register scheduling rules here.
    """
    logger.debug("Scheduler tick")


def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Scheduler started")

    while True:
        tick()
        time.sleep(settings.scheduler_tick_seconds)


if __name__ == "__main__":
    run()
