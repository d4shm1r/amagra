# ~/agentic-ai/report_generator.py
# ─────────────────────────────────────────────────────────────
# Diagnostic Report Generator — v0 (inward-facing)
#
# Synthesizes findings from all analytics subsystems into a
# single human-readable HTML report.
#
# Pipeline:
#   failure_miner  → routing failures + regret clusters
#   specialization → per-agent structural health
#   coherence      → system-level C(t) snapshot
#   counterfactual → top routing improvement candidates
#
# Output: logs/diagnostic_report_<timestamp>.html
#
# Usage:
#   python3 report_generator.py              # generate + open
#   python3 report_generator.py --json       # also dump JSON
#   python3 report_generator.py --out PATH   # custom output path
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import os
import sys
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_LOGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


# ── Data model ────────────────────────────────────────────────

@dataclass
class AgentHealth:
    name:           str
    decisions:      int
    conflict_rate:  float
    avg_regret:     float
    avg_quality:    float
    verdict:        str
    verdict_reason: str
    top_domain:     str
    action_dist:    dict = field(default_factory=dict)

    @property
    def health_score(self) -> float:
        """0–1 composite: low conflict, low regret, high quality."""
        return round(
            (1 - self.conflict_rate) * 0.35
            + max(0.0, 1 - self.avg_regret * 4) * 0.25
            + self.avg_quality * 0.40,
            3,
        )


@dataclass
class FailureCase:
    decision_id: int
    agent:       str
    action:      str
    regret:      float
    query:       str


@dataclass
class CounterfactualOpportunity:
    decision_id:    int
    query:          str
    original_agent: str
    suggested_alt:  str | None
    regret:         float
    conflict:       bool
    priority:       str


@dataclass
class ReportData:
    generated_at:   str
    window:         int

    # System-level
    total_decisions:    int
    conflict_rate:      float
    reflection_rate:    float
    avg_regret:         float
    coherence:          float
    c_routing:          float
    c_calib:            float
    c_quality:          float
    g_r_mean:           float
    mem_avg_quality:    float
    mem_count:          int

    # Per-agent
    agents:             list[AgentHealth] = field(default_factory=list)

    # Failures
    top_failures:       list[FailureCase] = field(default_factory=list)
    conflict_clusters:  dict = field(default_factory=dict)   # agent → {rate, n}
    action_clusters:    dict = field(default_factory=dict)   # action → {count, avg_regret}

    # Counterfactuals
    cf_candidates:      list[CounterfactualOpportunity] = field(default_factory=list)

    # Derived
    overall_health:     float = 0.0
    health_label:       str   = "UNKNOWN"


# ── Collection ────────────────────────────────────────────────

def collect(window: int = 20) -> ReportData:
    """Pull data from all analytics subsystems and assemble ReportData."""

    print("[report] loading coherence...", flush=True)
    try:
        from cognition.coherence import current_coherence
        coh = current_coherence(window)
        coherence_val  = coh.C
        c_routing      = coh.c_routing
        c_calib        = coh.c_calib
        c_quality      = coh.c_quality
        g_r_mean       = coh.G_r_mean
        mem_avg_quality = coh.mem_avg_quality
        mem_count      = coh.mem_n
    except Exception as e:
        print(f"[report] coherence unavailable: {e}")
        coherence_val = c_routing = c_calib = c_quality = 0.0
        g_r_mean = mem_avg_quality = 0.0
        mem_count = 0

    print("[report] loading failure miner...", flush=True)
    try:
        from cognition.failure_miner import mine
        fm = mine(500)
        total_decisions  = fm.get("total_decisions", 0)
        conflict_rate    = fm.get("summary", {}).get("conflict_rate", 0.0)
        reflection_rate  = fm.get("summary", {}).get("reflection_rate", 0.0)
        avg_regret       = fm.get("summary", {}).get("avg_regret", 0.0)
        top_failures     = [
            FailureCase(
                decision_id = f["id"],
                agent       = f["agent"],
                action      = f["action"],
                regret      = f["regret"],
                query       = f["task"],
            )
            for f in fm.get("top_failure_tasks", [])
        ]
        conflict_clusters = {
            a: {"rate": v["conflict_rate"], "n": v["total"]}
            for a, v in fm.get("conflict_by_agent", {}).items()
        }
        action_clusters = fm.get("action_clusters", {})
    except Exception as e:
        print(f"[report] failure_miner unavailable: {e}")
        total_decisions = 0
        conflict_rate = reflection_rate = avg_regret = 0.0
        top_failures = []
        conflict_clusters = {}
        action_clusters = {}

    print("[report] loading specialization...", flush=True)
    try:
        from training.specialization import compute
        spec = compute()
        agents = [
            AgentHealth(
                name           = name,
                decisions      = r["total_decisions"],
                conflict_rate  = r["conflict_rate"],
                avg_regret     = r["avg_regret"],
                avg_quality    = r["avg_quality_proxy"],
                verdict        = r.get("verdict") or "unknown",
                verdict_reason = r.get("verdict_reason") or "",
                top_domain     = r.get("top_domain", ""),
                action_dist    = r.get("action_distribution", {}),
            )
            for name, r in sorted(spec.items(), key=lambda x: -x[1]["total_decisions"])
        ]
    except Exception as e:
        print(f"[report] specialization unavailable: {e}")
        agents = []

    print("[report] loading counterfactual candidates...", flush=True)
    try:
        from cognition.counterfactual import top_counterfactual_candidates
        cf_raw = top_counterfactual_candidates(8)
        cf_candidates = [
            CounterfactualOpportunity(
                decision_id    = c["decision_id"],
                query          = c["query"],
                original_agent = c["original_agent"],
                suggested_alt  = c["suggested_alt"],
                regret         = c["regret"],
                conflict       = c["conflict"],
                priority       = c["priority"],
            )
            for c in cf_raw
        ]
    except Exception as e:
        print(f"[report] counterfactual unavailable: {e}")
        cf_candidates = []

    # Overall health: weighted composite
    overall = round(
        coherence_val * 0.35
        + (1 - conflict_rate) * 0.30
        + (1 - min(avg_regret * 4, 1.0)) * 0.20
        + mem_avg_quality * 0.15,
        3,
    )

    if overall >= 0.80:
        label = "HEALTHY"
    elif overall >= 0.65:
        label = "MODERATE"
    elif overall >= 0.50:
        label = "DEGRADED"
    else:
        label = "CRITICAL"

    return ReportData(
        generated_at     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        window           = window,
        total_decisions  = total_decisions,
        conflict_rate    = conflict_rate,
        reflection_rate  = reflection_rate,
        avg_regret       = avg_regret,
        coherence        = coherence_val,
        c_routing        = c_routing,
        c_calib          = c_calib,
        c_quality        = c_quality,
        g_r_mean         = g_r_mean,
        mem_avg_quality  = mem_avg_quality,
        mem_count        = mem_count,
        agents           = agents,
        top_failures     = top_failures,
        conflict_clusters = conflict_clusters,
        action_clusters  = action_clusters,
        cf_candidates    = cf_candidates,
        overall_health   = overall,
        health_label     = label,
    )


# ── HTML rendering ────────────────────────────────────────────

def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"

def _score(v: float) -> str:
    return f"{v:.3f}"

def _bar(v: float, w: int = 120) -> str:
    """Mini SVG bar for tables."""
    fill = "#2C5F8A" if v >= 0.7 else ("#E07B00" if v >= 0.5 else "#B03030")
    return (
        f'<svg width="{w}" height="10" style="vertical-align:middle">'
        f'<rect width="{w}" height="10" rx="3" fill="#e8e8e8"/>'
        f'<rect width="{int(v * w)}" height="10" rx="3" fill="{fill}"/>'
        f'</svg>'
    )

def _verdict_badge(v: str) -> str:
    colors = {
        "core":       ("#1A4A1A", "#C8E6C9"),
        "narrow":     ("#6A4A00", "#FFF9C4"),
        "struggling": ("#7B1A1A", "#FFCDD2"),
        "redundant":  ("#1A2A4A", "#BBDEFB"),
    }
    fg, bg = colors.get(v, ("#333", "#eee"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:10px;font-size:11px;font-weight:600">{v.upper()}</span>'
    )

def _health_badge(label: str, score: float) -> str:
    colors = {
        "HEALTHY":  ("#1A4A1A", "#C8E6C9"),
        "MODERATE": ("#6A4A00", "#FFF9C4"),
        "DEGRADED": ("#7B1A1A", "#FFCDD2"),
        "CRITICAL": ("#5A0000", "#FF8A80"),
    }
    fg, bg = colors.get(label, ("#333", "#eee"))
    return (
        f'<span style="background:{bg};color:{fg};padding:4px 14px;'
        f'border-radius:12px;font-size:13px;font-weight:700;'
        f'letter-spacing:0.5px">{label} {score:.3f}</span>'
    )

def _priority_badge(p: str) -> str:
    if p == "high":
        return '<span style="background:#FFCDD2;color:#7B1A1A;padding:1px 7px;border-radius:8px;font-size:11px">HIGH</span>'
    return '<span style="background:#FFF9C4;color:#6A4A00;padding:1px 7px;border-radius:8px;font-size:11px">MED</span>'


def _section(title: str, body: str, anchor: str = "") -> str:
    aid = f' id="{anchor}"' if anchor else ""
    return f"""
<section{aid} style="margin:2em 0 1em;border-radius:8px;overflow:hidden;
  box-shadow:0 1px 4px rgba(0,0,0,.10)">
  <div style="background:#2C5F8A;color:#fff;padding:10px 18px;
    font-size:15px;font-weight:600;letter-spacing:0.3px">{title}</div>
  <div style="padding:18px;background:#fff">{body}</div>
</section>"""


def _kv_grid(*pairs) -> str:
    """Responsive key-value grid for summary stats."""
    cells = "".join(
        f'<div style="background:#F4F8FC;border-radius:8px;padding:14px 18px;'
        f'min-width:140px;flex:1">'
        f'<div style="color:#555;font-size:11px;text-transform:uppercase;'
        f'letter-spacing:0.5px;margin-bottom:4px">{k}</div>'
        f'<div style="font-size:20px;font-weight:700;color:#1a1a2e">{v}</div>'
        f'</div>'
        for k, v in pairs
    )
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:8px">'
        f'{cells}</div>'
    )


def render_html(d: ReportData) -> str:
    # ── Executive summary ──────────────────────────────────────
    exec_body = f"""
{_kv_grid(
    ("Total Decisions",  str(d.total_decisions)),
    ("Coherence C(t)",   _score(d.coherence)),
    ("Conflict Rate",    _pct(d.conflict_rate)),
    ("Avg Regret",       _score(d.avg_regret)),
    ("Reflection Rate",  _pct(d.reflection_rate)),
    ("Memory Bank",      f"{d.mem_count} records"),
    ("Mem Avg Quality",  _score(d.mem_avg_quality)),
    ("Reflection Gain",  f"{d.g_r_mean:+.4f}"),
)}
<p style="margin-top:16px;color:#444;font-size:13px">
  System health assessed over the most recent {d.window} decisions.
  Coherence is the composite of routing consistency, calibration accuracy,
  and response quality (C = {_pct(d.coherence)}).
</p>"""

    # ── Coherence breakdown ────────────────────────────────────
    coh_rows = "".join(
        f"<tr><td style='padding:8px 12px'>{name}</td>"
        f"<td style='padding:8px 12px'>{_bar(val)}</td>"
        f"<td style='padding:8px 12px;font-weight:600'>{_score(val)}</td>"
        f"<td style='padding:8px 12px;color:#555;font-size:12px'>{desc}</td></tr>"
        for name, val, desc in [
            ("C_routing",  d.c_routing, "1 − conflict_rate — brain/router agreement"),
            ("C_calib",    d.c_calib,   "1 − mean|calibration bias| per agent"),
            ("C_quality",  d.c_quality, "Mean proxy performance over window"),
            ("C(t)",       d.coherence, "Composite (equal-weight average)"),
        ]
    )
    coh_body = f"""
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#F4F8FC;font-size:12px;text-transform:uppercase;color:#666">
    <th style="padding:8px 12px;text-align:left">Component</th>
    <th style="padding:8px 12px;text-align:left">Score</th>
    <th style="padding:8px 12px;text-align:left">Value</th>
    <th style="padding:8px 12px;text-align:left">Definition</th>
  </tr></thead>
  <tbody>{coh_rows}</tbody>
</table>
<p style="margin-top:12px;font-size:12px;color:#666">
  Reflection gain G<sub>r</sub> = s<sub>final</sub> − s<sub>initial</sub>:
  mean = {d.g_r_mean:+.4f}.
  {"✓ Reflection is non-destructive." if d.g_r_mean >= 0 else "⚠ Mean gain is negative — reflection may be degrading responses."}
</p>"""

    # ── Agent specialization ───────────────────────────────────
    if d.agents:
        agent_rows = "".join(
            f"<tr style='border-top:1px solid #eee'>"
            f"<td style='padding:9px 12px;font-weight:600;font-family:monospace'>{a.name}</td>"
            f"<td style='padding:9px 12px;text-align:center'>{a.decisions}</td>"
            f"<td style='padding:9px 12px'>{_bar(1 - a.conflict_rate, 90)} {_pct(a.conflict_rate)}</td>"
            f"<td style='padding:9px 12px'>{_bar(max(0.0, 1 - a.avg_regret * 4), 90)} {_score(a.avg_regret)}</td>"
            f"<td style='padding:9px 12px'>{_bar(a.avg_quality, 90)} {_score(a.avg_quality)}</td>"
            f"<td style='padding:9px 12px;text-align:center'>{_bar(a.health_score, 60)} {_score(a.health_score)}</td>"
            f"<td style='padding:9px 12px'>{_verdict_badge(a.verdict)}</td>"
            f"</tr>"
            for a in d.agents
        )
        agent_body = f"""
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#F4F8FC;font-size:12px;text-transform:uppercase;color:#666">
    <th style="padding:8px 12px;text-align:left">Agent</th>
    <th style="padding:8px 12px;text-align:center">N</th>
    <th style="padding:8px 12px;text-align:left">Conflict Rate</th>
    <th style="padding:8px 12px;text-align:left">Avg Regret</th>
    <th style="padding:8px 12px;text-align:left">Avg Quality</th>
    <th style="padding:8px 12px;text-align:left">Health</th>
    <th style="padding:8px 12px;text-align:left">Verdict</th>
  </tr></thead>
  <tbody>{agent_rows}</tbody>
</table>"""
    else:
        agent_body = "<p style='color:#888'>No specialization data available.</p>"

    # ── Conflict analysis ──────────────────────────────────────
    if d.conflict_clusters:
        conf_rows = "".join(
            f"<tr style='border-top:1px solid #eee'>"
            f"<td style='padding:8px 12px;font-family:monospace'>{a}</td>"
            f"<td style='padding:8px 12px'>{_bar(v['rate'], 100)} {_pct(v['rate'])}</td>"
            f"<td style='padding:8px 12px;color:#555'>{v['n']} decisions</td>"
            f"<td style='padding:8px 12px;font-size:12px;color:#888'>"
            f"{'⚠ Structural routing conflict' if v['rate'] > 0.40 else 'Within normal range'}"
            f"</td></tr>"
            for a, v in sorted(d.conflict_clusters.items(), key=lambda x: -x[1]["rate"])
        )
        conf_body = f"""
<p style="margin-bottom:12px;color:#444;font-size:13px">
  A conflict occurs when the core brain overrides the keyword router.
  Rates above 40% indicate a structural routing gap, not a tuning issue.
</p>
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#F4F8FC;font-size:12px;text-transform:uppercase;color:#666">
    <th style="padding:8px 12px;text-align:left">Agent</th>
    <th style="padding:8px 12px;text-align:left">Conflict Rate</th>
    <th style="padding:8px 12px;text-align:left">Volume</th>
    <th style="padding:8px 12px;text-align:left">Assessment</th>
  </tr></thead>
  <tbody>{conf_rows}</tbody>
</table>"""
    else:
        conf_body = "<p style='color:#888'>No conflict data available.</p>"

    # ── Top failure cases ──────────────────────────────────────
    if d.top_failures:
        fail_rows = "".join(
            f"<tr style='border-top:1px solid #eee'>"
            f"<td style='padding:8px 12px;color:#888;font-size:12px'>#{f.decision_id}</td>"
            f"<td style='padding:8px 12px;font-family:monospace;font-size:12px'>{f.agent}</td>"
            f"<td style='padding:8px 12px'><span style='background:#EEF4FB;padding:2px 6px;"
            f"border-radius:4px;font-size:11px'>{f.action}</span></td>"
            f"<td style='padding:8px 12px;color:#B03030;font-weight:600'>{_score(f.regret)}</td>"
            f"<td style='padding:8px 12px;font-size:12px;color:#444;max-width:340px;"
            f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{f.query}</td>"
            f"</tr>"
            for f in d.top_failures
        )
        fail_body = f"""
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#F4F8FC;font-size:12px;text-transform:uppercase;color:#666">
    <th style="padding:8px 12px">ID</th>
    <th style="padding:8px 12px;text-align:left">Agent</th>
    <th style="padding:8px 12px;text-align:left">Action</th>
    <th style="padding:8px 12px;text-align:left">Regret</th>
    <th style="padding:8px 12px;text-align:left">Query</th>
  </tr></thead>
  <tbody>{fail_rows}</tbody>
</table>"""
    else:
        fail_body = "<p style='color:#888'>No high-regret decisions found (threshold 0.25).</p>"

    # ── Counterfactual opportunities ───────────────────────────
    if d.cf_candidates:
        cf_rows = "".join(
            f"<tr style='border-top:1px solid #eee'>"
            f"<td style='padding:8px 12px;color:#888;font-size:12px'>#{c.decision_id}</td>"
            f"<td style='padding:8px 12px;font-family:monospace;font-size:12px'>{c.original_agent}</td>"
            f"<td style='padding:8px 12px;font-family:monospace;font-size:12px;color:#2C5F8A'>"
            f"{c.suggested_alt or '—'}</td>"
            f"<td style='padding:8px 12px;font-weight:600;color:#B03030'>{_score(c.regret)}</td>"
            f"<td style='padding:8px 12px'>{_priority_badge(c.priority)}</td>"
            f"<td style='padding:8px 12px;font-size:12px;color:#444;max-width:280px;"
            f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{c.query}</td>"
            f"</tr>"
            for c in d.cf_candidates
        )
        cf_body = f"""
<p style="margin-bottom:12px;color:#444;font-size:13px">
  Decisions ranked by regret × conflict for counterfactual investigation.
  "Suggested alt" is the router's preferred agent when the brain overrode it.
  Statistical validity requires 400+ real sessions.
</p>
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#F4F8FC;font-size:12px;text-transform:uppercase;color:#666">
    <th style="padding:8px 12px">ID</th>
    <th style="padding:8px 12px;text-align:left">Chosen</th>
    <th style="padding:8px 12px;text-align:left">Alt</th>
    <th style="padding:8px 12px;text-align:left">Regret</th>
    <th style="padding:8px 12px;text-align:left">Priority</th>
    <th style="padding:8px 12px;text-align:left">Query</th>
  </tr></thead>
  <tbody>{cf_rows}</tbody>
</table>"""
    else:
        cf_body = "<p style='color:#888'>No counterfactual candidates found.</p>"

    # ── Full HTML ──────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agentic AI — Diagnostic Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #F0F4F8;
    color: #1a1a2e;
    font-size: 14px;
    line-height: 1.5;
  }}
  .page {{ max-width: 960px; margin: 0 auto; padding: 32px 20px 64px; }}
  a {{ color: #2C5F8A; text-decoration: none; }}
  table {{ font-size: 13px; }}
  th {{ font-weight: 600; text-align: left; }}
  @media print {{
    body {{ background: #fff; }}
    .page {{ padding: 0; }}
    section {{ box-shadow: none !important; border: 1px solid #ddd; }}
  }}
</style>
</head>
<body>
<div class="page">

<!-- Header -->
<div style="background:linear-gradient(135deg,#1a2a4a,#2C5F8A);
  color:#fff;border-radius:12px;padding:28px 32px;margin-bottom:24px">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:1.5px;
    opacity:.75;margin-bottom:6px">AGENTIC AI SYSTEM</div>
  <div style="font-size:26px;font-weight:700;margin-bottom:4px">
    Diagnostic Report
  </div>
  <div style="font-size:13px;opacity:.80">
    Generated {d.generated_at} &nbsp;·&nbsp;
    Analysis window: {d.window} decisions &nbsp;·&nbsp;
    Total dataset: {d.total_decisions} decisions
  </div>
  <div style="margin-top:16px">
    {_health_badge(d.health_label, d.overall_health)}
  </div>
</div>

<!-- TOC -->
<div style="background:#fff;border-radius:8px;padding:16px 20px;
  margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,.08)">
  <span style="color:#888;font-size:12px;text-transform:uppercase;
    letter-spacing:0.5px">Sections: </span>
  <a href="#exec">Executive Summary</a> &nbsp;·&nbsp;
  <a href="#coherence">Coherence</a> &nbsp;·&nbsp;
  <a href="#agents">Agent Health</a> &nbsp;·&nbsp;
  <a href="#conflicts">Routing Conflicts</a> &nbsp;·&nbsp;
  <a href="#failures">Top Failures</a> &nbsp;·&nbsp;
  <a href="#cf">Counterfactual Opportunities</a>
</div>

{_section("1 · Executive Summary", exec_body, "exec")}
{_section("2 · Coherence Functional C(t)", coh_body, "coherence")}
{_section("3 · Agent Specialization Health", agent_body, "agents")}
{_section("4 · Routing Conflict Analysis", conf_body, "conflicts")}
{_section("5 · Top Failure Cases (by Regret)", fail_body, "failures")}
{_section("6 · Counterfactual Routing Opportunities", cf_body, "cf")}

<!-- Footer -->
<div style="text-align:center;color:#aaa;font-size:11px;margin-top:32px">
  phi4-mini · LangGraph · RTX 2050 &nbsp;·&nbsp;
  Report generated by report_generator.py
</div>

</div>
</body>
</html>"""


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate agentic AI diagnostic report")
    parser.add_argument("--window", type=int, default=20,
                        help="Rolling window size for coherence (default 20)")
    parser.add_argument("--out", type=str, default=None,
                        help="Output HTML path (default: logs/diagnostic_report_<ts>.html)")
    parser.add_argument("--json", action="store_true",
                        help="Also dump report data as JSON")
    parser.add_argument("--no-open", action="store_true",
                        help="Don't open the report in browser after generating")
    args = parser.parse_args()

    data = collect(window=args.window)

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = args.out or os.path.join(_LOGS, f"diagnostic_report_{ts}.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    html = render_html(data)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[report] HTML saved → {path}")

    if args.json:
        json_path = path.replace(".html", ".json")
        # Convert to serializable dict
        raw = {
            "generated_at":    data.generated_at,
            "overall_health":  data.overall_health,
            "health_label":    data.health_label,
            "total_decisions": data.total_decisions,
            "coherence":       data.coherence,
            "c_routing":       data.c_routing,
            "c_calib":         data.c_calib,
            "c_quality":       data.c_quality,
            "conflict_rate":   data.conflict_rate,
            "reflection_rate": data.reflection_rate,
            "avg_regret":      data.avg_regret,
            "g_r_mean":        data.g_r_mean,
            "mem_avg_quality": data.mem_avg_quality,
            "mem_count":       data.mem_count,
            "agents": [
                {
                    "name":          a.name,
                    "decisions":     a.decisions,
                    "conflict_rate": a.conflict_rate,
                    "avg_regret":    a.avg_regret,
                    "avg_quality":   a.avg_quality,
                    "health_score":  a.health_score,
                    "verdict":       a.verdict,
                }
                for a in data.agents
            ],
            "top_failures": [
                {"id": f.decision_id, "agent": f.agent, "regret": f.regret, "query": f.query}
                for f in data.top_failures
            ],
            "cf_candidates": [
                {
                    "id":           c.decision_id,
                    "original":     c.original_agent,
                    "suggested":    c.suggested_alt,
                    "regret":       c.regret,
                    "priority":     c.priority,
                }
                for c in data.cf_candidates
            ],
        }
        with open(json_path, "w") as jf:
            json.dump(raw, jf, indent=2)
        print(f"[report] JSON saved → {json_path}")

    if not args.no_open:
        import subprocess
        import shutil
        # Try to open in browser
        for cmd in ["xdg-open", "open", "firefox", "chromium-browser"]:
            if shutil.which(cmd):
                subprocess.Popen([cmd, path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                print(f"[report] opened with {cmd}")
                break
        else:
            print(f"[report] no browser found — open manually: {path}")

    # Summary to stdout
    print()
    print(f"  Overall Health : {data.health_label} ({data.overall_health:.3f})")
    print(f"  Coherence C(t) : {data.coherence:.4f}  "
          f"(routing={data.c_routing:.3f}  calib={data.c_calib:.3f}  quality={data.c_quality:.3f})")
    print(f"  Decisions      : {data.total_decisions}  "
          f"conflict={_pct(data.conflict_rate)}  regret={data.avg_regret:.4f}")
    print(f"  Memory         : {data.mem_count} records  avg_q={data.mem_avg_quality:.3f}")
    print(f"  G_r (reflect)  : {data.g_r_mean:+.4f}")
    if data.agents:
        print()
        print("  Agent Health:")
        for a in data.agents:
            print(f"    {a.name:<25} health={a.health_score:.3f}  "
                  f"conflict={_pct(a.conflict_rate)}  [{a.verdict.upper()}]")


if __name__ == "__main__":
    main()
