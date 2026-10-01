"""Prompt 02 tests: Structured logging + redaction."""

from __future__ import annotations

import io
import json

import aegis
from aegis import (
    LogLevel,
    Redactor,
    redact_value,
)


def _build_logger_sink():
    buf = io.StringIO()
    sink = aegis.StreamSink if hasattr(aegis, "StreamSink") else None
    if sink is None:
        # Reach in via the logger module directly
        from aegis.l2_foundation.telemetry.logger import StreamSink

        sink = StreamSink
    stream_sink = sink(buf)
    from aegis.l2_foundation.telemetry.logger import JSONFormatter, StructuredLogger

    log = StructuredLogger(
        "test.sink", sinks=[stream_sink], level=LogLevel.DEBUG, formatter=JSONFormatter()
    )
    return log, buf


def test_structured_logger_json_has_correlation_and_fields():
    log, buf = _build_logger_sink()
    cid_ctx = aegis.CorrelationContext.new()
    with cid_ctx.enter():
        log.info("hello", answer=42)
    raw = buf.getvalue().strip().splitlines()
    assert len(raw) == 1
    rec = json.loads(raw[0])
    assert rec["level"] == "INFO"
    assert rec["msg"] == "hello"
    assert rec["logger"] == "test.sink"
    assert rec["correlation_id"] == str(cid_ctx.correlation_id)
    assert rec["meta"]["answer"] == 42


def test_log_level_filters():
    log, buf = _build_logger_sink()
    log.set_level(LogLevel.WARNING)
    log.info("not-seen")
    log.warning("seen")
    lines = buf.getvalue().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["msg"] == "seen"


def test_redact_redacts_api_key_and_password():
    r = Redactor()
    case1 = r.redact({"Authorization": "Bearer eyJfooxxx.yyy.zzz"})
    assert "REDACTED" in str(case1)
    case2 = r.redact("db url: postgres://user:password=s3cret!@host/x")
    assert "s3cret" not in str(case2)
    case3 = r.redact({"API_KEY": "abcdef1234567890abcdef1234567890"})
    assert "REDACTED" in str(case3["API_KEY"])


def test_secret_ref_redacted_by_default():
    val = "secret://providers/groq"
    assert "SECRET_REF" in str(redact_value(val))


def test_exception_logged_as_error_field():
    log, buf = _build_logger_sink()
    try:
        raise RuntimeError("boom")
    except Exception as exc:
        log.error("failed", exc=exc)
    line = buf.getvalue().strip()
    rec = json.loads(line)
    assert rec["error"] is not None
    assert "boom" in rec["error"]
