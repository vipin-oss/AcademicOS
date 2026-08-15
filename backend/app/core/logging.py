"""Logging configuration. Centralised, structured, level-driven.

V3 M19 (ADR-066): ``LOG_JSON=1`` switches the formatter to one JSON object per
line (machine-parseable for log shippers/metrics); the default remains the
human-readable line format.
"""
from __future__ import annotations

import json
import logging
import sys

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    """One JSON object per log record (parseable, no structured-logging dep)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    if getattr(settings, "log_json", False):
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO if settings.environment != "test" else logging.DEBUG)


configure_logging()
logger = logging.getLogger("academicos")
