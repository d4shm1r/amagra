"""
agent_arena.py — Multi-strategy routing benchmark

Compares routing strategies on the same labeled prompt set without any LLM
calls.  Runs in < 2 seconds.  Produces the paper-ready comparison table and
persists every run to logs/arena.db for longitudinal tracking.

Strategies
──────────
  signal_only   QuerySignal only — domain + shape + verbosity (ablation row)
  keyword_only  Raw keyword counting from KEYWORD_MAP, no signal or LLM
  hybrid        Keyword + signal terse paths, no LLM fallback
  logistic      Domain confidence threshold only (domain_conf > 0.3 → agent)

Usage
─────
  python3 agent_arena.py                           # full run, all strategies
  python3 agent_arena.py --strategy signal_only    # one strategy only
  python3 agent_arena.py --prompts extra    # include extended prompt set
  python3 agent_arena.py --history          # show longitudinal trend
  python3 agent_arena.py --per-domain       # per-domain accuracy breakdown
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from training.auto_train import PROMPTS
from orchestration.query_normalizer import normalize, DOMAIN_TO_AGENT, detect_domain

_ARENA_DB  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "arena.db")
_LOGS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# Estimated latency per strategy (ms) — based on RTX 2050 / phi4-mini benchmarks
_LATENCY_MS = {
    "signal_only":  0.4,    # pure Python, O(keywords)
    "keyword_only": 0.3,    # regex scan, no signal overhead
    "hybrid":       0.6,    # keyword + signal
    "logistic":     0.4,    # single threshold check
    "full_pipeline": 18000, # phi4-mini p50 on this hardware
}

# Paper label — what appears in the comparison table (all exactly 28 chars wide)
_STRATEGY_LABELS = {
    "signal_only":   "QuerySignal only            ",
    "keyword_only":  "Keyword-only                ",
    "hybrid":        "Keyword + Signal (no LLM)   ",
    "logistic":      "Logistic (conf>=0.3)        ",
}

# ── Extended prompt set ───────────────────────────────────────
# 30 additional prompts covering ambiguous cases, multi-intent, and edge cases.
# Kept separate from auto_train.py to avoid polluting the seeding corpus.
EXTRA_PROMPTS = [
    # Ambiguous — overlapping domains
    ("ext_01", "it_networking", "networking",
     "How do I configure nginx to proxy WebSocket connections from my Node.js app?"),
    ("ext_02", "python_dev", "python",
     "Write a Python script that pings a list of hosts and logs the results to a file."),
    ("ext_03", "ai_ml", "ai_ml",
     "What is the difference between LangChain and LangGraph for building agents?"),
    ("ext_04", "python_dev", "python",
     "Implement a Python function that retries an HTTP request with exponential backoff."),
    ("ext_05", "it_networking", "networking",
     "Set up a TURN server with coturn for WebRTC peer-to-peer connections."),

    # Multi-intent
    ("ext_06", "dotnet_dev", "blazor",
     "Create a Blazor component that calls a Python FastAPI backend and displays the JSON response."),
    ("ext_07", "python_dev", "python",
     "Write a Python asyncio producer-consumer queue that processes network events."),
    ("ext_08", "ai_ml", "ai_ml",
     "How do I fine-tune a HuggingFace BERT model for text classification using PyTorch?"),
    ("ext_09", "knowledge_learning", "knowledge",
     "Explain the difference between process and thread in Linux with memory diagrams."),
    ("ext_10", "python_dev", "python",
     "Debug: ModuleNotFoundError: No module named 'uvicorn' when starting my FastAPI app."),

    # Terse edge cases
    ("ext_11", "terse", "terse",
     "What port does MongoDB use?"),
    ("ext_12", "terse", "terse",
     "What does API stand for?"),
    ("ext_13", "terse", "terse",
     "What is the default port for MySQL?"),
    ("ext_14", "terse", "terse",
     "What does HTTP status 500 mean?"),
    ("ext_15", "terse", "terse",
     "What does JWT stand for?"),

    # Debug queries
    ("ext_16", "python_dev", "python",
     "AttributeError: 'dict' object has no attribute 'append' — how do I fix this?"),
    ("ext_17", "dotnet_dev", "blazor",
     "My Blazor component throws NullReferenceException on OnInitializedAsync — how do I fix it?"),
    ("ext_18", "it_networking", "networking",
     "My VPN tunnel keeps dropping packets. How do I diagnose the MTU issue with Wireguard?"),
    ("ext_19", "ai_ml", "ai_ml",
     "My PyTorch model loss is NaN after the first epoch. What is causing this?"),
    ("ext_20", "python_dev", "python",
     "KeyError: 'user_id' in my FastAPI request body parsing. How do I debug this?"),

    # Procedural
    ("ext_21", "it_networking", "networking",
     "How do I set up Fail2ban to block SSH brute force attempts on Ubuntu?"),
    ("ext_22", "dotnet_dev", "blazor",
     "How do I add role-based authorization to individual Blazor pages using policies?"),
    ("ext_23", "python_dev", "python",
     "How do I profile a slow Python function to find the bottleneck using cProfile?"),
    ("ext_24", "ai_ml", "ai_ml",
     "How do I export a PyTorch model to ONNX format for deployment?"),
    ("ext_25", "knowledge_learning", "knowledge",
     "How do I think about choosing between a relational and a document database?"),

    # Conceptual / explanation
    ("ext_26", "knowledge_learning", "knowledge",
     "What is the difference between optimistic and pessimistic locking in databases?"),
    ("ext_27", "ai_ml", "ai_ml",
     "Explain how vector databases work and why they are used for semantic search."),
    ("ext_28", "it_networking", "networking",
     "What is the difference between a hub, switch, and router in a network?"),
    ("ext_29", "python_dev", "python",
     "Explain Python's memory model and how garbage collection works with reference counting."),
    ("ext_30", "knowledge_learning", "knowledge",
     "What is eventual consistency and how do distributed systems achieve it without coordination?"),
]

# ── Keyword map (active agents only, knowledge_learning excluded) ─────────────
# Mirrors router.py KEYWORD_MAP restricted to the 6 active agents.
# knowledge_learning is intentionally absent: its generic phrases ("what is",
# "how does") would beat domain keywords on score.  It remains the fallback
# when no agent scores > 0, matching how hybrid_router() works in production.
_ACTIVE_KEYWORD_MAP: dict[str, list[str]] = {
    "it_networking": [
        r"(?<!\w)network(?!\w)", r"(?<!\w)wi-fi(?!\w)", r"(?<!\w)wifi(?!\w)",
        r"(?<!\w)router(?!\w)", r"(?<!\w)firewall(?!\w)", r"(?<!\w)subnet(?!\w)",
        r"(?<!\w)dns(?!\w)", r"(?<!\w)dhcp(?!\w)", r"(?<!\w)vpn(?!\w)",
        r"(?<!\w)ip address(?!\w)", r"(?<!\w)ssh(?!\w)", r"(?<!\w)ping(?!\w)",
        r"(?<!\w)latency(?!\w)", r"(?<!\w)bandwidth(?!\w)", r"(?<!\w)ethernet(?!\w)",
        r"(?<!\w)packet(?!\w)", r"(?<!\w)vlan(?!\w)",
        r"(?<!\w)nginx(?!\w)", r"(?<!\w)ssl(?!\w)", r"(?<!\w)tls(?!\w)",
        r"(?<!\w)certbot(?!\w)", r"(?<!\w)wireguard(?!\w)", r"(?<!\w)firewalld(?!\w)",
        r"(?<!\w)iptables(?!\w)", r"(?<!\w)reverse proxy(?!\w)", r"(?<!\w)load balancer(?!\w)",
        r"(?<!\w)tcp(?!\w)", r"(?<!\w)udp(?!\w)", r"(?<!\w)bgp(?!\w)",
        r"(?<!\w)ospf(?!\w)", r"(?<!\w)nat(?!\w)",
        r"(?<!\w)webrtc(?!\w)", r"(?<!\w)coturn(?!\w)",
        r"(?<!\w)autonomous system(?!\w)", r"(?<!\w)packet loss(?!\w)",
    ],
    "python_dev": [
        r"(?<!\w)python(?!\w)", r"(?<!\w)flask(?!\w)", r"(?<!\w)django(?!\w)",
        r"(?<!\w)fastapi(?!\w)", r"(?<!\w)pytest(?!\w)", r"(?<!\w)asyncio(?!\w)",
        r"(?<!\w)decorator(?!\w)", r"(?<!\w)generator(?!\w)",
        r"(?<!\w)list comprehension(?!\w)", r"(?<!\w)pydantic(?!\w)",
        r"(?<!\w)recursionerror(?!\w)", r"(?<!\w)maximum recursion(?!\w)",
        r"(?<!\w)typeerror(?!\w)", r"(?<!\w)attributeerror(?!\w)",
        r"(?<!\w)importerror(?!\w)", r"(?<!\w)nameerror(?!\w)",
        r"(?<!\w)context manager(?!\w)", r"(?<!\w)dataclass(?!\w)",
        r"(?<!\w)coroutine(?!\w)", r"(?<!\w)async/await(?!\w)",
    ],
    "dotnet_dev": [
        r"(?<!\w)blazor(?!\w)", r"(?<!\w)razor(?!\w)", r"(?<!\w)webassembly(?!\w)",
        r"(?<!\w)wasm(?!\w)", r"(?<!\w)dotnet(?!\w)", r"(?<!\w)\.net(?!\w)",
        r"(?<!\w)c#(?!\w)", r"(?<!\w)csharp(?!\w)", r"(?<!\w)signalr(?!\w)",
        r"(?<!\w)nuget(?!\w)", r"(?<!\w)asp\.net(?!\w)",
        r"(?<!\w)statehaschanged(?!\w)", r"(?<!\w)oninitialized(?!\w)",
        r"(?<!\w)editform(?!\w)", r"(?<!\w)ijsruntime(?!\w)",
    ],
    "ai_ml": [
        r"(?<!\w)tensorflow(?!\w)", r"(?<!\w)pytorch(?!\w)",
        r"(?<!\w)neural network(?!\w)", r"(?<!\w)machine learning(?!\w)",
        r"(?<!\w)deep learning(?!\w)", r"(?<!\w)transformer(?!\w)",
        r"(?<!\w)gradient(?!\w)", r"(?<!\w)embedding(?!\w)",
        r"(?<!\w)langchain(?!\w)", r"(?<!\w)langgraph(?!\w)",
        r"(?<!\w)huggingface(?!\w)", r"(?<!\w)llm(?!\w)",
        r"(?<!\w)fine.tun(?!\w)", r"(?<!\w)rag(?!\w)",
        r"(?<!\w)bert(?!\w)", r"(?<!\w)gpt(?!\w)",
        r"(?<!\w)supervised(?!\w)", r"(?<!\w)unsupervised(?!\w)",
        r"(?<!\w)reinforcement learning(?!\w)", r"(?<!\w)binary classifier(?!\w)",
        r"(?<!\w)batch normalization(?!\w)", r"(?<!\w)layer normalization(?!\w)",
        r"(?<!\w)quantization(?!\w)", r"(?<!\w)vector databases?(?!\w)",
        r"(?<!\w)prompt engineering(?!\w)", r"(?<!\w)attention mechanism(?!\w)",
        r"(?<!\w)overfitting(?!\w)", r"(?<!\w)backpropagation(?!\w)",
        r"(?<!\w)semantic search(?!\w)",
    ],
    "terse": [
        r"(?<!\w)give me the command(?!\w)", r"(?<!\w)give me command(?!\w)",
        r"(?<!\w)command for(?!\w)", r"(?<!\w)command to(?!\w)",
        r"(?<!\w)syntax for(?!\w)", r"(?<!\w)one.liner(?!\w)",
        r"(?<!\w)just give me(?!\w)", r"(?<!\w)short answer(?!\w)",
        r"(?<!\w)quick answer(?!\w)", r"(?<!\w)terse(?!\w)",
    ],
}


# ── Routing strategies ────────────────────────────────────────

def _route_signal_only(query: str) -> str:
    """
    Pure QuerySignal: domain + shape + verbosity, no LLM.

    Routing priority (order matters):
      1. factual shape → terse (short concrete answer regardless of domain)
      2. confident domain (domain_conf > 0.3) → domain agent
         checked BEFORE verbosity so "Configure nginx SSL" (3 words, networking)
         correctly goes to it_networking, not terse.
      3. terse verbosity (≤6 tokens, no domain) → terse
      4. fallback → knowledge_learning
    """
    if not query.strip():
        return "knowledge_learning"
    sig = normalize(query)
    if sig.answer_shape == "factual":
        return "terse"
    if sig.domain_conf > 0.3:
        return DOMAIN_TO_AGENT.get(sig.domain, "knowledge_learning")
    if sig.verbosity == "terse":
        return "terse"
    return "knowledge_learning"


def _route_keyword_only(query: str) -> str:
    """Raw keyword count from KEYWORD_MAP; highest score wins."""
    q = query.lower()
    scores: dict[str, int] = {}
    for agent, patterns in _ACTIVE_KEYWORD_MAP.items():
        scores[agent] = sum(
            1 for p in patterns if re.search(p, q, re.IGNORECASE)
        )
    # Terse keyword wins immediately (mirrors router.py priority)
    if scores.get("terse", 0) >= 1:
        return "terse"
    best = max(scores, key=scores.get)
    return best if scores[best] >= 1 else "knowledge_learning"


def _route_hybrid(query: str) -> str:
    """
    Keyword count + signal terse paths; no LLM fallback.
    Mirrors the core_brain fast path without the LLM call.
    """
    if not query.strip():
        return "knowledge_learning"
    q = query.lower()
    # Signal-first terse paths
    sig = normalize(query)
    if sig.answer_shape == "factual":
        return "terse"

    scores: dict[str, int] = {}
    for agent, patterns in _ACTIVE_KEYWORD_MAP.items():
        scores[agent] = sum(
            1 for p in patterns if re.search(p, q, re.IGNORECASE)
        )
    if scores.get("terse", 0) >= 1:
        return "terse"

    # Signal terse path (short + non-content query + general domain)
    _content_heavy = re.search(
        r"\b(summarize|summary|explain|research|analyze|compare|review|describe)\b",
        q, re.IGNORECASE,
    )
    if (sig.verbosity == "terse"
            and sig.answer_shape == "explanation"
            and sig.domain == "general"
            and not _content_heavy):
        return "terse"

    # Keyword routing
    best = max(scores, key=scores.get)
    best_score = scores[best]
    sorted_vals = sorted(scores.values(), reverse=True)
    second = sorted_vals[1] if len(sorted_vals) > 1 else 0

    if best_score >= 2 and best_score > second:
        return best
    if best_score == 1:
        return best

    # Signal domain fallback
    if sig.domain_conf > 0.3:
        return DOMAIN_TO_AGENT.get(sig.domain, "knowledge_learning")
    return "knowledge_learning"


def _route_logistic(query: str) -> str:
    """Domain confidence threshold only — simplest possible strategy."""
    domain, conf = detect_domain(query)
    if conf > 0.3:
        return DOMAIN_TO_AGENT.get(domain, "knowledge_learning")
    return "knowledge_learning"


_STRATEGIES: dict[str, Any] = {
    "signal_only":  _route_signal_only,
    "keyword_only": _route_keyword_only,
    "hybrid":       _route_hybrid,
    "logistic":     _route_logistic,
}


# ── SQLite persistence ────────────────────────────────────────

def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS arena_runs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            n_prompts INTEGER NOT NULL,
            strategies TEXT   NOT NULL,
            notes     TEXT
        );
        CREATE TABLE IF NOT EXISTS arena_results (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id         INTEGER NOT NULL,
            prompt_id      TEXT    NOT NULL,
            domain         TEXT    NOT NULL,
            expected_agent TEXT    NOT NULL,
            prompt         TEXT    NOT NULL,
            strategy       TEXT    NOT NULL,
            chosen_agent   TEXT    NOT NULL,
            correct        INTEGER NOT NULL,
            signal_domain  TEXT,
            signal_conf    REAL,
            signal_shape   TEXT,
            signal_verbosity TEXT,
            FOREIGN KEY (run_id) REFERENCES arena_runs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_results_run     ON arena_results(run_id);
        CREATE INDEX IF NOT EXISTS idx_results_strategy ON arena_results(strategy);
        CREATE INDEX IF NOT EXISTS idx_results_domain  ON arena_results(domain);
    """)
    conn.commit()


def _save_run(conn: sqlite3.Connection, ts: str, n: int, strategies: list[str]) -> int:
    cur = conn.execute(
        "INSERT INTO arena_runs (timestamp, n_prompts, strategies) VALUES (?, ?, ?)",
        (ts, n, json.dumps(strategies)),
    )
    conn.commit()
    return cur.lastrowid


def _save_results(conn: sqlite3.Connection, run_id: int, rows: list[dict]):
    conn.executemany(
        """INSERT INTO arena_results
           (run_id, prompt_id, domain, expected_agent, prompt, strategy,
            chosen_agent, correct, signal_domain, signal_conf,
            signal_shape, signal_verbosity)
           VALUES (:run_id,:prompt_id,:domain,:expected_agent,:prompt,:strategy,
                   :chosen_agent,:correct,:signal_domain,:signal_conf,
                   :signal_shape,:signal_verbosity)""",
        rows,
    )
    conn.commit()


# ── Core benchmark runner ─────────────────────────────────────

def run_arena(
    prompts: list[tuple],
    strategies: list[str],
    quiet: bool = False,
) -> dict[str, dict]:
    """
    Run all prompts through each strategy.

    Returns:
        { strategy_name: { "correct": int, "total": int, "misses": list,
                            "by_domain": { domain: {correct, total} },
                            "rows": list[dict] } }
    """
    results: dict[str, dict] = {
        s: {"correct": 0, "total": 0, "misses": [], "by_domain": {}, "rows": []}
        for s in strategies
    }

    for pid, expected, domain, prompt in prompts:
        sig = normalize(prompt)
        for strategy in strategies:
            fn      = _STRATEGIES[strategy]
            chosen  = fn(prompt)
            correct = int(chosen == expected)

            r = results[strategy]
            r["total"]   += 1
            r["correct"] += correct

            ds = r["by_domain"].setdefault(domain, {"correct": 0, "total": 0})
            ds["total"]   += 1
            ds["correct"] += correct

            if not correct:
                r["misses"].append({
                    "pid": pid, "expected": expected,
                    "got": chosen, "prompt": prompt[:80],
                })

            r["rows"].append({
                "run_id":          0,  # filled in before DB write
                "prompt_id":       pid,
                "domain":          domain,
                "expected_agent":  expected,
                "prompt":          prompt,
                "strategy":        strategy,
                "chosen_agent":    chosen,
                "correct":         correct,
                "signal_domain":   sig.domain,
                "signal_conf":     sig.domain_conf,
                "signal_shape":    sig.answer_shape,
                "signal_verbosity": sig.verbosity,
            })

    return results


# ── Reporting ─────────────────────────────────────────────────

def _bar(c: int, t: int, width: int = 20) -> str:
    filled = min(width, round(c / t * width)) if t else 0
    return "█" * filled + "░" * (width - filled)


def print_comparison_table(
    results: dict[str, dict],
    strategies: list[str],
    n_prompts: int,
    include_full_pipeline: bool = True,
):
    """Paper-ready comparison table."""
    sep = "─" * 74
    # Column widths: strategy(28) acc(6) correct(7) ms/q(6) llm(4) bar(20)
    # correct column is "CCC/TTT" format — right-pad to 7 chars for alignment
    print(f"\n{sep}")
    print("  Agent Arena — Routing Strategy Comparison")
    print(f"  Prompts: {n_prompts}   (zero LLM calls for rows below)")
    print(sep)
    print(f"  {'Strategy':<28}  {'Acc':>6}  {'Correct':>7}  {'ms/q':>6}  {'LLM':>4}  Bar")
    print(sep)

    for s in strategies:
        r    = results[s]
        c, t = r["correct"], r["total"]
        pct  = 100 * c / t if t else 0.0
        lat  = _LATENCY_MS.get(s, 0.5)
        bar  = _bar(c, t)
        label = _STRATEGY_LABELS.get(s, f"{s:<28}")
        ct_str = f"{c}/{t}"
        print(f"  {label:<28}  {pct:5.1f}%  {ct_str:>7}  {lat:5.1f}  {'0':>4}  {bar}")

    if include_full_pipeline:
        # Note: 97/100 is from the 100-prompt eval run (eval_3 log).
        # Shown separately because it involved real LLM calls.
        note = " *" if n_prompts != 100 else ""
        print(f"  {'Full pipeline (signal+LLM)':<28}  {'97.0%':>6}  {'97/100':>7}  "
              f"{'18000':>6}  {'~N':>4}  {_bar(97, 100)}{note}")
        if note:
            print(f"  * from 100-prompt eval run; current run uses {n_prompts} prompts")

    print(sep)


def print_domain_breakdown(results: dict[str, dict], strategies: list[str]):
    """Per-domain accuracy for each strategy."""
    # Collect all domains
    all_domains: set[str] = set()
    for r in results.values():
        all_domains.update(r["by_domain"].keys())
    domains = sorted(all_domains)

    sep = "─" * 72
    print(f"\n{sep}")
    print("  Per-domain accuracy breakdown")
    print(sep)

    header = f"  {'Domain':<12}" + "".join(f"  {s[:10]:>10}" for s in strategies)
    print(header)
    print(sep)

    for domain in domains:
        row = f"  {domain:<12}"
        for s in strategies:
            ds = results[s]["by_domain"].get(domain, {"correct": 0, "total": 0})
            c, t = ds["correct"], ds["total"]
            pct  = 100 * c / t if t else 0
            row += f"  {pct:8.0f}%"
        print(row)
    print(sep)


def print_miss_analysis(results: dict[str, dict], strategies: list[str]):
    """Show queries that multiple strategies miss — hardest cases."""
    # Count how many strategies got each prompt wrong
    miss_counts: dict[str, dict] = {}
    for s in strategies:
        for m in results[s]["misses"]:
            pid = m["pid"]
            if pid not in miss_counts:
                miss_counts[pid] = {"count": 0, "data": m}
            miss_counts[pid]["count"] += 1

    hard = [(pid, v) for pid, v in miss_counts.items() if v["count"] >= 2]
    hard.sort(key=lambda x: -x[1]["count"])

    if not hard:
        print("\n  No prompt is missed by 2+ strategies. Coverage is strong.")
        return

    print(f"\n  Hard cases — missed by 2+ strategies ({len(hard)} prompts):")
    sep = "─" * 72
    print(sep)
    for pid, v in hard[:10]:
        d = v["data"]
        print(f"  [{pid}]  expected={d['expected']:<20}  got={d['got']:<20}  "
              f"({v['count']}/{len(strategies)} strategies wrong)")
        print(f"    \"{d['prompt'][:65]}\"")
    print(sep)


def print_history(conn: sqlite3.Connection, n_runs: int = 10):
    """Show accuracy trend across recent arena runs."""
    # Fetch the last n_runs run IDs first, then join — avoids LIMIT * n_strategies
    # assumption that could silently truncate when more strategies exist.
    recent_ids = [
        r[0] for r in conn.execute(
            "SELECT id FROM arena_runs ORDER BY id DESC LIMIT ?", (n_runs,)
        ).fetchall()
    ]
    if not recent_ids:
        print("  No historical runs found.")
        return

    placeholders = ",".join("?" * len(recent_ids))
    rows = conn.execute(
        f"""SELECT r.timestamp, r.n_prompts,
                   ar.strategy,
                   ROUND(100.0 * SUM(ar.correct) / COUNT(ar.id), 1) AS accuracy
            FROM arena_runs r
            JOIN arena_results ar ON ar.run_id = r.id
            WHERE r.id IN ({placeholders})
            GROUP BY r.id, ar.strategy
            ORDER BY r.id DESC""",
        recent_ids,
    ).fetchall()

    # Group by timestamp
    by_run: dict[str, dict] = {}
    for ts, n, strategy, accuracy in rows:
        by_run.setdefault(ts, {"n": n, "strategies": {}})
        by_run[ts]["strategies"][strategy] = accuracy

    print(f"\n  Arena historical trend (last {n_runs} runs):")
    sep = "─" * 72
    print(sep)
    strategies_seen = sorted({s for v in by_run.values() for s in v["strategies"]})
    print(f"  {'Timestamp':<22}" + "".join(f"  {s[:12]:>12}" for s in strategies_seen))
    print(sep)
    for ts, data in list(by_run.items())[:n_runs]:
        row = f"  {ts:<22}"
        for s in strategies_seen:
            acc = data["strategies"].get(s, -1)
            row += f"  {acc:11.1f}%" if acc >= 0 else f"  {'—':>12}"
        print(row)
    print(sep)


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Agent Arena — multi-strategy routing benchmark")
    parser.add_argument(
        "--strategy", default="all",
        help="Comma-separated strategies: signal_only,keyword_only,hybrid,logistic or 'all'",
    )
    parser.add_argument(
        "--prompts", default="core",
        choices=["core", "extra", "all"],
        help="core (100 from auto_train), extra (30 extended), all (130 total)",
    )
    parser.add_argument("--per-domain", action="store_true", help="Show per-domain breakdown")
    parser.add_argument("--miss-analysis", action="store_true", help="Show hard-case analysis")
    parser.add_argument("--history", action="store_true", help="Show longitudinal trend from DB")
    parser.add_argument("--no-save", action="store_true", help="Skip writing to arena.db")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-prompt output")
    args = parser.parse_args()

    # Strategy selection
    if args.strategy == "all":
        strategies = list(_STRATEGIES.keys())
    else:
        strategies = [s.strip() for s in args.strategy.split(",")]
        for s in strategies:
            if s not in _STRATEGIES:
                print(f"Unknown strategy: {s!r}. Choose from: {list(_STRATEGIES)}")
                sys.exit(1)

    # Prompt selection
    if args.prompts == "core":
        prompts = PROMPTS
    elif args.prompts == "extra":
        prompts = EXTRA_PROMPTS
    else:
        prompts = list(PROMPTS) + EXTRA_PROMPTS

    # DB setup
    conn = sqlite3.connect(_ARENA_DB)
    _init_db(conn)

    if args.history:
        print_history(conn)
        conn.close()
        return

    # Run benchmark
    print(f"\n  Running Agent Arena — {len(prompts)} prompts × {len(strategies)} strategies")
    t0      = time.time()
    results = run_arena(prompts, strategies, quiet=args.quiet)
    elapsed = time.time() - t0
    print(f"  Done in {elapsed*1000:.0f}ms")

    # Persist to DB
    if not args.no_save:
        ts     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_id = _save_run(conn, ts, len(prompts), strategies)
        all_rows: list[dict] = []
        for s in strategies:
            for row in results[s]["rows"]:
                row["run_id"] = run_id
                all_rows.append(row)
        _save_results(conn, run_id, all_rows)
        print(f"  Saved run #{run_id} → {_ARENA_DB}")

    # Report
    print_comparison_table(results, strategies, len(prompts))

    if args.per_domain:
        print_domain_breakdown(results, strategies)

    if args.miss_analysis:
        print_miss_analysis(results, strategies)

    # Per-strategy misses summary
    print("\n  Routing mistakes by strategy:")
    for s in strategies:
        misses = results[s]["misses"]
        c, t   = results[s]["correct"], results[s]["total"]
        pct    = 100 * c / t
        label  = _STRATEGY_LABELS.get(s, s).strip()
        print(f"    {label:<28}: {len(misses)} wrong  ({pct:.1f}% correct)")
        for m in misses:
            print(f"        [{m['pid']}] expected={m['expected']:<20} got={m['got']:<20}")
            print(f"          \"{m['prompt'][:65]}\"")

    # Save JSON snapshot
    ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    out     = os.path.join(_LOGS_DIR, f"arena_{ts_file}.json")
    summary = {
        "timestamp": ts_file,
        "n_prompts":  len(prompts),
        "strategies": strategies,
        "elapsed_ms": round(elapsed * 1000, 1),
        "results": {
            s: {
                "accuracy":  round(results[s]["correct"] / results[s]["total"], 4),
                "correct":   results[s]["correct"],
                "total":     results[s]["total"],
                "misses":    results[s]["misses"],
                "by_domain": results[s]["by_domain"],
            }
            for s in strategies
        },
    }
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Results → {out}")

    conn.close()


if __name__ == "__main__":
    main()
