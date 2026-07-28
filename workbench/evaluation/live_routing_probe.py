"""
Live routing-coherence probe (NV-1).

Disentangles THREE metrics that a parked note conflated into a false "gap". On one
labeled prompt set it reports, apples-to-apples:

  (1) Offline signal-only ACCURACY   signal_route(prompt) == expected   (the ablation number)
  (2) Live full-pipeline ACCURACY    /ask's final_agent   == expected   (the real live route)
  (3) Live mean routing CONFIDENCE   mean(confidence)                   (== C_routing)

The parked claim ("c_routing 0.73 vs offline 1.0 = routing degrades live") compared
(3) against (1) — mean CONFIDENCE against ACCURACY, two different axes. Post-O7,
`cognition/coherence.py` defines `C_routing = mean routing confidence` with a 0.67
default, so it structurally cannot reach 1.0; 0.73 is a healthy confidence level, not
a degraded accuracy. The honest comparison is (1) vs (2). This probe measures all
three and cross-checks (3) against the live `/coherence` endpoint.

Server must be up with a live model (Ollama or a cloud provider):

    # boot: ollama serve & ; uvicorn api:app --port 8000
    PYTHONPATH=. .venv/bin/python workbench/evaluation/live_routing_probe.py --n 138

Writes a JSON artifact to logs/live_routing_probe.json unless --no-write.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workbench.auto_train import PROMPTS  # (pid, expected_agent, domain, prompt)
from workbench.evaluation.ablation_eval import signal_route


def _get(base: str, path: str, timeout: float = 15.0) -> dict:
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post(base: str, path: str, payload: dict, timeout: float = 180.0) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.reason}
    except Exception as e:  # noqa: BLE001 — network probe, any failure is a skipped sample
        return 0, {"error": str(e)}


def run(base: str, n: int, write: bool) -> dict:
    health = _get(base, "/health")
    if health.get("ollama") != "online" and not health.get("intelligence", {}).get("claude_available"):
        print(f"⚠  No live model (health: {health.get('status')}, ollama={health.get('ollama')}). "
              f"Routing may fall back to signal-only, defeating the point.", file=sys.stderr)
    print(f"health: status={health.get('status')} model={health.get('model')} "
          f"ollama={health.get('ollama')} version={health.get('version')}")

    prompts = PROMPTS[:n] if n else PROMPTS
    print(f"driving {len(prompts)} /ask requests …")
    t0 = time.time()
    driven = 0
    for i, (pid, expected, domain, prompt) in enumerate(prompts, 1):
        code, _ = _post(base, "/ask", {"message": prompt})
        if code == 200:
            driven += 1
        else:
            print(f"  [{i}/{len(prompts)}] {pid} HTTP {code} (skipped)")
        if i % 10 == 0:
            print(f"  {i}/{len(prompts)} … {time.time() - t0:.0f}s elapsed")
    print(f"driven {driven}/{len(prompts)} in {time.time() - t0:.0f}s")

    # Pull the decisions back and match by exact task text (fresh instance → our traffic only).
    dec = _get(base, f"/decisions?limit={len(prompts) + 50}")["decisions"]
    by_task: dict[str, list[dict]] = {}
    for d in reversed(dec):  # chronological
        by_task.setdefault((d.get("task") or "").strip(), []).append(d)

    rows, matched = [], 0
    off_correct = live_correct = agree = 0
    confs: list[float] = []
    for pid, expected, domain, prompt in prompts:
        offline = signal_route(prompt)
        bucket = by_task.get(prompt.strip())
        live = conf = None
        if bucket:
            d = bucket.pop(0)  # consume in order for duplicate prompts
            live = d["final_agent"]
            conf = float(d["confidence"])
            matched += 1
            confs.append(conf)
            off_correct += (offline == expected)
            live_correct += (live == expected)
            agree += (live == offline)
        rows.append({"pid": pid, "expected": expected, "offline": offline,
                     "live": live, "confidence": conf})

    m = matched or 1
    coherence = _get(base, "/coherence")
    result = {
        "n_prompts": len(prompts),
        "n_matched": matched,
        "offline_signal_accuracy": round(off_correct / m, 4),
        "live_pipeline_accuracy": round(live_correct / m, 4),
        "live_vs_offline_agreement": round(agree / m, 4),
        "live_mean_confidence": round(sum(confs) / len(confs), 4) if confs else None,
        "live_min_confidence": round(min(confs), 4) if confs else None,
        "live_max_confidence": round(max(confs), 4) if confs else None,
        "coherence_c_routing": coherence.get("c_routing"),
        "coherence_low_confidence_rate": coherence.get("low_confidence_rate"),
        "coherence_C": coherence.get("C"),
        "coherence_window": coherence.get("window"),
        "coherence_n_decisions": coherence.get("n_decisions"),
        "health_model": health.get("model"),
        "health_version": health.get("version"),
    }

    print("\n" + "=" * 66)
    print("  Live routing-coherence probe")
    print("=" * 66)
    print(f"  matched {matched}/{len(prompts)} prompts to decisions\n")
    print(f"  (1) offline signal-only accuracy : {result['offline_signal_accuracy']:.3f}")
    print(f"  (2) live full-pipeline accuracy  : {result['live_pipeline_accuracy']:.3f}"
          f"   ← apples-to-apples vs (1)")
    print(f"      live vs offline agreement    : {result['live_vs_offline_agreement']:.3f}")
    print(f"  (3) live mean routing confidence : {result['live_mean_confidence']}"
          f"   (== C_routing; NOT accuracy)")
    print(f"      confidence range             : "
          f"[{result['live_min_confidence']}, {result['live_max_confidence']}]")
    print(f"      /coherence C_routing         : {result['coherence_c_routing']}"
          f"   (low-conf rate {result['coherence_low_confidence_rate']})")
    delta = None
    if result["live_mean_confidence"] is not None and result["coherence_c_routing"] is not None:
        delta = abs(result["live_mean_confidence"] - result["coherence_c_routing"])
        print(f"      |mean_conf − C_routing|      : {delta:.4f}  "
              f"({'✓ same axis' if delta < 0.05 else '⚠ windowed differently'})")
    print("\n  Verdict: (3) is CONFIDENCE, (1)/(2) are ACCURACY — do not compare (3) to (1).")

    if write:
        out = os.path.join(os.environ.get("AMAGRA_DATA_DIR", "logs"), "live_routing_probe.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as f:
            json.dump({"summary": result, "rows": rows}, f, indent=2)
        print(f"\n  wrote {out}")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--n", type=int, default=0, help="limit prompts (0 = all)")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    run(a.base, a.n, write=not a.no_write)
