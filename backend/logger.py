#!/usr/bin/env python3
"""
AEGIS Structured Logger
========================
Rotating file + stderr logger for the AEGIS backend.
Every log entry includes a timestamp and optional task_id.

Usage:
    from backend.logger import get_logger
    log = get_logger("server")
    log.info("Started", extra={"task_id": "abc123"})
"""

import logging
import logging.handlers
from pathlib import Path
from backend.config import cfg

_LOG_FILE = cfg.LOGS_DIR / "aegis.log"
_LOG_FMT = "%(asctime)s [%(levelname)s] %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S"

# Root AEGIS logger — all child loggers inherit this handler
_root = logging.getLogger("aegis")
if not _root.handlers:
    _root.setLevel(logging.DEBUG)

    # Rotating file — 5 MB × 3 backups
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT))
    _root.addHandler(fh)

    # Stderr — WARNING and above only (keeps terminal clean)
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT))
    _root.addHandler(sh)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'aegis' namespace."""
    return logging.getLogger(f"aegis.{name}")
