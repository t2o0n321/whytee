"""Structured logging with a per-request correlation id.

A ``request_id`` is generated for every HTTP request (or taken from an inbound
``X-Request-ID`` header, e.g. propagated from n8n) and injected into every log
record via a contextvar + logging filter, so lines emitted deep in the provider
stack can be correlated back to the originating request.
"""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attach the current request id to each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    """Configure root logging once, honouring ``LOG_LEVEL`` (default INFO)."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
