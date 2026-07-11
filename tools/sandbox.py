"""
tools/sandbox.py — run short Python snippets under resource limits.

The v1.1 "sandboxed code execution" capability. An agent can run the code it
writes and see the output, without that code being able to hog the box or read
the server's environment. Isolation layers:

  * **Interpreter isolation** — ``python3 -I -S``: ignore PYTHONPATH/PYTHON*,
    don't add cwd or user-site to sys.path, skip site customization.
  * **Resource limits** (POSIX ``setrlimit`` in a ``preexec_fn``) — CPU seconds,
    address space (memory), output file size, process/thread count (fork-bomb
    guard), and core dumps disabled.
  * **Scrubbed environment** — the child gets a minimal env (just PATH + a temp
    HOME/TMPDIR), so server secrets in ``os.environ`` are never inherited.
  * **Throwaway cwd** — runs in a fresh temp directory, removed afterward.
  * **Wall-clock timeout** — the whole process group is killed on timeout.
  * **OS-level jail** (when available) — execution is wrapped in bubblewrap
    (``bwrap``) with ``--unshare-all``: the child sees only /usr, /bin and /lib*
    read-only plus its throwaway workdir, and has **no network**. Detected once
    at first use; ``AMAGRA_SANDBOX_NO_BWRAP=1`` forces it off.

Blast radius WITHOUT bwrap (``isolation_mode() == "rlimit-only"``): the child
keeps the server's filesystem view and network access, so any caller of the
sandbox can read every file the server user can read and make outbound
connections. That mode is a resource jail, NOT a security boundary — never
enable ``AMAGRA_SANDBOX=1`` on a shared or internet-exposed host without
bubblewrap installed (#134). ``GET /sandbox/status`` reports the active mode.
"""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

# `resource` (setrlimit) is POSIX-only and absent on Windows. Import it lazily so
# this module — pulled in unconditionally via routes/sandbox.py → api.py — never
# crashes app startup on Windows. The sandbox itself needs POSIX resource limits
# to be a real jail, so run_python() refuses to run without it (see below); the
# rest of the backend boots normally. The route is opt-in (AMAGRA_SANDBOX=1).
try:
    import resource
except ImportError:  # non-POSIX (Windows)
    resource = None

DEFAULT_TIMEOUT = 5            # wall-clock seconds
DEFAULT_CPU_SECONDS = 5        # RLIMIT_CPU
DEFAULT_MEM_BYTES = 512 * 1024 * 1024   # RLIMIT_AS (512 MB)
DEFAULT_FSIZE_BYTES = 16 * 1024 * 1024  # RLIMIT_FSIZE (16 MB)
DEFAULT_NPROC = 64             # RLIMIT_NPROC — cap subprocesses/threads (fork-bomb guard)
DEFAULT_OUTPUT_LIMIT = 64 * 1024        # bytes of stdout/stderr kept
MAX_CODE_BYTES = 256 * 1024

# Interpreter that exists INSIDE the jail. sys.executable may live in a venv
# under $HOME, which the jail deliberately hides — use the system python there.
_JAILED_PYTHON = shutil.which("python3", path="/usr/bin:/bin")

_isolation: str | None = None  # detected once, cached ("bwrap" | "rlimit-only")

# Where the submitted code appears inside the jail — outside the workdir, so
# the sandboxed cwd stays a pristine empty directory.
_JAIL_CODE_PATH = "/run/amagra/main.py"


def _bwrap_args(workdir: str, code_file: str | None = None) -> list[str]:
    """bwrap argv prefix: read-only system dirs, the workdir, nothing else.

    --unshare-all covers net/pid/ipc/uts/user/cgroup. /etc is intentionally
    NOT bound (python runs without it; it can hold host secrets) — only
    ld.so.cache, best-effort, for linker speed. Later args mount over earlier
    ones, so the workdir bind must follow the /tmp tmpfs.
    """
    args = ["bwrap"]
    for d in ("/usr", "/bin", "/lib", "/lib64"):
        if os.path.isdir(d):
            args += ["--ro-bind", d, d]
    args += [
        "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--tmpfs", "/tmp",
        "--proc", "/proc",
        "--dev", "/dev",
        "--bind", workdir, workdir,
        "--chdir", workdir,
    ]
    if code_file:
        args += ["--ro-bind", code_file, _JAIL_CODE_PATH]
    args += [
        "--unshare-all",
        "--die-with-parent",
        "--",
    ]
    return args


def isolation_mode() -> str:
    """"bwrap" when the OS-level jail is active, else "rlimit-only".

    Probed once per process by actually running a snippet inside the jail —
    bwrap can be installed yet unusable (kernel/apparmor restrictions on
    unprivileged user namespaces), so presence of the binary isn't enough.
    """
    global _isolation
    if _isolation is None:
        _isolation = "bwrap" if _bwrap_usable() else "rlimit-only"
    return _isolation


def _bwrap_usable() -> bool:
    if os.environ.get("AMAGRA_SANDBOX_NO_BWRAP", "0") == "1":
        return False
    if resource is None or not _JAILED_PYTHON or not shutil.which("bwrap"):
        return False
    probe_dir = tempfile.mkdtemp(prefix="amagra-sbx-probe-")
    try:
        r = subprocess.run(
            _bwrap_args(probe_dir) + [_JAILED_PYTHON, "-I", "-S", "-c", "print('ok')"],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0 and r.stdout.strip() == "ok"
    except Exception:
        return False
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)


def _preexec(cpu_seconds: int, mem_bytes: int, fsize_bytes: int, nproc: int):
    """Return a child-side hook that drops resource limits and starts a new session.

    Returns None when `resource` is unavailable (non-POSIX) — subprocess requires
    preexec_fn=None there. run_python() blocks that path anyway, so this is belt-
    and-suspenders.
    """
    if resource is None:
        return None

    def _apply():
        os.setsid()  # own process group, so a timeout can kill the whole tree
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if mem_bytes:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # Cap process/thread creation so sandboxed code can't fork-bomb the host.
        if nproc and hasattr(resource, "RLIMIT_NPROC"):
            resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
    return _apply


def run_python(code: str,
               timeout: float = DEFAULT_TIMEOUT,
               cpu_seconds: int = DEFAULT_CPU_SECONDS,
               mem_bytes: int = DEFAULT_MEM_BYTES,
               fsize_bytes: int = DEFAULT_FSIZE_BYTES,
               output_limit: int = DEFAULT_OUTPUT_LIMIT,
               nproc: int = DEFAULT_NPROC) -> dict:
    """Execute `code` in an isolated subprocess. Never raises for runtime errors.

    Returns {stdout, stderr, exit_code, timed_out, duration_ms, truncated,
    isolation} — `isolation` is "bwrap" (OS-level jail) or "rlimit-only".
    """
    if resource is None:
        # No POSIX setrlimit → we can't cap CPU/memory/forks, so this stops being a
        # resource jail. Refuse rather than run arbitrary code unbounded. (Windows.)
        raise RuntimeError(
            "code sandbox requires a POSIX host (resource limits unavailable on this platform)"
        )
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
    isolation = isolation_mode()
    if isolation == "bwrap":
        # RLIMIT_NPROC counts ALL processes of the real UID, so applying it in
        # preexec would make bwrap's own clone() fail (EAGAIN) on any host where
        # the user runs more than `nproc` processes. Set it INSIDE the jail
        # instead, after bwrap has spawned the interpreter but before user code
        # runs. User code is ro-bound at _JAIL_CODE_PATH (keeping the cwd
        # pristine — the file is a sibling of the workdir, not inside it) and
        # run via compile('<sandbox>') so its traceback line numbers survive
        # the bootstrap prefix.
        code_path = workdir + ".code.py"
        with open(code_path, "w", encoding="utf-8") as fh:
            fh.write(code)
        boot = ""
        if nproc:
            boot = (f"import resource as _r; "
                    f"_r.setrlimit(_r.RLIMIT_NPROC, ({nproc}, {nproc})); del _r; ")
        boot += (f"exec(compile(open({_JAIL_CODE_PATH!r}, encoding='utf-8').read(), "
                 f"'<sandbox>', 'exec'))")
        cmd = (_bwrap_args(workdir, code_file=code_path)
               + [_JAILED_PYTHON, "-I", "-S", "-c", boot])
        preexec_nproc = 0
    else:
        cmd = [sys.executable, "-I", "-S", "-c", code]
        preexec_nproc = nproc
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=workdir, env=env, text=True,
            # CPU/memory/fsize rlimits apply to bwrap itself and are inherited
            # by the jailed child — those stay active in both isolation modes.
            preexec_fn=_preexec(cpu_seconds, mem_bytes, fsize_bytes, preexec_nproc),
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
        try:
            os.unlink(workdir + ".code.py")
        except OSError:
            pass

    duration_ms = int((time.monotonic() - started) * 1000)
    truncated = len(stdout) > output_limit or len(stderr) > output_limit
    return {
        "stdout": stdout[:output_limit],
        "stderr": stderr[:output_limit],
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "truncated": truncated,
        "isolation": isolation,
    }
