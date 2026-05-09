"""
Centralized Structured JSON Logging Configuration for SecureNOC Backend.

All modules should use `get_logger(__name__)` to obtain a logger instance.
This ensures every log line is a single-line JSON object compatible with
Elasticsearch / Kibana ingestion — no regex parsing required.

Required dependency: python-json-logger
"""

import logging
import os
import sys
from datetime import datetime, timezone

from pythonjsonlogger import jsonlogger


# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
SERVICE_NAME = os.getenv("SERVICE_NAME", "securenoc-backend")
ENVIRONMENT = os.getenv("APP_ENV", "development")
# DEBUG in dev, INFO in production/staging
LOG_LEVEL = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO


# ---------------------------------------------------------------------------
# Custom JSON Formatter
# ---------------------------------------------------------------------------
class StructuredJsonFormatter(jsonlogger.JsonFormatter):
    """
    Extends python-json-logger to inject standard fields into every log line:
      - timestamp  (ISO-8601 UTC)
      - level
      - service
      - environment
      - logger     (module name)
    """

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict):
        super().add_fields(log_record, record, message_dict)

        # Timestamp in ISO-8601 UTC — Kibana's preferred format
        log_record["timestamp"] = (
            datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
        )

        # Standard fields
        log_record["level"] = record.levelname
        log_record["service"] = SERVICE_NAME
        log_record["environment"] = ENVIRONMENT
        log_record["logger"] = record.name

        # Move 'message' to top-level key if not already present
        if "message" not in log_record:
            log_record["message"] = record.getMessage()

        # Remove redundant default keys that python-json-logger may add
        for key in ("levelname", "name", "asctime"):
            log_record.pop(key, None)


# ---------------------------------------------------------------------------
# Shared formatter & handler
# ---------------------------------------------------------------------------
_json_formatter = StructuredJsonFormatter()

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(_json_formatter)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger configured for structured JSON output.

    Usage:
        from logger import get_logger
        logger = get_logger(__name__)
        logger.info("Server started", extra={"port": 8000})
    """
    _logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if not _logger.handlers:
        _logger.addHandler(_stream_handler)
        _logger.setLevel(LOG_LEVEL)
        _logger.propagate = False  # Prevent duplicate logs from root logger

    return _logger


def setup_uvicorn_logging() -> None:
    """
    Override Uvicorn's default loggers so their output also becomes
    structured JSON. Call this ONCE at application startup.
    """
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers.clear()
        uv_logger.addHandler(_stream_handler)
        uv_logger.setLevel(LOG_LEVEL)
        uv_logger.propagate = False
