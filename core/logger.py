import logging
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "changes.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


# ── Internal (non-fatal) failure sink — #196 ─────────────────────────────────

_internal_log = logging.getLogger("amagra.internal")

# Bounded by construction: callers pass string literals from a small fixed set,
# so this cannot grow per-request the way #194's rate-limit window did.
_internal_failures: dict[str, int] = {}


def log_internal_failure(component: str, exc: BaseException, *, detail: str = "") -> None:
    """Record a deliberately non-fatal failure instead of swallowing it.

    Telemetry, tracing and snapshot writes are best-effort by design — a failed
    trace must never fail the user's request, which is why they were wrapped in
    `except Exception: pass`. But that makes the observability layer itself
    unobservable: it can be broken for weeks with nothing to notice it by. This
    keeps the request path exactly as unaffected while leaving evidence behind.

    Routes to `logging` rather than a file so it adds no new path to manage and
    no test-isolation surface — it inherits whatever handlers the host config.

    Never raises: a failure in the failure logger must not escalate into the
    request failure the bare `pass` existed to prevent.
    """
    try:
        _internal_failures[component] = _internal_failures.get(component, 0) + 1
        _internal_log.warning(
            "internal failure in %s: %s: %s%s",
            component,
            type(exc).__name__,
            # Bare timeouts stringify to "" (see #193) — never log a blank cause.
            str(exc) or "(no message)",
            f" [{detail}]" if detail else "",
        )
    except Exception:
        pass


def internal_failure_counts() -> dict[str, int]:
    """Failure counts by component since process start (or the last reset).

    Queryable so the swallowed failures become a signal, not just log noise.
    """
    return dict(_internal_failures)


def reset_internal_failures() -> None:
    """Clear the counters — for tests and for a future /health surface."""
    _internal_failures.clear()

def log_event(event_type: str, detail: str, agent: str = "system"):
    """Write a timestamped event to the change log."""
    ts    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line  = f"[{ts}] {event_type:<10} agent={agent:<20} {detail}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(line)

def ask_permission(action: str, path: str, agent: str) -> bool:
    """Ask user permission before writing to disk."""
    print(f"\n📝 [{agent}] wants to write:")
    print(f"   → {path}")
    print(f"   Action: {action}")
    answer = input("   Allow? [y/n]: ").strip().lower()
    allowed = answer == 'y'
    log_event(
        "WRITE" if allowed else "SKIP",
        f"path={path}",
        agent
    )
    return allowed

def log_routing(task: str, agent: str, reason: str):
    """Log every coordinator routing decision."""
    log_event("ROUTE", f"→{agent:<20} reason='{reason}' task='{task[:60]}'", "coordinator")

def log_response(agent: str, task: str):
    """Log every agent response."""
    log_event("RESPOND", f"task='{task[:60]}'", agent)

def read_log(last_n: int = 50) -> list:
    """Read last N log entries as list of dicts."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()
    entries = []
    for line in lines[-last_n:]:
        line = line.strip()
        if not line:
            continue
        try:
            ts        = line[1:20]
            rest      = line[22:]
            parts     = rest.split()
            etype     = parts[0] if parts else "INFO"
            entries.append({"ts": ts, "type": etype, "detail": rest})
        except Exception:
            entries.append({"ts": "", "type": "INFO", "detail": line})
    return list(reversed(entries))
