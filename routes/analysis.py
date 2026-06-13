import os
import sqlite3
import glob
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from .deps import _ROOT

router = APIRouter()


@router.get("/analysis/failures")
def get_failure_analysis(limit: int = 500, save: bool = False):
    from cognition.failure_miner import mine, save_report
    report = mine(limit=limit)
    if save:
        save_report(report)
    return report


@router.get("/policy/health")
def get_policy_health(limit: int = 200):
    gate_path = os.path.join(_ROOT, "logs", "gate.db")
    if not os.path.exists(gate_path):
        return {"total": 0, "no_data": True}

    con = sqlite3.connect(gate_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM critic_gate ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()

    if not rows:
        return {"total": 0, "no_data": True}

    total          = len(rows)
    accepted_first = sum(1 for r in rows if r["accepted_on_first"] == 1)
    retry_count    = total - accepted_first

    initial_scores = [r["score_initial"] for r in rows]
    retry_rows     = [r for r in rows if r["score_retry"] is not None]
    retry_scores   = [r["score_retry"] for r in retry_rows]

    mean_uplift = negative_retry_pct = separation_power = 0.0
    if retry_rows:
        uplifts            = [r["score_retry"] - r["score_initial"] for r in retry_rows]
        mean_uplift        = sum(uplifts) / len(uplifts)
        negative_retry_pct = sum(1 for u in uplifts if u < 0) / len(uplifts)
        separation_power   = mean_uplift

    gains = [
        max(r["score_retry"], r["score_initial"]) - r["score_initial"]
        if r["score_retry"] is not None else 0.0
        for r in rows
    ]
    marginal_value = sum(gains) / total if total > 0 else 0.0

    def bucket(scores, n=10):
        b = [0] * n
        for s in scores:
            b[min(int(s * n), n - 1)] += 1
        return b

    by_agent: dict = {}
    for r in rows:
        a = r["agent"] or "unknown"
        if a not in by_agent:
            by_agent[a] = {"total": 0, "retry": 0, "scores": []}
        by_agent[a]["total"] += 1
        if r["score_retry"] is not None:
            by_agent[a]["retry"] += 1
        by_agent[a]["scores"].append(r["score_initial"])

    agent_stats = {
        a: {
            "total":      v["total"],
            "retry_rate": round(v["retry"] / v["total"], 3),
            "avg_score":  round(sum(v["scores"]) / len(v["scores"]), 3),
        }
        for a, v in by_agent.items()
    }

    recent = [dict(r) for r in reversed(rows[:40])]

    return {
        "total":               total,
        "acceptance_rate":     round(accepted_first / total, 3),
        "retry_rate":          round(retry_count / total, 3),
        "mean_uplift":         round(mean_uplift, 4),
        "negative_retry_pct":  round(negative_retry_pct, 3),
        "separation_power":    round(separation_power, 4),
        "marginal_value":      round(marginal_value, 4),
        "avg_score_initial":   round(sum(initial_scores) / len(initial_scores), 3),
        "avg_score_retry":     round(sum(retry_scores) / len(retry_scores), 3) if retry_scores else None,
        "score_distribution":       bucket(initial_scores),
        "retry_score_distribution": bucket(retry_scores) if retry_scores else None,
        "recent_events":       recent,
        "by_agent":            agent_stats,
        "threshold":           0.70,
    }


@router.get("/data/stats")
def get_dataset_stats(rebuild: bool = False):
    from cognition.trace_builder import build_traces, load_cached_traces, dataset_stats
    try:
        traces = build_traces() if rebuild else load_cached_traces()
        if not traces:
            traces = build_traces()
        return dataset_stats(traces)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/traces")
def get_data_traces(limit: int = 100, only_real: bool = False):
    from cognition.trace_builder import load_cached_traces, build_traces
    try:
        traces = load_cached_traces()
        if not traces:
            traces = build_traces()
        if only_real:
            traces = [t for t in traces if not t["labels"]["is_eval"]]
        return {"traces": traces[:limit], "total": len(traces)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/traces.jsonl")
def download_traces_jsonl(rebuild: bool = False):
    from cognition.trace_builder import build_traces, load_cached_traces, save_traces
    try:
        traces = build_traces() if rebuild else load_cached_traces()
        if not traces:
            traces = build_traces()
        if rebuild:
            save_traces(traces)
        content = "\n".join(json.dumps(t) for t in traces)
        return Response(
            content=content,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=trace_dataset.jsonl"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/specialization")
def get_specialization(rebuild: bool = False):
    from training.specialization import compute
    from cognition.trace_builder import load_cached_traces, build_traces
    try:
        traces = build_traces() if rebuild else load_cached_traces()
        if not traces:
            traces = build_traces()
        return compute(traces)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/counterfactual/candidates")
def get_counterfactual_candidates(n: int = 10):
    from cognition.counterfactual import top_counterfactual_candidates
    try:
        return {"candidates": top_counterfactual_candidates(n=n)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/counterfactual/{decision_id}")
def run_counterfactual(decision_id: int, alt_agent: str, dry_run: bool = True):
    from cognition.counterfactual import simulate_alternative
    try:
        return simulate_alternative(decision_id, alt_agent, dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
def generate_report(window: int = 20):
    from training.report_generator import collect, render_html
    try:
        data = collect(window=window)
        html = render_html(data)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(_ROOT, "logs", f"diagnostic_report_{ts}.html")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return {
            "status":         "generated",
            "file":           path,
            "overall_health": data.overall_health,
            "health_label":   data.health_label,
            "coherence":      data.coherence,
            "total_decisions": data.total_decisions,
            "conflict_rate":  data.conflict_rate,
            "agents":         [
                {"name": a.name, "health_score": a.health_score, "verdict": a.verdict}
                for a in data.agents
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/download")
def download_latest_report():
    logs_dir = os.path.join(_ROOT, "logs")
    files = sorted(glob.glob(os.path.join(logs_dir, "diagnostic_report_*.html")))
    if not files:
        raise HTTPException(status_code=404, detail="No report generated yet. Call GET /report first.")
    with open(files[-1], encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/analysis/memory_backend")
def get_memory_backend_info():
    from memory_core.backend import get_backend, _FAISS_PROMOTE_THRESHOLD
    try:
        info = get_backend().backend_info()
        info["promote_threshold"] = _FAISS_PROMOTE_THRESHOLD
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/memory_backend/bench")
def bench_memory_backend(n: int = 5):
    if n < 1 or n > 20:
        raise HTTPException(status_code=400, detail="n must be 1–20")
    from memory_core.backend import benchmark_retrieval
    try:
        return benchmark_retrieval(n_queries=n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/memory_backend/promote")
def promote_memory_backend():
    from memory_core.backend import promote_if_needed, get_backend
    promoted = promote_if_needed()
    info     = get_backend().backend_info()
    return {"promoted": promoted, "backend": info}


@router.get("/data/graph/stats")
def get_graph_stats(rebuild: bool = False):
    from decision.graph import build_graph, load_graph, save_graph
    from cognition.trace_builder import load_cached_traces, build_traces
    try:
        if rebuild:
            traces = build_traces()
            g = build_graph(traces)
            save_graph(g)
        else:
            g = load_graph()
            if not g:
                traces = load_cached_traces() or build_traces()
                g = build_graph(traces)
                save_graph(g)
        return {
            "version":     g.get("version"),
            "created_at":  g.get("created_at"),
            "trace_count": g.get("trace_count"),
            "stats":       g.get("stats"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/causal/{decision_id}")
def get_causal_path(decision_id: int):
    from decision.graph import load_graph, build_graph, save_graph, causal_path
    from cognition.trace_builder import load_cached_traces, build_traces
    try:
        g = load_graph()
        if not g:
            traces = load_cached_traces() or build_traces()
            g = build_graph(traces)
            save_graph(g)
        return causal_path(g, decision_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/graph/agent/{agent_id}")
def get_agent_subgraph(agent_id: str):
    from decision.graph import load_graph, build_graph, save_graph, agent_subgraph
    from cognition.trace_builder import load_cached_traces, build_traces
    try:
        g = load_graph()
        if not g:
            g = build_graph(load_cached_traces() or build_traces())
            save_graph(g)
        return agent_subgraph(g, agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/graph/memory/{memory_id}")
def get_memory_influence(memory_id: int):
    from decision.graph import load_graph, build_graph, save_graph, memory_influence
    from cognition.trace_builder import load_cached_traces, build_traces
    try:
        g = load_graph()
        if not g:
            g = build_graph(load_cached_traces() or build_traces())
            save_graph(g)
        return memory_influence(g, memory_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/learned_router")
def get_learned_router_stats():
    try:
        from orchestration.learned_router import stats
        return stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/learned_router/train")
def retrain_learned_router():
    try:
        from orchestration.learned_router import _MODEL_PATH, train, invalidate_cache
        from cognition.trace_builder import load_cached_traces, build_traces
        if os.path.exists(_MODEL_PATH):
            os.remove(_MODEL_PATH)
        invalidate_cache()
        traces = load_cached_traces() or build_traces()
        result = train(traces, verbose=False)
        return {"status": "retrained", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/learned_router/predict")
def predict_learned_router(q: str, action: str = "unknown"):
    try:
        from orchestration.query_normalizer import normalize, DOMAIN_TO_AGENT
        from orchestration.learned_router import predict as lr_predict
        sig = normalize(q, action)
        lr_agent, lr_conf = lr_predict(
            sig.domain, sig.domain_conf,
            sig.answer_shape, sig.verbosity, action,
        )
        signal_agent = DOMAIN_TO_AGENT.get(sig.domain, "knowledge_learning")
        return {
            "query":        q,
            "signal": {
                "domain":    sig.domain,
                "conf":      sig.domain_conf,
                "shape":     sig.answer_shape,
                "verbosity": sig.verbosity,
                "action":    action,
            },
            "signal_agent":  signal_agent,
            "learned_agent": lr_agent,
            "learned_conf":  lr_conf,
            "agree":         signal_agent == lr_agent,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
