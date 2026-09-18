"""Structured JSON logging for the dummy app, written to a per-run log file."""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

LOGGER_NAME = "orders"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in getattr(record, "context", {}).items():
            payload[key] = value
        if record.exc_info:
            exc_type, exc, tb = record.exc_info
            payload["error_type"] = getattr(exc_type, "__name__", str(exc_type))
            payload["error"] = str(exc)
            frames = traceback.format_exception(exc_type, exc, tb, limit=15)
            payload["traceback"] = "".join(frames[-25:])
        return json.dumps(payload)


def configure(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log(level: int, message: str, /, exc_info=None, **context: object) -> None:
    logging.getLogger(LOGGER_NAME).log(
        level, message, exc_info=exc_info, extra={"context": context}
    )
