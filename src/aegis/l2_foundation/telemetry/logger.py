"""L2 Structured Logger.
Format: JSON (production) or human-readable "development" (console).
Every log record carries: timestamp, level, logger/module, correlation_id, request_id, task_id,
metadata, exception info (when provided). Sensitive values are redacted BEFORE serializing.

Never use bare print() in core runtime code. Always use get_logger(__name__).
"""

from __future__ import annotations

import abc
import datetime
import io
import json
import sys
import threading
import traceback
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, TextIO

from aegis.l2_foundation.crypto.redact import Redactor, get_default_redactor
from aegis.l2_foundation.telemetry.context import CorrelationContext


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    NOTICE = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    FATAL = 60


# Backwards compat with common string names
_LEVEL_NAMES = {
    "debug": LogLevel.DEBUG,
    "info": LogLevel.INFO,
    "notice": LogLevel.NOTICE,
    "warn": LogLevel.WARNING,
    "warning": LogLevel.WARNING,
    "error": LogLevel.ERROR,
    "critical": LogLevel.CRITICAL,
    "fatal": LogLevel.FATAL,
}


def parse_level(raw: str | int | LogLevel) -> LogLevel:
    if isinstance(raw, LogLevel):
        return raw
    if isinstance(raw, int):
        return LogLevel(raw)
    r = str(raw).lower().strip()
    if r in _LEVEL_NAMES:
        return _LEVEL_NAMES[r]
    raise ValueError(f"Unknown log level: {raw!r}")


@dataclass
class LogRecord:
    timestamp: float  # POSIX seconds UTC
    level: LogLevel
    logger: str
    message: str
    correlation_id: str | None = None
    request_id: str | None = None
    task_id: str | None = None
    parent_op_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    exc_info: str | None = None  # formatted traceback, redacted

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "ts": self.timestamp,
            "iso": datetime.datetime.fromtimestamp(
                self.timestamp, tz=datetime.UTC
            ).isoformat(),
            "level": self.level.name,
            "logger": self.logger,
            "msg": self.message,
        }
        if self.correlation_id is not None:
            d["correlation_id"] = self.correlation_id
        if self.request_id is not None:
            d["request_id"] = self.request_id
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.parent_op_id is not None:
            d["parent_op_id"] = self.parent_op_id
        if self.metadata:
            d["meta"] = self.metadata
        if self.exc_info:
            d["error"] = self.exc_info
        return d


class Formatter(abc.ABC):
    @abc.abstractmethod
    def format(self, record: LogRecord) -> str: ...


class JSONFormatter(Formatter):
    def __init__(self) -> None:
        self._encoder = json.JSONEncoder(default=str, ensure_ascii=False, separators=(",", ":"))

    def format(self, record: LogRecord) -> str:
        return self._encoder.encode(record.as_dict())


class DevelopmentFormatter(Formatter):
    def format(self, record: LogRecord) -> str:
        iso = datetime.datetime.fromtimestamp(record.timestamp, tz=datetime.UTC).strftime(
            "%H:%M:%S.%f"
        )[:-3]
        parts = [f"{iso} {record.level.name:<8} [{record.logger}]"]
        cid = record.correlation_id[:8] if record.correlation_id else "--------"
        parts.append(f"cid={cid}")
        if record.task_id:
            parts.append(f"tid={record.task_id[:8]}")
        parts.append(record.message)
        if record.metadata:
            parts.append("| " + ", ".join(f"{k}={v}" for k, v in record.metadata.items())[:200])
        if record.exc_info:
            parts.append("\n" + record.exc_info)
        return " ".join(parts)


class Sink(abc.ABC):
    @abc.abstractmethod
    def write(self, line: str) -> None: ...

    @abc.abstractmethod
    def flush(self) -> None: ...

    def close(self) -> None:  # pragma: no cover - default no-op
        self.flush()


class StreamSink(Sink):
    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._lock = threading.Lock()

    def write(self, line: str) -> None:
        with self._lock:
            self._stream.write(line + "\n")

    def flush(self) -> None:
        with self._lock:
            self._stream.flush()


class FileSink(Sink):
    def __init__(self, path: str | Path, *, append: bool = True) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self._path.open("a" if append else "w", encoding="utf-8")
        self._lock = threading.Lock()

    def write(self, line: str) -> None:
        with self._lock:
            self._fp.write(line + "\n")

    def flush(self) -> None:
        with self._lock:
            self._fp.flush()

    def close(self) -> None:
        with self._lock:
            self._fp.close()


_LOGGER_REGISTRY_LOCK = threading.RLock()
_LOGGER_REGISTRY: dict[str, StructuredLogger] = {}


class StructuredLogger:
    """A single named logger. Thread-safe. All public methods mirror the usual logger API."""

    def __init__(
        self,
        name: str,
        *,
        sinks: list[Sink] | None = None,
        level: LogLevel = LogLevel.INFO,
        formatter: Formatter | None = None,
        redactor: Redactor | None = None,
        include_correlation: bool = True,
    ) -> None:
        self.name = name
        self.sinks: list[Sink] = list(sinks or [StreamSink(sys.stderr)])
        self.level: LogLevel = level
        self.formatter: Formatter = formatter or DevelopmentFormatter()
        self.redactor: Redactor = redactor or get_default_redactor()
        self.include_correlation = include_correlation
        self._lock = threading.RLock()

    # -------- Sink management --------

    def add_sink(self, sink: Sink) -> None:
        with self._lock:
            self.sinks.append(sink)

    def set_formatter(self, fmt: Formatter) -> None:
        with self._lock:
            self.formatter = fmt

    def set_level(self, level: LogLevel | str | int) -> None:
        self.level = parse_level(level)

    # -------- Logging API --------

    def is_enabled(self, level: LogLevel) -> bool:
        return level >= self.level

    def _log(
        self,
        level: LogLevel,
        message: str,
        *,
        metadata: dict[str, Any] | None = None,
        exc_info: BaseException | None = None,
        correlation: CorrelationContext | None = None,
    ) -> None:
        if not self.is_enabled(level):
            return
        ctx = correlation or (
            CorrelationContext.get_current_or_none() if self.include_correlation else None
        )
        red_meta = self.redactor.redact(metadata or {})
        exc_str: str | None = None
        if exc_info is not None:
            buf = io.StringIO()
            traceback.print_exception(
                type(exc_info), exc_info, exc_info.__traceback__, limit=10, file=buf
            )
            exc_str = self.redactor.redact(buf.getvalue())
        ts = datetime.datetime.now(tz=datetime.UTC).timestamp()
        record = LogRecord(
            timestamp=ts,
            level=level,
            logger=self.name,
            message=str(message),
            correlation_id=str(ctx.correlation_id) if ctx else None,
            request_id=str(ctx.request_id) if ctx and ctx.request_id else None,
            task_id=str(ctx.task_id) if ctx and ctx.task_id else None,
            parent_op_id=str(ctx.parent_op_id) if ctx and ctx.parent_op_id else None,
            metadata=red_meta,
            exc_info=exc_str,
        )
        line = self.formatter.format(record)
        for sink in list(self.sinks):
            try:
                sink.write(line)
                sink.flush()
            except Exception:
                pass

    def debug(self, message: str, **meta: Any) -> None:
        self._log(LogLevel.DEBUG, message, metadata=meta or None)

    def info(self, message: str, **meta: Any) -> None:
        self._log(LogLevel.INFO, message, metadata=meta or None)

    def notice(self, message: str, **meta: Any) -> None:
        self._log(LogLevel.NOTICE, message, metadata=meta or None)

    def warning(self, message: str, **meta: Any) -> None:
        self._log(LogLevel.WARNING, message, metadata=meta or None)

    warn = warning

    def error(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        **meta: Any,
    ) -> None:
        self._log(LogLevel.ERROR, message, metadata=meta or None, exc_info=exc)

    def critical(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        **meta: Any,
    ) -> None:
        self._log(LogLevel.CRITICAL, message, metadata=meta or None, exc_info=exc)

    def fatal(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        **meta: Any,
    ) -> None:
        self._log(LogLevel.FATAL, message, metadata=meta or None, exc_info=exc)

    def exception(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        **meta: Any,
    ) -> None:
        if exc is None:
            exc = sys.exc_info()[1]  # type: ignore[assignment]
        self._log(LogLevel.ERROR, message, metadata=meta or None, exc_info=exc)


# Global logger settings
_ROOT_LOGGER_NAME = "aegis"
_ROOT_CONFIGURED = False


def _build_default_root() -> StructuredLogger:
    logger = StructuredLogger(
        _ROOT_LOGGER_NAME,
        sinks=[StreamSink(sys.stderr)],
        level=LogLevel.INFO,
        formatter=DevelopmentFormatter(),
        include_correlation=True,
    )
    return logger


def configure_root_logger(
    *,
    level: LogLevel | str | int = LogLevel.INFO,
    format: str = "development",  # noqa: A002 - matches config key
    file_path: str | Path | None = None,
) -> StructuredLogger:
    """Called by ConfigLoader / bootstrap to reconfigure the root logger."""
    global _ROOT_CONFIGURED
    with _LOGGER_REGISTRY_LOCK:
        root = _LOGGER_REGISTRY.get(_ROOT_LOGGER_NAME) or _build_default_root()
        root.set_level(parse_level(level))
        if format.lower() == "json":
            root.set_formatter(JSONFormatter())
        else:
            root.set_formatter(DevelopmentFormatter())
        if file_path is not None:
            root.add_sink(FileSink(file_path))
        _LOGGER_REGISTRY[_ROOT_LOGGER_NAME] = root
        _ROOT_CONFIGURED = True
        return root


def get_logger(name: str | None = None) -> StructuredLogger:
    """Primary public API. Prefer get_logger(__name__) at module import time."""
    resolved_name = name or _ROOT_LOGGER_NAME
    with _LOGGER_REGISTRY_LOCK:
        if resolved_name not in _LOGGER_REGISTRY:
            root = _LOGGER_REGISTRY.get(_ROOT_LOGGER_NAME)
            if root is None:
                root = _build_default_root()
                _LOGGER_REGISTRY[_ROOT_LOGGER_NAME] = root
            # Child loggers share the root's sinks/level/formatter/redactor but keep their own logger name
            child = StructuredLogger(
                resolved_name,
                sinks=list(root.sinks),
                level=root.level,
                formatter=root.formatter,
                redactor=root.redactor,
                include_correlation=root.include_correlation,
            )
            _LOGGER_REGISTRY[resolved_name] = child
        return _LOGGER_REGISTRY[resolved_name]
