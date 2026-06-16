"""
Tests for tools/sandbox.py — isolated Python execution under resource limits.

POSIX-only (setrlimit/setsid); skipped elsewhere.
"""

import os
import resource
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not hasattr(os, "setsid"):
    pytest.skip("POSIX sandbox only", allow_module_level=True)

import tools.sandbox as sbx


def test_hello_world_stdout():
    r = sbx.run_python("print('hello sandbox')")
    assert r["exit_code"] == 0
    assert r["stdout"].strip() == "hello sandbox"
    assert r["timed_out"] is False


def test_exception_goes_to_stderr_nonzero():
    r = sbx.run_python("raise ValueError('boom')")
    assert r["exit_code"] != 0
    assert "ValueError" in r["stderr"]


def test_timeout_is_enforced():
    r = sbx.run_python("while True: pass", timeout=1, cpu_seconds=10)
    assert r["timed_out"] is True
    assert r["duration_ms"] >= 900


@pytest.mark.skipif(not hasattr(resource, "RLIMIT_NPROC"),
                    reason="RLIMIT_NPROC unavailable")
def test_nproc_limit_blocks_fork_bomb():
    """RLIMIT_NPROC must stop runaway process creation (S4 fork-bomb guard)."""
    code = (
        "import os, sys\n"
        "n = 0\n"
        "try:\n"
        "    while n < 10000:\n"
        "        if os.fork() == 0:\n"
        "            os._exit(0)\n"
        "        n += 1\n"
        "except OSError:\n"
        "    sys.exit(7)\n"  # hit the NPROC ceiling — the limit held
    )
    r = sbx.run_python(code, timeout=5, nproc=16)
    # What must NOT happen is a clean exit 0 (10k forks all succeeded).
    assert r["exit_code"] != 0


def test_cpu_limit_kills_busy_loop():
    # No wall timeout pressure (high), but CPU rlimit (1s) must terminate it.
    r = sbx.run_python("while True: pass", timeout=20, cpu_seconds=1)
    assert r["exit_code"] != 0  # killed by SIGXCPU or wall fallback


def test_environment_is_scrubbed():
    os.environ["AMAGRA_SECRET_PROBE"] = "leaked-value"
    try:
        r = sbx.run_python(
            "import os; print(os.environ.get('AMAGRA_SECRET_PROBE', 'ABSENT'))"
        )
    finally:
        os.environ.pop("AMAGRA_SECRET_PROBE", None)
    assert r["stdout"].strip() == "ABSENT"


def test_output_is_truncated():
    r = sbx.run_python("print('x' * 100000)", output_limit=1000)
    assert r["truncated"] is True
    assert len(r["stdout"]) <= 1000


def test_empty_code_rejected():
    with pytest.raises(ValueError):
        sbx.run_python("   ")


def test_runs_in_throwaway_cwd():
    # cwd is a fresh temp dir, not the project tree.
    r = sbx.run_python("import os; print(os.listdir('.'))")
    assert r["exit_code"] == 0
    assert r["stdout"].strip() == "[]"
