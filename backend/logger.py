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
import json
import re
from datetime import datetime
from pathlib import Path
from backend.config import cfg

_LOG_FILE = cfg.LOGS_DIR / "aegis.log"

class SecretScrubber:
    """Removes sensitive tokens from log messages."""
    # Pattern looks for typical hex tokens or generic secrets
    _token_pattern = re.compile(r'([0-9a-fA-F]{32,64})|(Bearer\s+[^\s"]+)')
    
    @classmethod
    def scrub(cls, text: str) -> str:
        if not text: return text
        return cls._token_pattern.sub("[REDACTED]", str(text))

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = self.record_to_msg(record)
        msg = SecretScrubber.scrub(msg)
        
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "component": record.name.split('.')[-1] if '.' in record.name else record.name,
            "message": msg
        }
        # Include extra structured fields if present
        for field in ["task_id", "agent_id", "project_id", "event", "trace_id", "latency_ms", "tokens_used", "tool"]:
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)
                
        # Include exception if present
        if record.exc_info:
            log_obj["exception"] = SecretScrubber.scrub(self.formatException(record.exc_info))
            
        return json.dumps(log_obj)

    def record_to_msg(self, record: logging.LogRecord) -> str:
        return record.getMessage()

# Root AEGIS logger — all child loggers inherit this handler
_root = logging.getLogger("aegis")
if not _root.handlers:
    _root.setLevel(logging.DEBUG)

    # Rotating file — 5 MB × 3 backups
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(JSONFormatter())
    _root.addHandler(fh)

    # Stderr — WARNING and above only (keeps terminal clean)
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    # Stderr gets regular format for human readability
    sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s | %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))
    _root.addHandler(sh)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'aegis' namespace."""
    return logging.getLogger(f"aegis.{name}")
