"""
transparency.py — Component Transparency Classifier (Phase 38)

The control-plane question the event bus was built to answer:

    "For each component in my AI system, can I see what it acted on
     and how certain it was — or is it a black box?"

This module is a pure, read-only consumer of logs/events.db (same posture
as metrics_engine.py — it collects no new data). It groups recent events by
the component that emitted them and classifies each component as:

    transparent  — its events carry BOTH an evidence signal (what it acted
                   on) AND a confidence signal (how certain it was)
    partial      — its events carry one of the two, not both
    opaque       — its events carry neither
    unobserved   — the component exists in the catalog but emitted nothing
                   in the observation window

The classification is derived from the payloads components ALREADY emit,
so a component becomes more transparent simply by enriching its payload —
no interface to implement, no method to add. That is the whole point: the
quarantine in core/contract.py stays lean; transparency is observed, not
mandated.
"""
from __future__ import annotations

from typing import Any, Dict, List

from infrastructure.event_bus import EventType, recent_events

# Stored event types come in two shapes depending on how they were emitted:
#   "query.received"            (the EventType value — the documented form)
#   "EventType.QUERY_RECEIVED"  (str(Enum) repr — what str-Enum produces on
#                                this Python, see classify note below)
# Normalize both to the dotted value before bucketing.
_NAME_TO_VALUE = {f"EventType.{e.name}": e.value for e in EventType}

# ── What counts as a signal ──────────────────────────────────
# A payload key means the component disclosed *how certain* it was.
CONFIDENCE_KEYS = frozenset({
    "confidence", "uncertainty", "total_risk", "risk",
    "score", "signal_conf", "regret",
})
# A payload key means the component disclosed *what it acted on* — the
# evidence/reason behind its action (the essay's "what evidence / why").
EVIDENCE_KEYS = frozenset({
    "issues", "evidence", "recommendation", "reason", "signal", "args",
    "factors", "memory_id", "memory_ids", "source", "sources",
    "query", "steps", "parallel_groups",
})

# ── Component catalog: event-type prefix → human-facing component ──
# Prefix match against EventType values (see infrastructure/event_bus.py).
# Listing a component here lets it report as "unobserved" instead of
# silently vanishing when it has emitted nothing yet.
CATALOG: Dict[str, str] = {
    "query":         "Intake",
    "agent":         "Router",
    "response":      "Responder",
    "plan":          "Planner",
    "step":          "Verifier",
    "risk":          "Risk Gate",
    "reflection":    "Reflector",
    "memory":        "Memory",
    "contradiction": "Memory",
    "routing":       "Learner",
    "learning":      "Learner",
    "world":         "World Model",
    "uci":           "Metrics",
    "tool":          "Tools",
    "delta":         "Dispatch",
}


def _component_for(event_type: str) -> str:
    """Map an event type to its component, tolerating both the dotted-value
    form ('query.received') and the enum-repr form ('EventType.QUERY_RECEIVED')."""
    value = _NAME_TO_VALUE.get(event_type, event_type)
    head = value.split(".", 1)[0]
    return CATALOG.get(head, head or "unknown")


def _status(has_conf: bool, has_evid: bool) -> str:
    if has_conf and has_evid:
        return "transparent"
    if has_conf or has_evid:
        return "partial"
    return "opaque"


def classify_components(window: int = 2000) -> Dict[str, Any]:
    """
    Classify every observed component over the last `window` events.

    Returns:
        {
          "components": [
            {"component", "status", "events", "has_confidence",
             "has_evidence", "confidence_keys", "evidence_keys",
             "sample_event"},
            ...
          ],
          "summary": {"transparent": n, "partial": n,
                      "opaque": n, "unobserved": n},
          "transparency_score": 0.0-1.0,   # share of catalog that is transparent
        }
    """
    events = recent_events(n=window)

    # Aggregate the union of payload keys per component.
    agg: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        comp = _component_for(ev.get("type", ""))
        payload = ev.get("payload") or {}
        keys = {k for k, v in payload.items() if v not in (None, "", [], {})}

        slot = agg.setdefault(comp, {
            "events": 0,
            "conf": set(),
            "evid": set(),
            "sample": None,
        })
        slot["events"] += 1
        slot["conf"] |= (keys & CONFIDENCE_KEYS)
        slot["evid"] |= (keys & EVIDENCE_KEYS)
        if slot["sample"] is None:
            slot["sample"] = {"type": ev.get("type"), "payload": payload}

    rows: List[Dict[str, Any]] = []
    for comp, slot in agg.items():
        has_conf = bool(slot["conf"])
        has_evid = bool(slot["evid"])
        rows.append({
            "component":       comp,
            "status":          _status(has_conf, has_evid),
            "events":          slot["events"],
            "has_confidence":  has_conf,
            "has_evidence":    has_evid,
            "confidence_keys": sorted(slot["conf"]),
            "evidence_keys":   sorted(slot["evid"]),
            "sample_event":    slot["sample"],
        })

    # Surface cataloged components that emitted nothing as "unobserved".
    observed = {r["component"] for r in rows}
    for comp in sorted(set(CATALOG.values())):
        if comp not in observed:
            rows.append({
                "component":       comp,
                "status":          "unobserved",
                "events":          0,
                "has_confidence":  False,
                "has_evidence":    False,
                "confidence_keys": [],
                "evidence_keys":   [],
                "sample_event":    None,
            })

    rows.sort(key=lambda r: (-r["events"], r["component"]))

    summary = {"transparent": 0, "partial": 0, "opaque": 0, "unobserved": 0}
    for r in rows:
        summary[r["status"]] = summary.get(r["status"], 0) + 1

    cataloged = len(set(CATALOG.values()))
    score = round(summary["transparent"] / cataloged, 3) if cataloged else 0.0

    return {
        "components": rows,
        "summary": summary,
        "transparency_score": score,
        "window": window,
    }
