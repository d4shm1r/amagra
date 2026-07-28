"""
The internal (non-fatal) failure sink — #196.

Telemetry, tracing and COS emissions are best-effort by design: a failed trace
must never fail the user's request. They were therefore wrapped in
`except Exception: pass`, which made the observability layer itself
unobservable — it could be broken indefinitely with nothing to notice it by.

These tests pin the two halves of the contract that replaced it:
  1. the caller is still unaffected (nothing propagates, nothing raises),
  2. the failure leaves evidence (a counter + a log record).

Run: python3 -m pytest tests/test_internal_failure_sink.py -v
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.logger as logger  # noqa: E402


def setup_function():
    logger.reset_internal_failures()


# ── the sink itself ──────────────────────────────────────────────────────────

def test_counts_by_component():
    logger.log_internal_failure("telemetry.routing", ValueError("x"))
    logger.log_internal_failure("telemetry.routing", ValueError("y"))
    logger.log_internal_failure("cos.emit.plan_created", KeyError("z"))
    assert logger.internal_failure_counts() == {
        "telemetry.routing": 2,
        "cos.emit.plan_created": 1,
    }


def test_counts_snapshot_is_a_copy():
    logger.log_internal_failure("telemetry.traces", ValueError("x"))
    snap = logger.internal_failure_counts()
    snap["telemetry.traces"] = 999
    assert logger.internal_failure_counts()["telemetry.traces"] == 1


def test_reset_clears():
    logger.log_internal_failure("telemetry.sessions", ValueError("x"))
    logger.reset_internal_failures()
    assert logger.internal_failure_counts() == {}


def test_emits_a_warning_with_component_and_type(caplog):
    with caplog.at_level(logging.WARNING, logger="amagra.internal"):
        logger.log_internal_failure("telemetry.traces", KeyError("missing"))
    msg = caplog.text
    assert "telemetry.traces" in msg
    assert "KeyError" in msg


def test_empty_exception_message_never_logs_blank():
    # The #193 lesson: bare httpx/asyncio timeouts stringify to "". A sink that
    # logged str(exc) verbatim would record a failure with no discernible cause.
    import httpx
    assert str(httpx.ReadTimeout("")) == ""
    with_caplog = logging.getLogger("amagra.internal")
    records = []
    h = logging.Handler(); h.emit = records.append
    with_caplog.addHandler(h)
    try:
        logger.log_internal_failure("telemetry.routing", httpx.ReadTimeout(""))
    finally:
        with_caplog.removeHandler(h)
    assert records and "(no message)" in records[0].getMessage()


def test_detail_is_included_when_given(caplog):
    with caplog.at_level(logging.WARNING, logger="amagra.internal"):
        logger.log_internal_failure("telemetry.routing", ValueError("x"), detail="run_id=abc")
    assert "run_id=abc" in caplog.text


def test_sink_never_raises_even_if_logging_breaks(monkeypatch):
    # A failure inside the failure logger must not escalate into the request
    # failure the bare `pass` existed to prevent.
    def boom(*a, **k):
        raise RuntimeError("logging backend down")

    monkeypatch.setattr(logger._internal_log, "warning", boom)
    logger.log_internal_failure("telemetry.routing", ValueError("x"))  # must not raise


# ── wired into a real telemetry path ─────────────────────────────────────────

def test_failing_telemetry_write_is_recorded_and_does_not_propagate(monkeypatch):
    import routes.ask_pipeline as ap

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ap.sqlite3, "connect", boom)

    # The caller sees nothing — the request path is exactly as unaffected as
    # it was under `except Exception: pass`.
    ap._log_telemetry("what is 2+2", "python_dev", 0.91, "simple", 12)

    # ...but the failure is no longer invisible.
    assert logger.internal_failure_counts().get("telemetry.routing") == 1
