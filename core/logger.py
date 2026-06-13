import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "changes.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

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
