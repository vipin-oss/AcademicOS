"""Logging configuration. Centralised, structured, level-driven."""
from __future__ import annotations

import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
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
