import logging
from collections.abc import Mapping
from typing import Any

from app.core.context import get_correlation_id, get_request_id


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.correlation_id = get_correlation_id() or "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "request_id=%(request_id)s correlation_id=%(correlation_id)s %(message)s"
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def safe_log_extra(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return explicitly supplied technical metadata only.

    Business documents, passwords, API keys and AI prompts must not be passed here.
    """
    return dict(extra or {})
