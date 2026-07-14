"""
observability/logging.py — Structured JSON logging.

Configures structlog for production-grade structured logging
with correlation IDs per task.
"""

from __future__ import annotations

import logging
import os
import sys
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production use."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add task_id if present in extras
        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id
        if hasattr(record, "node_id"):
            log_data["node_id"] = record.node_id
        if hasattr(record, "worker"):
            log_data["worker"] = record.worker

        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.utcnow().strftime("%H:%M:%S")
        level = record.levelname.ljust(7)
        name = record.name.split(".")[-1]

        extras = ""
        if hasattr(record, "task_id"):
            extras += f" [task={record.task_id[:8]}]"
        if hasattr(record, "node_id"):
            extras += f" [node={record.node_id}]"

        return f"{ts} | {level} | {name}{extras} | {record.getMessage()}"


def setup_logging(
    level: str = "INFO",
    format: str = "json",
) -> None:
    """Configure logging for the orchestrator service."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Choose formatter
    if format == "json":
        formatter = JSONFormatter()
    else:
        formatter = ConsoleFormatter()

    # Configure root handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    logging.getLogger("ars").info("Logging initialized: level=%s format=%s", level, format)
