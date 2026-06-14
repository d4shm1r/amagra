"""
tools/sandbox.py — run short Python snippets under resource limits.

The v1.1 "sandboxed code execution" capability. An agent can run the code it
writes and see the output, without that code being able to hog the box or read
the server's environment. Isolation layers:

  * **Interpreter isolation** — ``python3 -I -S``: ignore PYTHONPATH/PYTHON*,
    don't add cwd or user-site to sys.path, skip site customization.
  * **Resource limits** (POSIX ``setrlimit`` in a ``preexec_fn``) — CPU seconds,
    address space (memory), output file size, and core dumps disabled.
  * **Scrubbed environment** — the child gets a minimal env (just PATH + a temp
    HOME/TMPDIR), so server secrets in ``os.environ`` are never inherited.
  * **Throwaway cwd** — runs in a fresh temp directory, removed afterward.
  * **Wall-clock timeout** — the whole process group is killed on timeout.

Not isolated: **network**. Blocking it requires namespaces/root, which a
self-hosted single-process server can't assume. Treat this as a resource jail,
not a security boundary against a determined adversary — gate the route
(``AMAGRA_SANDBOX=1``) before exposing it.
"""

import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time

DEFAULT_TIMEOUT = 5            # wall-clock seconds
DEFAULT_CPU_SECONDS = 5        # RLIMIT_CPU
DEFAULT_MEM_BYTES = 512 * 1024 * 1024   # RLIMIT_AS (512 MB)
DEFAULT_FSIZE_BYTES = 16 * 1024 * 1024  # RLIMIT_FSIZE (16 MB)
DEFAULT_OUTPUT_LIMIT = 64 * 1024        # bytes of stdout/stderr kept
MAX_CODE_BYTES = 256 * 1024


def _preexec(cpu_seconds: int, mem_bytes: int, fsize_bytes: int):
    """Return a child-side hook that drops resource limits and starts a new session."""
    def _apply():
        os.setsid()  # own process group, so a timeout can kill the whole tree
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if mem_bytes:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return _apply


def run_python(code: str,
               timeout: float = DEFAULT_TIMEOUT,
               cpu_seconds: int = DEFAULT_CPU_SECONDS,
               mem_bytes: int = DEFAULT_MEM_BYTES,
               fsize_bytes: int = DEFAULT_FSIZE_BYTES,
               output_limit: int = DEFAULT_OUTPUT_LIMIT) -> dict:
    """Execute `code` in an isolated subprocess. Never raises for runtime errors.

    Returns {stdout, stderr, exit_code, timed_out, duration_ms, truncated}.
    """
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code must be a non-empty string")
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise ValueError(f"code exceeds {MAX_CODE_BYTES} bytes")

    workdir = tempfile.mkdtemp(prefix="amagra-sbx-")
    # Minimal env — no inherited secrets; HOME/TMP point inside the throwaway dir.
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": workdir,
        "TMPDIR": workdir,
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", code],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=workdir, env=env, text=True,
            preexec_fn=_preexec(cpu_seconds, mem_bytes, fsize_bytes),
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = proc.communicate()
            exit_code = -signal.SIGKILL
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    duration_ms = int((time.monotonic() - started) * 1000)
    truncated = len(stdout) > output_limit or len(stderr) > output_limit
    return {
        "stdout": stdout[:output_limit],
        "stderr": stderr[:output_limit],
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "truncated": truncated,
    }
