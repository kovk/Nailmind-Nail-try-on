from __future__ import annotations

import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any


def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nailmind")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(message)s")

    file_handler = TimedRotatingFileHandler(
        log_dir / "api.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def log_event_json(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))
